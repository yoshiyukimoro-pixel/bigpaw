#!/usr/bin/env python3
"""One-time REAL Stream tus/upload/playback smoke check on a synthetic 1-second video.

Uses only 1.7 KB of generated non-user media in memory. The sample is deleted
from Cloudflare in finally. Never store or transmit user's videos via Railway.
Never emit credentials, UID, or signed tus URL to logs.
"""
import os, re, json, base64, zlib, time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import quote,urlsplit

MARKER='.bigpaw-tus-live-smoke-20261027-v1.json'
DATA='eNp9VM1vG0UUHyekKl8igqDmEIkBoioSsbNjO65jsVKDKfWBSlwoHwKW2dlZ7+LdncnM2LF7osABrghFiEPFhUNUIi5ISEiolcqt/AGNQEIIhEBIIE70Qs2btd04AbramfnNm9/7mvd2EUI4NAMZa5EiNIPsCqNMe4ykskoQmu2mQvQQQknaiwJ06Jn9JR8FZN+Dp3CYdXR/Gt3xmYH3Y6NoB/ArppP7nP23Nev7zn7+0+/rtwNY5oHRsC7xRJsDDWt3fqw7s5gGMQWA0+Bo7iv5eP7rfFOMgkRNTnpxwKeZ52EvWjQLEm45hWtpnIUAFnppbnQ6zOVgdLYUKB5OpXFfVyV4hAtva+MngK9oo4Mpzme2aP9zFTbx06gFa2vCePhZ4NdIiWyUiENwEvv9cq06pbE4HMK8DqxmIUD3DH9Ai21YP91/5uTVp21N7rLTypOtnRcL6Fj024/XH7v6982bVnVeUi3HYdix4Bs1vuPF/sS8Nvn9T8KdQ+i4xQuQ1rTcjjo74M6NZPPj8xV0eD/Ry20tgS12xNZYH63A2YWpdEE+8y2sD8C43175eEA8TEz1xyew0m5gbF+8lPJ8tc+j0z0AfaOolMl0BVbjUaMt7xoh8hrTXDkPGooRQjFOQS0qsD0eKg5NNHsiBRIEtndsbjjc/e7Mr1/9vN/6Ymf1Bt5//Pc/bMFwETOhOCYAVYU4dVwhnGyEG3DQKgFh7dxzZ84Wq3jzfBOYAWdw0BRykPDQ4LLjVIplp1wBYWSMbKytbW9vl2wLi4RmJaHaa9ZLKTJpAhwhTSwy3cCM+pS5BEObuhUccD8RrOOShtNwMM1oMtDcdfqVhtMnpIJT7ka8j3XXB3QKSz0AVZg9Fbik5IASTDiN+zzwrEUCGp6iWZu7pIZZpERKPVAl2CieJLEGVO/XA2YAsK3UdSAEGlwQGXfLZJUQHFJtPKk7sbSMkYEt6Ykw1Ny4xTI2kQIN7ZZxIkSHRrDxJjKCdRIzfiBwcKZyHyxOqbFxxJnhKqFAArmfdBUdeEykkhrYM7gi+IPFGZgAoqKWEyqacg2X5XtyADgOwLfv0YBKm4Xv+TG1nqBzeJ7XNo/bkfEBCckzry0knI6EElQ7fAC23fK6M4Ye/FfcdawZzzjrGrfq4Ny5vVHFdQTainm3s7XnirlMhTiFz5PbrGDjlislB2/ZXFynVAMord18pX23tgFAGy7dKo4l1Aj6AUoItugWlN8WE70JDXySv/sOenB466+97y+eu/bEeufLF+qfX7/8/gdX+KtnefuhPz9875vXTlwG5r2bHy0nzeGt3Z2X7Y/57s1LT/XfegT9dNF+BoVL1DSHhb0RZm9Y/A/sfIO3'

