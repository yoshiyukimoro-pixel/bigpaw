from pathlib import Path

root=Path('/app')
server_path=root/'backend/server.py'
admin_path=root/'operator-admin.html'

s=server_path.read_text(encoding='utf-8')

HELPER_MARK='def analytics_track_public_pageview(handler, path, query):'
if HELPER_MARK not in s:
    anchor='def init_db():\n'
    if s.count(anchor)!=1:
        raise SystemExit(('analytics_init_anchor_count',s.count(anchor)))
    helper=r'''ANALYTICS_PUBLIC_PAGES={
    '/','/index.html','/search.html','/puppy-detail.html','/breeders.html','/breeder-detail.html',
    '/breed-guide.html','/breed-guide-detail.html','/breed-standard-poodle.html','/cost-simulator.html',
    '/match.html','/faq.html','/contact.html','/privacy.html','/terms.html','/legal-notice.html',
    '/login.html','/register.html','/favorites.html','/compare.html','/mypage.html','/notifications.html',
    '/inquiry.html','/forgot-password.html','/reset-password.html','/verify-email.html'
}
ANALYTICS_BOT_WORDS=('bot','crawler','spider','slurp','facebookexternalhit','preview','headless','monitoring')
ANALYTICS_PAGE_LABELS={
    '/':'トップ','/index.html':'トップ','/search.html':'子犬を探す','/puppy-detail.html':'子犬詳細',
    '/breeders.html':'ブリーダー一覧','/breeder-detail.html':'ブリーダー詳細','/breed-guide.html':'大型犬ガイド',
    '/breed-guide-detail.html':'犬種ガイド詳細','/breed-standard-poodle.html':'スタンダードプードルガイド',
    '/cost-simulator.html':'飼育費シミュレーター','/match.html':'犬種マッチ','/faq.html':'よくある質問',
    '/contact.html':'お問い合わせ','/favorites.html':'お気に入り','/compare.html':'比較','/mypage.html':'マイページ',
    '/notifications.html':'お知らせ','/inquiry.html':'問い合わせ入力','/login.html':'ログイン','/register.html':'新規登録'
}

def analytics_jst_day_start(ts=None):
    ts=int(ts or now())
    return int(((ts+9*3600)//86400)*86400-9*3600)

def analytics_track_public_pageview(handler, path, query):
    try:
        if path not in ANALYTICS_PUBLIC_PAGES and not (path.startswith('/breed-') and path.endswith('.html')):
            return
        ua=str(handler.headers.get('User-Agent',''))[:500]
        low=ua.lower()
        if not ua or any(x in low for x in ANALYTICS_BOT_WORDS):
            return
        # Operators and breeders checking the public site are not counted as customer traffic.
        try:
            u=handler.current_user()
            if u and u.get('role') in ('operator','breeder'):
                return
        except Exception:
            pass
        ip=str(handler.client_address[0] if handler.client_address else '')
        visitor_hash=hashlib.sha256(('BIGPAW-ANALYTICS-V1|'+ip+'|'+ua).encode('utf-8','ignore')).hexdigest()[:32]
        puppy_id=''
        if path=='/puppy-detail.html':
            puppy_id=str((query.get('id') or [''])[0])[:120]
        t=now()
        con=db()
        con.execute('INSERT INTO analytics_pageviews(visitor_hash,path,puppy_id,created_at) VALUES(?,?,?,?)',
                    (visitor_hash,path,puppy_id,t))
        # Keep only six months of anonymous aggregates.
        con.execute('DELETE FROM analytics_pageviews WHERE created_at<?',(t-180*86400,))
        con.commit(); con.close()
    except Exception as exc:
        print('ANALYTICS_TRACK_ERROR|'+type(exc).__name__,flush=True)

def analytics_operator_payload():
    t=now(); today=analytics_jst_day_start(t); d7=today-6*86400; d30=today-29*86400
    con=db()
    try:
        one=lambda sql,args=(): con.execute(sql,args).fetchone()[0]
        today_pv=one('SELECT COUNT(*) FROM analytics_pageviews WHERE created_at>=?',(today,))
        today_vis=one('SELECT COUNT(DISTINCT visitor_hash) FROM analytics_pageviews WHERE created_at>=?',(today,))
        pv7=one('SELECT COUNT(*) FROM analytics_pageviews WHERE created_at>=?',(d7,))
        vis7=one('SELECT COUNT(DISTINCT visitor_hash) FROM analytics_pageviews WHERE created_at>=?',(d7,))
        pv30=one('SELECT COUNT(*) FROM analytics_pageviews WHERE created_at>=?',(d30,))
        vis30=one('SELECT COUNT(DISTINCT visitor_hash) FROM analytics_pageviews WHERE created_at>=?',(d30,))
        details7=one("SELECT COUNT(*) FROM analytics_pageviews WHERE created_at>=? AND path='/puppy-detail.html'",(d7,))
        inquiry_today=one('SELECT COUNT(*) FROM inquiries WHERE created_at>=?',(today,))
        inquiry7=one('SELECT COUNT(*) FROM inquiries WHERE created_at>=?',(d7,))
        inquiry30=one('SELECT COUNT(*) FROM inquiries WHERE created_at>=?',(d30,))
        pages=con.execute('''SELECT path,COUNT(*) views,COUNT(DISTINCT visitor_hash) visitors
                             FROM analytics_pageviews WHERE created_at>=?
                             GROUP BY path ORDER BY views DESC,path LIMIT 5''',(d30,)).fetchall()
        puppies=con.execute('''SELECT a.puppy_id,p.breed,p.name,COUNT(*) views,COUNT(DISTINCT a.visitor_hash) visitors
                               FROM analytics_pageviews a LEFT JOIN puppies p ON p.id=a.puppy_id
                               WHERE a.created_at>=? AND a.path='/puppy-detail.html' AND a.puppy_id!=''
                               GROUP BY a.puppy_id,p.breed,p.name ORDER BY views DESC,a.puppy_id LIMIT 5''',(d30,)).fetchall()
        first=con.execute('SELECT MIN(created_at) FROM analytics_pageviews').fetchone()[0]
        return {
            'today':{'visitors':today_vis,'pv':today_pv},
            'days7':{'visitors':vis7,'pv':pv7},
            'days30':{'visitors':vis30,'pv':pv30},
            'inquiries':{'today':inquiry_today,'days7':inquiry7,'days30':inquiry30},
            'funnel7':{'puppyDetailViews':details7,'inquiries':inquiry7,'rate':round((inquiry7/details7)*100,1) if details7 else 0},
            'popularPages':[{'path':r['path'],'label':ANALYTICS_PAGE_LABELS.get(r['path'],r['path']),'views':r['views'],'visitors':r['visitors']} for r in pages],
            'popularPuppies':[{'id':r['puppy_id'],'breed':r['breed'] or '掲載終了・不明','name':r['name'] or r['puppy_id'],'views':r['views'],'visitors':r['visitors']} for r in puppies],
            'trackingSince':first or None,
            'timezone':'Asia/Tokyo'
        }
    finally:
        con.close()

'''
    s=s.replace(anchor,helper+anchor,1)

