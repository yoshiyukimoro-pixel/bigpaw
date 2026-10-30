Warning: truncated output (original token count: 45244)
Total output lines: 2243

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
import planned_litters as bp_planned_litters
import shop_live_checkout_bridge as bp_shop_checkout
import shop_live_webhook_bridge as bp_shop_webhook

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
CLOUDFLARE_STREAM_ACCOUNT_ID = os.environ.get('BIGPAW_CLOUDFLARE_STREAM_ACCOUNT_ID','').strip()
CLOUDFLARE_STREAM_API_TOKEN = os.environ.get('BIGPAW_CLOUDFLARE_STREAM_API_TOKEN','').strip()
CLOUDFLARE_STREAM_CUSTOMER_CODE = os.environ.get('BIGPAW_CLOUDFLARE_STREAM_CUSTOMER_CODE','').strip()
CLOUDFLARE_STREAM_API_BASE = os.environ.get('BIGPAW_CLOUDFLARE_STREAM_API_BASE','https://api.cloudflare.com/client/v4').rstrip('/')
PUPPY_VIDEO_MAX_SECONDS = 60
PUPPY_VIDEO_MAX_BYTES = 200 * 1024 * 1024
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

def invoice_fee_breakdown_text(invoice):
    """Explicitly separate the platform success fee from optional 推しワン fees."""
    amount=int(invoice['sale_amount'])
    rate=int(invoice['rate_bps'])
    total=int(invoice['fee_amount'])
    if rate==800:
        base=(amount*500)//10000
        promotion=(amount*300)//10000
        return f"通常成約手数料（5％）：{base:,}円\n推しワン利用料（3％）：{promotion:,}円\n請求合計（税込）：{total:,}円"
    if rate==300:
        waived_label = "先着100頭キャンペーン" if "先着100頭" in str(invoice["note"] or "") else "初回無料特典"
        return f"通常成約手数料（{waived_label}適用）：0円\n推しワン利用料（3％）：{total:,}円\n請求合計（税込）：{total:,}円"
    return f"通常成約手数料（{rate/100:g}％）：{total:,}円\n請求合計（税込）：{total:,}円"

def ensure_commission_invoice(con, deal):
    # One tax-inclusive success-fee invoice per completed deal.
    if not deal or not deal['breeder_id']:
        return None
    existing=con.execute('SELECT * FROM commission_invoices WHERE deal_id=?',(deal['id'],)).fetchone()
    if existing:
        return existing
    sale_amount=int(deal['total_price'])
    # Frozen per-deal promotion, preserving invoices already issued.
    try:
        decision=con.execute('SELECT rate_bps,waived FROM sale_fee_decisions WHERE deal_id=?',(deal['id'],)).fetchone()
    except sqlite3.OperationalError:
        decision=None
    # Invoice the 5% standard fee plus optional 3% promotion separately.
    # The first-sale benefit waives only the 5% portion.
    decision_bps=int(decision['rate_bps']) if decision else COMMISSION_RATE_BPS
    standard_waived=bool(decision and decision['waived'])
    rate_bps=decision_bps-(COMMISSION_RATE_BPS if standard_waived else 0)
    if rate_bps==800:
        fee_amount=(sale_amount*500)//10000 + (sale_amount*300)//10000
    else:
        fee_amount=(sale_amount*rate_bps)//10000
    issued=now(); due=issued + COMMISSION_DUE_DAYS*86400
    inv_id=make_id('inv_')
    invoice_no='BP-'+time.strftime('%Y%m%d',time.localtime(issued))+'-'+secrets.token_hex(3).upper()
    sql = 'INSERT INTO commission_invoices (id,invoice_no,deal_id,breeder_id,sale_amount,rate_bps,fee_amount,status,issued_at,due_at,paid_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
    con.execute(sql,(inv_id,invoice_no,deal['id'],deal['breeder_id'],sale_amount,rate_bps,fee_amount,'issued',issued,due,None,('BIG PAW 成約手数料5％＋推しワン利用料3％（税込）' if rate_bps==800 else 'BIG PAW 初回成約無料・推しワン利用料3％（税込）' if rate_bps==300 else f'BIG PAW 成約手数料（{rate_bps/100:g}%・税込）')))
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
            stage='due_today'; …30244 tokens truncated…rror':'forbidden'},403)
            # Do not hard-delete a puppy already referenced by a transaction.
            if con.execute('SELECT 1 FROM inquiries WHERE puppy_id=? LIMIT 1',(puppy['id'],)).fetchone() or con.execute('SELECT 1 FROM deals WHERE puppy_id=? LIMIT 1',(puppy['id'],)).fetchone():
                con.close(); return self.send_json({'error':'puppy_has_transactions','message':'問い合わせ・取引履歴があるため削除できません。非公開に変更してください。'},409)
            uploads=con.execute('SELECT stored_name FROM uploads WHERE puppy_id=?',(puppy['id'],)).fetchall()
            video_uid=str(puppy['video_uid'] or '') if 'video_uid' in puppy.keys() else ''
            con.execute('DELETE FROM uploads WHERE puppy_id=?',(puppy['id'],))
            con.execute('DELETE FROM favorites WHERE puppy_id=?',(puppy['id'],))
            con.execute('DELETE FROM puppies WHERE id=?',(puppy['id'],))
            audit(con,u['id'],'puppy_deleted','puppy',puppy['id'])
            con.commit(); con.close()
            for row in uploads:
                try:(UPLOADS / row['stored_name']).unlink(missing_ok=True)
                except Exception:pass
            if video_uid: delete_stream_video(video_uid)
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
                bodytxt=f"成約申請が承認されました。{invoice['invoice_no'] if invoice else ''} / {invoice_fee_breakdown_text(invoice)}" if invoice else '成約申請が承認されました。'
                con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),breeder_user['id'],'deal_report','成約が確定しました',bodytxt,0,t))
            audit(con,u['id'],'deal_completion_report_approved','deal',d['id'],f"{r['final_sale_amount']}:{r['pickup_date']}"); con.commit()
            if breeder_user and invoice:
                due_txt=time.strftime('%Y年%m月%d日',time.localtime(invoice['due_at']))
                send_mail(breeder_user['email'],'BIG PAW 成約確定・成約手数料のご請求',f"{breeder_user['kennel_name']} 様\n\n成約申請を確認しました。\n{invoice_fee_breakdown_text(invoice)}\n請求番号: {invoice['invoice_no']}\n支払期限: {due_txt}\n\nBIG PAW管理画面から請求書をご確認ください。")
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
        if bp_planned_litters.handle(self, 'PATCH', path, {}, { 'db':db, 'now':now, 'make_id':make_id, 'audit':audit, 'send_mail':send_mail, 'public_profile_has_direct_contact':public_profile_has_direct_contact, 'public_url':PUBLIC_BASE_URL }): return
        return self.send_json({'error':'not_found'},404)

if __name__=='__main__':
    if IS_PRODUCTION:
        if not os.environ.get('BIGPAW_ADMIN_EMAIL') or len(os.environ.get('BIGPAW_ADMIN_PASSWORD',''))<12:
            raise SystemExit('Production requires BIGPAW_ADMIN_EMAIL and BIGPAW_ADMIN_PASSWORD (12+ chars)')
        if DEV_LINKS:
            raise SystemExit('BIGPAW_DEV_LINKS must be 0 in production')
    init_db(); threading.Thread(target=automation_monitor_loop,daemon=True,name='automation-monitor').start(); threading.Thread(target=weekly_drive_monitor_loop,daemon=True,name='weekly-drive-monitor').start(); os.chdir(ROOT); port=int(os.environ.get('PORT','8080'))
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
