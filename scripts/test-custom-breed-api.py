#!/usr/bin/env python3
"""Isolated HTTP integration test: custom-breed registration, editing and public read."""
import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18083"

def request(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    raw = None if data is None else json.dumps(data, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + path, data=raw, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as reply:
            body = reply.read()
            return reply.status, json.loads(body) if body else None
    except urllib.error.HTTPError as ex:
        content = ex.read()
        return ex.code, json.loads(content) if content else None

def html(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as resp:
        return resp.status, resp.read().decode("utf-8")

code, status = request("GET","/api/health")
assert code == 200, (code,status)
code, result = request("POST","/api/login",{
    "email":"smoke@example.com",
    "password":"SmokeTestPassword123!",
})
assert code == 200 and result.get("token"), ("operator login failed",code,result)
operator_token=result["token"]
breed="ゴールデンドゥードル"
code, created = request("POST","/api/puppies",{
    "name":"カスタム犬種の検証"+uuid.uuid4().hex[:6],
    "breed":breed,"breedKey":"other","gender":"男の子",
    "color":"クリーム","birth":"2026-10-10","price":220000,
    "area":"埼玉県","areaKey":"saitama","desc":"DOG44 custom breed isolated test"
},operator_token)
assert code == 201 and created.get("breed")==breed and created.get("breedKey")=="other", (code,created)
pid=created["id"]
code, puppies=request("GET","/api/puppies")
assert code==200 and any(p.get("id")==pid and p.get("breed")==breed for p in puppies), "public search missing custom breed"
code, public=request("GET","/api/puppies/"+pid)
assert code==200 and public.get("breed")==breed and public.get("breedKey")=="other", "public puppy detail missing name"
newbreed="ラブラドゥードル"
code, changed=request("PATCH","/api/puppies/"+pid,{
    "breed":newbreed,"breedKey":"other"
},operator_token)
assert code==200 and changed.get("breed")==newbreed and changed.get("breedKey")=="other", (code,changed)
code, updated=request("GET","/api/puppies/"+pid)
assert code==200 and updated.get("breed")==newbreed, "public detail did not preserve breed edit"
assert not any(p.get("id")==pid and p.get("breed")==breed for p in request("GET","/api/puppies")[1]), "old custom name still publicly displayed"
code, page=html("/breeder-puppy-new.html")
assert code==200 and "assets/breed-data.js" in page and "photoPreview" in page, "registration UI missing"
code, picker=html("/assets/breed-data.js")
assert code==200 and "bpOtherBreedName" in picker and "input.required=true" in picker, "custom name input not served"
code, results=html("/search.html")
assert code==200 and "bpOtherBreedSearch" in results and "selected.includes('other')" in results, "custom breed search not served after runtime patches"
code, details=html("/puppy-detail.html")
assert code==200 and "BigPawBridge.puppy" in details, "detail page regressed"
print("CUSTOM_BREED_HTTP_OK|create=201|public_list=200|public_detail=200|edit=200|name_search=200|photo_ui=preserved|detail=preserved")
