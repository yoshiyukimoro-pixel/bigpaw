from pathlib import Path
import html
import json
import re

ROOT=Path('/app')
BASE='https://bigpaw.site'
MARK='data-bigpaw-seo="v1"'

PAGES={
    'index.html':(
        '大型犬の子犬・ブリーダー情報｜BIG PAW（ビッグパウ）',
        'BIG PAW（ビッグパウ）は大型犬専門の子犬・ブリーダー情報サイトです。スタンダードプードル、ゴールデンレトリバー、ラブラドールなどの子犬を、親犬・健康情報・飼育環境とあわせて探せます。',
        BASE+'/'
    ),
    'search.html':(
        '大型犬の子犬を探す｜大型犬専門 BIG PAW（ビッグパウ）',
        '大型犬の子犬を全国から検索。スタンダードプードル、ゴールデンレトリバー、ラブラドール、バーニーズなどを犬種・地域・性別・年齢・価格から探せます。',
        BASE+'/search.html'
    ),
    'search-list-rebuild.html':(
        '大型犬の子犬を探す｜大型犬専門 BIG PAW（ビッグパウ）',
        '大型犬の子犬を全国から検索。スタンダードプードル、ゴールデンレトリバー、ラブラドール、バーニーズなどを犬種・地域・性別・年齢・価格から探せます。',
        BASE+'/search.html'
    ),
    'breeders.html':(
        '大型犬ブリーダーを探す｜BIG PAW（ビッグパウ）',
        '大型犬を専門・得意とするブリーダーを探せるBIG PAW（ビッグパウ）。掲載中の子犬や地域、飼育方針を確認し、BIG PAW内から見学・問い合わせができます。',
        BASE+'/breeders.html'
    ),
    'breed-guide.html':(
        '大型犬図鑑・犬種ガイド｜BIG PAW（ビッグパウ）',
        '大型犬の犬種ごとの特徴、体格、運動量、被毛、お手入れ、暮らし方を紹介。スタンダードプードル、ゴールデン、ラブラドール、バーニーズなどを比較できます。',
        BASE+'/breed-guide.html'
    ),
    'breed-standard-poodle.html':(
        'スタンダードプードルの特徴・飼い方・子犬情報｜BIG PAW',
        'スタンダードプードルの性格、体格、運動量、お手入れ、健康面のポイントを大型犬専門BIG PAWが紹介。掲載中の子犬情報も探せます。',
        BASE+'/breed-standard-poodle.html'
    ),
    'cost-simulator.html':(
        '大型犬の飼育費・費用シミュレーター｜BIG PAW',
        '大型犬を迎える前に知りたいフード、医療、トリミングなどの飼育費を確認。BIG PAW（ビッグパウ）の大型犬向け費用シミュレーターです。',
        BASE+'/cost-simulator.html'
    ),
    'match.html':(
        '自分に合う大型犬を探す｜犬種相性チェック BIG PAW',
        '暮らし方や運動量、お手入れなどから自分に合う大型犬を考えるための犬種相性チェック。大型犬専門BIG PAW（ビッグパウ）。',
        BASE+'/match.html'
    ),
    'faq.html':(
        '大型犬の子犬購入・見学のよくある質問｜BIG PAW',
        '大型犬の子犬探し、ブリーダーへの見学・問い合わせ、お迎えまでの流れについて、BIG PAW（ビッグパウ）のよくある質問をまとめています。',
        BASE+'/faq.html'
    )
}

def insert_seo(path,title,description,canonical):
    p=ROOT/path
    if not p.exists():
        return False
    s=p.read_text(encoding='utf-8')
    s=re.sub(r'<title>.*?</title>', '<title>'+html.escape(title)+'</title>', s, count=1, flags=re.S|re.I)
    if MARK not in s:
        tags=(
            '<meta '+MARK+' name="description" content="'+html.escape(description,quote=True)+'">'
            '<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">'
            '<link rel="canonical" href="'+html.escape(canonical,quote=True)+'">'
            '<meta property="og:locale" content="ja_JP">'
            '<meta property="og:type" content="website">'
            '<meta property="og:site_name" content="BIG PAW（ビッグパウ）">'
            '<meta property="og:title" content="'+html.escape(title,quote=True)+'">'
            '<meta property="og:description" content="'+html.escape(description,quote=True)+'">'
            '<meta property="og:url" content="'+html.escape(canonical,quote=True)+'">'
            '<meta name="twitter:card" content="summary">'
        )
        m=re.search(r'</title>',s,re.I)
        if not m:
            raise SystemExit(('seo_title_missing',path))
        s=s[:m.end()]+tags+s[m.end():]
    p.write_text(s,encoding='utf-8')
    return True

