"""
Career Tracker — Flask Web Dashboard

Premium dark-mode dashboard with glassmorphism design,
color-coded job notifications, live SSE updates,
and a searchable company directory.
"""

from __future__ import annotations

import json
import logging
import queue
import sqlite3
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from config.settings import get_settings, PROJECT_ROOT
from schema.job import Job, NotificationPriority, JobCategory

logger = logging.getLogger(__name__)

# ─── Global SSE Event Queue ──────────────────────────
# Dashboard clients connect via SSE and receive events
# pushed from the pipeline when new jobs are found.
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def create_app() -> Flask:
    """Flask application factory."""
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "dashboard" / "templates"),
        static_folder=str(PROJECT_ROOT / "dashboard" / "static"),
    )
    app.config["SECRET_KEY"] = "career-tracker-dashboard-secret"

    # Ensure database and tables exist
    try:
        settings = get_settings()
        ensure_notification_tables(settings.db_path)
    except Exception as e:
        logger.warning("Failed to initialize database tables: %s", e)


    @app.template_filter("human_date")
    def _human_date_filter(val: str | None) -> str:
        if not val:
            return "Recently"
        try:
            # Parse ISO date string
            if "T" in str(val):
                clean_val = str(val).split(".")[0].replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_val)
            else:
                dt = datetime.strptime(str(val)[:19], "%Y-%m-%d %H:%M:%S")

            now = datetime.now(timezone.utc)
            diff = now - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else now - dt
            seconds = int(diff.total_seconds())

            if seconds < 60:
                return "Just now"
            elif seconds < 3600:
                mins = seconds // 60
                return f"{mins} min{'s' if mins > 1 else ''} ago"
            elif seconds < 86400:
                hours = seconds // 3600
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif seconds < 172800:
                return f"Yesterday at {dt.strftime('%I:%M %p')}"
            else:
                return dt.strftime("%b %d, %Y")
        except Exception:
            return str(val)[:10] if val else "Recently"

    # ── Register Routes ──────────────────────────────
    register_routes(app)

    return app


