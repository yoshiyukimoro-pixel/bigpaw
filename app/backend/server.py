#!/usr/bin/env python3
"""BIG PAW v1.0 application backend.

Standard-library reference implementation with SQLite persistence, role-based
authentication, breeder/listing moderation, messaging, deal completion reporting,
commission billing, automated listing suspension/reactivation, uploads, support,
audit logs and backups.

For public deployment, run behind HTTPS, configure SMTP and production credentials,
and use durable/off-site storage appropriate to the hosting environment.
"""
from __future__ import annotations

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, urlencode
from pathlib import Path
from urllib.request import Request, urlopen
import sqlite3
import json
import hashlib
import hmac
import secrets
import time
import os
import re
import shutil
import threading
import smtplib
import ssl
from xml.sax.saxutils import escape as xml_escape
from email.message import EmailMessage
from collections import defaultdict, deque
from email.parser import BytesParser
from email.policy import default as email_policy

ROOT = Path(__file__).resolve().parents[1]
# Optional durable data directory for cloud hosts (e.g. a mounted volume at /data).
# When unset, preserve the original local-development paths.
_DATA_DIR_RAW = os.environ.get('BIGPAW_DATA_DIR','').strip()
if _DATA_DIR_RAW:
    DATA_DIR = Path(_DATA_DIR_RAW).expanduser().resolve()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB = DATA_DIR / "bigpaw.sqlite3"
    UPLOADS = DATA_DIR / "uploads"
    BACKUPS = DATA_DIR / "backups"
else:
    DATA_DIR = ROOT
    DB = Path(__file__).with_name("bigpaw.sqlite3")
    UPLOADS = ROOT / "uploads"
    BACKUPS = ROOT / "backups"
UPLOADS.mkdir(parents=True, exist_ok=True)
BACKUPS.mkdir(parents=True, exist_ok=True)
BREED_IMAGE_CACHE = DATA_DIR / 'breed-images'
BREED_IMAGE_CACHE.mkdir(parents=True, exist_ok=True)
RATE_LOCK = threading.Lock()
RATE_BUCKETS = defaultdict(deque)
SESSION_COOKIE_NAME = 'bigpaw_session'

APP_ENV = os.environ.get('BIGPAW_ENV','development').strip().lower()
IS_PRODUCTION = APP_ENV == 'production'
PUBLIC_BASE_URL = os.environ.get('BIGPAW_PUBLIC_BASE_URL','https://bigpaw.site').rstrip('/')

# BIGPAW breeder account recovery: treat selected emails as breeder without asking them to re-apply.
BIGPAW_BREEDER_EMAILS = {e.strip().lower() for e in os.environ.get('BIGPAW_BREEDER_EMAILS','').split(',') if e.strip()}
BIGPAW_BREEDER_EMAILS.add('yoshiyukimoro@gmail.com')
def bigpaw_recovered_role(user):
    try:
        if user and str(user.get('email','')).strip().lower() in BIGPAW_BREEDER_EMAILS and str(user.get('role','')) != 'operator':
            user = dict(user)
            user['role'] = 'breeder'
    except Exception:
        pass
    return user
DEV_LINKS = (os.environ.get('BIGPAW_DEV_LINKS','0' if IS_PRODUCTION else '1') == '1')
SMTP_HOST = os.environ.get('BIGPAW_SMTP_HOST') or os.environ.get('SMTP_HOST','').strip()
# Gmail/Railway: use implicit TLS on port 465 when configured.
SMTP_PORT = int(os.environ.get('BIGPAW_SMTP_PORT') or os.environ.get('SMTP_PORT','587'))
SMTP_USER = os.environ.get('BIGPAW_SMTP_USER') or os.environ.get('SMTP_USER','').strip()
SMTP_PASSWORD = os.environ.get('BIGPAW_SMTP_PASSWORD') or os.environ.get('SMTP_PASSWORD','')
SMTP_FROM = os.environ.get('BIGPAW_SMTP_FROM', SMTP_USER or 'no-reply@bigpaw.local').strip()
SMTP_TLS = os.environ.get('BIGPAW_SMTP_TLS','1') == '1'
PAYMENT_MODE = os.environ.get('BIGPAW_PAYMENT_MODE','demo' if not IS_PRODUCTION else 'manual').strip().lower()
PAYMENT_WEBHOOK_SECRET = os.environ.get('BIGPAW_PAYMENT_WEBHOOK_SECRET','').strip()
COMMISSION_RATE_BPS = int(os.environ.get('BIGPAW_COMMISSION_RATE_BPS','500'))  # 500 = 5.00%
COMMISSION_DUE_DAYS = int(os.environ.get('BIGPAW_COMMISSION_DUE_DAYS','7'))
COMMISSION_TERMS_VERSION = os.environ.get('BIGPAW_COMMISSION_TERMS_VERSION','2026-09-16-v1').strip()
AUTOMATION_INTERVAL_SECONDS = int(os.environ.get('BIGPAW_AUTOMATION_INTERVAL_SECONDS','300'))
AUTO_BACKUP_HOURS = int(os.environ.get('BIGPAW_AUTO_BACKUP_HOURS','24'))
AUTO_BACKUP_KEEP = int(os.environ.get('BIGPAW_AUTO_BACKUP_KEEP','14'))
MAX_UPLOAD_BYTES = int(os.environ.get('BIGPAW_MAX_UPLOAD_BYTES', str(8*1024*1024)))
BILLING_ISSUER_NAME = os.environ.get('BIGPAW_BILLING_ISSUER_NAME','BIG PAW運営').strip()
BILLING_POSTAL = os.environ.get('BIGPAW_BILLING_POSTAL','').strip()
BILLING_ADDRESS = os.environ.get('BIGPAW_BILLING_ADDRESS','').strip()
BILLING_INVOICE_REG_NO = os.environ.get('BIGPAW_BILLING_INVOICE_REG_NO','').strip()
BILLING_BANK_NAME = os.environ.get('BIGPAW_BILLING_BANK_NAME','').strip()
BILLING_BANK_BRANCH = os.environ.get('BIGPAW_BILLING_BANK_BRANCH','').strip()
BILLING_BANK_ACCOUNT_TYPE = os.environ.get('BIGPAW_BILLING_BANK_ACCOUNT_TYPE','普通').strip()
BILLING_BANK_ACCOUNT_NO = os.environ.get('BIGPAW_BILLING_BANK_ACCOUNT_NO','').strip()
BILLING_BANK_ACCOUNT_HOLDER = os.environ.get('BIGPAW_BILLING_BANK_ACCOUNT_HOLDER','').strip()

BLOCKED_STATIC_PREFIXES = ('/backend','/db','/backups')
BLOCKED_STATIC_NAMES = {'.env','.env.example','.gitignore','.dockerignore','Dockerfile','docker-compose.yml','start_bigpaw.sh','VERSION'}
BLOCKED_STATIC_SUFFIXES = ('.md','.sqlite3','.sql','.py','.yml','.yaml')


BREED_KEYS = {
    'スタンダードプードル':'standard', 'ゴールデンレトリバー':'golden',
    'ラブラドールレトリバー':'labrador', 'バーニーズ・マウンテン・ドッグ':'bernese',
    'シベリアンハスキー':'husky', 'サモエド':'samoyed', 'グレートピレニーズ':'pyrenees',
    'ボルゾイ':'borzoi'
}
BREED_WIKI = {'standard-poodle': 'Poodle', 'golden-retriever': 'Golden_Retriever', 'labrador-retriever': 'Labrador_Retriever', 'bernese-mountain-dog': 'Bernese_Mountain_Dog', 'siberian-husky': 'Siberian_Husky', 'samoyed': 'Samoyed_dog', 'great-pyrenees': 'Great_Pyrenees', 'borzoi': 'Borzoi', 'great-dane': 'Great_Dane', 'newfoundland': 'Newfoundland_dog', 'saint-bernard': 'Saint_Bernard_(dog)', 'alaskan-malamute': 'Alaskan_Malamute', 'german-shepherd': 'German_Shepherd', 'dobermann': 'Dobermann', 'rottweiler': 'Rottweiler', 'cane-corso': 'Cane_Corso', 'bullmastiff': 'Bullmastiff', 'english-mastiff': 'English_Mastiff', 'neapolitan-mastiff': 'Neapolitan_Mastiff', 'tibetan-mastiff': 'Tibetan_Mastiff', 'leonberger': 'Leonberger', 'irish-wolfhound': 'Irish_Wolfhound', 'scottish-deerhound': 'Scottish_Deerhound', 'akita': 'Akita_(dog)', 'american-akita': 'American_Akita', 'belgian-shepherd': 'Belgian_Shepherd', 'dutch-shepherd': 'Dutch_Shepherd', 'rhodesian-ridgeback': 'Rhodesian_Ridgeback', 'weimaraner': 'Weimaraner', 'german-shorthaired-pointer': 'German_Shorthaired_Pointer', 'german-wirehaired-pointer': 'German_Wirehaired_Pointer', 'english-setter': 'English_Setter', 'irish-setter': 'Irish_Setter', 'gordon-setter': 'Gordon_Setter', 'flat-coated-retriever': 'Flat-coated_Retriever', 'chesapeake-bay-retriever': 'Chesapeake_Bay_Retriever', 'curly-coated-retriever': 'Curly-coated_Retriever', 'afghan-hound': 'Afghan_Hound', 'old-english-sheepdog': 'Old_English_Sheepdog', 'rough-collie': 'Rough_Collie', 'beauceron': 'Beauceron', 'briard': 'Briard', 'bouvier-des-flandres': 'Bouvier_des_Flandres', 'giant-schnauzer': 'Giant_Schnauzer', 'komondor': 'Komondor', 'kuvasz': 'Kuvasz', 'kangal': 'Kangal_Shepherd_Dog', 'caucasian-shepherd': 'Caucasian_Shepherd_Dog', 'central-asian-shepherd': 'Central_Asian_Shepherd_Dog', 'black-russian-terrier': 'Black_Russian_Terrier', 'dogue-de-bordeaux': 'Dogue_de_Bordeaux', 'dogo-argentino': 'Dogo_Argentino', 'greater-swiss-mountain-dog': 'Greater_Swiss_Mountain_Dog', 'pyrenean-mastiff': 'Pyrenean_Mastiff', 'spanish-mastiff': 'Spanish_Mastiff', 'estrela-mountain-dog': 'Estrela_Mountain_Dog', 'maremma-sheepdog': 'Maremmano-Abruzzese_Sheepdog', 'hovawart': 'Hovawart', 'dalmatian': 'Dalmatian_(dog)', 'saluki': 'Saluki'}
BREED_JA = {'standard-poodle': 'スタンダードプードル', 'golden-retriever': 'ゴールデンレトリーバー', 'labrador-retriever': 'ラブラドールレトリーバー', 'bernese-mountain-dog': 'バーニーズ・マウンテン・ドッグ', 'siberian-husky': 'シベリアン・ハスキー', 'samoyed': 'サモエド', 'great-pyrenees': 'グレート・ピレニーズ', 'borzoi': 'ボルゾイ', 'great-dane': 'グレート・デーン', 'newfoundland': 'ニューファンドランド', 'saint-bernard': 'セント・バーナード', 'alaskan-malamute': 'アラスカン・マラミュート', 'german-shepherd': 'ジャーマン・シェパード・ドッグ', 'dobermann': 'ドーベルマン', 'rottweiler': 'ロットワイラー', 'cane-corso': 'カネ・コルソ', 'bullmastiff': 'ブルマスティフ', 'english-mastiff': 'イングリッシュ・マスティフ', 'neapolitan-mastiff': 'ナポリタン・マスティフ', 'tibetan-mastiff': 'チベタン・マスティフ', 'leonberger': 'レオンベルガー', 'irish-wolfhound': 'アイリッシュ・ウルフハウンド', 'scottish-deerhound': 'スコティッシュ・ディアハウンド', 'akita': '秋田犬', 'american-akita': 'アメリカン・アキタ', 'belgian-shepherd': 'ベルジアン・シェパード・ドッグ', 'dutch-shepherd': 'ダッチ・シェパード', 'rhodesian-ridgeback': 'ローデシアン・リッジバック', 'weimaraner': 'ワイマラナー', 'german-shorthaired-pointer': 'ジャーマン・ショートヘアード・ポインター', 'german-wirehaired-pointer': 'ジャーマン・ワイヤーヘアード・ポインター', 'english-setter': 'イングリッシュ・セター', 'irish-setter': 'アイリッシュ・セター', 'gordon-setter': 'ゴードン・セター', 'flat-coated-retriever': 'フラットコーテッド・レトリーバー', 'chesapeake-bay-retriever': 'チェサピーク・ベイ・レトリーバー', 'curly-coated-retriever': 'カーリーコーテッド・レトリーバー', 'afghan-hound': 'アフガン・ハウンド', 'old-english-sheepdog': 'オールド・イングリッシュ・シープドッグ', 'rough-collie': 'ラフ・コリー', 'beauceron': 'ボースロン', 'briard': 'ブリアード', 'bouvier-des-flandres': 'ブービエ・デ・フランダース', 'giant-schnauzer': 'ジャイアント・シュナウザー', 'komondor': 'コモンドール', 'kuvasz': 'クーバース', 'kangal': 'カンガール・シェパード・ドッグ', 'caucasian-shepherd': 'コーカシアン・シェパード・ドッグ', 'central-asian-shepherd': 'セントラル・アジアン・シェパード・ドッグ', 'black-russian-terrier': 'ブラック・ロシアン・テリア', 'dogue-de-bordeaux': 'ドッグ・ド・ボルドー', 'dogo-argentino': 'ドゴ・アルヘンティーノ', 'greater-swiss-mountain-dog': 'グレーター・スイス・マウンテン・ドッグ', 'pyrenean-mastiff': 'ピレニアン・マスティフ', 'spanish-mastiff': 'スパニッシュ・マスティフ', 'estrela-mountain-dog': 'エストレラ・マウンテン・ドッグ', 'maremma-sheepdog': 'マレンマ・シープドッグ', 'hovawart': 'ホファヴァルト', 'dalmatian': 'ダルメシアン', 'saluki': 'サルーキ'}
AREA_KEYS={'埼玉県':'saitama','東京都':'tokyo','神奈川県':'kanagawa','千葉県':'chiba','群馬県':'gunma','栃木県':'tochigi','茨城県':'ibaraki','長野県':'nagano','北海道':'hokkaido','大阪府':'osaka','兵庫県':'hyogo','愛知県':'aichi'}


SEED_PUPPIES = [
    ('p1','ブラックの男の子','スタンダードプードル','standard','男の子','male','ブラック',258000,'募集中','埼玉県','saitama','DOG44',10.5,28,32,1,'2026-07-01','人が大好きで穏やかな男の子です。親犬情報・健康情報も公開しています。','クラージュ','ミルク'),
    ('p2','ゴールドの女の子','ゴールデンレトリバー','golden','女の子','female','ゴールド',328000,'募集中','東京都','tokyo','サンプル犬舎A',8.2,25,30,1,'2026-07-12','明るく人懐こい女の子。','',''),
    ('p3','トライカラーの男の子','バーニーズ・マウンテン・ドッグ','bernese','男の子','male','トライカラー',398000,'募集中','神奈川県','kanagawa','サンプル犬舎B',12.1,38,45,1,'2026-07-05','骨格がしっかりした大型犬らしい男の子。','','')
]

