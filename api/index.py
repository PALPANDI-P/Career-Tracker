"""
Career Tracker — Vercel Serverless Entrypoint

Imports the Flask app factory and exports `app` for Vercel Serverless Function deployment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to Python module path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set VERCEL environment indicator
os.environ["VERCEL"] = "1"

from dashboard.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