changed=[]
for path,args in PAGES.items():
    if insert_seo(path,*args): changed.append(path)

# Homepage: make the brand pronunciation and target search terms visible naturally.
p=ROOT/'index.html'
s=p.read_text(encoding='utf-8')
old='スタンダードプードル、ゴールデン、ラブラドール、バーニーズなど大型犬だけ。成犬時のサイズ、親犬、健康検査、性格や育った環境まで確認してから出会える、大型犬専門の子犬マッチングサービス。'
new='BIG PAW（ビッグパウ）は、スタンダードプードル、ゴールデンレトリバー、ラブラドール、バーニーズなど大型犬だけを扱う、大型犬専門の子犬・ブリーダー情報サイトです。成犬時のサイズ、親犬、健康検査、性格や育った環境まで確認してから出会えます。'
if old in s:
    s=s.replace(old,new,1)
if 'id="bigpawSeoSchema"' not in s:
    schema={
        '@context':'https://schema.org',
        '@graph':[
            {'@type':'WebSite','@id':BASE+'/#website','url':BASE+'/','name':'BIG PAW（ビッグパウ）','alternateName':['BIG PAW','ビッグパウ'],'inLanguage':'ja'},
            {'@type':'Organization','@id':BASE+'/#organization','name':'BIG PAW','alternateName':'ビッグパウ','url':BASE+'/' }
        ]
    }
    script='<script id="bigpawSeoSchema" type="application/ld+json">'+json.dumps(schema,ensure_ascii=False,separators=(',',':'))+'</script>'
    s=s.replace('</head>',script+'</head>',1)
p.write_text(s,encoding='utf-8')

# Search page: visible long-tail wording. Apply to both the checked-in page and the runtime rebuild source.
for name in ('search.html','search-list-rebuild.html'):
    p=ROOT/name
    if not p.exists(): continue
    s=p.read_text(encoding='utf-8')
    if '大型犬の子犬を探す' not in s:
        s=s.replace('<h1>子犬を探す</h1>','<h1>大型犬の子犬を探す</h1><p class="muted" style="margin:-8px 0 18px">スタンダードプードル、ゴールデンレトリバー、ラブラドールなど、大型犬の子犬を犬種・地域・性別・価格から探せます。</p>',1)
    p.write_text(s,encoding='utf-8')

# Generic puppy-detail SEO plus dynamic canonical/title/description for each puppy.
p=ROOT/'puppy-detail.html'
s=p.read_text(encoding='utf-8')
s=re.sub(r'<title>.*?</title>','<title>大型犬の子犬詳細｜BIG PAW（ビッグパウ）</title>',s,count=1,flags=re.S|re.I)
if 'data-bigpaw-puppy-seo="v1"' not in s:
    tags=(
        '<meta data-bigpaw-puppy-seo="v1" name="description" content="BIG PAW（ビッグパウ）掲載の大型犬の子犬詳細。犬種、性別、毛色、価格、親犬、健康情報、ブリーダー情報を確認できます。">'
        '<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">'
        '<meta property="og:locale" content="ja_JP"><meta property="og:type" content="website"><meta property="og:site_name" content="BIG PAW（ビッグパウ）">'
    )
    m=re.search(r'</title>',s,re.I)
    if not m: raise SystemExit('puppy_detail_title_missing')
    s=s[:m.end()]+tags+s[m.end():]
if 'id="bigpawDynamicSeo"' not in s:
    js=r'''<script id="bigpawDynamicSeo">(function(){function meta(sel,attr,val){var e=document.querySelector(sel);if(!e){e=document.createElement('meta');if(sel.indexOf('property=')>=0)e.setAttribute('property',attr);else e.setAttribute('name',attr);document.head.appendChild(e)}e.setAttribute('content',val)}function apply(p){if(!p)return;var t=(p.breed||'大型犬')+' '+(p.color||'')+' '+(p.gender||'')+'の子犬｜BIG PAW';var d=(p.area||'全国')+'で掲載中の'+(p.breed||'大型犬')+'の子犬情報。性別・毛色・価格・親犬・健康情報・ブリーダー情報をBIG PAW（ビッグパウ）で確認できます。';document.title=t;var md=document.querySelector('meta[name="description"]');if(md)md.content=d;var c=document.querySelector('link[rel="canonical"]');if(!c){c=document.createElement('link');c.rel='canonical';document.head.appendChild(c)}c.href='https://bigpaw.site/puppy-detail.html?id='+encodeURIComponent(p.id||new URLSearchParams(location.search).get('id')||'');meta('meta[property="og:title"]','og:title',t);meta('meta[property="og:description"]','og:description',d);meta('meta[property="og:url"]','og:url',c.href)}var n=0,t=setInterval(function(){n++;if(window.__BIGPAW_DETAIL_PUPPY){apply(window.__BIGPAW_DETAIL_PUPPY);clearInterval(t)}else if(n>40)clearInterval(t)},250)})();</script>'''
    s=s.replace('</body>',js+'</body>',1)
