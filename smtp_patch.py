from pathlib import Path
p=Path("backend/server.py")
s=p.read_text(encoding="utf-8")
start=s.index("def send_mail(")
end=s.find("\ndef ", start+1)
if end < 0: end=len(s)
defline=s[start:s.find("\n",start)]
body=r'''
    import os, smtplib, ssl
    from email.message import EmailMessage
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
compile(s,"backend/server.py","exec")
p.write_text(s,encoding="utf-8")
