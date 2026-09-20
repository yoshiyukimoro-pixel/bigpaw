from pathlib import Path
import re
p=Path("backend/server.py")
s=p.read_text(encoding="utf-8")
start=s.index("def send_mail(")
end=s.find("\ndef ", start+1)
if end < 0: end=len(s)
defline=s[start:s.find("\n",start)]
body=r'''
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
'''
s=s[:start]+defline+body+s[end:]

# Force all generated email/login verification links to use the public production domain.
# Railway runs the app internally on 127.0.0.1:8080, but links sent to users must be https://bigpaw.site/...
public="https://bigpaw.site"
repls={
    "http://127.0.0.1:8080": public,
    "http://localhost:8080": public,
    "http://0.0.0.0:8080": public,
    'f"http://127.0.0.1:{PORT}"': '"'+public+'"',
    "f'http://127.0.0.1:{PORT}'": '"'+public+'"',
    'f"http://localhost:{PORT}"': '"'+public+'"',
    "f'http://localhost:{PORT}'": '"'+public+'"',
}
for a,b in repls.items():
    s=s.replace(a,b)
s=re.sub(r"http://127\.0\.0\.1:\\d+", public, s)
s=re.sub(r"http://localhost:\\d+", public, s)
s=re.sub(r"http://0\.0\.0\.0:\\d+", public, s)
# If the app has a configurable base URL, set its production fallback to the public domain.
s=s.replace("os.environ.get('BIGPAW_BASE_URL','')", "(os.environ.get('BIGPAW_BASE_URL') or 'https://bigpaw.site')")
s=s.replace('os.environ.get("BIGPAW_BASE_URL","")', '(os.environ.get("BIGPAW_BASE_URL") or "https://bigpaw.site")')
s=s.replace("os.environ.get('PUBLIC_BASE_URL','')", "(os.environ.get('PUBLIC_BASE_URL') or 'https://bigpaw.site')")
s=s.replace('os.environ.get("PUBLIC_BASE_URL","")', '(os.environ.get("PUBLIC_BASE_URL") or "https://bigpaw.site")')
compile(s,"backend/server.py","exec")
# Add a runtime-only Resend connectivity/auth probe (no email is sent).
probe = r'''
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
'''
s=s+"\n"+probe
p.write_text(s,encoding="utf-8")