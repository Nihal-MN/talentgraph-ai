"""API smoke test — exercises every route against a live server (dev tool)."""

import json
import urllib.request

BASE = "http://127.0.0.1:8300/api/v1"


def call(method: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode()
        return response.status, json.loads(body) if body else None


ok = 0

status, health = call("GET", "/health")
assert status == 200 and health["status"] == "ok", health
print(f"[1] health          ok | candidates={health['counts']['candidates']} "
      f"embed={health['ai']['embedding']['provider']} vector={health['retrieval']['vector_backend']}")
ok += 1

status, search = call("POST", "/search", {
    "query": "senior python backend engineer in Berlin with kubernetes experience",
    "limit": 6,
})
assert status == 200
print(f"[2] search(Berlin)  ok | total={search['total']} took={search['took_ms']}ms")
for item in search["results"][:6]:
    print(f"      #{item['rank']} {item['full_name']:22s} {item['location']:30s} "
          f"score={item['score']:.3f} signals={item['why']['signals_matched']}")
ok += 1

status, search2 = call("POST", "/search", {
    "query": "technical recruiter in the Gulf",
    "limit": 5,
})
assert status == 200
print(f"[3] search(Gulf)    ok | total={search2['total']}")
for item in search2["results"][:5]:
    print(f"      #{item['rank']} {item['full_name']:22s} {item['headline'][:40]:40s} {item['location']}")
ok += 1

status, candidates = call("GET", "/candidates?limit=3")
assert status == 200 and len(candidates) == 3
print(f"[4] candidates      ok | {[c['full_name'] for c in candidates]}")
ok += 1

status, detail = call("GET", f"/candidates/{search['results'][0]['id']}")
assert status == 200
print(f"[5] candidate/{detail['id']}   ok | {detail['full_name']} skills={len(detail['skills'])} "
      f"embedding={detail['embedding']['model']}")
ok += 1

status, ingested = call("POST", "/candidates/ingest", {
    "resume_text": (
        "Omar Al Farsi\nSenior Data Engineer\nowmar@example.com\n\n"
        "8 years building batch and streaming pipelines with Spark, Airflow, Kafka and dbt on AWS.\n"
        "Deep experience with Snowflake and PostgreSQL, plus Python and Terraform.\n"
        "Based in Dubai, United Arab Emirates. MSc Computer Science, NUS Singapore.\n"
    ),
})
assert status == 201, ingested
print(f"[6] ingest          ok | id={ingested['id']} {ingested['full_name']} "
      f"seniority={ingested['seniority']} years={ingested['years_experience']} "
      f"skills={ingested['skills_detected']} loc={ingested['location']}")
ok += 1

status, rediscovery = call("POST", "/rediscovery", {
    "jd_text": (
        "Senior Backend Engineer (5+ years) for our Dubai logistics platform. "
        "You will build Python/FastAPI services with PostgreSQL, Redis and Docker, "
        "own services end to end, and work with Kubernetes and Kafka. Fintech or "
        "logistics experience is a plus."
    ),
    "title": "Senior Backend Engineer",
    "company_name": "Example Freight Co",
    "limit": 5,
})
assert status == 200, rediscovery
print(f"[7] rediscovery     ok | job={rediscovery['job']['id']} "
      f"skills={rediscovery['parsed_jd']['skills'][:6]} gaps={rediscovery['gaps']}")
for item in rediscovery["matches"][:3]:
    print(f"      #{item['rank']} {item['full_name']:22s} {item['location']}")
ok += 1

status, saved = call("POST", "/saved-searches", {
    "name": "Smoke: Berlin backend + k8s",
    "query": {"raw": "senior python backend engineer in Berlin", "strategy": "hybrid",
              "rerank": True, "limit": 10},
})
assert status == 201
status, rerun = call("POST", f"/saved-searches/{saved['id']}/run")
assert status == 200 and rerun["saved_search"]["run_count"] == 1
print(f"[8] saved search    ok | id={saved['id']} run_count={rerun['saved_search']['run_count']} "
      f"results={len(rerun['results'])}")
ok += 1

status, recent = call("GET", "/search/recent?limit=5")
assert status == 200 and len(recent) >= 3
print(f"[9] search log      ok | recent={[(r['raw_query'][:40], r['result_count']) for r in recent[:3]]}")
ok += 1

status, benchmark = call("GET", "/evaluation/benchmark")
assert status == 200 and benchmark["metrics"]
print("[10] benchmark      ok | " + " | ".join(
    f"{k}: nDCG={v['ndcg_at_k']} MRR={v['mrr']}" for k, v in benchmark["metrics"].items()))
ok += 1

status, run = call("POST", "/evaluation/run", {"k": 10, "strategies": ["lexical", "hybrid_rerank"]})
assert status == 201 and set(run["metrics"].keys()) == {"lexical", "hybrid_rerank"}
print(f"[11] eval run       ok | run_id={run['benchmark_run_id']} k={run['k']} "
      f"duration={run['duration_ms']}ms")
ok += 1

print(f"\nSMOKE PASS — {ok}/11 routes exercised against the live server")