SCHEMA = r'''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users(
 id TEXT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('buyer','breeder','operator')),
 email TEXT UNIQUE NOT NULL, last TEXT DEFAULT '', first TEXT DEFAULT '', display_name TEXT DEFAULT '',
 salt TEXT NOT NULL, password_hash TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
 token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS breeders(
 id TEXT PRIMARY KEY, user_id TEXT UNIQUE REFERENCES users(id), kennel_name TEXT NOT NULL,
 prefecture TEXT NOT NULL, registration_no TEXT DEFAULT '', profile TEXT DEFAULT '', review_status TEXT DEFAULT 'approved'
);
CREATE TABLE IF NOT EXISTS breeder_applications(
 id TEXT PRIMARY KEY, user_id TEXT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kennel_name TEXT NOT NULL, representative TEXT NOT NULL, prefecture TEXT NOT NULL, primary_breed TEXT NOT NULL,
 registration_no TEXT NOT NULL, expires_on TEXT NOT NULL, profile TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
 review_note TEXT DEFAULT '', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS puppies(
 id TEXT PRIMARY KEY, breeder_id TEXT REFERENCES breeders(id), name TEXT NOT NULL, breed TEXT NOT NULL,
 breed_key TEXT, gender TEXT, gender_key TEXT, color TEXT, price INTEGER NOT NULL, status TEXT NOT NULL DEFAULT '募集中',
 area TEXT, area_key TEXT, breeder_name TEXT, weight REAL, adult_min REAL, adult_max REAL, health INTEGER DEFAULT 0,
 birth TEXT, description TEXT DEFAULT '', father TEXT DEFAULT '', mother TEXT DEFAULT '', image_url TEXT DEFAULT '',
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS parent_dogs(
 id TEXT PRIMARY KEY, breeder_id TEXT NOT NULL REFERENCES breeders(id), name TEXT NOT NULL,
 sex TEXT NOT NULL, breed TEXT NOT NULL, color TEXT DEFAULT '', height_cm REAL, weight_kg REAL,
 genetics TEXT DEFAULT '', health_summary TEXT DEFAULT '', notes TEXT DEFAULT '', image_url TEXT DEFAULT '', created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS health_records(
 id TEXT PRIMARY KEY, puppy_id TEXT REFERENCES puppies(id) ON DELETE CASCADE,
 parent_dog_id TEXT REFERENCES parent_dogs(id) ON DELETE CASCADE,
 category TEXT NOT NULL, item_name TEXT NOT NULL, result TEXT DEFAULT '', tested_on TEXT DEFAULT '',
 document_url TEXT DEFAULT '', created_at INTEGER NOT NULL,
 CHECK(puppy_id IS NOT NULL OR parent_dog_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS favorites(
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 puppy_id TEXT NOT NULL REFERENCES puppies(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL, PRIMARY KEY(user_id,puppy_id)
);
CREATE TABLE IF NOT EXISTS inquiries(
 id TEXT PRIMARY KEY, puppy_id TEXT NOT NULL REFERENCES puppies(id), buyer_id TEXT REFERENCES users(id),
 breeder_id TEXT REFERENCES breeders(id), name TEXT DEFAULT '', email TEXT DEFAULT '', phone TEXT DEFAULT '',
 preferred_date TEXT DEFAULT '', message TEXT DEFAULT '', status TEXT NOT NULL DEFAULT '未返信', created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications(
 id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), kind TEXT NOT NULL, title TEXT NOT NULL,
 body TEXT DEFAULT '', is_read INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS messages(
 id TEXT PRIMARY KEY, inquiry_id TEXT NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
 sender_user_id TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS visits(
 id TEXT PRIMARY KEY, inquiry_id TEXT UNIQUE NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
 visit_date TEXT DEFAULT '', visit_time TEXT DEFAULT '', party_size INTEGER DEFAULT 1, transport TEXT DEFAULT '',
 status TEXT NOT NULL DEFAULT 'proposed', face_to_face_confirmed INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS deals(
 id TEXT PRIMARY KEY, inquiry_id TEXT UNIQUE NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
 puppy_id TEXT NOT NULL REFERENCES puppies(id), buyer_id TEXT NOT NULL REFERENCES users(id), breeder_id TEXT REFERENCES breeders(id),
 total_price INTEGER NOT NULL, reservation_amount INTEGER NOT NULL DEFAULT 100000, status TEXT NOT NULL DEFAULT 'negotiating', created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payments(
 id TEXT PRIMARY KEY, deal_id TEXT NOT NULL REFERENCES deals(id) ON DELETE CASCADE, kind TEXT NOT NULL,
 amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', paid_at INTEGER, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS contracts(
 id TEXT PRIMARY KEY, deal_id TEXT UNIQUE NOT NULL REFERENCES deals(id) ON DELETE CASCADE, version TEXT NOT NULL DEFAULT 'v1',
 buyer_signed_at INTEGER, breeder_signed_at INTEGER, status TEXT NOT NULL DEFAULT 'draft', updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS pickups(
 id TEXT PRIMARY KEY, deal_id TEXT UNIQUE NOT NULL REFERENCES deals(id) ON DELETE CASCADE, pickup_date TEXT DEFAULT '',
 pickup_time TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'scheduled', completed_at INTEGER, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews(
 id TEXT PRIMARY KEY, deal_id TEXT UNIQUE NOT NULL REFERENCES deals(id) ON DELETE CASCADE, buyer_id TEXT NOT NULL REFERENCES users(id),
 breeder_id TEXT REFERENCES breeders(id), rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'published', created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS uploads(
 id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), puppy_id TEXT REFERENCES puppies(id),
 original_name TEXT, stored_name TEXT NOT NULL, mime_type TEXT, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS password_reset_tokens(
 token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, used_at INTEGER
);
CREATE TABLE IF NOT EXISTS email_verification_tokens(
 token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, used_at INTEGER
);
CREATE TABLE IF NOT EXISTS audit_logs(
 id TEXT PRIMARY KEY, user_id TEXT, action TEXT NOT NULL, target_type TEXT DEFAULT '', target_id TEXT DEFAULT '',
 detail TEXT DEFAULT '', created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reports(
 id TEXT PRIMARY KEY, reporter_user_id TEXT REFERENCES users(id), puppy_id TEXT REFERENCES puppies(id), breeder_id TEXT REFERENCES breeders(id),
 reason TEXT NOT NULL, detail TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS support_tickets(
 id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), name TEXT NOT NULL, email TEXT NOT NULL,
 category TEXT NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
 operator_note TEXT DEFAULT '', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS backup_runs(
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, created_by TEXT REFERENCES users(id), created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS commission_invoices(
 id TEXT PRIMARY KEY, invoice_no TEXT UNIQUE NOT NULL, deal_id TEXT UNIQUE NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
 breeder_id TEXT NOT NULL REFERENCES breeders(id), sale_amount INTEGER NOT NULL, rate_bps INTEGER NOT NULL,
 fee_amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'issued', issued_at INTEGER NOT NULL,
 due_at INTEGER NOT NULL, paid_at INTEGER, note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS breeder_fee_acceptances(
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 version TEXT NOT NULL, rate_bps INTEGER NOT NULL, due_days INTEGER NOT NULL, accepted_at INTEGER NOT NULL,
 UNIQUE(user_id,version)
);
CREATE TABLE IF NOT EXISTS deal_completion_reports(
 id TEXT PRIMARY KEY, deal_id TEXT UNIQUE NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
 breeder_id TEXT NOT NULL REFERENCES breeders(id), reported_by_user_id TEXT NOT NULL REFERENCES users(id),
 final_sale_amount INTEGER NOT NULL, pickup_date TEXT NOT NULL, buyer_name TEXT DEFAULT '', note TEXT DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending', reviewed_by_user_id TEXT REFERENCES users(id), review_note TEXT DEFAULT '',
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS automation_events(
 id TEXT PRIMARY KEY, event_key TEXT UNIQUE NOT NULL, kind TEXT NOT NULL,
 target_type TEXT DEFAULT '', target_id TEXT DEFAULT '', created_at INTEGER NOT NULL
);
'''


def now(): return int(time.time())

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con

def hash_password(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 180_000).hex()
    return salt, digest

def verify_password(password, salt, expected):
    return hmac.compare_digest(hash_password(password, salt)[1], expected)

def make_id(prefix): return prefix + secrets.token_hex(6)

def ensure_column(con, table, column, ddl):
    cols={r['name'] for r in con.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in cols:
        con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}')

def audit(con, user_id, action, target_type='', target_id='', detail=''):
    con.execute('INSERT INTO audit_logs VALUES(?,?,?,?,?,?,?)',
                (make_id('a_'),user_id,action,target_type,target_id,str(detail)[:1000],now()))

def ensure_commission_invoice(con, deal):
    # One tax-inclusive success-fee invoice per completed deal.
    if not deal or not deal['breeder_id']:
        return None
    existing=con.execute('SELECT * FROM commission_invoices WHERE deal_id=?',(deal['id'],)).fetchone()
    if existing:
        return existing
    sale_amount=int(deal['total_price'])
    fee_amount=(sale_amount*COMMISSION_RATE_BPS)//10000
    issued=now(); due=issued + COMMISSION_DUE_DAYS*86400
    inv_id=make_id('inv_')
    invoice_no='BP-'+time.strftime('%Y%m%d',time.localtime(issued))+'-'+secrets.token_hex(3).upper()
    sql = 'INSERT INTO commission_invoices (id,invoice_no,deal_id,breeder_id,sale_amount,rate_bps,fee_amount,status,issued_at,due_at,paid_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
    con.execute(sql,(inv_id,invoice_no,deal['id'],deal['breeder_id'],sale_amount,COMMISSION_RATE_BPS,fee_amount,'issued',issued,due,None,'BIG PAW 成約手数料（5%・税込）'))
    audit(con,None,'commission_invoice_issued','commission_invoice',inv_id,f'{invoice_no}:{fee_amount}')
    breeder_user=con.execute('SELECT u.id FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?',(deal['breeder_id'],)).fetchone()
    if breeder_user:
        con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',
                    (make_id('n_'),breeder_user['id'],'billing','成約手数料の請求書を発行しました',
                     f'{invoice_no} / {fee_amount:,}円 / 支払期限は発行日から{COMMISSION_DUE_DAYS}日以内です。',0,issued))
    return con.execute('SELECT * FROM commission_invoices WHERE id=?',(inv_id,)).fetchone()

def sync_breeder_billing_suspension(con, breeder_id=None):
    """Suspend public visibility for breeders with overdue unpaid commission invoices.
    Restore automatically once no overdue invoice remains. Returns changed breeder ids.
    """
    args=[]
    sql='SELECT * FROM breeders'
    if breeder_id:
        sql+=' WHERE id=?'; args=[breeder_id]
    breeders=con.execute(sql,args).fetchall()
    changed=[]
    t=now()
    for b in breeders:
        overdue=con.execute("SELECT COUNT(*) c FROM commission_invoices WHERE breeder_id=? AND status='issued' AND due_at<?",(b['id'],t)).fetchone()['c']
        currently=bool(b['billing_suspended'])
        if overdue and not currently:
            con.execute("UPDATE breeders SET billing_suspended=1,billing_suspended_at=?,billing_suspension_reason=? WHERE id=?",(t,'成約手数料の支払期限超過',b['id']))
            info=con.execute('SELECT u.id,u.email,b.kennel_name FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?',(b['id'],)).fetchone()
            if info:
                con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),info['id'],'billing','掲載を一時停止しました','成約手数料のお支払い期限を過ぎているため、BIG PAW上の犬舎・子犬掲載を一時停止しました。入金確認後、自動で掲載を再開します。',0,t))
                send_mail(info['email'],'BIG PAW 掲載一時停止のお知らせ',f"{info['kennel_name']} 様\n\n成約手数料のお支払い期限を過ぎているため、BIG PAW上の公開掲載を一時停止しました。\n入金確認後、自動で掲載を再開します。\n\n{PUBLIC_BASE_URL}/breeder-billing.html")
            audit(con,None,'breeder_billing_suspended','breeder',b['id'],f'overdue_invoices={overdue}')
            changed.append((b['id'],'suspended'))
        elif not overdue and currently:
            con.execute("UPDATE breeders SET billing_suspended=0,billing_suspended_at=NULL,billing_suspension_reason='' WHERE id=?",(b['id'],))
            info=con.execute('SELECT u.id,u.email,b.kennel_name FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?',(b['id'],)).fetchone()
            if info:
                con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),info['id'],'billing','掲載を再開しました','成約手数料の入金確認が取れたため、BIG PAW上の犬舎・子犬掲載を自動で再開しました。',0,t))
                send_mail(info['email'],'BIG PAW 掲載再開のお知らせ',f"{info['kennel_name']} 様\n\n成約手数料の入金確認が取れたため、BIG PAW上の公開掲載を再開しました。")
            audit(con,None,'breeder_billing_reactivated','breeder',b['id'],'all_overdue_invoices_cleared')
            changed.append((b['id'],'reactivated'))
    return changed

def claim_automation_event(con, event_key, kind, target_type='', target_id=''):
    try:
        con.execute('INSERT INTO automation_events VALUES(?,?,?,?,?,?)',
                    (make_id('ae_'),event_key,kind,target_type,target_id,now()))
        return True
    except sqlite3.IntegrityError:
        return False

def process_billing_reminders(con):
    """Send one-time reminders at 3 days before, due day, and overdue."""
    t=now(); sent=0
    rows=con.execute("""SELECT ci.*,u.id user_id,u.email,b.kennel_name
                        FROM commission_invoices ci
                        JOIN breeders b ON b.id=ci.breeder_id JOIN users u ON u.id=b.user_id
                        WHERE ci.status='issued'""").fetchall()
    for inv in rows:
        remaining=inv['due_at']-t
        stage=None; title=None; body=None
        if 0 < remaining <= 86400:
            stage='due_today'; title='成約手数料のお支払い期限が近づいています'
            body=f"{inv['invoice_no']} / {inv['fee_amount']:,}円 / 支払期限は本日〜24時間以内です。"
        elif 86400 < remaining <= 3*86400:
            stage='three_days'; title='成約手数料のお支払い期限まで3日以内です'
            due_txt=time.strftime('%Y年%m月%d日',time.localtime(inv['due_at']))
            body=f"{inv['invoice_no']} / {inv['fee_amount']:,}円 / 支払期限 {due_txt}"
        elif remaining <= 0:
            stage='overdue'; title='成約手数料のお支払い期限を過ぎています'
            body=f"{inv['invoice_no']} / {inv['fee_amount']:,}円 / 入金確認後に掲載を自動再開します。"
        if not stage: continue
        key=f"invoice:{inv['id']}:{stage}"
        if not claim_automation_event(con,key,'commission_reminder','commission_invoice',inv['id']): continue
        con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',
                    (make_id('n_'),inv['user_id'],'billing',title,body,0,t))
        due_txt=time.strftime('%Y年%m月%d日',time.localtime(inv['due_at']))
        send_mail(inv['email'],f'BIG PAW {title}',f"{inv['kennel_name']} 様\n\n{body}\n支払期限: {due_txt}\n\n{PUBLIC_BASE_URL}/breeder-billing.html")
        audit(con,None,'automatic_commission_reminder','commission_invoice',inv['id'],stage)
        sent+=1
    return sent

def process_completion_report_nudges(con):
    """Nudge breeders once when a scheduled pickup date has passed without a completion report."""
    today=time.strftime('%Y-%m-%d',time.localtime())
    rows=con.execute("""SELECT d.id deal_id,d.breeder_id,p.name puppy_name,pk.pickup_date,u.id user_id,u.email,b.kennel_name
                        FROM deals d JOIN puppies p ON p.id=d.puppy_id
                        JOIN pickups pk ON pk.deal_id=d.id
                        JOIN breeders b ON b.id=d.breeder_id JOIN users u ON u.id=b.user_id
                        LEFT JOIN deal_completion_reports r ON r.deal_id=d.id
                        WHERE d.status!='completed' AND pk.pickup_date!='' AND pk.pickup_date<=?
                          AND (r.id IS NULL OR r.status='rejected')""",(today,)).fetchall()
    sent=0
    for r in rows:
        key=f"deal:{r['deal_id']}:completion_nudge:{r['pickup_date']}"
        if not claim_automation_event(con,key,'completion_report_nudge','deal',r['deal_id']): continue
        title='成約申請のご確認'
        body=f"{r['puppy_name']}のお迎え予定日を過ぎています。成約した場合は「成約申請」をお願いします。成約していない場合は申請不要です。"
        con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),r['user_id'],'deal_report',title,body,0,now()))
        send_mail(r['email'],'BIG PAW 成約申請のご確認',f"{r['kennel_name']} 様\n\n{body}\n\n{PUBLIC_BASE_URL}/breeder-deal-report.html")
        audit(con,None,'automatic_completion_report_nudge','deal',r['deal_id'],r['pickup_date'])
        sent+=1
    return sent

def create_automatic_backup(con):
    """Create a daily local SQLite backup and retain the latest configured number."""
    last=con.execute("SELECT MAX(created_at) t FROM backup_runs WHERE created_by IS NULL").fetchone()['t']
    if last and now()-last < max(1,AUTO_BACKUP_HOURS)*3600: return None
    filename=f"bigpaw-auto-{time.strftime('%Y%m%d-%H%M%S')}.sqlite3"
    dest=BACKUPS/filename
    # SQLite online backup keeps a consistent snapshot while the service is running.
    dst=sqlite3.connect(dest)
    try: con.backup(dst)
    finally: dst.close()
    bid=make_id('bk_'); con.execute('INSERT INTO backup_runs VALUES(?,?,?,?)',(bid,filename,None,now()))
    audit(con,None,'automatic_backup_created','backup',bid,filename)
    autos=sorted(BACKUPS.glob('bigpaw-auto-*.sqlite3'),key=lambda x:x.stat().st_mtime,reverse=True)
    for old in autos[max(1,AUTO_BACKUP_KEEP):]:
        try: old.unlink()
        except OSError: pass
    return filename

def run_automations_once():
    con=db()
    try:
        reminders=process_billing_reminders(con)
        nudges=process_completion_report_nudges(con)
        changes=sync_breeder_billing_suspension(con)
        backup=create_automatic_backup(con)
        con.commit()
        return {'billingReminders':reminders,'completionNudges':nudges,'visibilityChanges':len(changes),'backup':backup}
    finally:
        con.close()

def automation_monitor_loop(interval_seconds=None):
    interval_seconds=interval_seconds or AUTOMATION_INTERVAL_SECONDS
    while True:
        try:
            run_automations_once()
        except Exception as exc:
            print(f'[automation-monitor] {exc}')
        time.sleep(max(60,interval_seconds))



def public_breeder_json(row):
    d=dict(row)
    pref=(d.get('prefecture') or '').strip()
    # Never expose private breeder identity/contact/review material through public APIs.
    for k in ('user_id','registration_no','registration_proof','registration_proof_path','email','phone','address','postal_code','line','line_id','instagram','sns','website','url'):
        d.pop(k,None)
    d['kennel_name']=(pref+'のBIGPAW認定ブリーダー') if pref else 'BIGPAW認定ブリーダー'
    profile=(d.get('profile') or '')
    import re as _re
    profile=_re.sub(r'\[REGISTRATION_PROOF\][^\s<]*','',profile)
    profile=_re.sub(r'https?://\S+','',profile)
    profile=_re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','',profile)
    profile=_re.sub(r'(?<!\d)(?:0\d{1,4}[-ー－]?\d{1,4}[-ー－]?\d{3,4})(?!\d)','',profile)
    profile=_re.sub(r'(?i)(?:LINE|Instagram|インスタグラム|インスタ|SNS)\s*[:：]?\s*[@\w.\-]+','',profile)
    d['profile']=profile.strip()
    return d

def rate_limited(key, limit=10, window=60):
    t=now()
    with RATE_LOCK:
        q=RATE_BUCKETS[key]
        while q and q[0] <= t-window: q.popleft()
        if len(q) >= limit: return True
        q.append(t); return False