# Durable anonymous analytics table.
init_old='def init_db():\n    con = db(); con.executescript(SCHEMA)\n'
init_new="def init_db():\n    con = db(); con.executescript(SCHEMA)\n    con.execute('''CREATE TABLE IF NOT EXISTS analytics_pageviews (id INTEGER PRIMARY KEY AUTOINCREMENT, visitor_hash TEXT NOT NULL, path TEXT NOT NULL, puppy_id TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL)''')\n    con.execute('CREATE INDEX IF NOT EXISTS idx_analytics_pageviews_created ON analytics_pageviews(created_at)')\n    con.execute('CREATE INDEX IF NOT EXISTS idx_analytics_pageviews_puppy ON analytics_pageviews(puppy_id,created_at)')\n"
if 'CREATE TABLE IF NOT EXISTS analytics_pageviews' not in s:
    if s.count(init_old)!=1:
        raise SystemExit(('analytics_init_block_count',s.count(init_old)))
    s=s.replace(init_old,init_new,1)

# Track only customer-facing HTML page loads. No analytics UI is exposed on customer/breeder pages.
track_mark='analytics_track_public_pageview(self,path,q)'
if track_mark not in s:
    get_anchor='        parsed=urlparse(self.path); path=parsed.path; q=parse_qs(parsed.query)\n'
    if s.count(get_anchor)!=1:
        raise SystemExit(('analytics_get_anchor_count',s.count(get_anchor)))
    s=s.replace(get_anchor,get_anchor+'        analytics_track_public_pageview(self,path,q)\n',1)

# Operator-only analytics API.
route_mark="if path=='/api/operator/analytics':"
if route_mark not in s:
    route_anchor="        if path=='/api/operator/stats':\n"
    if s.count(route_anchor)!=1:
        raise SystemExit(('analytics_route_anchor_count',s.count(route_anchor)))
    route="        if path=='/api/operator/analytics':\n            u=self.require(['operator'])\n            if not u:return\n            return self.send_json(analytics_operator_payload())\n"
    s=s.replace(route_anchor,route+route_anchor,1)

required=(HELPER_MARK,'CREATE TABLE IF NOT EXISTS analytics_pageviews',track_mark,route_mark,"self.require(['operator'])")
missing=[x for x in required if x not in s]
if missing:
    raise SystemExit(('operator_analytics_server_gate_missing',missing))
server_path.write_text(s,encoding='utf-8')

