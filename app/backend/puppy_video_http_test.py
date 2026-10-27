"""Isolated HTTP integration regression for BIG PAW puppy video support.

Never touches production or the real Cloudflare API. A local mock Stream API is used.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_DIR=Path(__file__).resolve().parents[1]


def check(condition,message):
    if not condition:
        raise AssertionError(message)


def call(base,method,path,body=None,token=None,expected=200):
    req=Request(base+path,method=method)
    req.add_header('Accept','application/json')
    if token:
        req.add_header('Authorization','Bearer '+token)
    if body is not None:
        req.add_header('Content-Type','application/json')
        req.data=json.dumps(body,ensure_ascii=False).encode()
    try:
        with urlopen(req,timeout=8) as response:
            code=response.status; raw=response.read()
    except HTTPError as exc:
        code=exc.code; raw=exc.read()
    check(code==expected,f'{method} {path}: expected {expected}, got {code}: '+raw.decode(errors='replace')[:500])
    return json.loads(raw or b'{}')


class MockStream:
    def __init__(self):
        self.lock=threading.Lock()
        self.direct_payloads=[]
        self.deleted=[]
        self.counter=0
        self.base=''

    def next_uid(self):
        with self.lock:
            self.counter+=1
            return f'testvideo{self.counter:02d}abcdefgh'

    def details(self,uid):
        if uid=='notuploaded1':
            return {'uid':uid,'duration':None,'readyToStream':False,'status':{'state':'pendingupload'},'meta':{'puppyId':'p1'}}
        if uid=='exact60video1':
            return {'uid':uid,'duration':60.0,'readyToStream':True,'status':{'state':'ready'},'meta':{'puppyId':'p1'}}
        if uid=='slightlylong1':
            return {'uid':uid,'duration':60.01,'readyToStream':True,'status':{'state':'ready'},'meta':{'puppyId':'p1'}}
        if uid=='longvideo1':
            return {'uid':uid,'duration':61.0,'readyToStream':True,'status':{'state':'ready'},'meta':{'puppyId':'p1'}}
        if uid=='otherpuppy1':
            return {'uid':uid,'duration':12.0,'readyToStream':True,'status':{'state':'ready'},'meta':{'puppyId':'p2'}}
        if uid=='secondvideo1':
            return {'uid':uid,'duration':18.5,'readyToStream':True,'status':{'state':'ready'},'meta':{'puppyId':'p1'}}
        return {'uid':uid,'duration':59.4,'readyToStream':True,'status':{'state':'ready'},'meta':{'puppyId':'p1'}}


def mock_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            return
        def send_json(self,payload,status=200):
            raw=json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def do_POST(self):
            if self.path=='/client/v4/accounts/test-account/stream/direct_upload':
                n=int(self.headers.get('Content-Length','0'))
                payload=json.loads(self.rfile.read(n) or b'{}')
                with state.lock:
                    state.direct_payloads.append({'payload':payload,'authorization':self.headers.get('Authorization','')})
                uid=state.next_uid()
                return self.send_json({'success':True,'result':{'uid':uid,'uploadURL':state.base+'/direct-upload/'+uid}})
            self.send_json({'success':False,'errors':[{'message':'not_found'}]},404)
        def do_GET(self):
            prefix='/client/v4/accounts/test-account/stream/'
            if self.path.startswith(prefix):
                uid=self.path[len(prefix):]
                return self.send_json({'success':True,'result':state.details(uid)})
            self.send_json({'success':False,'errors':[{'message':'not_found'}]},404)
        def do_DELETE(self):
            prefix='/client/v4/accounts/test-account/stream/'
            if self.path.startswith(prefix):
                uid=self.path[len(prefix):]
                with state.lock:
                    state.deleted.append(uid)
                return self.send_json({'success':True,'result':''})
            self.send_json({'success':False,'errors':[{'message':'not_found'}]},404)
    return Handler


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def main():
    state=MockStream()
    mock_port=free_port()
    state.base=f'http://127.0.0.1:{mock_port}'
    mock=ThreadingHTTPServer(('127.0.0.1',mock_port),mock_handler(state))
    mock_thread=threading.Thread(target=mock.serve_forever,daemon=True)
    mock_thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='bigpaw-puppy-video-') as td:
            port=free_port()
            base=f'http://127.0.0.1:{port}'
            env=dict(os.environ,PORT=str(port),BIGPAW_ENV='development',BIGPAW_DATA_DIR=td,
                     BIGPAW_PUBLIC_BASE_URL=base,BIGPAW_DEV_LINKS='0',
                     BIGPAW_AUTOMATION_INTERVAL_SECONDS='86400',
                     BIGPAW_CLOUDFLARE_STREAM_ACCOUNT_ID='test-account',
                     BIGPAW_CLOUDFLARE_STREAM_API_TOKEN='test-token',
                     BIGPAW_CLOUDFLARE_STREAM_CUSTOMER_CODE='testcustomer',
                     BIGPAW_CLOUDFLARE_STREAM_API_BASE=state.base+'/client/v4')
            proc=subprocess.Popen([sys.executable,str(BASE_DIR/'backend'/'server.py')],
                                  cwd=str(BASE_DIR),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
            try:
                for _ in range(120):
                    if proc.poll() is not None:
                        raise AssertionError('server stopped during startup: '+str(proc.returncode))
                    try:
                        if call(base,'GET','/api/health')['ok']:
                            break
                    except (URLError,AssertionError,TimeoutError):
                        time.sleep(.25)
                else:
                    raise AssertionError('server health timeout')

                buyer=call(base,'POST','/api/login',{'email':'demo@bigpaw.jp','password':'demo1234'})['token']
                breeder=call(base,'POST','/api/login',{'email':'dog44@bigpaw.jp','password':'demo1234'})['token']
                operator=call(base,'POST','/api/login',{'email':'admin@bigpaw.jp','password':'admin1234'})['token']
                check(bool(buyer and breeder and operator),'demo auth')

                # Existing product surfaces must remain available before video operations.
                check(call(base,'GET','/api/puppies'),'existing puppy API')
                check(call(base,'GET','/api/planned-litters')==[],'planned-litter API remains available')
                check(isinstance(call(base,'GET','/api/puppies/p1/photos',token=breeder),list),'photo API remains available')

                check(call(base,'POST','/api/puppies/p1/video-upload',{'fileName':'x.mov','fileSize':12345},buyer,403)['error']=='forbidden','buyer cannot provision video')
                too_big=200*1024*1024+1
                check(call(base,'POST','/api/puppies/p1/video-upload',{'fileName':'huge.mov','fileSize':too_big},breeder,413)['error']=='video_file_too_large','basic upload size guard')

                ticket=call(base,'POST','/api/puppies/p1/video-upload',{'fileName':'puppy.mov','fileSize':50*1024*1024},breeder,201)
                check(ticket['maxSeconds']==60 and ticket['uid'].startswith('testvideo'),'ticket created')
                payload=state.direct_payloads[-1]
                check(payload['authorization']=='Bearer test-token','Cloudflare token stays server-side')
                check(payload['payload']['maxDurationSeconds']==60,'Cloudflare duration hard limit')
                check(payload['payload']['meta']['puppyId']=='p1','ticket tied to puppy')
                check('127.0.0.1' in payload['payload']['allowedOrigins'],'allowed origin derived')

                attached=call(base,'POST','/api/puppies/p1/video',{'uid':ticket['uid']},breeder,201)
                check(attached['videoUid']==ticket['uid'],'video attached to owner puppy')
                check(attached['reviewStatus']=='approved','approved breeder video edit stays public')
                public=call(base,'GET','/api/puppies/p1')
                check(public['videoUid']==ticket['uid'],'approved video public')
                check(public['videoEmbedUrl']==f'https://customer-testcustomer.cloudflarestream.com/{ticket["uid"]}/iframe','public embed URL')
                check(public['videoThumbnailUrl'].endswith('/thumbnails/thumbnail.jpg'),'thumbnail URL')
                page=urlopen(base+'/puppy-detail.html',timeout=7).read().decode('utf-8','replace')
                check('puppy-video-public.js' in page,'public detail loads additive video renderer')
                headers=Request(base+'/puppy-detail.html',method='GET')
                with urlopen(headers,timeout=7) as response:
                    csp=response.headers.get('Content-Security-Policy','')
                check('frame-src' in csp and 'cloudflarestream.com' in csp,'CSP allows Stream iframe')
                check('https://videodelivery.net' in csp,'CSP allows Stream fallback domain without subdomain')
                check('connect-src' in csp and 'videodelivery.net' in csp,'CSP allows direct Stream upload')

                # An issued upload ticket without uploaded bytes cannot appear saved.
                pending=call(base,'POST','/api/puppies/p1/video',{'uid':'notuploaded1'},breeder,409)
                check(pending['error']=='video_upload_not_received','unused Stream upload ticket rejected')
                check(call(base,'GET','/api/puppies/p1')['videoUid']==ticket['uid'],'rejecting pending upload preserves existing video')

                exact=call(base,'POST','/api/puppies/p1/video',{'uid':'exact60video1'},operator,201)
                check(exact['videoUid']=='exact60video1','backend accepts exactly 60.0-second video')
                check(call(base,'POST','/api/puppies/p1/video',{'uid':'slightlylong1'},operator,400)['error']=='video_too_long','backend rejects 60.01-second video')
                check('slightlylong1' in state.deleted,'slightly overlong Cloudflare object cleaned')
                check(call(base,'POST','/api/puppies/p1/video',{'uid':'longvideo1'},operator,400)['error']=='video_too_long','backend rejects >60 second video')
                check('longvideo1' in state.deleted,'overlong Cloudflare object cleaned')
                check(call(base,'POST','/api/puppies/p1/video',{'uid':'otherpuppy1'},operator,403)['error']=='video_puppy_mismatch','cannot attach video ticket for another puppy')

                replaced=call(base,'POST','/api/puppies/p1/video',{'uid':'secondvideo1'},operator,201)
                check(replaced['videoUid']=='secondvideo1','one-video replacement')
                check(ticket['uid'] in state.deleted,'old Stream video deleted on replacement')
                check(call(base,'GET','/api/puppies/p1')['videoUid']=='secondvideo1','public exposes only replacement')

                # Create a different approved kennel and prove it cannot manage p1 video.
                con=sqlite3.connect(str(Path(td)/'bigpaw.sqlite3'))
                pw='other-video-pass-1234'; salt=secrets.token_hex(16)
                digest=hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),180000).hex()
                con.execute("INSERT INTO users (id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            ('u_other','breeder','other-video@bigpaw.jp','他犬舎','担当','他犬舎',salt,digest,int(time.time())))
                con.execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES (?,?,?,?,?,?,?)",
                            ('b_other','u_other','他の犬舎','東京都','','','approved'))
                con.commit(); con.close()
                other=call(base,'POST','/api/login',{'email':'other-video@bigpaw.jp','password':pw})['token']
                check(call(base,'POST','/api/puppies/p1/video-upload',{'fileName':'steal.mov','fileSize':1000},other,403)['error']=='forbidden','other kennel cannot provision video')
                check(call(base,'DELETE','/api/puppies/p1/video',token=other,expected=403)['error']=='forbidden','other kennel cannot delete video')

                removed=call(base,'DELETE','/api/puppies/p1/video',token=breeder)
                check(removed['ok'] is True,'owner deletes video')
                check('secondvideo1' in state.deleted,'deleted Stream object on remove')
                mine=call(base,'GET','/api/breeder/puppies',token=breeder)
                p1=next(x for x in mine if x['id']=='p1')
                check(p1['videoUid']=='' and p1['videoEmbedUrl']=='','DB cleared after video delete')
                check(call(base,'GET','/api/puppies/p1')['videoUid']=='','public video removed without harming listing')

                print('PUPPY_VIDEO_HTTP_INTEGRATION_OK: 1 video, 60s hard limit, ownership, moderation, replace/delete, public embed, existing APIs')
            finally:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait(timeout=5)
    finally:
        mock.shutdown();mock.server_close()


if __name__=='__main__':
    main()