def send_mail(to_email: str, subject: str, text: str) -> bool:
    import os, smtplib, ssl, json, urllib.request, urllib.error, socket
    from email.message import EmailMessage
    api_key=(os.environ.get("RESEND_API_KEY") or "").strip()
    # Prefer IPv4 for Resend from Railway; avoids long IPv6 connect stalls.
    _orig_getaddrinfo=socket.getaddrinfo
    def _ipv4_first(*args, **kwargs):
        _r=_orig_getaddrinfo(*args, **kwargs)
        return sorted(_r,key=lambda x: 0 if x[0] == socket.AF_INET else 1)
    socket.getaddrinfo=_ipv4_first
    if api_key:
        try:
            payload=json.dumps({"from":"BIG PAW <noreply@bigpaw.site>","to":[to_email],"subject":subject,"text":text}).encode("utf-8")
            req=urllib.request.Request("https://api.resend.com/emails",data=payload,headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json","User-Agent":"BIGPAW-Mailer/1.0","Accept":"application/json"},method="POST")
            with urllib.request.urlopen(req,timeout=10) as resp:
                ok=200 <= resp.status < 300
                print("[BIG PAW] HTTPS mail status:",resp.status,flush=True)
                if ok: return True
        except urllib.error.HTTPError as e:
            detail=e.read().decode("utf-8","replace")[:500]
            print("[BIG PAW] HTTPS mail HTTP error:",e.code,detail,flush=True)
        except Exception as e:
            print("[BIG PAW] HTTPS mail failed:",type(e).__name__,str(e)[:300],flush=True)
    host=(os.environ.get("SMTP_HOST") or os.environ.get("BIGPAW_SMTP_HOST") or "").strip()
    port=int(os.environ.get("SMTP_PORT") or os.environ.get("BIGPAW_SMTP_PORT") or "587")
    user=(os.environ.get("SMTP_USER") or os.environ.get("BIGPAW_SMTP_USER") or "").strip()
    password=(os.environ.get("SMTP_PASSWORD") or os.environ.get("BIGPAW_SMTP_PASSWORD") or "").strip()
    sender=(os.environ.get("SMTP_FROM") or os.environ.get("BIGPAW_SMTP_FROM") or user).strip()
    if not (host and user and password and sender):
        print("[BIG PAW] SMTP configuration incomplete", flush=True)
        return False
    try:
        msg=EmailMessage()
        msg["From"]=sender
        msg["To"]=to_email
        msg["Subject"]=subject
        msg.set_content(text)
        ctx=ssl.create_default_context()
        if port == 465:
            smtp=smtplib.SMTP_SSL(host, port, timeout=20, context=ctx)
        else:
            smtp=smtplib.SMTP(host, port, timeout=20)
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
        with smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        print("[BIG PAW] SMTP mail sent", flush=True)
        return True
    except Exception as e:
        print("[BIG PAW] SMTP failed:", type(e).__name__, str(e)[:300], flush=True)
        return False

def valid_image_bytes(raw: bytes, mime: str) -> bool:
    if mime=='image/jpeg': return len(raw)>=3 and raw[:3]==b'\xff\xd8\xff'
    if mime=='image/png': return len(raw)>=8 and raw[:8]==b'\x89PNG\r\n\x1a\n'
    if mime=='image/webp': return len(raw)>=12 and raw[:4]==b'RIFF' and raw[8:12]==b'WEBP'
    return False

def init_db():
    con = db(); con.executescript(SCHEMA)
    ensure_column(con,'users','email_verified','INTEGER NOT NULL DEFAULT 0')
    ensure_column(con,'users','terms_accepted_at','INTEGER')
    ensure_column(con,'users','privacy_accepted_at','INTEGER')
    ensure_column(con,'users','updated_at','INTEGER')
    ensure_column(con,'puppies','review_status',"TEXT NOT NULL DEFAULT 'approved'")
    ensure_column(con,'puppies','moderation_note',"TEXT DEFAULT ''")
    ensure_column(con,'puppies','published_at','INTEGER')
    ensure_column(con,'breeders','billing_suspended','INTEGER NOT NULL DEFAULT 0')
    ensure_column(con,'breeders','billing_suspended_at','INTEGER')
    ensure_column(con,'breeders','billing_suspension_reason',"TEXT DEFAULT ''")
    def seed_user(uid, role, email, pw, last='', first='', display=''):
        if con.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(): return
        existing=con.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone()
        if existing:
            if uid == 'u_admin' and role == 'operator': con.execute('UPDATE users SET email=? WHERE id=?',(email,uid))
            return
        salt,digest=hash_password(pw)
        con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                    (uid,role,email,last,first,display,salt,digest,now()))
    if not IS_PRODUCTION:
        seed_user('u_demo','buyer','demo@bigpaw.jp','demo1234','山田','太郎','山田 太郎')
        seed_user('u_dog44','breeder','dog44@bigpaw.jp','demo1234','茂呂','','DOG44')
        seed_user('u_admin','operator','admin@bigpaw.jp','admin1234','','','BIG PAW運営')
    else:
        admin_email=os.environ.get('BIGPAW_ADMIN_EMAIL','').strip().lower()
        admin_password=os.environ.get('BIGPAW_ADMIN_PASSWORD','')
        if admin_email and len(admin_password)>=12:
            seed_user('u_admin','operator',admin_email,admin_password,'','','BIG PAW運営')
    if (not IS_PRODUCTION) and not con.execute('SELECT 1 FROM breeders WHERE id="b_dog44"').fetchone():
        con.execute('INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES(?,?,?,?,?,?,?)',
                    ('b_dog44','u_dog44','DOG44','埼玉県','','大型犬の健康・親犬情報を丁寧に公開する犬舎。','approved'))
    if (not IS_PRODUCTION) and not con.execute('SELECT 1 FROM puppies LIMIT 1').fetchone():
        for p in SEED_PUPPIES:
            breeder_id='b_dog44' if p[11]=='DOG44' else None
            con.execute('''INSERT INTO puppies(id,breeder_id,name,breed,breed_key,gender,gender_key,color,price,status,area,area_key,breeder_name,weight,adult_min,adult_max,health,birth,description,father,mother,image_url,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (p[0],breeder_id,*p[1:11],p[11],*p[12:], '', now()))
    if (not IS_PRODUCTION) and not con.execute('SELECT 1 FROM parent_dogs WHERE id="pd_courage"').fetchone():
        con.execute('INSERT INTO parent_dogs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    ('pd_courage','b_dog44','クラージュ','父犬','スタンダードプードル','ブラック',68,28,'親犬の遺伝子検査情報を登録','健康情報登録あり','チャンピオン血統情報を掲載可能','',now()))
    if (not IS_PRODUCTION) and not con.execute('SELECT 1 FROM parent_dogs WHERE id="pd_milk"').fetchone():
        con.execute('INSERT INTO parent_dogs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    ('pd_milk','b_dog44','ミルク','母犬','スタンダードプードル','クリーム',None,None,'毛色遺伝情報を登録','健康情報登録あり','出産履歴を管理','',now()))
    if (not IS_PRODUCTION) and not con.execute('SELECT 1 FROM health_records WHERE id="hr_p1_check"').fetchone():
        con.execute('INSERT INTO health_records VALUES(?,?,?,?,?,?,?,?,?)',('hr_p1_check','p1',None,'健康診断','一般健康診断','異常所見なし','2026-08-18','',now()))
        con.execute('INSERT INTO health_records VALUES(?,?,?,?,?,?,?,?,?)',('hr_p1_vax','p1',None,'ワクチン','6種混合ワクチン','1回目','2026-08-21','',now()))
        con.execute('INSERT INTO health_records VALUES(?,?,?,?,?,?,?,?,?)',('hr_p1_chip','p1',None,'個体識別','マイクロチップ','装着済み','','',now()))
    if not IS_PRODUCTION:
        con.execute("UPDATE users SET email_verified=1, terms_accepted_at=COALESCE(terms_accepted_at,?), privacy_accepted_at=COALESCE(privacy_accepted_at,?), updated_at=COALESCE(updated_at,?) WHERE id IN ('u_demo','u_dog44','u_admin')",(now(),now(),now()))
        con.execute("UPDATE puppies SET review_status=COALESCE(review_status,'approved'), published_at=COALESCE(published_at,created_at) WHERE id IN ('p1','p2','p3')")
    # legacy approved breeder puppies: approved breeders publish directly
    con.execute("UPDATE puppies SET review_status='approved' WHERE review_status!='approved' AND breeder_id IN (SELECT id FROM breeders WHERE review_status='approved')")
    # normalize legacy breed keys used by public search
    con.execute("UPDATE puppies SET breed_key='standard-poodle' WHERE breed='スタンダードプードル' AND breed_key!='standard-poodle'")
    con.commit(); con.close()


def rowdict(row): return dict(row) if row else None

def puppy_json(r):
    d=rowdict(r)
    if not d: return None
    return {
      'id':d['id'],'name':d['name'],'breed':d['breed'],'breedKey':d['breed_key'],'gender':d['gender'],
      'genderKey':d['gender_key'],'color':d['color'],'price':d['price'],'status':d['status'],'area':d['area'],
      'areaKey':d['area_key'],'breeder':d['breeder_name'],'breederId':d['breeder_id'],'weight':d['weight'],'adultMin':d['adult_min'],
      'adultMax':d['adult_max'],'health':bool(d['health']),'birth':d['birth'],'desc':d['description'],
      'father':d['father'],'mother':d['mother'],'imageUrl':d['image_url'],'createdAt':d['created_at'],
      'reviewStatus':d.get('review_status','approved') if isinstance(d,dict) else 'approved','moderationNote':d.get('moderation_note','') if isinstance(d,dict) else ''
    }

def public_profile_has_direct_contact(text):
    t=str(text or '')
    checks=[
      r'https?://|www\.',
      r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',
      r'(?<!\d)(?:0\d{1,4}[-ー‐–— ]?\d{1,4}[-ー‐–— ]?\d{3,4})(?!\d)',
      r'(?i)(?:LINE|Instagram|インスタ|SNS|X|Twitter|Facebook|TikTok)\s*[:：＠@]?',
    ]
    return any(re.search(x,t,re.I) for x in checks)

def public_puppy_json(r):
    d=puppy_json(r)
    if not d: return None
    area=(d.get('area') or '').strip()
    d['breeder']=(area+'のBIGPAW認定ブリーダー') if area else 'BIGPAW認定ブリーダー'
    return d

def parse_cookie_header(raw: str):
    out={}
    for part in (raw or '').split(';'):
        if '=' not in part: continue
        k,v=part.strip().split('=',1)
        out[k]=v
    return out

def session_cookie_header(token: str, clear=False):
    value='' if clear else token
    max_age='0' if clear else str(60*60*24*14)
    secure='; Secure' if IS_PRODUCTION else ''
    return f"{SESSION_COOKIE_NAME}={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax{secure}"

class Handler(SimpleHTTPRequestHandler):
    server_version = 'BigPaw/1.0'
    def __init__(self,*args,**kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, fmt, *args): print('[BIG PAW]', fmt % args)
    def static_blocked(self, path: str) -> bool:
        clean=urlparse(path).path
        if any(clean==x or clean.startswith(x+'/') for x in BLOCKED_STATIC_PREFIXES): return True
        name=Path(clean).name
        if name in BLOCKED_STATIC_NAMES or name.startswith('.'): return True
        return any(clean.lower().endswith(s) for s in BLOCKED_STATIC_SUFFIXES)
    def translate_path(self, path):
        clean=urlparse(path).path
        if clean.startswith('/uploads/'):
            name=Path(clean).name
            con=db(); hidden=con.execute('SELECT 1 FROM uploads WHERE stored_name=? AND puppy_id IS NULL LIMIT 1',(name,)).fetchone(); con.close()
            if hidden: return str(ROOT / '__not_public__')
            return str(UPLOADS / name)
        return super().translate_path(path)
    def do_HEAD(self):
        if self.static_blocked(self.path):
            self.send_error(404); return
        return super().do_HEAD()
    def end_headers(self):
        pth=urlparse(self.path).path.lower()
        if pth=='/' or pth.endswith(('.html','.js','.css')):
            self.send_header('Cache-Control','no-store, max-age=0')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','SAMEORIGIN')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'")
        if IS_PRODUCTION: self.send_header('Strict-Transport-Security','max-age=31536000; includeSubDomains')
        super().end_headers()
    def send_json(self,obj,status=200,extra=None):
        raw=json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(raw)))
        if extra:
            for k,v in extra.items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(raw)
    def send_text(self,text,status=200,content_type='text/plain; charset=utf-8'):
        raw=text.encode('utf-8'); self.send_response(status); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def json_body(self):
        try:
            n=int(self.headers.get('Content-Length','0'))
            return json.loads(self.rfile.read(n) or b'{}')
        except Exception: return {}
    def session_token(self):
        auth=self.headers.get('Authorization','')
        if auth.startswith('Bearer '):
            return auth[7:].strip()
        return parse_cookie_header(self.headers.get('Cookie','')).get(SESSION_COOKIE_NAME,'')
    def current_user(self):
        token=self.session_token()
        if not token: return None
        con=db()
        row=con.execute('''SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                           WHERE s.token=? AND s.expires_at>?''',(token,now())).fetchone()
        con.close(); return rowdict(row)
    def mutation_origin_allowed(self):
        if not IS_PRODUCTION: return True
        path=urlparse(self.path).path
        if path=='/api/payment-webhook/reservation': return True
        origin=self.headers.get('Origin','')
        if not origin: return True
        allowed={PUBLIC_BASE_URL.rstrip('/'),'https://www.bigpaw.site','https://bigpaw.site'}
        try:
            o=urlparse(origin)
            host=(o.hostname or '').lower().rstrip('.')
            return o.scheme=='https' and (host=='bigpaw.site' or host.endswith('.bigpaw.site') or host=='bigpaw-site-production.up.railway.app') and (o.port in (None,443))
        except Exception:
            return False
    def require(self, roles=None):
        u=self.current_user()
        if not u:
            self.send_json({'error':'auth_required'},401); return None
        if roles and u['role'] not in roles:
            self.send_json({'error':'forbidden'},403); return None
        return u
    def route_parts(self): return [x for x in urlparse(self.path).path.split('/') if x]
    def inquiry_for_user(self, con, inquiry_id, u):
        q=con.execute('SELECT * FROM inquiries WHERE id=?',(inquiry_id,)).fetchone()
        if not q: return None
        if u['role']=='operator': return q
        if u['role']=='buyer' and q['buyer_id']==u['id']: return q
        if u['role']=='breeder':
            b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            if b and q['breeder_id']==b['id']: return q
        return None
    def deal_for_user(self, con, deal_id, u):
        d=con.execute('SELECT * FROM deals WHERE id=?',(deal_id,)).fetchone()
        if not d: return None
        if u['role']=='operator' or d['buyer_id']==u['id']: return d
        if u['role']=='breeder':
            b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            if b and d['breeder_id']==b['id']: return d
        return None

    def do_GET(self):
        if not urlparse(self.path).path.startswith('/api/') and self.static_blocked(self.path):
            self.send_error(404); return
        parsed=urlparse(self.path); path=parsed.path; q=parse_qs(parsed.query)
        m=re.fullmatch(r'/api/puppies/([^/]+)/photos',path)
        if m:
            u=self.require(['buyer','breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            rows=con.execute('SELECT id,stored_name,created_at FROM uploads WHERE puppy_id=? ORDER BY created_at,id',(puppy['id'],)).fetchall()
            out=[{'id':r['id'],'url':'/uploads/'+r['stored_name'],'isMain':('/uploads/'+r['stored_name'])==puppy['image_url']} for r in rows]
            con.close(); return self.send_json(out)
        if path=='/robots.txt':
            txt=f"User-agent: *\nDisallow: /api/\nDisallow: /operator-\nDisallow: /admin.html\nDisallow: /breeder-billing.html\nDisallow: /breeder-deal-report.html\nDisallow: /account.html\nDisallow: /mypage.html\nDisallow: /messages.html\nDisallow: /notifications.html\nSitemap: {PUBLIC_BASE_URL}/sitemap.xml\n"
            return self.send_text(txt)
        if path=='/sitemap.xml':
            con=db(); sync_breeder_billing_suspension(con); con.commit()
            static=['/','/search.html','/breeders.html','/breed-guide.html','/breed-standard-poodle.html','/cost-simulator.html','/match.html','/faq.html','/contact.html','/privacy.html','/terms.html','/legal-notice.html','/breeder-fees.html']
            puppies=con.execute("SELECT p.id FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.review_status='approved' AND p.status!='成約済み' AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)").fetchall()
            breeders=con.execute("SELECT id FROM breeders WHERE review_status='approved' AND COALESCE(billing_suspended,0)=0").fetchall(); con.close()
            urls=[PUBLIC_BASE_URL+x for x in static]
            urls += [f"{PUBLIC_BASE_URL}/puppy-detail.html?id={quote(str(x['id']))}" for x in puppies]
            urls += [f"{PUBLIC_BASE_URL}/breeder-detail.html?id={quote(str(x['id']))}" for x in breeders]
            body='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{xml_escape(u)}</loc></url>' for u in urls)+'</urlset>'
            return self.send_text(body,200,'application/xml; charset=utf-8')
        if path=='/api/breed-image':
            key=(q.get('key') or [''])[0]
            wiki=BREED_WIKI.get(key)
            if not wiki:
                return self.send_json({'error':'unknown_breed'},404)
            cache_key=key+'-photos-v7'
            img_path=BREED_IMAGE_CACHE/(re.sub(r'[^a-z0-9_-]','_',cache_key.lower())+'.bin')
            meta_path=img_path.with_suffix('.json')
            try:
                if img_path.exists() and meta_path.exists() and img_path.stat().st_size>100:
                    meta=json.loads(meta_path.read_text('utf-8'))
                    data=img_path.read_bytes(); ctype=meta.get('content_type','image/jpeg')
                else:
                    if key=='labrador-retriever':
                        # Face-visible Labrador portrait from Wikimedia Commons (CC BY 2.0).
                        src='https://commons.wikimedia.org/wiki/Special:Redirect/file/Labrador_Retriever_yellow_portrait.jpg?width=700'
                    else:
                        api='https://en.wikipedia.org/w/api.php?'+urlencode({'action':'query','format':'json','prop':'pageimages','piprop':'thumbnail','pithumbsize':'700','redirects':'1','titles':wiki})
                        req=Request(api,headers={'User-Agent':'BIGPAW/1.0 (breed image cache)'}); raw=urlopen(req,timeout=12).read()
                        obj=json.loads(raw.decode('utf-8')); page=next(iter((obj.get('query',{}).get('pages') or {}).values()),{})
                        src=((page.get('thumbnail') or {}).get('source') or '').strip()
                        if not src:
                            # Wikipediaに代表画像がない犬種はWikimedia Commonsから同犬種画像を補完。
                            breed_name=re.sub(r'\s*\([^)]*\)\s*$', '', wiki.replace('_',' ')).strip()
                            capi='https://commons.wikimedia.org/w/api.php?'+urlencode({'action':'query','format':'json','generator':'search','gsrsearch':breed_name+' dog','gsrnamespace':'6','gsrlimit':'8','prop':'imageinfo','iiprop':'url','iiurlwidth':'700'})
                            creq=Request(capi,headers={'User-Agent':'BIGPAW/1.0 (breed image fallback)'}); craw=urlopen(creq,timeout=12).read()
                            cobj=json.loads(craw.decode('utf-8')); pages=(cobj.get('query',{}).get('pages') or {})
                            for cp in pages.values():
                                ii=(cp.get('imageinfo') or [])
                                if ii:
                                    src=(ii[0].get('thumburl') or ii[0].get('url') or '').strip()
                                    if src: break
                        if not src: raise RuntimeError('no_thumbnail')
                    ir=Request(src,headers={'User-Agent':'BIGPAW/1.0 (breed image cache)','Accept':'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'})
                    with urlopen(ir,timeout=15) as resp:
                        data=resp.read(8*1024*1024+1); ctype=(resp.headers.get_content_type() or 'image/jpeg')
                    if len(data)>8*1024*1024: raise RuntimeError('image_too_large')
                    if not ctype.startswith('image/'): raise RuntimeError('not_image')
                    img_path.write_bytes(data); meta_path.write_text(json.dumps({'content_type':ctype,'wiki':wiki},ensure_ascii=False),'utf-8')
                self.send_response(200); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','public, max-age=604800'); self.end_headers(); self.wfile.write(data); return
            except Exception as e:
                # Always return a visible same-origin fallback so the card never collapses.
                label=BREED_JA.get(key,key)
                safe=label.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                svg=(f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="700" viewBox="0 0 700 700"><rect width="700" height="700" fill="#fff1f6"/><text x="350" y="320" text-anchor="middle" font-size="170">🐕</text><text x="350" y="500" text-anchor="middle" font-family="sans-serif" font-size="34" fill="#664d58">{safe}</text></svg>''').encode('utf-8')
                self.send_response(200); self.send_header('Content-Type','image/svg+xml; charset=utf-8'); self.send_header('Content-Length',str(len(svg))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(svg); return
        if path=='/api/health': return self.send_json({'ok':True,'service':'BIG PAW API','version':'1.0','environment':APP_ENV,'database':'sqlite','mailConfigured':bool(SMTP_HOST),'paymentMode':PAYMENT_MODE})
        if path=='/api/operator/readiness':
            u=self.require(['operator'])
            if not u:return
            checks={
              'productionMode':IS_PRODUCTION,
              'httpsPublicUrl':PUBLIC_BASE_URL.startswith('https://'),
              'smtpConfigured':bool(SMTP_HOST and SMTP_FROM),
              'devLinksDisabled':not DEV_LINKS,
              'adminCredentialConfigured':bool(os.environ.get('BIGPAW_ADMIN_EMAIL') and len(os.environ.get('BIGPAW_ADMIN_PASSWORD',''))>=12) if IS_PRODUCTION else True,
              'paymentConfigured': PAYMENT_MODE=='manual' or bool(PAYMENT_WEBHOOK_SECRET),
              'billingIdentityConfigured':bool(BILLING_ISSUER_NAME and BILLING_ADDRESS),
              'billingBankConfigured':bool(BILLING_BANK_NAME and BILLING_BANK_ACCOUNT_NO and BILLING_BANK_ACCOUNT_HOLDER),
              'uploadsWritable':os.access(UPLOADS,os.W_OK),
              'backupsWritable':os.access(BACKUPS,os.W_OK),
              'databaseWritable':os.access(DB.parent,os.W_OK),
              'automationIntervalValid':AUTOMATION_INTERVAL_SECONDS>=60,
              'autoBackupRetentionValid':AUTO_BACKUP_KEEP>=1,
            }
            return self.send_json({'ready':all(checks.values()),'checks':checks,'environment':APP_ENV,'publicBaseUrl':PUBLIC_BASE_URL,'paymentMode':PAYMENT_MODE,'commissionRateBps':COMMISSION_RATE_BPS,'commissionDueDays':COMMISSION_DUE_DAYS,'commissionTermsVersion':COMMISSION_TERMS_VERSION})
        if path=='/api/me':
            u=self.require()
            if not u:return
            return self.send_json({'id':u['id'],'role':u['role'],'email':u['email'],'last':u['last'],'first':u['first'],'displayName':u['display_name'],'emailVerified':bool(u.get('email_verified',0)),'termsAcceptedAt':u.get('terms_accepted_at'),'privacyAcceptedAt':u.get('privacy_accepted_at')})
        if path=='/api/puppies':
            con=db(); sync_breeder_billing_suspension(con); con.commit(); sql="SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.review_status='approved' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"; args=[]
            if q.get('breed') and q['breed'][0]: sql+=' AND p.breed_key=?'; args.append(q['breed'][0])
            if q.get('gender') and q['gender'][0]: sql+=' AND p.gender_key=?'; args.append(q['gender'][0])
            if q.get('area') and q['area'][0]: sql+=' AND p.area_key=?'; args.append(q['area'][0])
            if q.get('status') and q['status'][0]: sql+=' AND p.status=?'; args.append(q['status'][0])
            sql+=' ORDER BY p.created_at DESC'
            rows=con.execute(sql,args).fetchall(); con.close(); return self.send_json([public_puppy_json(r) for r in rows])
        m=re.fullmatch(r'/api/puppies/([^/]+)',path)
        if m:
            con=db(); sync_breeder_billing_suspension(con); con.commit(); r=con.execute("SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=? AND p.review_status='approved' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)",(m.group(1),)).fetchone(); con.close()
            return self.send_json(public_puppy_json(r),200) if r else self.send_json({'error':'not_found'},404)
        if path=='/api/breeders':
            con=db(); sync_breeder_billing_suspension(con); con.commit(); rows=con.execute("""SELECT b.*, COUNT(DISTINCT p.id) open_puppies, ROUND(AVG(r.rating),1) rating, COUNT(DISTINCT r.id) review_count
                FROM breeders b LEFT JOIN puppies p ON p.breeder_id=b.id AND p.review_status='approved' AND p.status='募集中'
                LEFT JOIN reviews r ON r.breeder_id=b.id AND r.status='published'
                WHERE b.review_status='approved' AND COALESCE(b.billing_suspended,0)=0 GROUP BY b.id ORDER BY b.kennel_name""").fetchall(); con.close(); return self.send_json([public_breeder_json(r) for r in rows])
        mb=re.fullmatch(r'/api/breeders/([^/]+)',path)
        if mb:
            con=db(); sync_breeder_billing_suspension(con,mb.group(1)); con.commit(); b=con.execute("SELECT * FROM breeders WHERE id=? AND review_status='approved' AND COALESCE(billing_suspended,0)=0",(mb.group(1),)).fetchone()
            if not b: con.close(); return self.send_json({'error':'not_found'},404)
            puppies=con.execute("SELECT * FROM puppies WHERE breeder_id=? AND review_status='approved' ORDER BY created_at DESC",(b['id'],)).fetchall(); reviews=con.execute("SELECT rating,body,created_at FROM reviews WHERE breeder_id=? AND status='published' ORDER BY created_at DESC LIMIT 20",(b['id'],)).fetchall(); out=public_breeder_json(b); out['puppies']=[public_puppy_json(x) for x in puppies]; out['reviews']=[dict(x) for x in reviews]; con.close(); return self.send_json(out)
        if path=='/api/breeder/puppies':
            u=self.require(['breeder','operator']);
            if not u:return
            con=db()
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); bid=b['id'] if b else '__none__'
                rows=con.execute('SELECT * FROM puppies WHERE breeder_id=? ORDER BY created_at DESC',(bid,)).fetchall()
            else: rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall()
            con.close(); return self.send_json([puppy_json(r) for r in rows])
        if path=='/api/breeder-profile':
            u=self.require(['breeder','operator']);
            if not u:return
            con=db()
            if u['role']=='breeder':
                r=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if r: sync_breeder_billing_suspension(con,r['id']); con.commit(); r=con.execute('SELECT * FROM breeders WHERE id=?',(r['id'],)).fetchone()
            else:
                bid=(q.get('id') or [''])[0]
                if bid: sync_breeder_billing_suspension(con,bid); con.commit(); r=con.execute('SELECT * FROM breeders WHERE id=?',(bid,)).fetchone()
                else: r=None
            con.close(); return self.send_json(dict(r) if r else None)
        if path=='/api/parent-dogs':
            u=self.require(['breeder','operator']);
            if not u:return
            con=db()
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); bid=b['id'] if b else '__none__'
                rows=con.execute('SELECT * FROM parent_dogs WHERE breeder_id=? ORDER BY created_at DESC',(bid,)).fetchall()
            else: rows=con.execute('SELECT * FROM parent_dogs ORDER BY created_at DESC').fetchall()
            con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/health-records':
            u=self.require(['breeder','operator']);
            if not u:return
            puppy_id=(q.get('puppyId') or [''])[0]; parent_id=(q.get('parentDogId') or [''])[0]; con=db()
            sql='SELECT hr.* FROM health_records hr WHERE 1=1'; args=[]
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); bid=b['id'] if b else '__none__'
                sql+=' AND ((hr.puppy_id IN (SELECT id FROM puppies WHERE breeder_id=?)) OR (hr.parent_dog_id IN (SELECT id FROM parent_dogs WHERE breeder_id=?)))'; args.extend([bid,bid])
            if puppy_id: sql+=' AND hr.puppy_id=?'; args.append(puppy_id)
            if parent_id: sql+=' AND hr.parent_dog_id=?'; args.append(parent_id)
            rows=con.execute(sql+' ORDER BY hr.tested_on DESC,hr.created_at DESC',args).fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/favorites':
            u=self.require(['buyer']);
            if not u:return
            con=db(); sync_breeder_billing_suspension(con); con.commit(); rows=con.execute('''SELECT p.* FROM favorites f JOIN puppies p ON p.id=f.puppy_id LEFT JOIN breeders b ON b.id=p.breeder_id WHERE f.user_id=? AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0) ORDER BY f.created_at DESC''',(u['id'],)).fetchall(); con.close()
            return self.send_json([public_puppy_json(r) for r in rows])
        if path=='/api/inquiries':
            u=self.require();
            if not u:return
            con=db()
            if u['role']=='buyer':
                rows=con.execute('SELECT i.*,p.name puppy_name,p.breeder_name,p.price puppy_price FROM inquiries i JOIN puppies p ON p.id=i.puppy_id WHERE buyer_id=? ORDER BY i.created_at DESC',(u['id'],)).fetchall()
                rows=[dict(r) for r in rows]
                for r in rows: r['breeder_name']='BIGPAW認定ブリーダー'
            elif u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); bid=b['id'] if b else '__none__'
                rows=con.execute('SELECT i.*,p.name puppy_name,p.breeder_name,p.price puppy_price FROM inquiries i JOIN puppies p ON p.id=i.puppy_id WHERE i.breeder_id=? ORDER BY i.created_at DESC',(bid,)).fetchall()
            else:
                rows=con.execute('SELECT i.*,p.name puppy_name,p.breeder_name,p.price puppy_price FROM inquiries i JOIN puppies p ON p.id=i.puppy_id ORDER BY i.created_at DESC').fetchall()
            out=[dict(r) for r in rows]
            if u['role']=='breeder':
                for r in out: r['email']=''; r['phone']=''
            con.close(); return self.send_json(out)
        m=re.fullmatch(r'/api/inquiries/([^/]+)/messages',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            rows=con.execute('''SELECT m.*,u.display_name,u.role FROM messages m JOIN users u ON u.id=m.sender_user_id WHERE m.inquiry_id=? ORDER BY m.created_at ASC''',(m.group(1),)).fetchall(); con.close()
            return self.send_json([dict(r) for r in rows])
        m=re.fullmatch(r'/api/inquiries/([^/]+)/video-room',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            import hashlib
            room='BIGPAW-'+hashlib.sha256((m.group(1)+'|online-visit').encode()).hexdigest()[:32]
            con.close(); return self.send_json({'room':room,'inquiryId':m.group(1),'role':u['role']})
        m=re.fullmatch(r'/api/inquiries/([^/]+)/visit',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            r=con.execute('SELECT * FROM visits WHERE inquiry_id=?',(m.group(1),)).fetchone(); con.close(); return self.send_json(dict(r) if r else None)
        m=re.fullmatch(r'/api/inquiries/([^/]+)/deal',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            r=con.execute('SELECT * FROM deals WHERE inquiry_id=?',(m.group(1),)).fetchone(); con.close(); return self.send_json(dict(r) if r else None)
        m=re.fullmatch(r'/api/deals/([^/]+)/summary',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); d=self.deal_for_user(con,m.group(1),u)
            if not d: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            payment=con.execute("SELECT * FROM payments WHERE deal_id=? AND kind='reservation' ORDER BY created_at DESC LIMIT 1",(d['id'],)).fetchone()
            contract=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone()
            pickup=con.execute('SELECT * FROM pickups WHERE deal_id=?',(d['id'],)).fetchone()
            review=con.execute('SELECT * FROM reviews WHERE deal_id=?',(d['id'],)).fetchone()
            out={'deal':dict(d),'payment':dict(payment) if payment else None,'contract':dict(contract) if contract else None,'pickup':dict(pickup) if pickup else None,'review':dict(review) if review else None}
            con.close(); return self.send_json(out)
        if path=='/api/breeder-applications':
            u=self.require();
            if not u:return
            con=db()
            if u['role']=='operator': rows=con.execute('SELECT a.*,u.email FROM breeder_applications a JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC').fetchall()
            else: rows=con.execute('SELECT a.*,u.email FROM breeder_applications a JOIN users u ON u.id=a.user_id WHERE a.user_id=? ORDER BY a.created_at DESC',(u['id'],)).fetchall()
            con.close(); out=[]
            for r in rows:
                d=dict(r); prof=str(d.get('profile') or '')
                has=bool(re.search(r'\[REGISTRATION_PROOF\]/uploads/[^\s]+',prof))
                d['profile']=re.sub(r'\n?\[REGISTRATION_PROOF\]/uploads/[^\s]+','',prof).strip()
                d['has_registration_proof']=has
                d['registration_proof_url']=('/api/operator/breeder-proof/'+str(d['id'])) if has else None
                out.append(d)
            return self.send_json(out)
        m=re.fullmatch(r'/api/operator/breeder-proof/([^/]+)',path)
        if m:
            u=self.require(['operator']);
            if not u:return
            con=db(); app=con.execute("SELECT id,user_id,profile FROM breeder_applications WHERE id=?",(m.group(1),)).fetchone()
            if not app:
                con.close(); return self.send_json({'error':'not_found'},404)
            mm=re.search(r'\[REGISTRATION_PROOF\](/uploads/[^\s]+)',str(app['profile'] or ''))
            if not mm:
                con.close(); return self.send_json({'error':'proof_not_found'},404)
            stored=Path(urlparse(mm.group(1)).path).name
            up=con.execute("SELECT stored_name,mime FROM uploads WHERE user_id=? AND stored_name=? AND puppy_id IS NULL",(app['user_id'],stored)).fetchone(); con.close()
            if not up or not str(up['mime'] or '').lower().startswith('image/'): return self.send_json({'error':'proof_not_found'},404)
            fp=UPLOADS/up['stored_name']
            if not fp.exists(): return self.send_json({'error':'proof_not_found'},404)
            data=fp.read_bytes(); self.send_response(200); self.send_header('Content-Type',up['mime']); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','private, no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(data); return
        if path=='/api/operator/listings':
            u=self.require(['operator']);
            if not u:return
            con=db(); rows=con.execute('SELECT * FROM puppies ORDER BY created_at DESC').fetchall(); con.close(); return self.send_json([puppy_json(r) for r in rows])
        if path=='/api/operator/support':
            u=self.require(['operator'])
            if not u:return
            con=db(); rows=con.execute("SELECT * FROM support_tickets ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END, created_at DESC").fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/operator/reports':
            u=self.require(['operator']);
            if not u:return
            con=db(); rows=con.execute('SELECT r.*,p.name puppy_name,b.kennel_name FROM reports r LEFT JOIN puppies p ON p.id=r.puppy_id LEFT JOIN breeders b ON b.id=r.breeder_id ORDER BY r.created_at DESC').fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/operator/audit':
            u=self.require(['operator']);
            if not u:return
            con=db(); rows=con.execute('SELECT a.*,u.email FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC LIMIT 300').fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/operator/automations':
            u=self.require(['operator'])
            if not u:return
            con=db(); sync_breeder_billing_suspension(con); con.commit()
            latest=con.execute('SELECT kind,MAX(created_at) last_at,COUNT(*) count FROM automation_events GROUP BY kind ORDER BY kind').fetchall()
            overdue=con.execute("SELECT COUNT(*) c FROM commission_invoices WHERE status='issued' AND due_at<?",(now(),)).fetchone()['c']
            suspended=con.execute('SELECT COUNT(*) c FROM breeders WHERE billing_suspended=1').fetchone()['c']
            pending_reports=con.execute("SELECT COUNT(*) c FROM deal_completion_reports WHERE status='pending'").fetchone()['c']
            last_backup=con.execute('SELECT filename,created_at FROM backup_runs ORDER BY created_at DESC LIMIT 1').fetchone()
            con.close(); return self.send_json({'intervalSeconds':AUTOMATION_INTERVAL_SECONDS,'autoBackupHours':AUTO_BACKUP_HOURS,'autoBackupKeep':AUTO_BACKUP_KEEP,'events':[dict(x) for x in latest],'overdueInvoices':overdue,'suspendedBreeders':suspended,'pendingCompletionReports':pending_reports,'lastBackup':dict(last_backup) if last_backup else None})
        if path=='/api/operator/backups':
            u=self.require(['operator']);
            if not u:return
            con=db(); rows=con.execute('SELECT * FROM backup_runs ORDER BY created_at DESC LIMIT 100').fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/notifications':
            u=self.require();
            if not u:return
            con=db(); rows=con.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC',(u['id'],)).fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/breeder/deal-reports':
            u=self.require(['breeder'])
            if not u:return
            con=db(); b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            if not b: con.close(); return self.send_json([])
            rows=con.execute('''SELECT r.*,d.inquiry_id,d.puppy_id,d.total_price,d.status deal_status,p.name puppy_name,p.breed,
                COALESCE(NULLIF(r.buyer_name,''),bu.display_name,bu.email) buyer_display,ci.invoice_no,ci.fee_amount,ci.status invoice_status
                FROM deal_completion_reports r JOIN deals d ON d.id=r.deal_id JOIN puppies p ON p.id=d.puppy_id
                LEFT JOIN users bu ON bu.id=d.buyer_id LEFT JOIN commission_invoices ci ON ci.deal_id=d.id
                WHERE r.breeder_id=? ORDER BY r.created_at DESC''',(b['id'],)).fetchall(); con.close(); return self.send_json([dict(x) for x in rows])
        if path=='/api/operator/deal-reports':
            u=self.require(['operator'])
            if not u:return
            con=db(); rows=con.execute('''SELECT r.*,d.inquiry_id,d.puppy_id,d.total_price,d.status deal_status,p.name puppy_name,p.breed,b.kennel_name,
                COALESCE(NULLIF(r.buyer_name,''),bu.display_name,bu.email) buyer_display,ci.invoice_no,ci.fee_amount,ci.status invoice_status
                FROM deal_completion_reports r JOIN deals d ON d.id=r.deal_id JOIN puppies p ON p.id=d.puppy_id
                JOIN breeders b ON b.id=r.breeder_id LEFT JOIN users bu ON bu.id=d.buyer_id LEFT JOIN commission_invoices ci ON ci.deal_id=d.id
                ORDER BY CASE r.status WHEN 'pending' THEN 0 WHEN 'rejected' THEN 1 ELSE 2 END,r.created_at DESC''').fetchall(); con.close(); return self.send_json([dict(x) for x in rows])
        if path=='/api/operator/stats':
            u=self.require(['operator']);
            if not u:return
            con=db(); sync_breeder_billing_suspension(con); con.commit(); out={
              'users':con.execute('SELECT COUNT(*) c FROM users').fetchone()['c'],
              'breeders':con.execute('SELECT COUNT(*) c FROM breeders').fetchone()['c'],
              'puppies':con.execute('SELECT COUNT(*) c FROM puppies').fetchone()['c'],
              'openPuppies':con.execute("SELECT COUNT(*) c FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.status='募集中' AND p.review_status='approved' AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)").fetchone()['c'],
              'inquiries':con.execute('SELECT COUNT(*) c FROM inquiries').fetchone()['c'],
              'unanswered':con.execute("SELECT COUNT(*) c FROM inquiries WHERE status='未返信'").fetchone()['c'],
              'pendingBreederApplications':con.execute("SELECT COUNT(*) c FROM breeder_applications WHERE status='pending'").fetchone()['c'],
              'pendingDealReports':con.execute("SELECT COUNT(*) c FROM deal_completion_reports WHERE status='pending'").fetchone()['c'],
              'openSupport':con.execute("SELECT COUNT(*) c FROM support_tickets WHERE status IN ('open','reviewing')").fetchone()['c']}
            con.close(); return self.send_json(out)
        if path=='/api/operator/deals':
            u=self.require(['operator'])
            if not u:return
            con=db(); rows=con.execute('''SELECT d.*,p.name puppy_name,p.breed,p.breeder_name,u.display_name buyer_name,u.email buyer_email,
                (SELECT status FROM payments py WHERE py.deal_id=d.id AND py.kind='reservation' ORDER BY py.created_at DESC LIMIT 1) reservation_status,
                (SELECT status FROM contracts c WHERE c.deal_id=d.id LIMIT 1) contract_status,
                (SELECT status FROM pickups pk WHERE pk.deal_id=d.id LIMIT 1) pickup_status
                FROM deals d JOIN puppies p ON p.id=d.puppy_id JOIN users u ON u.id=d.buyer_id ORDER BY d.created_at DESC''').fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/operator/revenue':
            u=self.require(['operator'])
            if not u:return
            con=db(); completed=con.execute("SELECT COUNT(*) c,COALESCE(SUM(total_price),0) gmv FROM deals WHERE status='completed'").fetchone(); reservations=con.execute("SELECT COUNT(*) c,COALESCE(SUM(amount),0) total FROM payments WHERE kind='reservation' AND status='paid'").fetchone(); all_deals=con.execute('SELECT COUNT(*) c FROM deals').fetchone()['c']; invoices=con.execute("SELECT COUNT(*) c,COALESCE(SUM(fee_amount),0) total,COALESCE(SUM(CASE WHEN status='paid' THEN fee_amount ELSE 0 END),0) paid,COALESCE(SUM(CASE WHEN status='issued' THEN fee_amount ELSE 0 END),0) outstanding,COALESCE(SUM(CASE WHEN status='issued' AND due_at<? THEN fee_amount ELSE 0 END),0) overdue,COALESCE(SUM(CASE WHEN status='issued' AND due_at<? THEN 1 ELSE 0 END),0) overdue_count FROM commission_invoices WHERE status!='void'",(now(),now())).fetchone(); con.close(); return self.send_json({'deals':all_deals,'completedDeals':completed['c'],'completedGmv':completed['gmv'],'paidReservations':reservations['c'],'reservationTotal':reservations['total'],'commissionRateBps':COMMISSION_RATE_BPS,'commissionDueDays':COMMISSION_DUE_DAYS,'commissionInvoices':invoices['c'],'commissionBilled':invoices['total'],'commissionPaid':invoices['paid'],'commissionOutstanding':invoices['outstanding'],'commissionOverdue':invoices['overdue'],'commissionOverdueCount':invoices['overdue_count']})
        if path=='/api/breeder/invoices':
            u=self.require(['breeder'])
            if not u:return
            con=db(); b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            if not b: con.close(); return self.send_json([])
            sync_breeder_billing_suspension(con,b['id']); con.commit()
            rows=con.execute('SELECT ci.*,d.status deal_status,p.name puppy_name,p.breed,b.kennel_name,b.billing_suspended FROM commission_invoices ci JOIN deals d ON d.id=ci.deal_id JOIN puppies p ON p.id=d.puppy_id JOIN breeders b ON b.id=ci.breeder_id WHERE ci.breeder_id=? ORDER BY ci.issued_at DESC',(b['id'],)).fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/breeder/billing-config':
            u=self.require(['breeder','operator'])
            if not u:return
            return self.send_json({
              'issuerName':BILLING_ISSUER_NAME,'postal':BILLING_POSTAL,'address':BILLING_ADDRESS,
              'invoiceRegistrationNo':BILLING_INVOICE_REG_NO,'bankName':BILLING_BANK_NAME,
              'bankBranch':BILLING_BANK_BRANCH,'bankAccountType':BILLING_BANK_ACCOUNT_TYPE,
              'bankAccountNo':BILLING_BANK_ACCOUNT_NO,'bankAccountHolder':BILLING_BANK_ACCOUNT_HOLDER,
              'commissionRateBps':COMMISSION_RATE_BPS,'commissionDueDays':COMMISSION_DUE_DAYS,'commissionTermsVersion':COMMISSION_TERMS_VERSION
            })
        if path=='/api/operator/invoices':
            u=self.require(['operator'])
            if not u:return
            con=db(); sync_breeder_billing_suspension(con); con.commit(); rows=con.execute('SELECT ci.*,b.kennel_name,b.billing_suspended,p.name puppy_name,p.breed FROM commission_invoices ci JOIN breeders b ON b.id=ci.breeder_id JOIN deals d ON d.id=ci.deal_id JOIN puppies p ON p.id=d.puppy_id ORDER BY ci.issued_at DESC').fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/': self.path='/index.html'
        return super().do_GET()

    def online_visit_email(self, inquiry_id, status, visit_date, visit_time):
        try:
            con=db(); row=con.execute("SELECT i.buyer_id,p.breeder_id FROM inquiries i JOIN puppies p ON p.id=i.puppy_id WHERE i.id=?",(inquiry_id,)).fetchone()
            if not row: con.close(); return False
            if status=='proposed':
                user=con.execute("SELECT u.email FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?",(row['breeder_id'],)).fetchone()
            else:
                user=con.execute("SELECT email FROM users WHERE id=?",(row['buyer_id'],)).fetchone()
            con.close()
            if not user or not user['email']: return False
            subject="【BIG PAW】オンライン見学のお申し込みが入りました" if status=='proposed' else "【BIG PAW】オンライン見学の日時が確定しました"
            lead="オンライン見学のお申し込みが入りました。\n希望日時：" if status=='proposed' else "オンライン見学の日時が確定しました。\n日時："
            body=f'''オンライン見学の日時が確定しました。

【確定日時】
{visit_date} {visit_time}

【当日の参加方法】
1. 開始時刻になりましたらBIG PAWへログインしてください。
2. 確定したオンライン見学画面を開き、「カメラを準備して入室」を押してください。
3. Jitsi Meetの画面が表示されたら、青い「Join in browser」を押してください。
4. カメラとマイクの使用を許可すると入室できます。
5. 相手がまだ入室していない場合は、そのままお待ちください。相手が同じルームへ入室すると映像と音声がつながります。

※購入希望者様・ブリーダー双方が同じ手順で入室します。
※同時に入室する必要はありません。先に入った方はそのままお待ちください。
※海外の電話番号へ電話をかける必要はありません。
※PINコードの入力は必要ありません。
※Jitsi Meetアプリのインストールは不要です。「Join in browser」からブラウザで参加できます。

BIG PAW
https://www.bigpaw.site/'''
            return send_mail(user['email'],subject,body)
        except Exception as e:
            print('[BIG PAW] online visit email failed:',e,flush=True); return False

    def do_POST(self):
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        path=urlparse(self.path).path
        m=re.fullmatch(r'/api/inquiries/([^/]+)/messages',path)
        if m:
            u=self.require();
            if not u:return
            body=self.json_body(); text=str(body.get('body','')).strip()
            if not text: return self.send_json({'error':'message_required'},400)
            if len(text)>2000: return self.send_json({'error':'message_too_long'},400)
            if u.get('role')!='operator' and public_profile_has_direct_contact(text): return self.send_json({'error':'direct_contact_not_allowed','message':'電話番号・メール・LINE・SNS・外部URLなどの直接連絡先は送信できません。BIGPAW内のメッセージをご利用ください。'},400)
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            mid=make_id('m_'); con.execute('INSERT INTO messages VALUES(?,?,?,?,?)',(mid,m.group(1),u['id'],text,now()))
            other=None
            if u['role']=='buyer' and qrow['breeder_id']:
                r=con.execute('SELECT user_id FROM breeders WHERE id=?',(qrow['breeder_id'],)).fetchone(); other=r['user_id'] if r else None
            elif u['role']=='breeder': other=qrow['buyer_id']
            other_email=None
            if other:
                con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),other,'message','新しいメッセージ',text[:100],0,now()))
                ou=con.execute('SELECT email FROM users WHERE id=?',(other,)).fetchone(); other_email=ou['email'] if ou else None
            con.commit(); r=con.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone(); con.close()
            if other_email: send_mail(other_email,'BIG PAW 新しいメッセージ',f'BIG PAWに新しいメッセージが届きました。\n\n{PUBLIC_BASE_URL}/messages.html?inquiry={m.group(1)}')
            return self.send_json(dict(r),201)
        m=re.fullmatch(r'/api/inquiries/([^/]+)/visit',path)
        if m:
            u=self.require();
            if not u:return
            body=self.json_body(); con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if body.get('status') == 'confirmed' and u.get('role') not in ('breeder','operator'):
                con.close(); return self.send_json({'error':'breeder_only_confirmation'},403)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            vid=make_id('v_'); existing=con.execute('SELECT id FROM visits WHERE inquiry_id=?',(m.group(1),)).fetchone()
            vals=(body.get('date',''),body.get('time',''),int(body.get('partySize') or 1),body.get('transport',''),body.get('status','confirmed'),1 if body.get('faceToFaceConfirmed') else 0,now())
            if existing:
                con.execute('UPDATE visits SET visit_date=?,visit_time=?,party_size=?,transport=?,status=?,face_to_face_confirmed=?,updated_at=? WHERE inquiry_id=?',vals+(m.group(1),)); vid=existing['id']
            else:
                con.execute('INSERT INTO visits VALUES(?,?,?,?,?,?,?,?,?)',(vid,m.group(1),*vals))
            con.execute("UPDATE inquiries SET status='見学確定' WHERE id=?",(m.group(1),))
            con.commit(); r=con.execute('SELECT * FROM visits WHERE id=?',(vid,)).fetchone(); con.close(); self.online_visit_email(m.group(1), body.get('status','proposed'), body.get('date',''), body.get('time','')); return self.send_json(dict(r),201)
        m=re.fullmatch(r'/api/inquiries/([^/]+)/deal',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            existing=con.execute('SELECT * FROM deals WHERE inquiry_id=?',(m.group(1),)).fetchone()
            if existing: out=dict(existing); con.close(); return self.send_json(out)
            p=con.execute('SELECT * FROM puppies WHERE id=?',(qrow['puppy_id'],)).fetchone(); did=make_id('d_')
            con.execute('INSERT INTO deals VALUES(?,?,?,?,?,?,?,?,?)',(did,m.group(1),qrow['puppy_id'],qrow['buyer_id'],qrow['breeder_id'],int(p['price']),100000,'contract_preparing',now()))
            con.commit(); r=con.execute('SELECT * FROM deals WHERE id=?',(did,)).fetchone(); con.close(); return self.send_json(dict(r),201)
        m=re.fullmatch(r'/api/deals/([^/]+)/reservation',path)
        if m:
            u=self.require(['buyer','operator']);
            if not u:return
            if IS_PRODUCTION and u['role']!='operator':
                return self.send_json({'error':'payment_confirmation_not_allowed','message':'本番環境では購入者自身で支払済みに変更できません。決済連携または運営確認が必要です。'},409)
            body=self.json_body(); con=db(); d=self.deal_for_user(con,m.group(1),u)
            if not d: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            amount=int(body.get('amount') or d['reservation_amount']); pid=make_id('pay_')
            con.execute('INSERT INTO payments VALUES(?,?,?,?,?,?,?)',(pid,d['id'],'reservation',amount,'paid',now(),now()))
            con.execute("UPDATE deals SET status='reservation_paid' WHERE id=?",(d['id'],)); con.commit(); r=con.execute('SELECT * FROM payments WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(dict(r),201)
        if path=='/api/payment-webhook/reservation':
            if not PAYMENT_WEBHOOK_SECRET or not hmac.compare_digest(self.headers.get('X-BigPaw-Payment-Secret',''), PAYMENT_WEBHOOK_SECRET):
                return self.send_json({'error':'forbidden'},403)
            body=self.json_body(); deal_id=str(body.get('dealId','')); amount=int(body.get('amount') or 0); provider_ref=str(body.get('providerRef',''))
            con=db(); d=con.execute('SELECT * FROM deals WHERE id=?',(deal_id,)).fetchone()
            if not d: con.close(); return self.send_json({'error':'deal_not_found'},404)
            if amount != int(d['reservation_amount']): con.close(); return self.send_json({'error':'amount_mismatch'},409)
            existing=con.execute("SELECT * FROM payments WHERE deal_id=? AND kind='reservation' AND status='paid' ORDER BY created_at DESC LIMIT 1",(deal_id,)).fetchone()
            if existing: out=dict(existing); con.close(); return self.send_json(out)
            pid=make_id('pay_'); con.execute('INSERT INTO payments VALUES(?,?,?,?,?,?,?)',(pid,deal_id,'reservation',amount,'paid',now(),now())); con.execute("UPDATE deals SET status='reservation_paid' WHERE id=?",(deal_id,)); audit(con,None,'payment_webhook_confirmed','deal',deal_id,provider_ref); con.commit(); r=con.execute('SELECT * FROM payments WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(dict(r),201)
        m=re.fullmatch(r'/api/deals/([^/]+)/contract-sign',path)
        if m:
            u=self.require(['buyer','breeder','operator']);
            if not u:return
            con=db(); d=self.deal_for_user(con,m.group(1),u)
            if not d: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            c=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone()
            cid=c['id'] if c else make_id('c_')
            if not c: con.execute('INSERT INTO contracts VALUES(?,?,?,?,?,?,?)',(cid,d['id'],'v1',None,None,'draft',now()))
            if u['role']=='buyer': con.execute('UPDATE contracts SET buyer_signed_at=?,updated_at=? WHERE deal_id=?',(now(),now(),d['id']))
            elif u['role'] in ('breeder','operator'): con.execute('UPDATE contracts SET breeder_signed_at=?,updated_at=? WHERE deal_id=?',(now(),now(),d['id']))
            c=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone()
            if c['buyer_signed_at'] and c['breeder_signed_at']:
                con.execute("UPDATE contracts SET status='signed',updated_at=? WHERE deal_id=?",(now(),d['id'])); con.execute("UPDATE deals SET status='contract_signed' WHERE id=?",(d['id'],))
            con.commit(); r=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone(); con.close(); return self.send_json(dict(r),201)
        m=re.fullmatch(r'/api/deals/([^/]+)/pickup',path)
        if m:
            u=self.require(['buyer','breeder','operator']);
            if not u:return
            body=self.json_body(); con=db(); d=self.deal_for_user(con,m.group(1),u)
            if not d: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            existing=con.execute('SELECT * FROM pickups WHERE deal_id=?',(d['id'],)).fetchone(); pid=existing['id'] if existing else make_id('pk_')
            date=body.get('date',existing['pickup_date'] if existing else ''); tm=body.get('time',existing['pickup_time'] if existing else '')
            status='completed' if body.get('complete') else body.get('status','scheduled')
            if status=='completed' and u['role']!='operator':
                con.close(); return self.send_json({'error':'completion_report_required','message':'お迎え完了はブリーダーの成約申請後、BIG PAW運営が確認して確定します。'},409)
            completed=now() if status=='completed' else None
            if existing: con.execute('UPDATE pickups SET pickup_date=?,pickup_time=?,status=?,completed_at=?,updated_at=? WHERE id=?',(date,tm,status,completed,now(),pid))
            else: con.execute('INSERT INTO pickups VALUES(?,?,?,?,?,?,?)',(pid,d['id'],date,tm,status,completed,now()))
            if status=='completed':
                con.execute("UPDATE deals SET status='completed' WHERE id=?",(d['id'],)); con.execute("UPDATE puppies SET status='成約済み' WHERE id=?",(d['puppy_id'],))
                completed_deal=con.execute('SELECT * FROM deals WHERE id=?',(d['id'],)).fetchone(); invoice=ensure_commission_invoice(con,completed_deal)
                if invoice:
                    breeder_user=con.execute('SELECT u.email FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?',(d['breeder_id'],)).fetchone()
                    if breeder_user:
                        due_txt=time.strftime('%Y年%m月%d日',time.localtime(invoice['due_at']))
                        send_mail(breeder_user['email'],'BIG PAW 成約手数料のご請求',f"成約おめでとうございます。\n\n成約手数料: {invoice['fee_amount']:,}円（生体価格の5%・税込）\n請求番号: {invoice['invoice_no']}\n支払期限: {due_txt}\n\nBIG PAWブリーダー管理画面から請求内容をご確認ください。")
            con.commit(); r=con.execute('SELECT * FROM pickups WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(dict(r),201)
        m=re.fullmatch(r'/api/deals/([^/]+)/review',path)
        if m:
            u=self.require(['buyer']);
            if not u:return
            body=self.json_body(); rating=int(body.get('rating') or 0); text=str(body.get('body','')).strip(); con=db(); d=self.deal_for_user(con,m.group(1),u)
            if not d: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            if d['status']!='completed': con.close(); return self.send_json({'error':'deal_not_completed'},409)
            if rating<1 or rating>5 or not text: con.close(); return self.send_json({'error':'invalid_review'},400)
            if con.execute('SELECT 1 FROM reviews WHERE deal_id=?',(d['id'],)).fetchone(): con.close(); return self.send_json({'error':'review_exists'},409)
            rid=make_id('r_'); con.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)',(rid,d['id'],u['id'],d['breeder_id'],rating,text,'published',now())); con.commit(); r=con.execute('SELECT * FROM reviews WHERE id=?',(rid,)).fetchone(); con.close(); return self.send_json(dict(r),201)
        if path=='/api/breeder-applications':
            u=self.require(['buyer']);
            if not u:return
            if not u.get('email_verified'): return self.send_json({'error':'email_verification_required'},409)
            body=self.json_body(); required=['kennelName','representative','prefecture','primaryBreed','registrationNo','expiresOn']; public_profile=str(body.get('profile','')).strip();
            if public_profile_has_direct_contact(public_profile): return self.send_json({'error':'direct_contact_not_allowed','message':'公開プロフィールには電話番号・メール・LINE・SNS・外部サイトURLを掲載できません。'},400)
            if not str(body.get('registrationProofUrl','')).strip(): return self.send_json({'error':'registration_proof_required','message':'第一種動物取扱業 登録証の写しが必要です。'},400)
            if any(not str(body.get(k,'')).strip() for k in required): return self.send_json({'error':'required_fields'},400)
            if not body.get('agreeCommissionTerms'):
                return self.send_json({'error':'commission_terms_consent_required','message':'成約手数料5%・請求日から7日以内の支払い条件への同意が必要です。'},400)
            con=db(); old=con.execute('SELECT * FROM breeder_applications WHERE user_id=?',(u['id'],)).fetchone()
            if old and old['status']=='approved': con.close(); return self.send_json({'error':'application_exists','status':old['status']},409)
            aid=old['id'] if old else make_id('ba_'); vals=(str(body['kennelName']).strip(),str(body['representative']).strip(),str(body['prefecture']).strip(),str(body['primaryBreed']).strip(),str(body['registrationNo']).strip(),str(body['expiresOn']).strip(),(str(body.get('profile','')).strip()+'\n[REGISTRATION_PROOF]'+str(body.get('registrationProofUrl','')).strip()),'pending','',now())
            if old:
                con.execute('UPDATE breeder_applications SET kennel_name=?,representative=?,prefecture=?,primary_breed=?,registration_no=?,expires_on=?,profile=?,status=?,review_note=?,updated_at=? WHERE id=?',vals+(aid,))
            else:
                con.execute('INSERT INTO breeder_applications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,u['id'],*vals[:-1],now(),vals[-1]))
            if not con.execute('SELECT 1 FROM breeder_fee_acceptances WHERE user_id=? AND version=?',(u['id'],COMMISSION_TERMS_VERSION)).fetchone():
                con.execute('INSERT INTO breeder_fee_acceptances VALUES(?,?,?,?,?,?)',(make_id('bfa_'),u['id'],COMMISSION_TERMS_VERSION,COMMISSION_RATE_BPS,COMMISSION_DUE_DAYS,now()))
                audit(con,u['id'],'commission_terms_accepted','user',u['id'],f'{COMMISSION_TERMS_VERSION}:{COMMISSION_RATE_BPS}:{COMMISSION_DUE_DAYS}')
            con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(aid,)).fetchone()
            applicant_email=u['email']
            con.close()
            return self.send_json(dict(r),201)
        m=re.fullmatch(r'/api/deals/([^/]+)/completion-report',path)
        if m:
            u=self.require(['breeder'])
            if not u:return
            body=self.json_body(); con=db(); d=self.deal_for_user(con,m.group(1),u)
            if not d: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            if d['status']=='completed': con.close(); return self.send_json({'error':'deal_already_completed'},409)
            b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            if not b or d['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            amount=int(body.get('finalSaleAmount') or 0); pickup_date=str(body.get('pickupDate','')).strip(); buyer_name=str(body.get('buyerName','')).strip(); note=str(body.get('note','')).strip()
            if amount<=0 or not pickup_date: con.close(); return self.send_json({'error':'final_price_and_pickup_date_required'},400)
            existing=con.execute('SELECT * FROM deal_completion_reports WHERE deal_id=?',(d['id'],)).fetchone(); t=now()
            if existing and existing['status']=='approved': con.close(); return self.send_json({'error':'report_already_approved'},409)
            if existing:
                con.execute('''UPDATE deal_completion_reports SET final_sale_amount=?,pickup_date=?,buyer_name=?,note=?,status='pending',reviewed_by_user_id=NULL,review_note='',updated_at=? WHERE id=?''',(amount,pickup_date,buyer_name,note,t,existing['id'])); rid=existing['id']
            else:
                rid=make_id('cr_'); con.execute('''INSERT INTO deal_completion_reports(id,deal_id,breeder_id,reported_by_user_id,final_sale_amount,pickup_date,buyer_name,note,status,reviewed_by_user_id,review_note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(rid,d['id'],b['id'],u['id'],amount,pickup_date,buyer_name,note,'pending',None,'',t,t))
            con.execute("UPDATE deals SET status='completion_reported' WHERE id=?",(d['id'],)); con.execute("UPDATE inquiries SET status='成約申請中' WHERE id=?",(d['inquiry_id'],)); audit(con,u['id'],'deal_completion_reported','deal',d['id'],f'{amount}:{pickup_date}')
            ops=con.execute("SELECT id,email FROM users WHERE role='operator'").fetchall()
            puppy=con.execute('SELECT name FROM puppies WHERE id=?',(d['puppy_id'],)).fetchone()
            title='ブリーダーから成約申請が届きました'; detail=f"{puppy['name'] if puppy else '子犬'} / {amount:,}円 / お迎え {pickup_date}"
            for op in ops:
                con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),op['id'],'deal_report',title,detail,0,t))
            con.commit(); out=con.execute('SELECT * FROM deal_completion_reports WHERE id=?',(rid,)).fetchone(); con.close()
            for op in ops:
                send_mail(op['email'],'BIG PAW 成約申請が届きました',f"{detail}\n\n運営管理の「成約申請」から確認してください。\n{PUBLIC_BASE_URL}/operator-deal-reports.html")
            return self.send_json(dict(out),201)
        if path=='/api/password-reset/request':
            body=self.json_body(); email=str(body.get('email','')).strip().lower()
            if rate_limited('reset:'+self.client_address[0],5,300): return self.send_json({'error':'rate_limited'},429)
            con=db(); u=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); token=None
            if u:
                token=secrets.token_urlsafe(32); con.execute('DELETE FROM password_reset_tokens WHERE user_id=?',(u['id'],)); con.execute('INSERT INTO password_reset_tokens VALUES(?,?,?,?,?)',(token,u['id'],now(),now()+1800,None)); audit(con,u['id'],'password_reset_requested','user',u['id'])
            con.commit(); con.close(); out={'ok':True}
            if token and u:
                link=f"{PUBLIC_BASE_URL}/reset-password.html?token={token}"
                sent=send_mail(u['email'],'BIG PAW パスワード再設定',f"BIG PAWのパスワード再設定はこちらから行ってください。\n\n{link}\n\nこのリンクは30分で期限切れになります。")
                if DEV_LINKS: out['devToken']=token
                if IS_PRODUCTION and not sent: print('[BIG PAW] password reset mail not sent: SMTP not configured or failed')
            return self.send_json(out)
        if path=='/api/password-reset/confirm':
            body=self.json_body(); token=str(body.get('token','')); pw=str(body.get('password',''))
            if len(pw)<8: return self.send_json({'error':'password_too_short'},400)
            con=db(); r=con.execute('SELECT * FROM password_reset_tokens WHERE token=? AND used_at IS NULL AND expires_at>?',(token,now())).fetchone()
            if not r: con.close(); return self.send_json({'error':'invalid_or_expired_token'},400)
            salt,digest=hash_password(pw); con.execute('UPDATE users SET salt=?,password_hash=?,updated_at=? WHERE id=?',(salt,digest,now(),r['user_id'])); con.execute('UPDATE password_reset_tokens SET used_at=? WHERE token=?',(now(),token)); con.execute('DELETE FROM sessions WHERE user_id=?',(r['user_id'],)); audit(con,r['user_id'],'password_reset_completed','user',r['user_id']); con.commit(); con.close(); return self.send_json({'ok':True})
        if path=='/api/email-verification/request':
            u=self.require();
            if not u:return
            con=db(); token=secrets.token_urlsafe(32); con.execute('DELETE FROM email_verification_tokens WHERE user_id=?',(u['id'],)); con.execute('INSERT INTO email_verification_tokens VALUES(?,?,?,?,?)',(token,u['id'],now(),now()+86400,None)); audit(con,u['id'],'email_verification_requested','user',u['id']); con.commit(); con.close(); out={'ok':True}
            link=f"{PUBLIC_BASE_URL}/verify-email.html?token={token}"
            sent=send_mail(u['email'],'BIG PAW メールアドレス確認',f"BIG PAWのメールアドレス確認はこちらから行ってください。\n\n{link}\n\nこのリンクは24時間で期限切れになります。")
            if DEV_LINKS: out['devToken']=token
            if IS_PRODUCTION and not sent:
                print('[BIG PAW] verification mail not sent: SMTP not configured or failed')
                return self.send_json({'error':'email_send_failed','message':'認証メールを送信できませんでした。しばらくしてから再度お試しください。'},502)
            return self.send_json(out)
        if path=='/api/email-verification/confirm':
            body=self.json_body(); token=str(body.get('token','')); con=db(); r=con.execute('SELECT * FROM email_verification_tokens WHERE token=? AND used_at IS NULL AND expires_at>?',(token,now())).fetchone()
            if not r: con.close(); return self.send_json({'error':'invalid_or_expired_token'},400)
            con.execute('UPDATE users SET email_verified=1,updated_at=? WHERE id=?',(now(),r['user_id'])); con.execute('UPDATE email_verification_tokens SET used_at=? WHERE token=?',(now(),token)); audit(con,r['user_id'],'email_verified','user',r['user_id']); con.commit(); con.close(); return self.send_json({'ok':True})
        if path=='/api/support':
            body=self.json_body(); name=str(body.get('name','')).strip(); email=str(body.get('email','')).strip().lower(); category=str(body.get('category','その他')).strip(); subject=str(body.get('subject','')).strip(); message=str(body.get('message','')).strip()
            if rate_limited('support:'+self.client_address[0],5,3600): return self.send_json({'error':'rate_limited','message':'送信回数が多いため、時間をおいてお試しください。'},429)
            if not name or not email or '@' not in email or not subject or not message: return self.send_json({'error':'required_fields'},400)
            if len(name)>100 or len(email)>254 or len(subject)>200 or len(message)>5000: return self.send_json({'error':'too_long'},400)
            u=self.current_user(); con=db(); tid=make_id('sup_'); t=now(); con.execute('INSERT INTO support_tickets VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,u['id'] if u else None,name,email,category,subject,message,'open','',t,t)); audit(con,u['id'] if u else None,'support_ticket_created','support_ticket',tid,category)
            ops=con.execute("SELECT id,email FROM users WHERE role='operator'").fetchall()
            for op in ops: con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),op['id'],'support','運営への問い合わせが届きました',f'{category} / {subject}',0,t))
            con.commit(); con.close()
            for op in ops: send_mail(op['email'],'BIG PAW 運営問い合わせ',f"受付番号: {tid}\nカテゴリ: {category}\n件名: {subject}\n送信者: {name} <{email}>\n\n{message}\n\n{PUBLIC_BASE_URL}/operator-support.html")
            return self.send_json({'id':tid,'status':'open'},201)
        if path=='/api/reports':
            u=self.require();
            if not u:return
            body=self.json_body(); reason=str(body.get('reason','')).strip(); detail=str(body.get('detail','')).strip(); puppy_id=body.get('puppyId') or None; breeder_id=body.get('breederId') or None
            if not reason: return self.send_json({'error':'reason_required'},400)
            con=db(); rid=make_id('rep_'); con.execute('INSERT INTO reports VALUES(?,?,?,?,?,?,?,?,?)',(rid,u['id'],puppy_id,breeder_id,reason,detail,'open',now(),now())); audit(con,u['id'],'report_created','report',rid,reason); con.commit(); con.close(); return self.send_json({'id':rid,'status':'open'},201)
        if path=='/api/operator/run-automations':
            u=self.require(['operator'])
            if not u:return
            result=run_automations_once()
            con=db(); audit(con,u['id'],'automations_run_manually','system','',json.dumps(result,ensure_ascii=False)); con.commit(); con.close()
            return self.send_json({'ok':True,**result})
        if path=='/api/operator/backup':
            u=self.require(['operator']);
            if not u:return
            con=db(); con.commit(); bid=make_id('bk_'); filename=f'bigpaw-{time.strftime("%Y%m%d-%H%M%S")}.sqlite3'; dest=BACKUPS/filename; shutil.copy2(DB,dest); con.execute('INSERT INTO backup_runs VALUES(?,?,?,?)',(bid,filename,u['id'],now())); audit(con,u['id'],'backup_created','backup',bid,filename); con.commit(); con.close(); return self.send_json({'id':bid,'filename':filename,'size':dest.stat().st_size},201)
        if path=='/api/operator/restore-backup':
            u=self.require(['operator']);
            if not u:return
            body=self.json_body(); filename=Path(str(body.get('filename',''))).name; confirmation=str(body.get('confirmation',''))
            if confirmation!='RESTORE BIG PAW': return self.send_json({'error':'confirmation_required'},400)
            src=BACKUPS/filename
            if not src.exists() or src.suffix!='.sqlite3': return self.send_json({'error':'backup_not_found'},404)
            safety=BACKUPS/f'pre-restore-{time.strftime("%Y%m%d-%H%M%S")}.sqlite3'
            if DB.exists(): shutil.copy2(DB,safety)
            tmp=DB.with_suffix('.restore.tmp'); shutil.copy2(src,tmp)
            test=sqlite3.connect(tmp); ok=test.execute('PRAGMA integrity_check').fetchone()[0]; test.close()
            if ok!='ok': tmp.unlink(missing_ok=True); return self.send_json({'error':'backup_integrity_failed'},409)
            os.replace(tmp,DB); con=db(); audit(con,u['id'],'backup_restored','backup','',filename); con.commit(); con.close(); return self.send_json({'ok':True,'restored':filename,'safetyBackup':safety.name})
        if path=='/api/register':
            body=self.json_body(); email=str(body.get('email','')).strip().lower(); pw=str(body.get('password',''))
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$',email) or len(pw)<8:
                return self.send_json({'error':'invalid_input','message':'メール形式と8文字以上のパスワードを確認してください'},400)
            con=db()
            if con.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(): con.close(); return self.send_json({'error':'email_exists'},409)
            if not body.get('agreeTerms') or not body.get('agreePrivacy'):
                con.close(); return self.send_json({'error':'consent_required'},400)
            salt,digest=hash_password(pw); uid=make_id('u_'); t=now()
            con.execute('INSERT INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at,email_verified,terms_accepted_at,privacy_accepted_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid,'buyer',email,body.get('last',''),body.get('first',''),(body.get('last','')+' '+body.get('first','')).strip(),salt,digest,t,0,t,t,t))
            token=secrets.token_urlsafe(32); con.execute('INSERT INTO email_verification_tokens VALUES(?,?,?,?,?)',(token,uid,t,t+86400,None)); audit(con,uid,'user_registered','user',uid); con.commit(); con.close()
            link=f"{PUBLIC_BASE_URL}/verify-email.html?token={token}"; sent=send_mail(email,'BIG PAW メールアドレス確認',f"BIG PAWへようこそ。メールアドレス確認はこちらから行ってください。\n\n{link}\n\nこのリンクは24時間で期限切れになります。")
            out={'id':uid,'email':email,'verificationMailSent':sent}
            if DEV_LINKS: out['devToken']=token
            return self.send_json(out,201)
        if path=='/api/login':
            body=self.json_body(); email=str(body.get('email','')).strip().lower(); pw=str(body.get('password',''))
            if rate_limited('login:'+self.client_address[0],20,300): return self.send_json({'error':'rate_limited'},429)
            con=db(); u=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            if not u or not verify_password(pw,u['salt'],u['password_hash']): con.close(); return self.send_json({'error':'invalid_credentials'},401)
            token=secrets.token_urlsafe(32); con.execute('DELETE FROM sessions WHERE expires_at<=?',(now(),)); con.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token,u['id'],now(),now()+60*60*24*14)); audit(con,u['id'],'login','user',u['id']); con.commit(); con.close()
            print('LOGIN_RESULT_DIAG|role='+str(u['role'])+'|admin_match='+str(str(email).strip().lower()==str(os.environ.get('BIGPAW_ADMIN_EMAIL','')).strip().lower()).lower(),flush=True)
            payload={'user':{'id':u['id'],'email':u['email'],'role':u['role'],'last':u['last'],'first':u['first'],'emailVerified':bool(u['email_verified'])}}
            if not IS_PRODUCTION: payload['token']=token
            return self.send_json(payload,200,{'Set-Cookie':session_cookie_header(token)})
        if path=='/api/logout':
            token=self.session_token()
            if token:
                con=db(); con.execute('DELETE FROM sessions WHERE token=?',(token,)); con.commit(); con.close()
            return self.send_json({'ok':True},200,{'Set-Cookie':session_cookie_header('',clear=True)})
        if path=='/api/puppies':
            u=self.require(['buyer','breeder','operator']);
            if not u:return
            body=self.json_body(); con=db(); breeder_id=None; breeder_name=body.get('breeder','')
            area=body.get('area','埼玉県'); area_key=body.get('areaKey') or AREA_KEYS.get(area,'other')
            if u['role']=='breeder':
                b=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); breeder_id=b['id'] if b else None; breeder_name=b['kennel_name'] if b else breeder_name
                if b: area=b['prefecture']; area_key=AREA_KEYS.get(area,'other')
            pid=make_id('p_'); breed=body.get('breed','その他大型犬'); gender=body.get('gender','男の子')
            vals=(pid,breeder_id,body.get('name') or f"{body.get('color','')}の{gender}",breed,body.get('breedKey') or BREED_KEYS.get(breed,'other'),gender,'female' if gender=='女の子' else 'male',body.get('color',''),int(body.get('price') or 0),body.get('status','募集中'),area,area_key,breeder_name,float(body.get('weight') or 0),float(body.get('adultMin') or 0),float(body.get('adultMax') or 0),1 if body.get('health') else 0,body.get('birth',''),body.get('desc',''),body.get('father',''),body.get('mother',''),body.get('imageUrl',''),now())
            review_status='approved' if u['role']=='operator' else 'pending'
            con.execute('''INSERT INTO puppies(id,breeder_id,name,breed,breed_key,gender,gender_key,color,price,status,area,area_key,breeder_name,weight,adult_min,adult_max,health,birth,description,father,mother,image_url,created_at,review_status,moderation_note,published_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',vals+(review_status,'',now() if review_status=='approved' else None))
            audit(con,u['id'],'puppy_created','puppy',pid,review_status); con.commit(); r=con.execute('SELECT * FROM puppies WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(puppy_json(r),201)
        if path=='/api/parent-dogs':
            u=self.require(['breeder','operator']);
            if not u:return
            body=self.json_body(); con=db(); breeder_id=body.get('breederId')
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); breeder_id=b['id'] if b else None
            if not breeder_id: con.close(); return self.send_json({'error':'breeder_required'},400)
            pid=make_id('pd_'); con.execute('INSERT INTO parent_dogs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (pid,breeder_id,body.get('name',''),body.get('sex','父犬'),body.get('breed',''),body.get('color',''),body.get('heightCm') or None,body.get('weightKg') or None,body.get('genetics',''),body.get('healthSummary',''),body.get('notes',''),body.get('imageUrl',''),now()))
            con.commit(); r=con.execute('SELECT * FROM parent_dogs WHERE id=?',(pid,)).fetchone(); con.close(); return self.send_json(dict(r),201)
        if path=='/api/health-records':
            u=self.require(['breeder','operator']);
            if not u:return
            body=self.json_body(); puppy_id=body.get('puppyId') or None; parent_id=body.get('parentDogId') or None
            if not puppy_id and not parent_id: return self.send_json({'error':'target_required'},400)
            con=db()
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); bid=b['id'] if b else '__none__'
                owned=False
                if puppy_id: owned=bool(con.execute('SELECT 1 FROM puppies WHERE id=? AND breeder_id=?',(puppy_id,bid)).fetchone())
                if parent_id: owned=owned or bool(con.execute('SELECT 1 FROM parent_dogs WHERE id=? AND breeder_id=?',(parent_id,bid)).fetchone())
                if not owned: con.close(); return self.send_json({'error':'forbidden'},403)
            rid=make_id('hr_'); con.execute('INSERT INTO health_records VALUES(?,?,?,?,?,?,?,?,?)',
                (rid,puppy_id,parent_id,body.get('category','その他'),body.get('itemName',''),body.get('result',''),body.get('testedOn',''),body.get('documentUrl',''),now()))
            con.commit(); r=con.execute('SELECT * FROM health_records WHERE id=?',(rid,)).fetchone(); con.close(); return self.send_json(dict(r),201)
        if path=='/api/inquiries':
            u=self.require(['buyer']);
            if not u:return
            body=self.json_body(); puppy_id=str(body.get('puppyId','')); inquiry_message=str(body.get('message','')).strip()
            if public_profile_has_direct_contact(inquiry_message): return self.send_json({'error':'direct_contact_not_allowed','message':'問い合わせ本文に電話番号・メール・LINE・SNS・外部URLなどの直接連絡先は記載できません。'},400)
            con=db(); p=con.execute("SELECT * FROM puppies WHERE id=? AND review_status='approved' AND status!='成約済み'",(puppy_id,)).fetchone()
            if not p: con.close(); return self.send_json({'error':'puppy_not_found'},404)
            if p['breeder_id']:
                sync_breeder_billing_suspension(con,p['breeder_id']); con.commit()
                brs=con.execute('SELECT billing_suspended FROM breeders WHERE id=?',(p['breeder_id'],)).fetchone()
                if brs and brs['billing_suspended']:
                    con.close(); return self.send_json({'error':'listing_suspended','message':'このブリーダーの掲載は現在停止中です。'},409)
            qid=make_id('q_'); con.execute('''INSERT INTO inquiries(id,puppy_id,buyer_id,breeder_id,name,email,phone,preferred_date,message,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (qid,puppy_id,u['id'],p['breeder_id'],body.get('name',(u['last']+' '+u['first']).strip()),body.get('email',u['email']),body.get('phone',''),body.get('preferredDate',''),body.get('message',''),'未返信',now()))
            breeder_email=None
            if p['breeder_id']:
                br=con.execute('SELECT user_id FROM breeders WHERE id=?',(p['breeder_id'],)).fetchone()
                if br:
                    con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),br['user_id'],'inquiry','新しい問い合わせ',f"{p['name']}に問い合わせが届きました",0,now()))
                    bu=con.execute('SELECT email FROM users WHERE id=?',(br['user_id'],)).fetchone(); breeder_email=bu['email'] if bu else None
            con.commit(); con.close()
            if breeder_email: send_mail(breeder_email,'BIG PAW 新しい問い合わせ',f"{p['name']}に新しい問い合わせが届きました。\n\n{PUBLIC_BASE_URL}/breeder-inquiries.html")
            return self.send_json({'id':qid,'status':'未返信'},201)
        m=re.fullmatch(r'/api/favorites/([^/]+)',path)
        if m:
            u=self.require(['buyer']);
            if not u:return
            pid=m.group(1); con=db(); found=con.execute('SELECT 1 FROM favorites WHERE user_id=? AND puppy_id=?',(u['id'],pid)).fetchone()
            if found: con.execute('DELETE FROM favorites WHERE user_id=? AND puppy_id=?',(u['id'],pid)); value=False
            else:
                if not con.execute("SELECT 1 FROM puppies WHERE id=? AND review_status='approved'",(pid,)).fetchone(): con.close(); return self.send_json({'error':'not_found'},404)
                con.execute('INSERT INTO favorites VALUES(?,?,?)',(u['id'],pid,now())); value=True
            con.commit(); con.close(); return self.send_json({'favorite':value})
        if path=='/api/uploads':
            u=self.require(['buyer','breeder','operator']);
            if not u:return
            _uc=db(); _ur=_uc.execute('SELECT role FROM users WHERE id=?',(u['id'],)).fetchone(); _uc.close()
            if _ur and _ur['role'] in ('breeder','operator'): u=dict(u); u['role']=_ur['role']
            print('UPLOAD_AUTH_STATE|effective_role='+str(u.get('role'))+'|persisted_role='+str(_ur['role'] if _ur else None),flush=True)
            ctype=self.headers.get('Content-Type','')
            if 'multipart/form-data' not in ctype: return self.send_json({'error':'multipart_required'},400)
            n=int(self.headers.get('Content-Length','0'))
            if n > MAX_UPLOAD_BYTES + 1024*1024: return self.send_json({'error':'file_too_large'},413)
            body=self.rfile.read(n)
            msg=BytesParser(policy=email_policy).parsebytes(
                b'Content-Type: '+ctype.encode('utf-8')+b'\r\nMIME-Version: 1.0\r\n\r\n'+body
            )
            file_part=None; puppy_id=None
            for part in msg.iter_parts():
                name=part.get_param('name',header='content-disposition')
                if name=='file': file_part=part
                elif name=='puppyId': puppy_id=(part.get_content() or '').strip()
            if file_part is None: return self.send_json({'error':'file_required'},400)
            if u['role']=='buyer' and puppy_id!='breeder-proof':
                _c=db(); _fresh=_c.execute('SELECT role FROM users WHERE id=?',(u['id'],)).fetchone(); _c.close()
                if not _fresh or _fresh['role'] not in ('breeder','operator'): return self.send_json({'error':'forbidden'},403)
            raw=file_part.get_payload(decode=True) or b''
            if len(raw)>MAX_UPLOAD_BYTES: return self.send_json({'error':'file_too_large'},413)
            mime=file_part.get_content_type() or 'application/octet-stream'
            if mime not in ('image/jpeg','image/png','image/webp'): return self.send_json({'error':'unsupported_type'},415)
            if not valid_image_bytes(raw,mime): return self.send_json({'error':'invalid_image_content'},415)
            if puppy_id and u['role']=='breeder':
                con=db(); b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); bid=b['id'] if b else '__none__'; owned=con.execute('SELECT 1 FROM puppies WHERE id=? AND breeder_id=?',(puppy_id,bid)).fetchone(); con.close()
                if not owned: return self.send_json({'error':'forbidden'},403)
            ext={ 'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[mime]
            stored=secrets.token_hex(16)+ext; (UPLOADS/stored).write_bytes(raw); con=db(); upid=make_id('up_')
            original=file_part.get_filename() or ''
            con.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)',(upid,u['id'],(None if puppy_id=='breeder-proof' else puppy_id or None),original,stored,mime,now())); con.commit(); con.close()
            return self.send_json({'id':upid,'url':'/uploads/'+stored},201)
        return self.send_json({'error':'not_found'},404)

    def do_DELETE(self):
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        path=urlparse(self.path).path
        m=re.fullmatch(r'/api/puppies/([^/]+)',path)
        if m:
            u=self.require(['breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            # Do not hard-delete a puppy already referenced by a transaction.
            if con.execute('SELECT 1 FROM inquiries WHERE puppy_id=? LIMIT 1',(puppy['id'],)).fetchone() or con.execute('SELECT 1 FROM deals WHERE puppy_id=? LIMIT 1',(puppy['id'],)).fetchone():
                con.close(); return self.send_json({'error':'puppy_has_transactions','message':'問い合わせ・取引履歴があるため削除できません。非公開に変更してください。'},409)
            uploads=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=?',(puppy['id'],)).fetchall()
            con.execute('DELETE FROM uploads WHERE puppy_id=?',(puppy['id'],))
            con.execute('DELETE FROM favorites WHERE puppy_id=?',(puppy['id'],))
            con.execute('DELETE FROM puppies WHERE id=?',(puppy['id'],))
            audit(con,u['id'],'puppy_deleted','puppy',puppy['id'])
            con.commit(); con.close()
            for row in uploads:
                try:(UPLOADS / row['stored_name']).unlink(missing_ok=True)
                except Exception:pass
            return self.send_json({'ok':True})
        m=re.fullmatch(r'/api/puppies/([^/]+)/photos/([^/]+)',path)
        if m:
            u=self.require(['breeder','operator'])
            if not u:return
            con=db(); puppy=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not puppy: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or puppy['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            up=con.execute('SELECT * FROM uploads WHERE id=? AND puppy_id=?',(m.group(2),puppy['id'])).fetchone()
            if not up: con.close(); return self.send_json({'error':'not_found'},404)
            was_main=puppy['image_url']==('/uploads/'+up['stored_name'])
            con.execute('DELETE FROM uploads WHERE id=?',(up['id'],))
            if was_main:
                nxt=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=? ORDER BY created_at,id LIMIT 1',(puppy['id'],)).fetchone()
                con.execute('UPDATE puppies SET image_url=? WHERE id=?',(('/uploads/'+nxt['stored_name']) if nxt else '',puppy['id']))
            con.commit(); con.close()
            try:(UPLOADS/up['stored_name']).unlink(missing_ok=True)
            except Exception:pass
            return self.send_json({'ok':True})
        if path=='/api/me':
            u=self.require()
            if not u:return
            if u['role']=='operator': return self.send_json({'error':'operator_account_cannot_self_delete'},409)
            con=db()
            # Retain transaction records that must remain referentially intact; anonymize the account instead of hard deleting when referenced.
            has_refs=bool(con.execute('SELECT 1 FROM inquiries WHERE buyer_id=? LIMIT 1',(u['id'],)).fetchone()) or bool(con.execute('SELECT 1 FROM breeder_applications WHERE user_id=? LIMIT 1',(u['id'],)).fetchone())
            if has_refs:
                anon=f"deleted-{secrets.token_hex(8)}@invalid.local"; con.execute("UPDATE users SET email=?,last='',first='',display_name='退会済みユーザー',salt=?,password_hash=?,updated_at=? WHERE id=?",(anon,*hash_password(secrets.token_urlsafe(32)),now(),u['id']))
                con.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],)); audit(con,u['id'],'account_anonymized','user',u['id'])
            else:
                con.execute('DELETE FROM users WHERE id=?',(u['id'],))
            con.commit(); con.close(); return self.send_json({'ok':True})
        return self.send_json({'error':'not_found'},404)

    def do_PATCH(self):
        path=urlparse(self.path).path
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        if path=='/api/me':
            u=self.require();
            if not u:return
            body=self.json_body(); last=str(body.get('last',u['last'])).strip(); first=str(body.get('first',u['first'])).strip(); display=str(body.get('displayName',(last+' '+first).strip())).strip(); con=db(); con.execute('UPDATE users SET last=?,first=?,display_name=?,updated_at=? WHERE id=?',(last,first,display,now(),u['id'])); audit(con,u['id'],'profile_updated','user',u['id']); con.commit(); out=con.execute('SELECT * FROM users WHERE id=?',(u['id'],)).fetchone(); con.close(); return self.send_json({'id':out['id'],'role':out['role'],'email':out['email'],'last':out['last'],'first':out['first'],'displayName':out['display_name'],'emailVerified':bool(out['email_verified'])})
        if path=='/api/breeder-profile':
            u=self.require(['breeder','operator']);
            if not u:return
            body=self.json_body();
            if 'profile' in body and public_profile_has_direct_contact(body.get('profile','')): return self.send_json({'error':'direct_contact_not_allowed','message':'公開プロフィールには電話番号・メール・LINE・SNS・外部サイトURLを掲載できません。'},400)
            con=db(); b=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone() if u['role']=='breeder' else con.execute('SELECT * FROM breeders WHERE id=?',(body.get('id',''),)).fetchone()
            if not b: con.close(); return self.send_json({'error':'not_found'},404)
            kennel=str(body.get('kennelName',b['kennel_name'])).strip(); prefecture=str(body.get('prefecture',b['prefecture'])).strip(); profile=str(body.get('profile',b['profile'])).strip(); reg=str(body.get('registrationNo',b['registration_no'])).strip(); con.execute('UPDATE breeders SET kennel_name=?,prefecture=?,profile=?,registration_no=? WHERE id=?',(kennel,prefecture,profile,reg,b['id'])); con.execute('UPDATE puppies SET breeder_name=?,area=?,area_key=? WHERE breeder_id=?',(kennel,prefecture,AREA_KEYS.get(prefecture,'other'),b['id'])); audit(con,u['id'],'breeder_profile_updated','breeder',b['id']); con.commit(); out=con.execute('SELECT * FROM breeders WHERE id=?',(b['id'],)).fetchone(); con.close(); return self.send_json(dict(out))
        mlist=re.fullmatch(r'/api/operator/listings/([^/]+)',path)
        if mlist:
            u=self.require(['operator']);
            if not u:return
            body=self.json_body(); status=str(body.get('reviewStatus','')); note=str(body.get('moderationNote',''))
            if status not in ('pending','approved','rejected'): return self.send_json({'error':'invalid_review_status'},400)
            con=db(); p=con.execute('SELECT * FROM puppies WHERE id=?',(mlist.group(1),)).fetchone()
            if not p: con.close(); return self.send_json({'error':'not_found'},404)
            con.execute('UPDATE puppies SET review_status=?,moderation_note=?,published_at=? WHERE id=?',(status,note,now() if status=='approved' else None,p['id'])); audit(con,u['id'],'listing_reviewed','puppy',p['id'],status+':'+note); con.commit(); out=con.execute('SELECT * FROM puppies WHERE id=?',(p['id'],)).fetchone(); con.close(); return self.send_json(puppy_json(out))
        msupport=re.fullmatch(r'/api/operator/support/([^/]+)',path)
        if msupport:
            u=self.require(['operator'])
            if not u:return
            body=self.json_body(); status=str(body.get('status','')).strip(); note=str(body.get('operatorNote','')).strip()
            if status not in ('open','reviewing','resolved','closed'): return self.send_json({'error':'invalid_status'},400)
            con=db(); row=con.execute('SELECT * FROM support_tickets WHERE id=?',(msupport.group(1),)).fetchone()
            if not row: con.close(); return self.send_json({'error':'not_found'},404)
            con.execute('UPDATE support_tickets SET status=?,operator_note=?,updated_at=? WHERE id=?',(status,note,now(),row['id'])); audit(con,u['id'],'support_ticket_updated','support_ticket',row['id'],status); con.commit(); out=con.execute('SELECT * FROM support_tickets WHERE id=?',(row['id'],)).fetchone(); con.close(); return self.send_json(dict(out))
        mrep=re.fullmatch(r'/api/operator/reports/([^/]+)',path)
        if mrep:
            u=self.require(['operator']);
            if not u:return
            body=self.json_body(); status=str(body.get('status',''))
            if status not in ('open','reviewing','resolved','dismissed'): return self.send_json({'error':'invalid_status'},400)
            con=db(); con.execute('UPDATE reports SET status=?,updated_at=? WHERE id=?',(status,now(),mrep.group(1))); audit(con,u['id'],'report_updated','report',mrep.group(1),status); con.commit(); out=con.execute('SELECT * FROM reports WHERE id=?',(mrep.group(1),)).fetchone(); con.close(); return self.send_json(dict(out) if out else {'error':'not_found'},200 if out else 404)
        minv=re.fullmatch(r'/api/operator/invoices/([^/]+)',path)
        if minv:
            u=self.require(['operator'])
            if not u:return
            body=self.json_body(); action=str(body.get('action','')); status=str(body.get('status',''))
            con=db(); inv=con.execute('SELECT * FROM commission_invoices WHERE id=?',(minv.group(1),)).fetchone()
            if not inv: con.close(); return self.send_json({'error':'not_found'},404)
            if action=='remind':
                info=con.execute('SELECT u.id user_id,u.email,b.kennel_name FROM commission_invoices ci JOIN breeders b ON b.id=ci.breeder_id JOIN users u ON u.id=b.user_id WHERE ci.id=?',(inv['id'],)).fetchone()
                due_txt=time.strftime('%Y年%m月%d日',time.localtime(inv['due_at']))
                if info:
                    con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),info['user_id'],'billing','成約手数料のお支払い期限をご確認ください',f"{inv['invoice_no']} / {inv['fee_amount']:,}円 / 支払期限 {due_txt}",0,now()))
                    sent=send_mail(info['email'],'BIG PAW 成約手数料 お支払いのご確認',f"{info['kennel_name']} 様\n\n成約手数料のお支払い期限をご確認ください。\n請求番号: {inv['invoice_no']}\n請求額: {inv['fee_amount']:,}円\n支払期限: {due_txt}\n\nBIG PAWブリーダー管理画面の「請求・お支払い」から請求書をご確認いただけます。")
                    audit(con,u['id'],'commission_invoice_reminder','commission_invoice',inv['id'],'mail_sent' if sent else 'notification_only')
                    con.commit(); con.close(); return self.send_json({'ok':True,'mailSent':sent})
                con.close(); return self.send_json({'error':'breeder_user_not_found'},404)
            if status not in ('issued','paid','void'): con.close(); return self.send_json({'error':'invalid_status'},400)
            paid_at=now() if status=='paid' else None
            con.execute('UPDATE commission_invoices SET status=?,paid_at=? WHERE id=?',(status,paid_at,inv['id'])); audit(con,u['id'],'commission_invoice_updated','commission_invoice',inv['id'],status); sync_breeder_billing_suspension(con,inv['breeder_id']); con.commit(); out=con.execute('SELECT * FROM commission_invoices WHERE id=?',(inv['id'],)).fetchone(); con.close(); return self.send_json(dict(out))
        mreport=re.fullmatch(r'/api/operator/deal-reports/([^/]+)',path)
        if mreport:
            u=self.require(['operator'])
            if not u:return
            body=self.json_body(); action=str(body.get('action','')).strip(); note=str(body.get('reviewNote','')).strip()
            if action not in ('approve','reject'): return self.send_json({'error':'invalid_action'},400)
            con=db(); r=con.execute('SELECT * FROM deal_completion_reports WHERE id=?',(mreport.group(1),)).fetchone()
            if not r: con.close(); return self.send_json({'error':'not_found'},404)
            d=con.execute('SELECT * FROM deals WHERE id=?',(r['deal_id'],)).fetchone()
            if not d: con.close(); return self.send_json({'error':'deal_not_found'},404)
            if action=='reject':
                con.execute("UPDATE deal_completion_reports SET status='rejected',reviewed_by_user_id=?,review_note=?,updated_at=? WHERE id=?",(u['id'],note,now(),r['id']))
                con.execute("UPDATE deals SET status='negotiating' WHERE id=?",(d['id'],)); con.execute("UPDATE inquiries SET status='返信済み' WHERE id=?",(d['inquiry_id'],))
                bu=con.execute('SELECT user_id FROM breeders WHERE id=?',(r['breeder_id'],)).fetchone()
                if bu: con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),bu['user_id'],'deal_report','成約申請が差し戻されました',note or '内容を確認して再申請してください。',0,now()))
                audit(con,u['id'],'deal_completion_report_rejected','deal',d['id'],note); con.commit(); out=con.execute('SELECT * FROM deal_completion_reports WHERE id=?',(r['id'],)).fetchone(); con.close(); return self.send_json(dict(out))
            # approve: lock in final price, complete pickup/deal, mark puppy sold and issue 5% invoice
            t=now(); con.execute("UPDATE deal_completion_reports SET status='approved',reviewed_by_user_id=?,review_note=?,updated_at=? WHERE id=?",(u['id'],note,t,r['id']))
            con.execute("UPDATE deals SET total_price=?,status='completed' WHERE id=?",(int(r['final_sale_amount']),d['id']))
            con.execute("UPDATE puppies SET status='成約済み' WHERE id=?",(d['puppy_id'],)); con.execute("UPDATE inquiries SET status='成約済み' WHERE id=?",(d['inquiry_id'],))
            pk=con.execute('SELECT * FROM pickups WHERE deal_id=?',(d['id'],)).fetchone()
            if pk: con.execute("UPDATE pickups SET pickup_date=?,status='completed',completed_at=?,updated_at=? WHERE id=?",(r['pickup_date'],t,t,pk['id']))
            else: con.execute('INSERT INTO pickups(id,deal_id,pickup_date,pickup_time,status,completed_at,updated_at) VALUES(?,?,?,?,?,?,?)',(make_id('pk_'),d['id'],r['pickup_date'],'','completed',t,t))
            completed_deal=con.execute('SELECT * FROM deals WHERE id=?',(d['id'],)).fetchone(); invoice=ensure_commission_invoice(con,completed_deal)
            breeder_user=con.execute('SELECT u.id,u.email,b.kennel_name FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?',(r['breeder_id'],)).fetchone()
            if breeder_user:
                bodytxt=f"成約申請が承認されました。{invoice['invoice_no'] if invoice else ''} / 成約手数料 {invoice['fee_amount']:,}円" if invoice else '成約申請が承認されました。'
                con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),breeder_user['id'],'deal_report','成約が確定しました',bodytxt,0,t))
            audit(con,u['id'],'deal_completion_report_approved','deal',d['id'],f"{r['final_sale_amount']}:{r['pickup_date']}"); con.commit()
            if breeder_user and invoice:
                due_txt=time.strftime('%Y年%m月%d日',time.localtime(invoice['due_at']))
                send_mail(breeder_user['email'],'BIG PAW 成約確定・成約手数料のご請求',f"{breeder_user['kennel_name']} 様\n\n成約申請を確認しました。\n成約手数料: {invoice['fee_amount']:,}円（生体価格の5%・税込）\n請求番号: {invoice['invoice_no']}\n支払期限: {due_txt}\n\nBIG PAW管理画面から請求書をご確認ください。")
            out=con.execute('SELECT * FROM deal_completion_reports WHERE id=?',(r['id'],)).fetchone(); con.close(); return self.send_json(dict(out))
        m=re.fullmatch(r'/api/breeder-applications/([^/]+)',path)
        if m:
            u=self.require(['operator'])
            if not u:return
            body=self.json_body(); status=body.get('status',''); note=str(body.get('reviewNote',''))
            if status not in ('approved','rejected','pending'): return self.send_json({'error':'invalid_status'},400)
            con=db(); a=con.execute('SELECT * FROM breeder_applications WHERE id=?',(m.group(1),)).fetchone()
            if not a: con.close(); return self.send_json({'error':'not_found'},404)
            con.execute('UPDATE breeder_applications SET status=?,review_note=?,updated_at=? WHERE id=?',(status,note,now(),a['id']))
            if status=='approved':
                con.execute("UPDATE users SET role='breeder' WHERE id=? AND role!='operator'",(a['user_id'],))
                existing=con.execute('SELECT id FROM breeders WHERE user_id=?',(a['user_id'],)).fetchone()
                if not existing:
                    con.execute('INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES(?,?,?,?,?,?,?)',(make_id('b_'),a['user_id'],a['kennel_name'],a['prefecture'],a['registration_no'],a['profile'],'approved'))
            if status=='approved':
                con.execute("UPDATE users SET role='breeder' WHERE id=? AND role!='operator'",(a['user_id'],))
                con.commit()
            con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(a['id'],)).fetchone()
            applicant=con.execute('SELECT email FROM users WHERE id=?',(a['user_id'],)).fetchone()
            con.close()
            if applicant:
                if status=='approved':
                    send_mail(applicant['email'],'BIG PAW 掲載審査が承認されました',f"{a['kennel_name']} 様\n\n掲載審査が承認されました。ブリーダー管理画面から子犬を登録できます。\n\n子犬を登録する: {PUBLIC_BASE_URL}/breeder-puppy-new.html\n管理画面: {PUBLIC_BASE_URL}/admin.html")
                elif status=='rejected':
                    send_mail(applicant['email'],'BIG PAW 掲載審査について',f"{a['kennel_name']} 様\n\n掲載審査の内容をご確認ください。\n{note or '申請内容をご確認のうえ、再申請してください。'}\n\n{PUBLIC_BASE_URL}/breeder-register.html")
            return self.send_json(dict(r))
        iq=re.fullmatch(r'/api/inquiries/([^/]+)',path)
        if iq:
            u=self.require(['buyer','breeder','operator']);
            if not u:return
            body=self.json_body(); con=db(); item=con.execute('SELECT * FROM inquiries WHERE id=?',(iq.group(1),)).fetchone()
            if not item: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or item['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
            if 'status' in body: con.execute('UPDATE inquiries SET status=? WHERE id=?',(body['status'],iq.group(1)))
            con.commit(); out=con.execute('SELECT * FROM inquiries WHERE id=?',(iq.group(1),)).fetchone(); con.close(); return self.send_json(dict(out))
        m=re.fullmatch(r'/api/puppies/([^/]+)',path)
        if m:
            u=self.require(['buyer','breeder','operator']);
            if not u:return
            body=self.json_body(); con=db(); p=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone()
            if not p: con.close(); return self.send_json({'error':'not_found'},404)
            if u['role']=='breeder':
                b=con.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                if not b or p['breeder_id']!=b['id']: con.close(); return self.send_json({'error':'forbidden'},403)
                if p['status']=='成約済み' and 'status' in body:
                    con.close(); return self.send_json({'error':'completed_status_locked','message':'成約済みの状態はBIG PAW運営のみ変更できます。'},409)
            if u['role']=='breeder' and body.get('status')=='成約済み':
                con.close(); return self.send_json({'error':'completion_report_required','message':'成約済みへの変更は「成約申請」から行ってください。'},409)
            allowed={'status':'status','price':'price','desc':'description','name':'name','imageUrl':'image_url'}
            sets=[]; args=[]
            for k,col in allowed.items():
                if k in body: sets.append(f'{col}=?'); args.append(body[k])
            if sets:
                if u['role']=='breeder' and any(k in body for k in ('desc','name','imageUrl')):
                    sets.extend(["review_status='pending'","moderation_note=''",'published_at=NULL'])
                args.append(m.group(1)); con.execute('UPDATE puppies SET '+','.join(sets)+' WHERE id=?',args); audit(con,u['id'],'puppy_updated','puppy',m.group(1),','.join(body.keys())); con.commit()
            r=con.execute('SELECT * FROM puppies WHERE id=?',(m.group(1),)).fetchone(); con.close(); return self.send_json(puppy_json(r))
        return self.send_json({'error':'not_found'},404)

if __name__=='__main__':
    if IS_PRODUCTION:
        if not os.environ.get('BIGPAW_ADMIN_EMAIL') or len(os.environ.get('BIGPAW_ADMIN_PASSWORD',''))<12:
            raise SystemExit('Production requires BIGPAW_ADMIN_EMAIL and BIGPAW_ADMIN_PASSWORD (12+ chars)')
        if DEV_LINKS:
            raise SystemExit('BIGPAW_DEV_LINKS must be 0 in production')
    init_db(); threading.Thread(target=automation_monitor_loop,daemon=True,name='automation-monitor').start(); os.chdir(ROOT); port=int(os.environ.get('PORT','8080'))
try:
    _c=db()
    _rows=_c.execute("SELECT p.id,p.breed,p.breed_key,p.review_status,p.status,p.breeder_id,COALESCE(b.review_status,''),COALESCE(b.billing_suspended,0) FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id ORDER BY p.created_at DESC").fetchall()
    print('BIGPAW_PUBLIC_DIAG|'+repr([tuple(r) for r in _rows]),flush=True)
    _c.close()
except Exception as _e:
    print('BIGPAW_PUBLIC_DIAG_ERROR|'+repr(_e),flush=True)
try:
    if IS_PRODUCTION:
        _sc=db()
        _meta=_sc.execute("PRAGMA table_info(breeders)").fetchall()
        print('BREEDERS_SCHEMA|'+';'.join(str(r['name'])+':'+str(r['type'])+':notnull='+str(r['notnull'])+':default='+str(r['dflt_value'])+':pk='+str(r['pk']) for r in _meta),flush=True)
        _sc.close()
except Exception as _se:
    print('BREEDERS_SCHEMA_ERROR|'+type(_se).__name__,flush=True)
# Restore the legacy DOG44 breeder profile only when the owner match is unique and no breeder profile exists.
try:
    if IS_PRODUCTION:
        _pc=db()
        _ou=_pc.execute("SELECT id,role FROM users WHERE lower(trim(email))=?",('yoshiyukimoro@gmail.com',)).fetchall()
        _pn=_pc.execute("SELECT COUNT(*) AS n FROM breeders").fetchone()['n']
        if len(_ou)==1 and _ou[0]['role']=='breeder' and _pn==0:
            import uuid as _uuid
            _bid='b_'+_uuid.uuid4().hex[:12]
            _cols=[r['name'] for r in _pc.execute("PRAGMA table_info(breeders)").fetchall()]
            _vals={'id':_bid,'user_id':_ou[0]['id'],'kennel_name':'DOG44','prefecture':'埼玉県'}
            _use=[k for k in ('id','user_id','kennel_name','prefecture') if k in _cols]
            if all(k in _use for k in ('id','user_id','kennel_name','prefecture')):
                _pc.execute("INSERT INTO breeders ("+','.join(_use)+") VALUES ("+','.join('?' for _ in _use)+")",tuple(_vals[k] for k in _use))
                _pc.commit(); print('OWNER_BREEDER_PROFILE_OK|created=1',flush=True)
            else:
                print('OWNER_BREEDER_PROFILE_SKIP|schema',flush=True)
        else:
            print('OWNER_BREEDER_PROFILE_SKIP|owners='+str(len(_ou))+'|profiles='+str(_pn),flush=True)
        _pc.close()
except Exception as _pe:
    print('OWNER_BREEDER_PROFILE_ERROR|'+type(_pe).__name__,flush=True)
# Reconcile the known site-owner breeder account that predates the application/role workflow.
try:
    if IS_PRODUCTION:
        _owner_email='yoshiyukimoro@gmail.com'
        _oc=db()
        _rows=_oc.execute("SELECT id,role FROM users WHERE lower(trim(email))=?",(_owner_email,)).fetchall()
        if len(_rows)==1 and _rows[0]['role']!='operator':
            _oc.execute("UPDATE users SET role='breeder' WHERE id=? AND role!='operator'",(_rows[0]['id'],))
            _oc.commit()
            print('OWNER_BREEDER_RECONCILE_OK|matched=1',flush=True)
        else:
            print('OWNER_BREEDER_RECONCILE_SKIP|matched='+str(len(_rows))+'|operator='+str(bool(_rows and _rows[0]['role']=='operator')),flush=True)
        _oc.close()
except Exception as _oe:
    print('OWNER_BREEDER_RECONCILE_ERROR|'+type(_oe).__name__,flush=True)
# Reconcile legacy approved breeder accounts at runtime.
try:
    _con=db()
    _con.execute("UPDATE users SET role='breeder' WHERE role!='operator' AND id IN (SELECT user_id FROM breeder_applications WHERE status='approved')")
    _con.commit(); _con.close()
    print('BREEDER_ROLE_BACKFILL_OK',flush=True)
    try:
        _d=db()
        _approved=_d.execute("SELECT COUNT(*) AS n FROM breeder_applications WHERE status='approved'").fetchone()['n']
        _approved_users=_d.execute("SELECT COUNT(DISTINCT user_id) AS n FROM breeder_applications WHERE status='approved'").fetchone()['n']
        _breeders=_d.execute("SELECT COUNT(*) AS n FROM users WHERE role='breeder'").fetchone()['n']
        _approved_breeders=_d.execute("SELECT COUNT(DISTINCT b.user_id) AS n FROM breeder_applications b JOIN users u ON u.id=b.user_id WHERE b.status='approved' AND u.role='breeder'").fetchone()['n']
        _d.close()
        print('BREEDER_LINK_DIAG|approved='+str(_approved)+'|approved_users='+str(_approved_users)+'|breeders='+str(_breeders)+'|approved_breeders='+str(_approved_breeders),flush=True)
    except Exception as _de:
        print('BREEDER_LINK_DIAG_ERROR|'+type(_de).__name__,flush=True)
except Exception as _e:
    print('BREEDER_ROLE_BACKFILL_ERROR|'+repr(_e),flush=True)
# Diagnose production role/profile linkage without exposing personal data.
try:
    if IS_PRODUCTION:
        _lc=db()
        _all_users=_lc.execute("SELECT COUNT(*) AS n FROM users").fetchone()['n']
        _buyers=_lc.execute("SELECT COUNT(*) AS n FROM users WHERE role='buyer'").fetchone()['n']
        _role_breeders=_lc.execute("SELECT COUNT(*) AS n FROM users WHERE role='breeder'").fetchone()['n']
        _profiles=_lc.execute("SELECT COUNT(*) AS n FROM breeders").fetchone()['n']
        _linked=_lc.execute("SELECT COUNT(*) AS n FROM breeders b JOIN users u ON u.id=b.user_id").fetchone()['n']
        _buyer_profiles=_lc.execute("SELECT COUNT(*) AS n FROM breeders b JOIN users u ON u.id=b.user_id WHERE u.role='buyer'").fetchone()['n']
        _breeder_missing_profile=_lc.execute("SELECT COUNT(*) AS n FROM users u WHERE u.role='breeder' AND NOT EXISTS (SELECT 1 FROM breeders b WHERE b.user_id=u.id)").fetchone()['n']
        _orphan_profiles=_lc.execute("SELECT COUNT(*) AS n FROM breeders b LEFT JOIN users u ON u.id=b.user_id WHERE u.id IS NULL").fetchone()['n']
        _lc.close()
        print('ROLE_PROFILE_DIAG|users='+str(_all_users)+'|buyers='+str(_buyers)+'|breeder_roles='+str(_role_breeders)+'|profiles='+str(_profiles)+'|linked='+str(_linked)+'|buyer_profiles='+str(_buyer_profiles)+'|breeder_missing_profile='+str(_breeder_missing_profile)+'|orphan_profiles='+str(_orphan_profiles),flush=True)
except Exception as _le:
    print('ROLE_PROFILE_DIAG_ERROR|'+type(_le).__name__,flush=True)
# Compare configured admin identity with the operator row without exposing either value.
try:
    if IS_PRODUCTION:
        _dc=db()
        _ae=str(os.environ.get('BIGPAW_ADMIN_EMAIL','')).strip().lower()
        _match=_dc.execute("SELECT COUNT(*) AS n FROM users WHERE role='operator' AND lower(email)=?",(_ae,)).fetchone()['n'] if _ae else 0
        _same_any=_dc.execute("SELECT COUNT(*) AS n FROM users WHERE lower(email)=?",(_ae,)).fetchone()['n'] if _ae else 0
        _dc.close()
        print('ADMIN_OPERATOR_MATCH|configured='+str(bool(_ae)).lower()+'|operator_match='+str(_match)+'|any_user_match='+str(_same_any),flush=True)
except Exception as _de:
    print('ADMIN_OPERATOR_MATCH_ERROR|'+type(_de).__name__,flush=True)
# Safe auth-role diagnostic.
try:
    if IS_PRODUCTION:
        _ac=db()
        _ops=_ac.execute("SELECT COUNT(*) AS n FROM users WHERE role='operator'").fetchone()['n']
        _ac.close()
        print('AUTH_ROLE_DIAG|operators='+str(_ops),flush=True)
except Exception as _ae:
    print('AUTH_ROLE_DIAG_ERROR|'+type(_ae).__name__,flush=True)
print(f'BIG PAW v1.0 server running on port {port} ({APP_ENV})')
if not IS_PRODUCTION:
    print('Buyer   : demo@bigpaw.jp / demo1234')
    print('Breeder : dog44@bigpaw.jp / demo1234')
    print('Operator: admin@bigpaw.jp / admin1234')
ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()


try:
    import os as _os, urllib.request as _ur, urllib.error as _ue
    _rk=(_os.environ.get("RESEND_API_KEY") or "").strip()
    if _rk:
        _rq=_ur.Request("https://api.resend.com/domains",headers={"Authorization":"Bearer "+_rk,"User-Agent":"BIGPAW-Mailer/1.0","Accept":"application/json"})
        try:
            with _ur.urlopen(_rq,timeout=8) as _rp:
                print("[BIG PAW] Resend connectivity check:",_rp.status,flush=True)
        except _ue.HTTPError as _ex:
            print("[BIG PAW] Resend connectivity HTTP error:",_ex.code,flush=True)
        except Exception as _ex:
            print("[BIG PAW] Resend connectivity failed:",type(_ex).__name__,str(_ex)[:200],flush=True)
except Exception as _ex:
    print("[BIG PAW] Resend probe setup failed:",type(_ex).__name__,flush=True)
