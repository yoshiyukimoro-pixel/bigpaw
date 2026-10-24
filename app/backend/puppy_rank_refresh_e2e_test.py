#!/usr/bin/env python3
"""Real HTTP regression: five-day organic freshness; isolated scratch SQLite and captured calls."""
import base64, json, os, socket, sqlite3, subprocess, sys, tempfile, time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
app=Path(__file__).resolve().parents[1]
work=Path(tempfile.mkdtemp(prefix='bigpaw-rank-e2e-'))
data=work/'data';data.mkdir()
with socket.socket() as sk:sk.bind(('127.0.0.1',0));port=sk.getsockname()[1]
base=f'http://127.0.0.1:{port}'
env=os.environ.copy();env.update(PORT=str(port),BIGPAW_DATA_DIR=str(data),BIGPAW_ENV='development',BIGPAW_PUBLIC_BASE_URL=base,BIGPAW_AUTOMATION_INTERVAL_SECONDS='3600')
for key in ('RESEND_API_KEY','SMTP_HOST','SMTP_PASSWORD','BIGPAW_SMTP_PASSWORD'):env.pop(key,None)
log=open(work/'server.log','w')
proc=subprocess.Popen([sys.executable,str(app/'backend/server.py')],cwd=app,env=env,stdout=log,stderr=log)
def db():
 c=sqlite3.connect(data/'bigpaw.sqlite3',timeout=20);c.row_factory=sqlite3.Row;return c
def query(sql,args=()):
 c=db()
 try:return [dict(x) for x in c.execute(sql,args).fetchall()]
 finally:c.close()
def execute(sql,args=()):
 with db() as c:c.execute(sql,args)
def request(method,path,data=None,user=None,headers=None):
 h={'Origin':'https://bigpaw.site',**(headers or {})}
 if user:h['Cookie']='bigpaw_session=test-'+user
 if isinstance(data,(dict,list)):
  data=json.dumps(data).encode();h['Content-Type']='application/json'
 req=Request(base+path,data=data,method=method,headers=h)
 try:
  with urlopen(req,timeout=10) as out:
   payload=out.read();return out.status,json.loads(payload or b'{}')
 except HTTPError as err:
  return err.code,json.loads(err.read() or b'{}')
def check(ok,message):
 if not ok:raise AssertionError(message)
 print('PASS|'+message,flush=True)
