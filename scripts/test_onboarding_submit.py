"""Public onboarding submit test. Secrets come from the environment.

Run: docker compose exec -T -e DIRECTOR_TOKEN=... -e OTP_CODE=... -e TEST_PASSWORD=... app python scripts/test_onboarding_submit.py
"""
import json
import os
import random
import sys
import urllib.error
import urllib.request

BASE = os.getenv("BASE_URL", "http://localhost:8000")
DIRECTOR = os.getenv("DIRECTOR_TOKEN", "")
CODE = os.getenv("OTP_CODE", "")
PASSWORD = os.getenv("TEST_PASSWORD", "")
EMAIL = os.getenv("OWNER_EMAIL", "junior@apextransportgroup.co.za")
if not DIRECTOR or not CODE or not PASSWORD:
    sys.exit("Set DIRECTOR_TOKEN, OTP_CODE and TEST_PASSWORD")


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
REG = f"OB-{RUN}"
PHONE = f"+2771{random.randint(1000000, 9999999)}"


def body(email, code, reg, phone):
    return {
        "company": {"legal_name": f"Onboard Test {RUN}", "registration_number": reg,
                    "country_code": "ZA", "phone": phone},
        "roles": ["transporter"],
        "transporter": {"operating_countries": ["ZA", "ZW"]},
        "code": code,
        "password": PASSWORD,
        "owner": {"full_name": "Junior Test", "email": email, "phone": phone},
    }


print("--- submit with the emailed code")
s, b = call("POST", "/onboarding/submit", None, body(EMAIL, CODE, REG, PHONE))
check("submit -> 201", s == 201, (s, b))
cid = b.get("company_id") if s == 201 else None
if cid:
    check("status unverified", b["status"] == "unverified", b)
    check("roles", b["roles"] == ["transporter"], b)
    check("owner_user_id set", b["owner_user_id"] is not None, b)

    print("--- stored data (director view)")
    s, d = call("GET", f"/companies/{cid}", DIRECTOR)
    check("company detail -> 200", s == 200, (s, d))
    check("registration number stored", d.get("registration_number") == REG, d)
    check("operating countries stored", d.get("operating_countries") == ["ZA", "ZW"], d)
    check("owner linked", [u["email"] for u in d.get("users", [])] == [EMAIL.lower()], d.get("users"))

    print("--- owner can log in")
    s, b2 = call("POST", "/auth/login", None, {"email": EMAIL, "password": PASSWORD})
    check("login -> tokens", s == 200 and bool((b2.get("tokens") or {}).get("access_token")), (s, b2))

print("--- repeat attempts")
s, b = call("POST", "/onboarding/submit", None, body(EMAIL, CODE, f"{REG}B", f"+2772{random.randint(1000000, 9999999)}"))
check("same email again -> 409", s == 409, (s, b))
s, b = call("POST", "/onboarding/submit", None,
            body(f"other.{RUN}@example.com", CODE, f"{REG}C", f"+2773{random.randint(1000000, 9999999)}"))
check("code for another email -> 400", s == 400, (s, b))

print(f"\n{sum(results)}/{len(results)} passed")
print("company:", cid)
sys.exit(0 if all(results) else 1)
