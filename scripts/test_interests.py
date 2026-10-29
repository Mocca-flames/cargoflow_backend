"""Load interests (callback requests) test.

Run: docker compose exec -T -e DIRECTOR_TOKEN=... -e TRANSPORTER_TOKEN=... app python scripts/test_interests.py
"""
import json
import os
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


def leads(load_id, token=DIRECTOR, extra=""):
    s, b = call("GET", f"/load-interests?load_id={load_id}&limit=200{extra}", token)
    return b if s == 200 and isinstance(b, list) else None


load = {"origin": "Rustenburg", "destination": "Kitwe", "commodity": "Chrome",
        "trucks_needed": 2, "rate": 2400, "currency": "USD"}
s, a = call("POST", "/loads", DIRECTOR, load)
s2, c = call("POST", "/loads", DIRECTOR, {**load, "origin": "Welkom"})
check("setup: two loads created", s == 201 and s2 == 201, (s, s2))
if s != 201 or s2 != 201:
    sys.exit(1)
open_id, closed_id = a["id"], c["id"]
call("PATCH", f"/loads/{closed_id}", DIRECTOR, {"status": "closed"})

good = {"full_name": "Piet Nel", "phone": "082 123 4567", "truck_type": "superlink", "consent": True}

print("--- public submit (no token)")
s, b = call("POST", f"/public/loads/{open_id}/interest", None, good)
check("valid interest -> 201", s == 201 and b.get("message"), (s, b))
rows = leads(open_id)
check("lead stored once", rows is not None and len(rows) == 1, rows)
if rows:
    r = rows[0]
    check("phone normalized to +27821234567", r["phone"] == "+27821234567", r["phone"])
    check("status is new", r["status"] == "new", r["status"])
    check("route attached", r["load_origin"] == "Rustenburg" and r["load_destination"] == "Kitwe", r)
    check("truck type kept", r["truck_type"] == "superlink", r["truck_type"])
    lead_id = r["id"]
else:
    lead_id = None

s, b = call("POST", f"/public/loads/{open_id}/interest", None, good)
check("same person twice -> same 201", s == 201 and b.get("message"), (s, b))
s, b = call("POST", f"/public/loads/{open_id}/interest", None, {**good, "phone": "+27 82 123 4567"})
check("same number other format -> 201", s == 201, (s, b))
rows = leads(open_id)
check("still only one lead", rows is not None and len(rows) == 1, rows)

s, b = call("POST", f"/public/loads/{open_id}/interest", None,
            {**good, "phone": "083 000 1111", "website": "http://spam.example"})
check("honeypot -> 201 (bots learn nothing)", s == 201 and b.get("message"), (s, b))
rows = leads(open_id)
check("honeypot stored nothing", rows is not None and all(x["phone"] != "+27830001111" for x in rows), rows)

s, b = call("POST", f"/public/loads/{open_id}/interest", None, {**good, "phone": "+260 97 123 4567", "full_name": "Joseph Banda"})
check("Zambian number accepted", s == 201, (s, b))
rows = leads(open_id)
check("two leads now", rows is not None and len(rows) == 2, rows)

print("--- public validation")
for name, patch, want in [
    ("no consent -> 422", {"consent": False}, 422),
    ("bad phone -> 422", {"phone": "abc"}, 422),
    ("bad truck_type -> 422", {"truck_type": "spaceship"}, 422),
    ("short name -> 422", {"full_name": "A"}, 422),
]:
    s, _ = call("POST", f"/public/loads/{open_id}/interest", None, {**good, **patch})
    check(name, s == want, s)
s, _ = call("POST", "/public/loads/999999/interest", None, good)
check("unknown load -> 404", s == 404, s)
s, _ = call("POST", f"/public/loads/{closed_id}/interest", None, good)
check("closed load -> 404", s == 404, s)

print("--- admin list and access")
s, _ = call("GET", "/load-interests")
check("list without token rejected", s in (401, 403), s)
s, _ = call("GET", "/load-interests", TRANSPORTER)
check("transporter cannot list -> 403", s == 403, s)
rows = leads(open_id, extra="&status=new")
check("status=new filter", rows is not None and len(rows) == 2, rows)
s, _ = call("GET", "/load-interests?status=nope", DIRECTOR)
check("bad status filter -> 422", s == 422, s)

print("--- admin update")
if lead_id:
    s, b = call("PATCH", f"/load-interests/{lead_id}", DIRECTOR, {"status": "contacted", "note": "Called, will onboard"})
    check("mark contacted -> 200", s == 200 and b["status"] == "contacted", (s, b))
    if s == 200:
        check("handled_at set", b["handled_at"] is not None, b)
        check("note saved", b["note"] == "Called, will onboard", b["note"])
    rows = leads(open_id, extra="&status=contacted")
    check("contacted filter finds it", rows is not None and [x["id"] for x in rows] == [lead_id], rows)
    rows = leads(open_id, extra="&status=new")
    check("new filter excludes it", rows is not None and lead_id not in [x["id"] for x in rows], rows)
    s, _ = call("PATCH", f"/load-interests/{lead_id}", DIRECTOR, {"status": "done"})
    check("bad status -> 422", s == 422, s)
    s, _ = call("PATCH", f"/load-interests/{lead_id}", TRANSPORTER, {"status": "dismissed"})
    check("transporter cannot update -> 403", s == 403, s)
s, _ = call("PATCH", "/load-interests/999999", DIRECTOR, {"status": "contacted"})
check("unknown lead -> 404", s == 404, s)

print(f"\n{sum(results)}/{len(results)} passed")
print("created load ids:", open_id, closed_id)
sys.exit(0 if all(results) else 1)
