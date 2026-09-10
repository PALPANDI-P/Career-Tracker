import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

db = Path("data/career_tracker.db")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Show latest run stats
cur.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT 1")
run = cur.fetchone()

print("=" * 65)
print("PIPELINE RUN SUMMARY  (2026-08-12)")
print("=" * 65)
print(f"  Companies scanned : {run['companies_processed']}")
print(f"  Total jobs found  : {run['jobs_found']}")
print(f"  NEW jobs (unseen) : {run['jobs_new']}")
print()

# Real jobs from good ATS sources (Greenhouse, Lever) — filter out JS garbage
cur.execute("""
    SELECT company, title, job_id, first_seen_at
    FROM seen_hashes
    WHERE title NOT LIKE '%Javascript%'
      AND title NOT LIKE '%Script%'
      AND title NOT LIKE '%<script%'
      AND title NOT LIKE '%function(%'
      AND title NOT LIKE '%Async Src%'
      AND title NOT LIKE '%async src%'
      AND length(title) < 120
    ORDER BY first_seen_at DESC
    LIMIT 300
""")
rows = cur.fetchall()

by_company = {}
for r in rows:
    c = r['company']
    if c not in by_company:
        by_company[c] = []
    by_company[c].append(r['title'])

total = sum(len(v) for v in by_company.values())
print(f"CLEAN NEW JOBS: {total} across {len(by_company)} companies")
print("=" * 65)

for company, titles in sorted(by_company.items(), key=lambda x: -len(x[1])):
    print(f"\n  [{company}]  ({len(titles)} roles)")
    for t in sorted(titles):
        print(f"    - {t}")

conn.close()
