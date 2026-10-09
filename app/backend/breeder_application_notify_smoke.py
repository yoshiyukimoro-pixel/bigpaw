#!/usr/bin/env python3
"""Smoke test breeder application and operator notification on an isolated server."""
import json
import sys
import urllib.request
import urllib.error
import uuid

base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8080'

def call(method,path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode('utf-8')
    req=urllib.request.Request(base+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=8) as r:
            return r.status,json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read() or b'{}')

def ok(cond,description):
    assert cond,description
    print('OK|'+description,flush=True)

status,_=call('GET','/api/health')
ok(status==200,'health')
status,_=call('POST','/api/breeder-applications',{})
ok(status==401,'anonymous_rejected')
email='notify-smoke-'+uuid.uuid4().hex[:10]+'@example.test'
password='Notification123!'
status,_=call('POST','/api/register',{'email':email,'password':password,'last':'試験','first':'申請','agreeTerms':True,'agreePrivacy':True})
ok(status==201,'buyer_registration')
status,login=call('POST','/api/login',{'email':email,'password':password})
ok(status==200 and bool(login.get('token')),'buyer_login')
token=login['token']
status,ver=call('POST','/api/email-verification/request',{},token)
ok(status==200 and bool(ver.get('devToken')),'verification_link')
status,_=call('POST','/api/email-verification/confirm',{'token':ver['devToken']},token)
ok(status==200,'email_verified')
app={'kennelName':'通知検証犬舎','representative':'試験 太郎','prefecture':'埼玉県','primaryBreed':'スタンダードプードル','registrationNo':'TEST-001','expiresOn':'2027-10-10','registrationProofUrl':'/uploads/test-proof.jpg'}
status,error=call('POST','/api/breeder-applications',app,token)
ok(status==400 and error.get('error')=='commission_terms_consent_required','fee_terms_required_'+str(status)+'_'+str(error.get('error')))
app['agreeCommissionTerms']=True
status,submitted=call('POST','/api/breeder-applications',app,token)
ok(status==201 and submitted.get('status')=='pending','application_created')
status,admin=call('POST','/api/login',{'email':'admin@bigpaw.jp','password':'admin1234'})
ok(status==200 and bool(admin.get('token')),'operator_login')
status,notices=call('GET','/api/notifications',token=admin['token'])
ok(status==200 and any(n.get('kind')=='breeder_application' for n in notices),'operator_notification_saved')
status,applications=call('GET','/api/breeder-applications',token=admin['token'])
ok(status==200 and any(a.get('id')==submitted['id'] for a in applications),'operator_sees_application')
print('BREEDER_APPLICATION_NOTIFY_SMOKE_OK',flush=True)
