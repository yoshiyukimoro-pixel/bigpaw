#!/usr/bin/env python3
"""Isolated HTTP regression for AI endpoint and 1/5/10 photos. Local demo only."""
import base64
import json
import sys
import urllib.request
import urllib.error
import uuid

BASE=sys.argv[1] if len(sys.argv)>1 else "http://127.0.0.1:18087"
if not ("127.0.0.1" in BASE or "localhost" in BASE):
    raise SystemExit("REFUSING_NON_LOCAL_AI_E2E")

def req(method,path,body=None,token=None):
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    headers={"Content-Type":"application/json"}
    if token: headers["Authorization"]="Bearer "+token
    r=urllib.request.Request(BASE+path,data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(r,timeout=10) as resp:
            return resp.status,json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code,json.load(exc)

def ensure(cond,msg):
    if not cond: raise AssertionError(msg)
    print("PASS",msg,flush=True)

st,result=req("POST","/api/login",{"email":"admin@bigpaw.jp","password":"admin1234"})
ensure(st==200 and result.get("token"),"operator signed in to isolated demo")
op=result["token"]
st,result=req("POST","/api/login",{"email":"dog44@bigpaw.jp","password":"demo1234"})
ensure(st==200 and result.get("token"),"breeder signed in to isolated demo")
breeder=result["token"]
st,result=req("POST","/api/login",{"email":"demo@bigpaw.jp","password":"demo1234"})
ensure(st==200 and result.get("token"),"buyer signed in to isolated demo")
buyer=result["token"]
source="サモエドのヤンヤンは2024年9月4日生まれです。合計金額13万円です。"
payload={"breederId":"b_dog44","notes":source,"consent":True}
st,result=req("POST","/api/operator/ai-listing-draft",payload)
ensure(st==401,"AI draft endpoint blocks anonymous requests")
st,result=req("POST","/api/operator/ai-listing-draft",payload,buyer)
ensure(st==403,"AI draft endpoint blocks buyer requests")
st,result=req("POST","/api/operator/ai-listing-draft",payload,breeder)
ensure(st==403,"AI draft endpoint blocks breeder requests")
st,result=req("POST","/api/operator/ai-listing-draft",dict(payload,consent=False),op)
ensure(st==400 and result.get("error")=="ai_consent_required","AI API requires explicit opt-in")
st,result=req("POST","/api/operator/ai-listing-draft",dict(payload,breederId="b_missing"),op)
ensure(st==404,"AI API rejects unknown breeder target")
st,result=req("POST","/api/operator/ai-listing-draft",payload,op)
ensure(st==503 and result.get("error")=="ai_not_configured","AI API fails closed without secret")

png=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==")
def upload(pid,seq):
    boundary="bigpaw"+uuid.uuid4().hex
    data=(
      (f"--{boundary}\r\nContent-Disposition: form-data; name=\"puppyId\"\r\n\r\n{pid}\r\n").encode()
      +(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"dog-{seq}.png\"\r\nContent-Type: image/png\r\n\r\n").encode()
      +png+(f"\r\n--{boundary}--\r\n").encode()
    )
    r=urllib.request.Request(BASE+"/api/uploads",data=data,method="POST",
      headers={"Content-Type":"multipart/form-data; boundary="+boundary,
               "Authorization":"Bearer "+op})
    try:
        with urllib.request.urlopen(r,timeout=10) as resp:
            return resp.status,json.load(resp)
    except urllib.error.HTTPError as err:
        return err.code,json.load(err)

for size in (1,5,10):
    name=f"AI-test-{size}-{uuid.uuid4().hex[:6]}"
    st,dog=req("POST","/api/puppies",{"breederId":"b_dog44","name":name,"breed":"サモエド",
        "gender":"男の子","birth":"2024-09-04","price":130000,"desc":"AI photo regression"},op)
    ensure(st==201 and dog.get("breederId")=="b_dog44","operator creates correctly attributed test dog for "+str(size))
    pid=dog["id"]
    first=None
    for seq in range(size):
        st,photo=upload(pid,seq)
        ensure(st==201 and bool(photo.get("url")),f"photo {seq+1}/{size} saved")
        if first is None:first=photo["url"]
    st,up=req("PATCH","/api/puppies/"+pid,{"imageUrl":first},op)
    ensure(st==200 and up.get("imageUrl")==first,"main photo saved for "+str(size))
    st,photos=req("GET","/api/puppies/"+pid+"/photos",token=breeder)
    ensure(st==200 and len(photos)==size and sum(bool(p.get("isMain")) for p in photos)==1,
       f"{size} photos are visible in breeder panel in correct count")
    st,puppies=req("GET","/api/breeder/puppies",token=breeder)
    ensure(st==200 and any(p.get("id")==pid and p.get("breederId")=="b_dog44" for p in puppies),
           "photo test remains in selected breeder kennel")
    if size==10:
        st,extra=upload(pid,10)
        ensure(st==409 and extra.get("error")=="photo_limit_reached",
               "eleventh image blocked by server")
print("ALL AI LISTING ISOLATED REGRESSIONS PASSED",flush=True)