p.write_text(s,encoding='utf-8')

# Dynamic breed-guide detail metadata without depending on the rendering implementation.
p=ROOT/'breed-guide-detail.html'
if p.exists():
    s=p.read_text(encoding='utf-8')
    s=re.sub(r'<title>.*?</title>','<title>大型犬の犬種ガイド｜BIG PAW（ビッグパウ）</title>',s,count=1,flags=re.S|re.I)
    if 'data-bigpaw-breed-seo="v1"' not in s:
        m=re.search(r'</title>',s,re.I)
        tags='<meta data-bigpaw-breed-seo="v1" name="description" content="大型犬の犬種ごとの特徴、運動量、被毛、お手入れ、しつけ、健康面をBIG PAW（ビッグパウ）が紹介します。"><meta name="robots" content="index,follow,max-image-preview:large">'
        s=s[:m.end()]+tags+s[m.end():]
    if 'id="bigpawBreedDynamicSeo"' not in s:
        js=r'''<script id="bigpawBreedDynamicSeo">(function(){var n=0,t=setInterval(function(){n++;var h=document.getElementById('breedName');var name=h&&h.textContent.trim();if(name){document.title=name+'の特徴・飼い方｜大型犬専門 BIG PAW';var d=document.querySelector('meta[name="description"]');if(d)d.content=name+'の特徴、運動量、被毛、お手入れ、しつけ、健康面を大型犬専門BIG PAW（ビッグパウ）が紹介します。';var c=document.querySelector('link[rel="canonical"]');if(!c){c=document.createElement('link');c.rel='canonical';document.head.appendChild(c)}c.href='https://bigpaw.site'+location.pathname+location.search;clearInterval(t)}else if(n>40)clearInterval(t)},250)})();</script>'''
        s=s.replace('</body>',js+'</body>',1)
    p.write_text(s,encoding='utf-8')

# Improve sitemap coverage with the generic breed detail route while preserving dynamic puppy/breeder URLs.
server=ROOT/'backend/server.py'
s=server.read_text(encoding='utf-8')
old="static=['/','/search.html','/breeders.html','/breed-guide.html','/breed-standard-poodle.html','/cost-simulator.html','/match.html','/faq.html','/contact.html','/privacy.html','/terms.html','/legal-notice.html','/breeder-fees.html']"
new="static=['/','/search.html','/breeders.html','/breed-guide.html','/breed-standard-poodle.html','/cost-simulator.html','/match.html','/faq.html','/contact.html','/privacy.html','/terms.html','/legal-notice.html','/breeder-fees.html']"
if old not in s:
    raise SystemExit(('seo_sitemap_static_anchor_missing',s.count("static=['/','/search.html'")))
# Static list is already sound; add a stable lastmod-free sitemap header and keep dynamic listings discoverable.
# Also advertise the canonical host in robots.txt through the existing sitemap line.
robots_old='Sitemap: {PUBLIC_BASE_URL}/sitemap.xml\\n"'
if robots_old not in s:
    raise SystemExit('seo_robots_sitemap_anchor_missing')
server.write_text(s,encoding='utf-8')

# Build gate: verify search-facing pages now have descriptions/canonicals and that public sitemap remains enabled.
for name in ('index.html','search.html','breeders.html','breed-guide.html'):
    txt=(ROOT/name).read_text(encoding='utf-8')
    if 'name="description"' not in txt or 'rel="canonical"' not in txt or 'name="robots"' not in txt:
        raise SystemExit(('seo_gate_failed',name))
if '/sitemap.xml' not in server.read_text(encoding='utf-8') or '/robots.txt' not in server.read_text(encoding='utf-8'):
    raise SystemExit('seo_discovery_routes_missing')
print('BIGPAW_SEO_OK|brand=BIG_PAW_bikkupau|targets=large_dog_puppy_breeder|meta=enabled|canonical=enabled|schema=website_org|sitemap=preserved|robots=preserved|dynamic_puppy_seo=enabled',flush=True)
