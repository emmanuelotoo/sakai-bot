# Sakai Bot

Monitors Sakai LMS for new announcements, assignments, and exams — sends Telegram notifications automatically.

## Features

- Tracks announcements across all courses
- Monitors assignments and deadlines
- Detects exams from announcements/calendar
- Sends Telegram alerts via Bot API
- Prevents duplicate notifications (Supabase)
- Runs on schedule via GitHub Actions

## Quick Start

### 1. Install

```bash
git clone https://github.com/emmanuelotoo/sakai-bot.git
cd sakai-bot
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Fill in `.env`:

```env
SAKAI_USERNAME=your_student_id
SAKAI_PASSWORD=your_password
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Set Up Supabase

Run in Supabase SQL Editor:

```sql
CREATE TABLE sent_notifications (
    id BIGSERIAL PRIMARY KEY,
    notification_type TEXT NOT NULL,
    dedup_key TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    course_code TEXT,
    title TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4. Run

```bash
python -m sakai_bot.main
```

## GitHub Actions

Add these secrets in **Settings → Secrets → Actions**:

- `SAKAI_USERNAME`, `SAKAI_PASSWORD`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

The bot runs every 2 hours automatically. Trigger manually via **Actions → Sakai Monitor → Run workflow**.

## Telegram Setup

1. **Create a bot**: Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the **API token** it gives you → `TELEGRAM_BOT_TOKEN`
4. **Get your chat ID**: Message [@userinfobot](https://t.me/userinfobot) or [@getidsbot](https://t.me/getidsbot)
5. Copy your **chat ID** → `TELEGRAM_CHAT_ID`
6. **Start your bot**: Open your bot in Telegram and click "Start" (required for the bot to message you)

> 💡 You can also use a group chat ID (add the bot to a group) or channel ID (add the bot as admin).

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request
