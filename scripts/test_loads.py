"""Loads API test. Tokens come from the environment, never from this file.

Run: docker compose exec -T -e DIRECTOR_TOKEN=... -e TRANSPORTER_TOKEN=... app python scripts/test_loads.py
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

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


def ids(path, token=DIRECTOR):
    s, b = call("GET", path, token)
    return [x["id"] for x in b] if s == 200 and isinstance(b, list) else None


status, spec = call("GET", "/openapi.json")
if status != 200 or "/loads" not in spec.get("paths", {}):
    sys.exit("The /loads router is not registered in app/main.py yet.")

tomorrow = (date.today() + timedelta(days=1)).isoformat()
yesterday = (date.today() - timedelta(days=1)).isoformat()
full = {
    "origin": "Durban Port", "destination": "Lubumbashi", "commodity": "Copper cathodes",
    "truck_type": "superlink", "trucks_needed": 3, "rate": 2800, "currency": "usd",
    "payment_terms": "14_days", "pickup_date": tomorrow,
    "backload_origin": "Lubumbashi", "backload_destination": "Durban Port",
    "backload_commodity": "Sulphur", "backload_rate": 1500,
}
forward = {"origin": "Johannesburg", "destination": "Harare", "commodity": "Maize",
           "trucks_needed": 1, "rate": 950, "currency": "ZAR"}

print("--- auth")
s, _ = call("GET", "/loads")
check("no token is rejected", s in (401, 403), s)

print("--- director: create")
s, b = call("POST", "/loads", DIRECTOR, full)
id1 = b.get("id") if s == 201 else None
check("load with backload -> 201", s == 201, (s, b))
if id1:
    check("currency uppercased to USD", b["currency"] == "USD", b["currency"])
    check("status defaults to open", b["status"] == "open", b["status"])
    check("has_backload is true", b["has_backload"] is True, b.get("has_backload"))
    check("company_id is null for staff post", b["company_id"] is None, b["company_id"])

s, b = call("POST", "/loads", DIRECTOR, forward)
id2 = b.get("id") if s == 201 else None
check("forward-only load -> 201", s == 201, (s, b))
if id2:
    check("forward-only has_backload false", b["has_backload"] is False, b.get("has_backload"))
    check("ZAR kept", b["currency"] == "ZAR", b["currency"])

s, b = call("POST", "/loads", DIRECTOR, {**forward, "payment_terms": "  70/30 on loading  "})
check("custom payment terms stored trimmed", s == 201 and b["payment_terms"] == "70/30 on loading", (s, b))
s, b = call("POST", "/loads", DIRECTOR, {**forward, "payment_terms": "   "})
check("blank payment terms -> null", s == 201 and b["payment_terms"] is None, (s, b))

print("--- director: validation")
for name, patch in [
    ("backload rate without route -> 422", {"backload_rate": 500}),
    ("currency EUR -> 422", {"currency": "EUR"}),
    ("bad truck_type -> 422", {"truck_type": "spaceship"}),
    ("payment_terms over 100 chars -> 422", {"payment_terms": "x" * 101}),
    ("past pickup_date -> 422", {"pickup_date": yesterday}),
    ("rate 0 -> 422", {"rate": 0}),
    ("trucks_needed 0 -> 422", {"trucks_needed": 0}),
]:
    s, b = call("POST", "/loads", DIRECTOR, {**forward, **patch})
    check(name, s == 422, (s, b))
s, b = call("POST", "/loads", DIRECTOR, {**forward, "company_id": 999999})
check("unknown company_id -> 404", s == 404, (s, b))

print("--- director: read and filter")
if id1:
    got = ids("/loads?limit=200")
    check("list contains new loads", got is not None and id1 in got and (id2 in got), got)
    got = ids("/loads?origin=durban&limit=200")
    check("origin filter (case-insensitive)", got is not None and id1 in got and id2 not in got, got)
    got = ids("/loads?destination=harare&limit=200")
    check("destination filter", got is not None and id2 in got and id1 not in got, got)
    got = ids("/loads?truck_type=superlink&limit=200")
    check("truck_type filter", got is not None and id1 in got and id2 not in got, got)
    s, b = call("GET", f"/loads/{id1}", DIRECTOR)
    check("get one load -> 200", s == 200 and b["id"] == id1, (s, b))
    s, b = call("GET", "/loads?status=nope", DIRECTOR)
    check("bad status filter -> 422", s == 422, (s, b))
s, b = call("GET", "/loads/999999", DIRECTOR)
check("get unknown load -> 404", s == 404, (s, b))

print("--- director: update")
if id1:
    s, b = call("PATCH", f"/loads/{id1}", DIRECTOR, {"status": "assigned"})
    check("status -> assigned", s == 200 and b["status"] == "assigned", (s, b))
    got = ids("/loads?status=assigned&limit=200")
    check("status filter finds it", got is not None and id1 in got, got)
    s, b = call("PATCH", f"/loads/{id1}", DIRECTOR, {"status": "done"})
    check("bad status -> 422", s == 422, (s, b))
    s, b = call("PATCH", f"/loads/{id1}", DIRECTOR, {"trucks_needed": 0})
    check("trucks_needed 0 -> 422", s == 422, (s, b))

print("--- transporter (not a broker)")
s, b = call("POST", "/loads", TRANSPORTER, forward)
check("cannot post loads -> 403", s == 403 and "broker" in str(b).lower(), (s, b))
got = ids("/loads?limit=200", TRANSPORTER)
check("can read the board", got is not None, got)
if id1:
    s, b = call("GET", f"/loads/{id1}", TRANSPORTER)
    check("can read one load", s == 200, (s, b))
    s, b = call("PATCH", f"/loads/{id1}", TRANSPORTER, {"status": "closed"})
    check("cannot update a staff load -> 404", s == 404, (s, b))

print(f"\n{sum(results)}/{len(results)} passed")
print("created load ids:", id1, id2)
sys.exit(0 if all(results) else 1)
