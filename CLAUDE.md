# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sakai Bot monitors a Sakai LMS instance for new announcements, assignments, and exams, then sends Telegram notifications. It deduplicates using Supabase (PostgreSQL) and runs every 2 hours via GitHub Actions.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Install in editable mode (dev)
pip install -e ".[dev]"

# Run the bot
python -m sakai_bot.main

# Tests
pytest
pytest --cov=src/sakai_bot

# Formatting & linting
black src/
ruff check src/
```

## Architecture

The bot follows a pipeline: **authenticate → scrape → deduplicate → format → notify**.

- **`src/sakai_bot/main.py`** — `SakaiMonitor` orchestrates the full workflow. Retries up to 2 times on auth errors with 60s+ backoff. Sends error notifications via Telegram on failure.
- **`src/sakai_bot/config.py`** — Pydantic Settings singleton (LRU-cached) loading from environment variables / `.env`.
- **`src/sakai_bot/models.py`** — Pydantic models for `Course`, `Announcement`, `Assignment`, `Exam`, `SentNotification`. Each notification model computes a `dedup_key` (stable ID) and `content_hash` (SHA256 for change detection).
- **`src/sakai_bot/auth/sakai_session.py`** — HTML form login to Sakai (`/portal/xlogin`), session cookie + CSRF management, auto-logout via context manager.
- **`src/sakai_bot/scrapers/`** — Base class with shared date parsing/HTML cleaning. Scrapers use Sakai REST APIs (`/direct/site.json`, `/direct/announcement/`, `/direct/assignment/`). `ExamDetector` extracts exams from announcement text via keyword/regex matching.
- **`src/sakai_bot/db/`** — Supabase client (cached singleton). `NotificationStore` uses `dedup_key` for primary dedup + `content_hash` for update detection. Falls back to in-memory dedup if table is missing.
- **`src/sakai_bot/notify/`** — `TelegramNotifier` sends via Bot API with automatic message splitting at 4096 chars. `MessageFormatter` produces rich Markdown with urgency indicators.

## Configuration

All config is via environment variables (see `.env.example`). Key variables: `SAKAI_BASE_URL`, `SAKAI_USERNAME`, `SAKAI_PASSWORD`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Optional: `CURRENT_SEMESTER`, `COURSE_LEVEL_FILTER`, `TIMEZONE` (default: `Africa/Accra`).

## CI/CD

GitHub Actions workflow (`.github/workflows/monitor.yml`) runs every 2 hours on `ubuntu-latest` with Python 3.11. Supports manual dispatch with a debug flag. Uploads error logs as artifacts on failure.

## Code Style

- Black with 100-char line length
- Ruff rules: E, F, W, I, N, UP, B, C4 (E501 ignored)
- Python 3.10+ target
