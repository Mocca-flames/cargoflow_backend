"""Public loads board test. Needs only DIRECTOR_TOKEN (to create and close test loads).

Run: docker compose exec -T -e DIRECTOR_TOKEN=... app python scripts/test_public_loads.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("BASE_URL", "http://localhost:8000")
DIRECTOR = os.getenv("DIRECTOR_TOKEN", "")
if not DIRECTOR:
    sys.exit("Set DIRECTOR_TOKEN")

PRIVATE = ("note", "company_id", "posted_by", "status", "updated_at")


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


base = {"origin": "Pretoria", "destination": "Ndola", "commodity": "Fertiliser",
        "truck_type": "tautliner", "trucks_needed": 2, "rate": 2100, "currency": "USD",
        "payment_terms": "on_delivery", "note": "SECRET-NOTE call 0820000000"}

s, a = call("POST", "/loads", DIRECTOR, {**base, "backload_origin": "Ndola", "backload_destination": "Pretoria",
                                         "backload_commodity": "Copper", "backload_rate": 900})
s2, b = call("POST", "/loads", DIRECTOR, {**base, "origin": "Cape Town", "destination": "Windhoek"})
check("setup: two loads created", s == 201 and s2 == 201, (s, s2))
if s != 201 or s2 != 201:
    sys.exit(1)
ida, idb = a["id"], b["id"]

print("--- public read, no token")
s, lst = call("GET", "/public/loads?limit=50")
check("list needs no token -> 200", s == 200 and isinstance(lst, list), (s, lst))
pub_ids = [x["id"] for x in lst] if s == 200 else []
check("open loads are listed", ida in pub_ids and idb in pub_ids, pub_ids)

s, one = call("GET", f"/public/loads/{ida}")
check("get one -> 200", s == 200 and one["id"] == ida, (s, one))
if s == 200:
    check("backload shown", one["has_backload"] is True and one["backload_rate"] is not None, one)
    leaked = [k for k in PRIVATE if k in one]
    check("no private fields in single load", not leaked, leaked)
if lst:
    leaked = [k for k in PRIVATE if any(k in x for x in lst)]
    check("no private fields in list", not leaked, leaked)
check("SECRET-NOTE never appears", "SECRET-NOTE" not in json.dumps([lst, one]), "note leaked")

print("--- filters and limits")
s, f = call("GET", "/public/loads?origin=pretoria&limit=50")
fi = [x["id"] for x in f] if s == 200 else []
check("origin filter", ida in fi and idb not in fi, fi)
s, f = call("GET", "/public/loads?destination=windhoek&limit=50")
fi = [x["id"] for x in f] if s == 200 else []
check("destination filter", idb in fi and ida not in fi, fi)
s, f = call("GET", "/public/loads?limit=1")
check("limit=1 returns one", s == 200 and len(f) == 1, (s, f))
s, _ = call("GET", "/public/loads?limit=500")
check("limit above 50 -> 422", s == 422, s)
s, _ = call("GET", "/public/loads/999999")
check("unknown id -> 404", s == 404, s)

print("--- only open loads are public")
for status in ("assigned", "closed"):
    s, _ = call("PATCH", f"/loads/{idb}", DIRECTOR, {"status": status})
    check(f"set status {status}", s == 200, s)
    s, _ = call("GET", f"/public/loads/{idb}")
    check(f"{status} load -> 404 on public get", s == 404, s)
    s, f = call("GET", "/public/loads?limit=50")
    check(f"{status} load hidden from public list", s == 200 and idb not in [x["id"] for x in f], s)

print("--- private API still needs a token")
s, _ = call("GET", "/loads")
check("GET /loads without token rejected", s in (401, 403), s)

print(f"\n{sum(results)}/{len(results)} passed")
print("created load ids:", ida, idb)
sys.exit(0 if all(results) else 1)