# Operator dashboard UI only.
h=admin_path.read_text(encoding='utf-8')
UI_MARK='id="bpOperatorAnalytics"'
if UI_MARK not in h:
    storage_anchor='<section class="section"><div class="card pad storage-card" id="storageCard"'
    if h.count(storage_anchor)!=1:
        raise SystemExit(('analytics_admin_storage_anchor_count',h.count(storage_anchor)))
    panel='''<section class="section" id="bpOperatorAnalytics"><div class="card pad"><div class="bp-analytics-head"><div><h2 style="margin:0 0 4px">一般ユーザー アクセス</h2><p class="muted" style="margin:0">一般ユーザー画面だけを匿名集計。運営・ブリーダーの閲覧は除外します。</p></div><small class="muted" id="opAnalyticsSince">集計開始後から表示</small></div><div class="statgrid bp-analytics-stats" style="margin-top:14px"><div class="card statbox"><span class="muted">今日の訪問者</span><b id="opVisitorsToday">-</b></div><div class="card statbox"><span class="muted">今日のPV</span><b id="opPvToday">-</b></div><div class="card statbox"><span class="muted">7日間の訪問者</span><b id="opVisitors7">-</b></div><div class="card statbox"><span class="muted">30日間の訪問者</span><b id="opVisitors30">-</b></div></div><div class="bp-analytics-grid"><div><h3>人気の子犬（30日）</h3><div id="opPopularPuppies" class="bp-analytics-list"><span class="muted">集計中…</span></div></div><div><h3>人気ページ（30日）</h3><div id="opPopularPages" class="bp-analytics-list"><span class="muted">集計中…</span></div></div></div><div class="notice" id="opAnalyticsFunnel" style="margin-top:14px">問い合わせ状況を集計中…</div></div></section>'''
    h=h.replace(storage_anchor,panel+storage_anchor,1)

style_mark='.bp-analytics-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}'
if style_mark not in h:
    style_anchor='</style></head>'
    if h.count(style_anchor)!=1:
        raise SystemExit(('analytics_admin_style_anchor_count',h.count(style_anchor)))
    css='''<style>.bp-analytics-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.bp-analytics-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}.bp-analytics-list{display:grid;gap:8px}.bp-analytics-row{display:flex;justify-content:space-between;gap:12px;padding:10px 12px;border:1px solid #eee3a8;border-radius:12px;background:#fff}.bp-analytics-row strong{font-size:15px}.bp-analytics-row span{white-space:nowrap;font-weight:800;color:#705d00}@media(max-width:800px){.bp-analytics-head{display:block}.bp-analytics-grid{grid-template-columns:1fr}.bp-analytics-stats{grid-template-columns:1fr 1fr}}</style>'''
    h=h.replace(style_anchor,css+style_anchor,1)

script_mark='window.__BIGPAW_OPERATOR_ANALYTICS__=true'
if script_mark not in h:
    script_anchor='</body></html>'
    if h.count(script_anchor)!=1:
        raise SystemExit(('analytics_admin_body_anchor_count',h.count(script_anchor)))
    js=r'''<script>(async()=>{window.__BIGPAW_OPERATOR_ANALYTICS__=true;const t=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=String(v??0)};const list=(id,rows,puppy)=>{const box=document.getElementById(id);if(!box)return;box.textContent='';if(!rows||!rows.length){const e=document.createElement('span');e.className='muted';e.textContent='まだ集計データがありません。';box.appendChild(e);return}rows.forEach(r=>{const row=document.createElement('div');row.className='bp-analytics-row';const left=document.createElement('strong');left.textContent=puppy?((r.breed||'')+'／'+(r.name||'')):(r.label||r.path||'');const right=document.createElement('span');right.textContent=(r.views||0)+' PV';row.append(left,right);box.appendChild(row)})};try{const a=await BigPawAPI.request('/operator/analytics');t('opVisitorsToday',a.today&&a.today.visitors);t('opPvToday',a.today&&a.today.pv);t('opVisitors7',a.days7&&a.days7.visitors);t('opVisitors30',a.days30&&a.days30.visitors);list('opPopularPuppies',a.popularPuppies,true);list('opPopularPages',a.popularPages,false);const f=a.funnel7||{},iq=a.inquiries||{};const fe=document.getElementById('opAnalyticsFunnel');if(fe)fe.textContent='問い合わせ：今日 '+(iq.today||0)+'件 ／ 7日 '+(iq.days7||0)+'件 ／ 30日 '+(iq.days30||0)+'件　｜　7日間：子犬詳細 '+(f.puppyDetailViews||0)+'PV → 問い合わせ '+(f.inquiries||0)+'件（約'+(f.rate||0)+'%）';const se=document.getElementById('opAnalyticsSince');if(se)se.textContent=a.trackingSince?('集計開始 '+new Date(a.trackingSince*1000).toLocaleString('ja-JP')):'集計はこれから開始'}catch(e){const fe=document.getElementById('opAnalyticsFunnel');if(fe)fe.textContent='アクセス集計を読み込めませんでした。';list('opPopularPuppies',[],true);list('opPopularPages',[],false)}})();</script>'''
    h=h.replace(script_anchor,js+script_anchor,1)

admin_required=(UI_MARK,style_mark,script_mark,'一般ユーザー アクセス','opVisitorsToday','opPopularPuppies')
missing=[x for x in admin_required if x not in h]
if missing:
    raise SystemExit(('operator_analytics_admin_gate_missing',missing))
admin_path.write_text(h,encoding='utf-8')
print('OPERATOR_ANALYTICS_OK|public_tracking=anonymous|operator_breeder_excluded|dashboard=operator_only|popular_pages=30d|popular_puppies=30d|funnel=7d',flush=True)
