#!/usr/bin/env python3
"""End-to-end smoke checks for operator proxy puppy ownership.

Runs against a disposable development server, NEVER against production.
"""
import json
import sys
import urllib.request
import urllib.error
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18085"

def req(method, path, body=None, token=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as ex:
        return ex.code, json.loads(ex.read() or b"{}")

def ensure(ok, message):
    if not ok:
        raise AssertionError(message)
    print("PASS", message, flush=True)

def breeder(tag, prefecture, operator):
    suffix = uuid.uuid4().hex[:9]
    email = f"proxy-{tag}-{suffix}@example.test"
    password = "Proxy1234!"
    st, r = req("POST", "/api/register", {"email":email,"password":password,
        "last":"代理掲載","first":tag,"agreeTerms":True,"agreePrivacy":True})
    ensure(st == 201, "registered breeder user " + tag)
    st, r = req("POST", "/api/login", {"email":email,"password":password})
    ensure(st == 200 and bool(r.get("token")), "logged in as future breeder " + tag)
    token = r["token"]
    st, r = req("POST", "/api/email-verification/request", {}, token)
    ensure(st == 200 and bool(r.get("devToken")), "obtained dev email verification")
    st, r = req("POST", "/api/email-verification/confirm", {"token":r["devToken"]})
    ensure(st == 200, "verified email")
    st, r = req("POST", "/api/breeder-applications", {
        "kennelName":"代理掲載" + tag + "犬舎", "representative":"試験 " + tag,
        "prefecture":prefecture,"primaryBreed":"サモエド",
        "registrationNo":"PROXY-"+tag+"-"+suffix,"expiresOn":"2027-12-31",
        "profile":"大型犬の健康に配慮して飼育しています。",
        "visitAddress":prefecture+"架空市試験区一丁目",
        "visitPhone":"090-0000-0000",
        "visitAccess":"車でのアクセス可",
        "registrationProofUrl":"/uploads/smoke-registration-proof.jpg",
        "agreeCommissionTerms":True
    }, token)
    ensure(st == 201 and bool(r.get("id")), "requested breeder approval " + tag + f" (HTTP {st}: {r})")
    st, r = req("PATCH", "/api/breeder-applications/" + r["id"],
                {"status":"approved", "reviewNote":"proxy test"}, operator)
    ensure(st == 200 and r.get("status") == "approved", "approved breeder " + tag)
    st, r = req("POST", "/api/login", {"email":email,"password":password})
    ensure(st == 200 and r.get("user",{}).get("role") == "breeder",
           "promoted to breeder " + tag)
    token = r["token"]
    st, profile = req("GET", "/api/breeder-profile", token=token)
    ensure(st == 200 and bool(profile.get("id")), "resolved breeder id " + tag)
    return token, profile["id"], profile["kennel_name"]

st, r = req("GET","/api/health")
ensure(st == 200, "development server healthy")
st, r = req("POST","/api/login",{"email":"admin@bigpaw.jp","password":"admin1234"})
ensure(st == 200 and bool(r.get("token")), "operator logged in")
operator = r["token"]
a_token, aid, a_name = breeder("A", "千葉県", operator)
b_token, bid, b_name = breeder("B", "神奈川県", operator)

body = {
    "name":"ヤンヤン","breeder":"DOG44","area":"埼玉県","areaKey":"saitama",
    "breed":"サモエド","breedKey":"samoyed",
    "birth":"2024-09-04","gender":"男の子","color":"ホワイト",
    "weight":23,"price":130000,
    "desc":"代理掲載のテスト"
}
st, bad = req("POST", "/api/puppies", body, operator)
ensure(st == 400 and bad.get("error") == "operator_breeder_selection_required",
       "operator cannot create a breederless listing")
st, bad = req("POST", "/api/puppies", dict(body, breederId="b_invalid"), operator)
ensure(st == 404 and bad.get("error") == "breeder_not_found",
       "operator cannot attach to missing breeder")
st, created = req("POST", "/api/puppies", dict(body, breederId=aid), operator)
ensure(st == 201 and bool(created.get("id")), "operator created selected breeder listing")
pid = created["id"]
ensure(created.get("breederId") == aid and created.get("breeder") == a_name,
       "database-selected breeder owns proxy listing, not DOG44")
ensure(created.get("area") == "千葉県" and created.get("areaKey") != "saitama",
       "location came from selected breeder rather than form")
ensure(created.get("name") == "ヤンヤン" and created.get("birth") == "2024-09-04" and created.get("price") == 130000,
       "provided dog data is retained")
ensure(created.get("reviewStatus") == "approved",
       "existing operator publication path is unchanged")

st, a_list = req("GET", "/api/breeder/puppies", token=a_token)
st2, b_list = req("GET", "/api/breeder/puppies", token=b_token)
ensure(st == 200 and st2 == 200 and any(p["id"] == pid for p in a_list)
       and all(p["id"] != pid for p in b_list),
       "target breeder sees proxy dog and other breeder does not")
st, public = req("GET", "/api/puppies")
ensure(st == 200 and any(p["id"] == pid and p["breederId"] == aid for p in public),
       "public dog listing resolves to correct breeder")

st, bad = req("PATCH", "/api/puppies/" + pid, {"price":1}, b_token)
ensure(st == 403, "different breeder cannot edit proxy listing")
st, created_b = req("POST", "/api/puppies", dict(body, name="B所有犬", breederId=aid), b_token)
ensure(st == 201 and created_b.get("breederId") == bid and created_b.get("breeder") == b_name,
       "breeder cannot forge ownership with proxy breederId")
st, listings = req("GET", "/api/operator/listings", token=operator)
ensure(st == 200 and any(p["id"] == pid and p["breederId"] == aid for p in listings),
       "operator listing view attributes proxy dog to target kennel")
print("ALL OPERATOR PROXY LISTING TESTS PASSED", flush=True)