def register_routes(app: Flask) -> None:
    """Register all dashboard routes."""

    @app.route("/")
    def index():
        """Main dashboard page."""
        settings = get_settings()
        stats = _get_dashboard_stats(settings.db_path)
        recent_notifications = _get_recent_notifications(settings.db_path, limit=20)
        return render_template(
            "index.html",
            stats=stats,
            notifications=recent_notifications,
        )

    @app.route("/jobs")
    def jobs_page():
        """Job listings with filtering."""
        settings = get_settings()
        region = request.args.get("region", "all")
        category = request.args.get("category", "all")
        search_q = request.args.get("q", "")
        jobs_list = _get_jobs(
            settings.db_path, region=region, category=category, search=search_q
        )
        return render_template(
            "jobs.html",
            jobs=jobs_list,
            current_region=region,
            current_category=category,
            search_q=search_q,
        )

    @app.route("/companies")
    def companies_page():
        """Company directory with career page links."""
        region = request.args.get("region", "all")
        category = request.args.get("category", "all")
        companies_list = _get_companies(region=region, category=category)
        return render_template(
            "companies.html",
            companies=companies_list,
            current_region=region,
            current_category=category,
        )

    @app.route("/notifications")
    def notifications_page():
        """Full notification history."""
        settings = get_settings()
        notifications = _get_recent_notifications(settings.db_path, limit=100)
        return render_template("notifications.html", notifications=notifications)

    @app.route("/survey")
    def survey_page():
        """Fresher hiring trends & company recruitment survey."""
        from advisor.ai_engine import get_fresher_hiring_survey
        survey_data = get_fresher_hiring_survey()
        return render_template("survey.html", survey=survey_data)

    @app.route("/discovery")
    def discovery_page():
        """Startup & Mid-size Company Discovery Dashboard."""
        settings = get_settings()
        from dedup.store import DedupStore
        store = DedupStore(settings.db_path)
        status_filter = request.args.get("status", "all")
        priority_filter = request.args.get("priority", "all")
        companies = store.get_discovered_companies(status=status_filter, priority=priority_filter, limit=100)
        return render_template(
            "discovery.html",
            companies=companies,
            current_status=status_filter,
            current_priority=priority_filter,
        )

    @app.route("/discovery/company/<int:company_id>")
    def discovery_company_detail(company_id: int):
        """Company Intelligence & Evidence Detail view."""
        settings = get_settings()
        from dedup.store import DedupStore
        store = DedupStore(settings.db_path)
        companies = store.get_discovered_companies(limit=500)
        co = next((c for c in companies if c.get("id") == company_id), None)
        if not co:
            return "Company not found", 404
        return render_template("discovery_detail.html", company=co)

    # ── API Endpoints ─────────────────────────────────

    @app.route("/api/pipeline/run", methods=["POST"])
    def api_run_pipeline():
        """Trigger background pipeline refresh and dispatch email alerts."""
        def _run_bg():
            try:
                from orchestrator.run import main as run_orchestrator
                run_orchestrator()
            except Exception as e:
                logger.warning("Background pipeline execution error: %s", e)

        thread = threading.Thread(target=_run_bg, daemon=True)
        thread.start()

        return jsonify({
            "status": "started",
            "message": "Pipeline scan initiated! New fresher jobs are being fetched and notifications sent to palulaptop@gmail.com.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.route("/api/cron/run", methods=["GET", "POST"])
    def api_cron_run():
        """Vercel Cron endpoint to run job aggregator periodically."""
        try:
            from orchestrator.api_pipeline import run_api_pipeline
            summary = run_api_pipeline()
            return jsonify({
                "status": "success",
                "summary": summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning("Vercel cron execution error: %s", e)
            return jsonify({"status": "error", "message": str(e)}), 500


    @app.route("/api/stats")
    def api_stats():
        """Dashboard stats JSON."""
        settings = get_settings()
        return jsonify(_get_dashboard_stats(settings.db_path))

    @app.route("/api/ai/survey")
    def api_ai_survey():
        """Fresher recruitment AI survey JSON."""
        from advisor.ai_engine import get_fresher_hiring_survey
        return jsonify(get_fresher_hiring_survey())

    @app.route("/api/notifications")
    def api_notifications():
        """Recent notifications JSON."""
        settings = get_settings()
        limit = request.args.get("limit", 20, type=int)
        return jsonify(_get_recent_notifications(settings.db_path, limit=limit))

    @app.route("/api/jobs/export")
    def api_export_jobs():
        """Export job notifications as a CSV file."""
        import csv
        import io

        settings = get_settings()
        jobs = _get_recent_notifications(settings.db_path, limit=500)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Job Title", "Company", "Location", "Match Score", "Priority", "Category", "Apply URL", "Match Reason", "Posted Date"])

        for job in jobs:
            writer.writerow([
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                f"{int(job.get('match_score', 0) * 100)}%",
                job.get("priority", ""),
                job.get("category", ""),
                job.get("url", ""),
                job.get("match_reason", ""),
                job.get("created_at", ""),
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=fresher_jobs_digest.csv"},
        )

    @app.route("/api/health")
    def api_health():
        """System health and diagnostic status endpoint."""
        import sys
        import os
        settings = get_settings()
        stats = _get_dashboard_stats(settings.db_path)
        return jsonify({
            "status": "healthy",
            "version": "0.1.0",
            "python_version": sys.version.split()[0],
            "environment": "vercel" if os.getenv("VERCEL") else "local",
            "db_path": settings.db_path,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Discovery API Endpoints ───────────────────────

    @app.route("/api/companies/discovered")
    def api_discovered_companies():
        """Get list of all discovered companies."""
        settings = get_settings()
        from dedup.store import DedupStore
        store = DedupStore(settings.db_path)
        status_f = request.args.get("status", "all")
        priority_f = request.args.get("priority", "all")
        limit = request.args.get("limit", 100, type=int)
        companies = store.get_discovered_companies(status=status_f, priority=priority_f, limit=limit)
        return jsonify(companies)

    @app.route("/api/companies/startups")
    def api_companies_startups():
        """Get list of discovered startups."""
        settings = get_settings()
        from dedup.store import DedupStore
        store = DedupStore(settings.db_path)
        all_co = store.get_discovered_companies(limit=500)
        startups = [c for c in all_co if "STARTUP" in str(c.get("company_size", "")).upper()]
        return jsonify(startups)

    @app.route("/api/companies/mid-size")
    def api_companies_mid_size():
        """Get list of discovered mid-size companies."""
        settings = get_settings()
        from dedup.store import DedupStore
        store = DedupStore(settings.db_path)
        all_co = store.get_discovered_companies(limit=500)
        mid_size = [c for c in all_co if "MID_SIZE" in str(c.get("company_size", "")).upper()]
        return jsonify(mid_size)

    @app.route("/api/companies/active-hiring")
    def api_companies_active_hiring():
        """Get list of companies actively hiring."""
        settings = get_settings()
        from dedup.store import DedupStore
        store = DedupStore(settings.db_path)
        all_co = store.get_discovered_companies(limit=500)
        active = [c for c in all_co if c.get("priority") in ["P0", "P1"]]
        return jsonify(active)

    @app.route("/api/discovery/run", methods=["POST"])
    def api_run_discovery():
        """Trigger dynamic company discovery cycle."""
        try:
            from discovery.pipeline import run_company_discovery_pipeline
            summary = run_company_discovery_pipeline()
            return jsonify({
                "status": "success",
                "summary": summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning("Discovery run error: %s", e)
            return jsonify({"status": "error", "message": str(e)}), 500


    @app.route("/api/jobs/<job_id>/status", methods=["PUT"])
    def api_update_job_status(job_id: str):
        """Update job application status (saved, applied, interviewing, rejected)."""
        data = request.get_json(silent=True) or {}
        new_status = data.get("status", "unread")

        valid_statuses = {"unread", "saved", "applied", "interviewing", "rejected"}
        if new_status not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400

        settings = get_settings()
        ensure_notification_tables(settings.db_path)
        with sqlite3.connect(settings.db_path) as conn:
            conn.execute(
                "UPDATE notifications SET status = ? WHERE job_id = ?",
                (new_status, job_id),
            )
            conn.commit()

        return jsonify({"status": "updated", "job_id": job_id, "new_status": new_status})

    @app.route("/api/resume/analyze", methods=["POST"])
    def api_analyze_resume():
        """Analyze resume alignment against a job description using AI engine."""
        from advisor.ai_engine import analyze_fresher_fit_ai
        data = request.get_json(silent=True) or {}

        job_title = data.get("job_title", "Software Developer")
        job_desc = data.get("job_desc", "")
        company = data.get("company", "Tech Company")
        skills = data.get("skills", ["Python", "Flask", "SQL", "React"])
        user_summary = data.get("user_summary", "MCA fresher seeking developer roles.")

        if not job_desc:
            return jsonify({"error": "Missing job_desc parameter"}), 400

        score, reason, note = analyze_fresher_fit_ai(
            job_title=job_title,
            job_desc=job_desc,
            company=company,
            skills=skills,
            user_summary=user_summary,
        )

        return jsonify({
            "match_score": score,
            "match_percentage": f"{int(score * 100)}%",
            "match_reason": reason,
            "fresher_note": note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Server-Sent Events (SSE) ─────────────────────

    @app.route("/stream")
    def stream():
        """SSE endpoint for live job notifications."""

        def event_stream():
            q: queue.Queue = queue.Queue()
            with _sse_lock:
                _sse_clients.append(q)
            try:
                # Send initial heartbeat
                yield "data: {\"type\": \"connected\"}\n\n"
                while True:
                    try:
                        event = q.get(timeout=30)
                        yield f"data: {json.dumps(event)}\n\n"
                    except queue.Empty:
                        # Send keepalive every 30s
                        yield ": keepalive\n\n"
            except GeneratorExit:
                pass
            finally:
                with _sse_lock:
                    if q in _sse_clients:
                        _sse_clients.remove(q)

        return Response(
            event_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # ── HTMX Partials ─────────────────────────────────

    @app.route("/partials/job-card/<job_id>")
    def partial_job_card(job_id: str):
        """Render a single job card (HTMX partial)."""
        settings = get_settings()
        job_data = _get_job_by_id(settings.db_path, job_id)
        if not job_data:
            return "", 404
        return render_template("partials/job_card.html", job=job_data)

    @app.route("/partials/notification/<int:notif_id>")
    def partial_notification(notif_id: int):
        """Render a single notification card (HTMX partial)."""
        settings = get_settings()
        notif = _get_notification_by_id(settings.db_path, notif_id)
        if not notif:
            return "", 404
        return render_template("partials/notification.html", notification=notif)


# ─── SSE Push Function (called from pipeline) ───────

def push_notification(notification: dict) -> None:
    """Push a notification event to all connected SSE clients."""
    with _sse_lock:
        for client_queue in _sse_clients:
            try:
                client_queue.put_nowait(notification)
            except queue.Full:
                pass


# ─── Notification DB Helpers ─────────────────────────

def ensure_notification_tables(db_path: str) -> None:
    """Create notification tables if they don't exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path, timeout=20.0) as conn:

        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except sqlite3.OperationalError:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                url TEXT NOT NULL,
                match_score REAL DEFAULT 0.0,
                match_reason TEXT DEFAULT '',
                priority TEXT DEFAULT 'normal',
                category TEXT DEFAULT 'unknown',
                region TEXT DEFAULT 'global',
                city TEXT,
                is_read INTEGER DEFAULT 0,
                is_emailed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'unread',
                created_at TEXT NOT NULL,
                UNIQUE(job_id)
            )
        """)
        # Ensure status & is_emailed columns exist if table was created previously
        try:
            conn.execute("ALTER TABLE notifications ADD COLUMN status TEXT DEFAULT 'unread'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE notifications ADD COLUMN is_emailed INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notif_priority
            ON notifications (priority)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notif_created
            ON notifications (created_at DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notif_region
            ON notifications (region)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notif_search_composite
            ON notifications (title, company, region)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notif_status
            ON notifications (status)
        """)
        conn.commit()



def save_notification(db_path: str, notification: dict) -> int:
    """Save a notification to the database. Returns the notification ID."""
    ensure_notification_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO notifications
            (job_id, title, company, location, url, match_score, match_reason,
             priority, category, region, city, is_fresher_eligible, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notification.get("job_id", ""),
                notification.get("title", ""),
                notification.get("company", ""),
                notification.get("location"),
                notification.get("url", ""),
                notification.get("match_score", 0.0),
                notification.get("match_reason", ""),
                notification.get("priority", "normal"),
                notification.get("category", "unknown"),
                notification.get("region", "global"),
                notification.get("city"),
                1 if notification.get("is_fresher_eligible") else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def determine_priority(match_score: float, is_fresher: bool, job_category: str) -> str:
    """
    Determine notification priority based on match score and job category.

    Priority mapping:
    - URGENT (red):   walk-in or limited deadline
    - HOT (green):    score >= 80% AND fresher-eligible
    - GOOD (blue):    score >= 65%
    - WORTH_CHECKING (yellow): score 55-65%
    - NEW (purple):   any new job
    """
    if job_category == "walk_in":
        return NotificationPriority.URGENT.value

    if match_score >= 0.80 and is_fresher:
        return NotificationPriority.HOT.value

    if match_score >= 0.65:
        return NotificationPriority.GOOD.value

    if match_score >= 0.55:
        return NotificationPriority.WORTH_CHECKING.value

    return NotificationPriority.NEW.value


# ─── Private DB Query Functions ──────────────────────

def _get_dashboard_stats(db_path: str) -> dict:
    """Get summary stats for the dashboard."""
    ensure_notification_tables(db_path)
    companies = _get_companies(region="all", category="all")
    total_genuine_companies = len(companies)

    try:
        with sqlite3.connect(db_path) as conn:
            total_jobs = conn.execute(
                "SELECT COUNT(*) FROM seen_hashes"
            ).fetchone()[0]
            total_notifications = conn.execute(
                "SELECT COUNT(*) FROM notifications"
            ).fetchone()[0]
            unread = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE is_read = 0"
            ).fetchone()[0]
            hot_count = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE priority IN ('hot', 'urgent')"
            ).fetchone()[0]

            # Last run info
            last_run = None
            try:
                row = conn.execute(
                    "SELECT timestamp, companies_processed, jobs_found, jobs_new "
                    "FROM runs ORDER BY run_id DESC LIMIT 1"
                ).fetchone()
                if row:
                    last_run = {
                        "timestamp": row[0],
                        "companies": row[1],
                        "jobs_found": row[2],
                        "jobs_new": row[3],
                    }
            except sqlite3.OperationalError:
                pass

        return {
            "total_genuine_companies": total_genuine_companies,
            "total_jobs_tracked": total_jobs,
            "total_notifications": total_notifications,
            "unread_count": unread,
            "hot_matches": hot_count,
            "last_run": last_run,
        }
    except sqlite3.OperationalError:
        return {
            "total_genuine_companies": total_genuine_companies,
            "total_jobs_tracked": 0,
            "total_notifications": 0,
            "unread_count": 0,
            "hot_matches": 0,
            "last_run": None,
        }


def _get_recent_notifications(db_path: str, limit: int = 20) -> list[dict]:
    """Get recent notifications ordered by creation date."""
    ensure_notification_tables(db_path)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM notifications
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []


def _get_jobs(
    db_path: str, region: str = "all", category: str = "all", search: str = ""
) -> list[dict]:
    """Get jobs with optional filtering."""
    ensure_notification_tables(db_path)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM notifications WHERE 1=1"
            params: list = []

            if region != "all":
                query += " AND region = ?"
                params.append(region)
            if category != "all":
                query += " AND category = ?"
                params.append(category)
            if search:
                query += " AND (title LIKE ? OR company LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])

            query += " ORDER BY created_at DESC LIMIT 200"
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []


def _get_job_by_id(db_path: str, job_id: str) -> dict | None:
    """Get a single job by ID."""
    ensure_notification_tables(db_path)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM notifications WHERE job_id = ?", (job_id,)
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None


def _get_notification_by_id(db_path: str, notif_id: int) -> dict | None:
    """Get a single notification by ID."""
    ensure_notification_tables(db_path)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM notifications WHERE id = ?", (notif_id,)
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None


def _get_companies(region: str = "all", category: str = "all") -> list[dict]:
    """Load companies from YAML files and return as a filtered list."""
    import yaml

    settings = get_settings()
    companies_dir = Path(settings.companies_dir)
    all_companies = []

    yaml_files = [
        "tier1.yaml",
        "tamil_nadu.yaml",
        "karnataka.yaml",
        "kerala.yaml",
    ]

    for yaml_file in yaml_files:
        filepath = companies_dir / yaml_file
        if not filepath.exists():
            continue
        with open(filepath, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
        for co in data.get("companies", []):
            co["source_file"] = yaml_file.replace(".yaml", "")
            # Derive region from tags or filename
            tags = co.get("tags", [])
            if "tamil-nadu" in tags:
                co["_region"] = "tamil_nadu"
            elif "karnataka" in tags:
                co["_region"] = "karnataka"
            elif "kerala" in tags:
                co["_region"] = "kerala"
            else:
                co["_region"] = "global"

            # Derive category from tags
            if "big-tech" in tags:
                co["_category"] = "big-tech"
            elif "mnc" in tags or "services" in tags:
                co["_category"] = "mnc"
            elif "startup" in tags:
                co["_category"] = "startup"
            elif "product-company" in tags or "unicorn" in tags:
                co["_category"] = "product"
            elif "consulting" in tags or "big4" in tags:
                co["_category"] = "consulting"
            elif "fintech" in tags or "banking" in tags:
                co["_category"] = "fintech"
            else:
                co["_category"] = "other"

            all_companies.append(co)

    # Apply filters
    if region != "all":
        all_companies = [c for c in all_companies if c["_region"] == region]
    if category != "all":
        all_companies = [c for c in all_companies if c["_category"] == category]

    return all_companies


# ─── App Runner ──────────────────────────────────────

def run_dashboard(host: str = "0.0.0.0", port: int = 5000, debug: bool = True) -> None:
    """Run the dashboard server."""
    app = create_app()
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run_dashboard()
