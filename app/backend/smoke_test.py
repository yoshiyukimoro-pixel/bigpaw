#!/usr/bin/env python3
import json, sys, urllib.request, urllib.error, uuid
BASE=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8080'

def req(method,path,body=None,token=None):
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
    r=urllib.request.Request(BASE+path,data=data,method=method,headers={'Content-Type':'application/json'})
    if token:r.add_header('Authorization','Bearer '+token)
    try:
        with urllib.request.urlopen(r,timeout=5) as x:
            raw=x.read(); return x.status,json.loads(raw or b'{}')
    except urllib.error.HTTPError as e:
        raw=e.read(); return e.code,json.loads(raw or b'{}')

def req_text(method,path,body=None,token=None):
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
    r=urllib.request.Request(BASE+path,data=data,method=method,headers={'Content-Type':'application/json'})
    if token:r.add_header('Authorization','Bearer '+token)
    try:
        with urllib.request.urlopen(r,timeout=5) as x:
            return x.status,x.read().decode('utf-8','replace')
    except urllib.error.HTTPError as e:
        return e.code,e.read().decode('utf-8','replace')

def ok(cond,msg):
    if not cond: raise AssertionError(msg)
    print('✓',msg)

st,h=req('GET','/api/health');ok(st==200 and h.get('version')=='1.0','health v1.0')
email='smoke-'+uuid.uuid4().hex[:8]+'@example.test'; pw='Smoke1234!'
st,r=req('POST','/api/register',{'email':email,'password':pw,'last':'試験','first':'太郎','agreeTerms':True,'agreePrivacy':True});ok(st==201,'buyer registration')
st,r=req('POST','/api/login',{'email':email,'password':pw});ok(st==200 and r.get('token'),'buyer login'); buyer=r['token']
st,r=req('POST','/api/email-verification/request',{},buyer);ok(st==200 and r.get('devToken'),'verification token issued')
st,r=req('POST','/api/email-verification/confirm',{'token':r['devToken']});ok(st==200,'email verified')
st,r=req('POST','/api/password-reset/request',{'email':email});ok(st==200 and r.get('devToken'),'reset token issued')
st,r=req('POST','/api/password-reset/confirm',{'token':r['devToken'],'password':'Smoke5678!'});ok(st==200,'password reset')
st,r=req('POST','/api/login',{'email':email,'password':'Smoke5678!'});ok(st==200,'login with new password'); buyer=r['token']

app={'kennelName':'SMOKE犬舎','representative':'試験 太郎','prefecture':'埼玉県','primaryBreed':'スタンダードプードル','registrationNo':'SMOKE-001','expiresOn':'2027-12-31','profile':'料金同意テスト','registrationProofUrl':'/uploads/smoke-registration-proof.jpg'}
st,r=req('POST','/api/breeder-applications',app,buyer);ok(st==400 and r.get('error')=='commission_terms_consent_required','breeder fee consent required')
app['agreeCommissionTerms']=True
st,r=req('POST','/api/breeder-applications',app,buyer);ok(st==201,'breeder fee terms accepted with application')

st,r=req('POST','/api/login',{'email':'dog44@bigpaw.jp','password':'demo1234'});ok(st==200,'breeder login'); breeder=r['token']
st,r=req('POST','/api/puppies',{'breed':'スタンダードプードル','breedKey':'standard','gender':'男の子','color':'ブラック','price':299000,'area':'埼玉県','areaKey':'saitama','name':'審査テスト犬','desc':'掲載審査テスト'} ,breeder);ok(st==201 and r.get('reviewStatus')=='pending','new breeder listing is pending'); pid=r['id']
st,public=req('GET','/api/puppies');ok(all(x['id']!=pid for x in public),'pending listing hidden from public')
st,mine=req('GET','/api/breeder/puppies',token=breeder);ok(any(x['id']==pid for x in mine),'pending listing visible to breeder')