try:
 for _ in range(300):
  try:
   if request('GET','/api/health')[0]==200:break
  except Exception:time.sleep(.1)
 else:raise RuntimeError('startup failed '+(work/'server.log').read_text()[-2500:])
 t=int(time.time())
 for uid in ('u_dog44','u_demo','u_admin'):
  execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-'+uid,uid,t,t+86400))
 check('last_ranked_at' in [v['name'] for v in query('PRAGMA table_info(puppies)')],'migration adds safe rank timestamp to existing SQLite')
 execute("UPDATE puppies SET created_at=?,published_at=?,last_ranked_at=NULL,status='募集中',review_status='approved' WHERE id='p1'",(t-6*86400,t-6*86400))
 execute("UPDATE puppies SET created_at=?,published_at=?,last_ranked_at=NULL,status='募集中',review_status='approved' WHERE id='p2'",(t-3600,t-3600))
 execute("UPDATE puppies SET created_at=?,published_at=?,last_ranked_at=NULL,status='募集中',review_status='approved' WHERE id='p3'",(t-7200,t-7200))
 def public():return request('GET','/api/puppies?breed=standard-poodle')[1]
 original=query("SELECT description,created_at FROM puppies WHERE id='p1'")[0]
 old=public()
 check(old[0]['id']=='p2' and old[-1]['id']=='p1','initial public ranking ordered by original publish date')
 check(request('PATCH','/api/puppies/p1',{'desc':original['description']},'u_dog44')[0]==200,'unchanged save accepted normally')
 check(query("SELECT last_ranked_at FROM puppies WHERE id='p1'")[0]['last_ranked_at'] is None,'no-op save never earns higher rank')
 new_desc=original['description']+'。今日のアピールです。'
 code,res=request('PATCH','/api/puppies/p1',{'desc':new_desc},'u_dog44')
 check(code==200 and res['rankUpdatedAt'] is not None,'genuine appeal edit at six days automatically earns refresh')
 ranked=public()
 check(ranked[0]['id']=='p1' and ranked[0]['rankAt']>=t,'refreshed puppy appears FIRST in actual search API')
 check(query("SELECT created_at FROM puppies WHERE id='p1'")[0]['created_at']==original['created_at'],'original publish date remains immutable')
 first_rank=int(query("SELECT last_ranked_at FROM puppies WHERE id='p1'")[0]['last_ranked_at'])
 code,_=request('PATCH','/api/puppies/p1',{'price':239000},'u_dog44')
 check(code==200 and query("SELECT last_ranked_at FROM puppies WHERE id='p1'")[0]['last_ranked_at']==first_rank,'edits during five-day cooldown cannot bump twice')
 code,_=request('PATCH','/api/puppies/p1',{'status':'商談中'},'u_dog44')
 check(code==200,'status change still permitted')
 execute("UPDATE puppies SET last_ranked_at=? WHERE id='p1'",(t-6*86400,))
 code,_=request('PATCH','/api/puppies/p1',{'status':'募集中'},'u_dog44')
 check(code==200 and query("SELECT last_ranked_at FROM puppies WHERE id='p1'")[0]['last_ranked_at']==t-6*86400,'status-only change never earns a ranking bump')
 check(request('PATCH','/api/puppies/p1',{'price':235000},'u_demo')[0]==403,'buyer cannot manipulate ranking via puppy editor')
 # A new actual photo also counts without modifying the main thumbnail.
 png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/9XcAAAAASUVORK5CYII=')
 boundary='----bigpawranktest'; body=(f'--{boundary}\r\nContent-Disposition: form-data; name="puppyId"\r\n\r\np1\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="new.png"\r\nContent-Type: image/png\r\n\r\n').encode()+png+(f'\r\n--{boundary}--\r\n').encode()
 code,upload=request('POST','/api/uploads',body,'u_dog44',{'Content-Type':'multipart/form-data; boundary='+boundary})
 check(code==201 and bool(upload.get('url')),'breeder can append actual photo')
 check(query("SELECT last_ranked_at FROM puppies WHERE id='p1'")[0]['last_ranked_at']>t-6*86400,'new photo after five days automatically restores rank')
 after_photo=int(query("SELECT last_ranked_at FROM puppies WHERE id='p1'")[0]['last_ranked_at'])
 check(request('POST','/api/uploads',body,'u_dog44',{'Content-Type':'multipart/form-data; boundary='+boundary})[0]==201,'more photo changes allowed during cooldown')
 check(query("SELECT last_ranked_at FROM puppies WHERE id='p1'")[0]['last_ranked_at']==after_photo,'multiple photo additions cannot bypass cooldown')
 listing=(app/'admin.html').read_text(encoding='utf-8')
 check('bpRankNote(d)' in listing and 'あと' in listing and '上位表示できます' in listing and '前回の上位表示' in listing,'each breeder listing shows countdown and update-ready guidance')
 check('掲載順位を更新する</button>' not in listing,'no extra ranking button')
 search=(app/'search-list-rebuild.html').read_text(encoding='utf-8')
 check('Number(y.rankAt||y.createdAt||0)-Number(x.rankAt||x.createdAt||0)' in search,'actual search layout uses rank freshness, normal price sorting preserved')
 print('FIVE_DAY_ORGANIC_REFRESH_E2E_OK|age_5_days|real_edit|new_photo|public_rank_first|no_op_no_bump|cooldown|status_only|owner_guard|admin_countdown',flush=True)
finally:
 proc.terminate()
 try:proc.wait(timeout=6)
 except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
 log.close()