def run(env=None,fetch=urlopen,out=print):
    e=env or os.environ
    account=str(e.get('BIGPAW_CLOUDFLARE_STREAM_ACCOUNT_ID') or '').strip()
    token=str(e.get('BIGPAW_CLOUDFLARE_STREAM_API_TOKEN') or '').strip()
    home=str(e.get('BIGPAW_DATA_DIR') or '').strip()
    if not (account and token and home):return
    marker=Path(home)/MARKER
    if marker.exists():return
    base=str(e.get('BIGPAW_CLOUDFLARE_STREAM_API_BASE') or 'https://api.cloudflare.com/client/v4').rstrip('/')
    media=zlib.decompress(base64.b64decode(DATA))
    root=base+'/accounts/'+quote(account,safe='')+'/stream'
    hdr={'Authorization':'Bearer '+token,'Tus-Resumable':'1.0.0',
         'Upload-Length':str(len(media)),
         'Upload-Metadata':'name '+base64.b64encode(b'bigpaw-auto-smoke-1s.mp4').decode()+
                            ',maxdurationseconds '+base64.b64encode(b'60').decode(),
         'Upload-Creator':'bigpaw-smoke-no-user'}
    uid=''
    result={'phase':'unknown'}
    try:
        with fetch(Request(root+'?direct_user=true',data=b'',headers=hdr,method='POST'),timeout=20) as resp:
            uid=str(resp.headers.get('stream-media-id') or '')
            location=str(resp.headers.get('Location') or '')
            if resp.status!=201:raise RuntimeError('tus_create_bad_http')
        loc=urlsplit(location)
        if not re.fullmatch('[A-Za-z0-9_-]{8,64}',uid) or loc.scheme!='https' or loc.hostname not in ('upload.cloudflarestream.com','upload.videodelivery.net'):
            raise RuntimeError('tus_bad_direct_url_or_uid')
        result={'phase':'tus_ticket_created','host':loc.hostname}
        update={'meta':{'puppyId':'bigpaw-smoke-only','name':'automated-test'},
                'maxDurationSeconds':60,'requireSignedURLs':False}
        with fetch(Request(root+'/'+quote(uid,safe=''),
             data=json.dumps(update).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},
             method='POST'),timeout=20) as resp:
            payload=json.loads(resp.read(20000) or b'{}')
            if not payload.get('success',True):raise RuntimeError('tus_metadata_failed')
        result['phase']='metadata_updated'
        with fetch(Request(location,data=media,method='PATCH',headers={
             'Tus-Resumable':'1.0.0','Upload-Offset':'0',
             'Content-Type':'application/offset+octet-stream'}),timeout=30) as resp:
            received=int(resp.headers.get('Upload-Offset') or '-1')
            if resp.status!=204 or received!=len(media):raise RuntimeError('tus_patch_not_accepted')
        result['phase']='bytes_received'
        for _ in range(15):
            with fetch(Request(root+'/'+quote(uid,safe=''),
                 headers={'Authorization':'Bearer '+token},method='GET'),timeout=10) as resp:
                status=json.loads(resp.read(30000) or b'{}').get('result',{})
            state=str((status.get('status') or {}).get('state') or '').lower()
            if state and state!='pendingupload':
                result['phase']='processed_or_queued'
                result['state']=state if state in ('queued','inprogress','ready','error','downloading') else 'other'
                if state=='ready':
                    try:
                        with fetch(Request('https://videodelivery.net/'+quote(uid,safe='')+'/iframe',
                             method='GET'),timeout=15) as player:
                            result['player_http_ok']=(player.status==200)
                    except Exception:
                        result['player_http_ok']=False
                break
            time.sleep(1)
        if result['phase']=='bytes_received':result['phase']='processing_not_yet_visible'
    except HTTPError as ex:
        result['http']=int(ex.code)
        result['phase']=result['phase']+'_http_failed'
    except Exception as ex:
        result['failure_type']=type(ex).__name__
        result['phase']=result['phase']+'_failed'
    finally:
        if uid and re.fullmatch('[A-Za-z0-9_-]{8,64}',uid):
            try:
                with fetch(Request(root+'/'+quote(uid,safe=''),headers={'Authorization':'Bearer '+token},method='DELETE'),timeout=20):pass
                result['deleted']=True
            except Exception:
                result['deleted']=False
        try:
            marker.parent.mkdir(parents=True,exist_ok=True)
            marker.write_text(json.dumps(result),encoding='utf-8')
        except OSError:pass
        out('BIGPAW_TUS_LIVE_SMOKE|'+ '|'.join(str(k)+'='+str(v) for k,v in result.items()))
if __name__=='__main__':run()