st,r=req('POST','/api/login',{'email':'admin@bigpaw.jp','password':'admin1234'});ok(st==200,'operator login'); admin=r['token']
st,l=req('GET','/api/operator/listings',token=admin);ok(any(x['id']==pid for x in l),'operator sees pending listing')
st,r=req('PATCH','/api/operator/listings/'+pid,{'reviewStatus':'approved','moderationNote':'smoke test approved'},admin);ok(st==200 and r.get('reviewStatus')=='approved','operator approves listing')
st,public=req('GET','/api/puppies');ok(any(x['id']==pid for x in public),'approved listing public')

# Completion-report workflow: breeder reports a sale, operator confirms it, 5% invoice is created.
st,x=req('PATCH','/api/puppies/'+pid,{'status':'成約済み'},breeder);ok(st==409 and x.get('error')=='completion_report_required','breeder cannot bypass completion report with sold status')
st,q=req('POST','/api/inquiries',{'puppyId':pid,'name':'試験 太郎','email':email,'preferredDate':'2026-09-20','message':'成約申請の動作確認'},buyer);ok(st==201,'buyer inquiry for completion report'); qid=q['id']
st,d=req('POST','/api/inquiries/'+qid+'/deal',{},breeder);ok(st in (200,201) and d.get('id'),'breeder creates deal'); did=d['id']
st,x=req('POST','/api/deals/'+did+'/pickup',{'date':'2026-09-20','complete':True},breeder);ok(st==409 and x.get('error')=='completion_report_required','breeder cannot directly complete sale')
st,cr=req('POST','/api/deals/'+did+'/completion-report',{'finalSaleAmount':299000,'pickupDate':'2026-09-20','buyerName':'試験 太郎','note':'smoke completion'},breeder);ok(st==201 and cr.get('status')=='pending','breeder submits completion report')
st,rs=req('GET','/api/operator/deal-reports',token=admin);ok(any(x['id']==cr['id'] and x['status']=='pending' for x in rs),'operator sees pending completion report')
st,ap=req('PATCH','/api/operator/deal-reports/'+cr['id'],{'action':'approve','reviewNote':'確認済み'},admin);ok(st==200 and ap.get('status')=='approved','operator approves completion report')
st,inv=req('GET','/api/breeder/invoices',token=breeder);ok(any(x['deal_id']==did and x['fee_amount']==14950 for x in inv),'5 percent invoice created after approval')
st,summary=req('GET','/api/deals/'+did+'/summary',token=buyer);ok(st==200 and summary['deal']['status']=='completed','deal completed after approval')

st,r=req('POST','/api/reports',{'puppyId':pid,'reason':'動作確認','detail':'smoke test report'},buyer);ok(st==201,'report created')
st,reps=req('GET','/api/operator/reports',token=admin);ok(any(x['id']==r['id'] for x in reps),'operator sees report')
st,bk=req('POST','/api/operator/backup',{},admin);ok(st==201 and bk.get('filename'),'backup created')
st,a=req('GET','/api/operator/audit',token=admin);ok(st==200 and len(a)>0,'audit log available')
# Support/contact workflow.
st,sup=req('POST','/api/support',{'name':'試験 太郎','email':email,'category':'サイト利用について','subject':'smoke support','message':'support workflow test'});ok(st==201 and sup.get('id'),'anonymous support ticket created')
st,sups=req('GET','/api/operator/support',token=admin);ok(any(x['id']==sup['id'] for x in sups),'operator sees support ticket')
st,sup2=req('PATCH','/api/operator/support/'+sup['id'],{'status':'resolved','operatorNote':'smoke resolved'},admin);ok(st==200 and sup2.get('status')=='resolved','operator resolves support ticket')
# Public crawler/static security endpoints.
st,robots=req_text('GET','/robots.txt');ok(st==200 and 'Sitemap:' in robots and 'Disallow: /api/' in robots,'robots.txt available')
st,sitemap=req_text('GET','/sitemap.xml');ok(st==200 and '<urlset' in sitemap and 'operator-admin' not in sitemap,'public sitemap generated')
st,blocked=req_text('GET','/backend/server.py');ok(st==404,'backend source blocked from static web')
print('ALL SMOKE TESTS PASSED')
