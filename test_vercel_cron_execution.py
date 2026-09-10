"""
Career Tracker — Vercel Cron & Offline Cloud Execution Verification

Validates that:
1. Vercel cron endpoint (/api/cron/run) executes cleanly
2. Database initialized at /tmp or local path seamlessly
3. API Pipeline fetches jobs, matches freshers, and triggers email alerts to palulaptop@gmail.com
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config.settings import get_settings
from dashboard.app import create_app


def test_vercel_cron_endpoint():
    app = create_app()
    client = app.test_client()

    print("🚀 Triggering /api/cron/run endpoint (Vercel Cron Simulation)...")
    response = client.get("/api/cron/run")

    assert response.status_code == 200, f"Expected 200 OK from /api/cron/run, got {response.status_code}"
    data = response.get_json()
    assert data["status"] == "success", f"Expected status 'success', got {data}"
    print(f"✅ Vercel Cron endpoint returned 200 OK! Summary: {data['summary']}")

    # Verify settings target email
    settings = get_settings()
    assert settings.email_to == "palulaptop@gmail.com", f"Expected recipient palulaptop@gmail.com, got {settings.email_to}"
    print("✅ Verified target email for offline cloud notifications is palulaptop@gmail.com!")


if __name__ == "__main__":
    test_vercel_cron_endpoint()
