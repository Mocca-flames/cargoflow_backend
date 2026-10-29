"""Company detail test. Tokens come from the environment.

Run: docker compose exec -T -e DIRECTOR_TOKEN=... -e TRANSPORTER_TOKEN=... app python scripts/test_company_detail.py
"""
import json
import os
import random
import sys
import urllib.error
import urllib.request

BASE = os.getenv("BASE_URL", "http://localhost:8000")
DIRECTOR = os.getenv("DIRECTOR_TOKEN", "")
TRANSPORTER = os.getenv("TRANSPORTER_TOKEN", "")
if not DIRECTOR or not TRANSPORTER:
    sys.exit("Set DIRECTOR_TOKEN and TRANSPORTER_TOKEN")


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode()


results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"   -> {detail}"))


RUN = random.randint(100000, 999999)

print("--- auth")
s, _ = call("GET", "/companies/4")
check("no token is rejected", s in (401, 403), s)
s, _ = call("GET", "/companies/4", TRANSPORTER)
check("transporter -> 403", s == 403, s)
s, _ = call("GET", "/companies/999999", DIRECTOR)
check("unknown company -> 404", s == 404, s)

print("--- fresh transporter company (staff-created, with owner)")
s, b = call("POST", "/onboarding/staff-submit", DIRECTOR, {
    "company": {"legal_name": f"Detail Test {RUN}", "registration_number": f"DT-{RUN}",
                "country_code": "ZA"},
    "roles": ["transporter"],
    "transporter": {"operating_countries": ["ZA", "MZ"]},
    "create_owner": True,
    "owner": {"full_name": "Detail Owner", "email": f"detail.{RUN}@example.com",
              "phone": f"+2778{random.randint(1000000, 9999999)}"},
})
check("create test company -> 201", s == 201, (s, b))
cid = b.get("company_id") if s == 201 else None
if cid:
    s, d = call("GET", f"/companies/{cid}", DIRECTOR)
    check("detail -> 200", s == 200, (s, d))
    check("status unverified", d.get("status") == "unverified", d.get("status"))
    check("roles", d.get("roles") == ["transporter"], d.get("roles"))
    check("operating_countries", d.get("operating_countries") == ["ZA", "MZ"], d.get("operating_countries"))
    check("broker fields null", d.get("corridors") is None and d.get("finds_trucks") is None, d)
    check("one user (the owner)", len(d.get("users", [])) == 1
          and d["users"][0]["email"] == f"detail.{RUN}@example.com", d.get("users"))
    check("no documents yet", d.get("documents") == [], d.get("documents"))
    check("missing_documents not empty", len(d.get("missing_documents", [])) > 0, d.get("missing_documents"))
    check("no password hash leaked", "password" not in json.dumps(d).lower(), "password in body")

print("--- broker company")
s, b = call("POST", "/onboarding/staff-submit", DIRECTOR, {
    "company": {"legal_name": f"Detail Broker {RUN}", "registration_number": f"DB-{RUN}",
                "country_code": "ZA"},
    "roles": ["broker"],
    "broker": {"corridors": ["ZA-ZW"], "finds_trucks": True},
    "create_owner": False,
})
check("create broker -> 201", s == 201, (s, b))
if s == 201:
    s, d = call("GET", f"/companies/{b['company_id']}", DIRECTOR)
    check("broker detail 200", s == 200, (s, d))
    check("corridors and finds_trucks", d.get("corridors") == ["ZA-ZW"] and d.get("finds_trucks") is True, d)
    check("transporter field null", d.get("operating_countries") is None, d.get("operating_countries"))
    check("no users", d.get("users") == [], d.get("users"))

print("--- company 4 (has documents)")
s, d = call("GET", "/companies/4", DIRECTOR)
if s == 200:
    docs = d["documents"]
    check("has documents", len(docs) > 0, docs)
    check("no superseded documents", all(x["status"] != "superseded" for x in docs), docs)
    check("type names resolved", all(x["type_name"] for x in docs if x["document_type_id"]), docs)
    check("truck document carries truck_id", any(x["truck_id"] == 1 for x in docs), docs)
else:
    check("company 4 readable", False, (s, d))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
