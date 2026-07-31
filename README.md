# Career Tracker 🎯

AI-powered career page tracker that monitors company job boards, matches listings against your profile, and delivers Telegram alerts — with LLM agents used **only** where judgment is genuinely required.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Orchestrator │────▶│  Fetch Agent  │────▶│  Extraction  │
│  (plain loop)│     │ (requests/PW) │     │    Agent     │
└──────┬───────┘     └──────────────┘     │ (hybrid LLM) │
       │                                   └──────┬───────┘
       │                                          │
       │              ┌──────────────┐            │
       │              │   Dedup      │◀───────────┘
       │              │ (hash store) │    List[Job]
       │              └──────┬───────┘
       │                     │
       ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Seniority  │◀────│ Match & Judge │────▶│  Notifier    │
│    Filter    │     │ (TF-IDF+LLM) │     │ Agent (LLM)  │
│  (regex)     │     └──────────────┘     └──────┬───────┘
└──────────────┘                                  │
                                                  ▼
                                           ┌──────────────┐
                                           │   Telegram    │
                                           └──────────────┘
```

### Agent Boundaries

| Component | LLM? | Purpose |
|-----------|-------|---------|
| Orchestrator | ❌ | Loop, dispatch, retry — plain Python |
| Fetch Agent | ❌ | HTTP requests or Playwright — deterministic |
| Extraction Agent | 🔶 Hybrid | ATS JSON first, LLM fallback for messy HTML |
| Match & Judge | 🔶 Hybrid | TF-IDF baseline, LLM only for borderline (55–80%) |
| Notifier Agent | ✅ | Drafts 2–3 line "why this fits" notes |
| Resume Advisor | ✅ | On-demand JD↔resume comparison (stretch) |

## Quick Start

```bash
# Clone and install
git clone <repo-url> career-tracker
cd career-tracker
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Edit your profile
# Edit config/profile.yaml with your skills and preferences

# Run the pipeline
career-tracker run

# Run tests
pytest
```

## Project Structure

```
career-tracker/
  companies/           # YAML company configs
  config/              # Settings + user profile
  schema/              # Pydantic Job model (shared contract)
  fetcher/             # Page fetching (requests / Playwright)
  extractor/           # Job extraction (ATS parsers / LLM fallback)
  dedup/               # SQLite-based deduplication
  matcher/             # TF-IDF scoring + LLM judgment
  filter/              # Seniority regex filter
  notifier/            # Telegram alerts + LLM note drafting
  orchestrator/        # Main pipeline loop
  scheduler/           # APScheduler cron
  advisor/             # Resume advisor (stretch goal)
  dashboard/           # Flask + HTMX web UI
  tests/               # pytest test suite
```

## Build Phases

| Phase | What | Agent Added |
|-------|------|-------------|
| 0 | Foundation + Schema | — |
| 1 | MVP Crawler (ATS JSON) | Extraction Agent (stubbed) |
| 2 | TF-IDF Matching | Match Agent (baseline only) |
| 3 | Telegram Notifications | Notifier Agent (first LLM) |
| 4 | Scheduler + DB | Orchestrator formalized |
| 5 | JS Pages + HTML | Extraction Agent LLM goes live |
| 6 | Dashboard | — |
| 7 | AI Upgrade | LLM Judge + Resume Advisor |
| 8 | Polish | — |

## License

MIT
