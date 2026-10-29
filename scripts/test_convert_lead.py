"""Convert-lead test. Tokens come from the environment.

Run: docker compose exec -T -e DIRECTOR_TOKEN=... -e TRANSPORTER_TOKEN=... app python scripts/test_convert_lead.py
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


def company(reg_suffix, **extra):
    return {
        "company": {"legal_name": f"Convert Test {RUN}-{reg_suffix}",
                    "registration_number": f"CT-{RUN}-{reg_suffix}",
                    "country_code": "ZA"},
        "roles": ["transporter"],
        "transporter": {"operating_countries": ["ZA", "ZW"]},
        **extra,
    }


# One test load, several leads with unique phones.
s, b = call("POST", "/loads", DIRECTOR, {
    "origin": "Johannesburg", "destination": "Harare", "commodity": "Convert test",
    "trucks_needed": 1, "rate": 900, "currency": "ZAR"})
if s != 201:
    sys.exit(f"could not create test load: {s} {b}")
load_id = b["id"]

phones = {}


def make_lead(tag):
    phone = f"+2779{random.randint(1000000, 9999999)}"
    s, b = call("POST", f"/public/loads/{load_id}/interest", None, {
        "full_name": f"Lead {tag} {RUN}", "phone": phone, "consent": True})
    assert s == 201, (s, b)
    s, rows = call("GET", f"/load-interests?load_id={load_id}&limit=200", DIRECTOR)
    row = next(r for r in rows if r["phone"] == phone)
    phones[row["id"]] = phone
    return row["id"]


def lead_row(lead_id):
    s, rows = call("GET", f"/load-interests?load_id={load_id}&limit=200", DIRECTOR)
    return next((r for r in rows if r["id"] == lead_id), None)


owner_email = f"convert.{RUN}@example.com"
l1, l2, l3, l4, l5 = (make_lead(t) for t in "ABCDE")

print("--- auth")
s, _ = call("POST", f"/load-interests/{l1}/convert", None, company("1", create_owner=False))
check("no token is rejected", s in (401, 403), s)
s, _ = call("POST", f"/load-interests/{l1}/convert", TRANSPORTER, company("1", create_owner=False))
check("transporter -> 403", s == 403, s)

print("--- not found and validation")
s, _ = call("POST", "/load-interests/999999/convert", DIRECTOR, company("x", create_owner=False))
check("unknown lead -> 404", s == 404, s)
s, b = call("POST", f"/load-interests/{l1}/convert", DIRECTOR, company("1", create_owner=True))
check("create_owner without owner_email -> 422", s == 422, (s, b))
bad = company("1", create_owner=False)
bad.pop("transporter")
s, b = call("POST", f"/load-interests/{l1}/convert", DIRECTOR, bad)
check("transporter role without profile -> 422", s == 422, (s, b))
check("lead untouched after validation errors", (lead_row(l1) or {}).get("status") == "new", lead_row(l1))

print("--- happy path (with owner)")
s, b = call("POST", f"/load-interests/{l1}/convert", DIRECTOR,
            company("1", create_owner=True, owner_email=owner_email))
check("convert -> 201", s == 201, (s, b))
cid = b.get("company_id") if s == 201 else None
if cid:
    check("company unverified", b["status"] == "unverified", b)
    check("roles returned", b["roles"] == ["transporter"], b)
    check("owner_user_id set", b["owner_user_id"] is not None, b)
row = lead_row(l1)
check("lead status onboarded", row and row["status"] == "onboarded", row)
check("lead company_id linked", row and row["company_id"] == cid, row)
check("lead handled_at stamped", row and row["handled_at"] is not None, row)

print("--- converting twice")
s, b = call("POST", f"/load-interests/{l1}/convert", DIRECTOR,
            company("1b", create_owner=False))
check("already onboarded -> 409", s == 409, (s, b))

print("--- duplicates leave the lead untouched")
s, b = call("POST", f"/load-interests/{l2}/convert", DIRECTOR, company("1", create_owner=False))
check("duplicate registration number -> 409", s == 409, (s, b))
check("lead 2 still new", (lead_row(l2) or {}).get("status") == "new", lead_row(l2))
s, b = call("POST", f"/load-interests/{l3}/convert", DIRECTOR,
            company("3", create_owner=True, owner_email=owner_email))
check("duplicate owner email -> 409", s == 409, (s, b))
check("lead 3 still new", (lead_row(l3) or {}).get("status") == "new", lead_row(l3))

print("--- no owner")
s, b = call("POST", f"/load-interests/{l4}/convert", DIRECTOR, company("4", create_owner=False))
check("convert without owner -> 201", s == 201, (s, b))
if s == 201:
    check("owner_user_id is null", b["owner_user_id"] is None, b)
row = lead_row(l4)
check("lead 4 onboarded", row and row["status"] == "onboarded", row)

print("--- broker role")
body = company("5", create_owner=False)
body["roles"] = ["broker"]
body.pop("transporter")
body["broker"] = {"corridors": ["ZA-ZW"], "finds_trucks": True}
s, b = call("POST", f"/load-interests/{l5}/convert", DIRECTOR, body)
check("broker convert -> 201", s == 201 and b.get("roles") == ["broker"], (s, b))

print(f"\n{sum(results)}/{len(results)} passed")
print("test load:", load_id, "leads:", l1, l2, l3, l4, l5, "company:", cid)
sys.exit(0 if all(results) else 1)
