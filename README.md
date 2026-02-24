# Sakai Bot

Monitors Sakai LMS for new announcements, assignments, and exams — sends Telegram notifications automatically. Runs every 2 hours via GitHub Actions.

## Setup

```bash
git clone https://github.com/emmanuelotoo/sakai-bot.git
cd sakai-bot
pip install -r requirements.txt
pip install -e .
cp .env.example .env   # fill in your credentials
python -m sakai_bot.main
```

## Supabase Table

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

## GitHub Actions Secrets

Add in **Settings → Secrets → Actions**:

`SAKAI_BASE_URL` · `SAKAI_USERNAME` · `SAKAI_PASSWORD` · `SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID`

## Telegram Setup

1. Message [@BotFather](https://t.me/BotFather), send `/newbot`, copy the token → `TELEGRAM_BOT_TOKEN`
2. Message [@userinfobot](https://t.me/userinfobot), copy your ID → `TELEGRAM_CHAT_ID`
3. Open your bot and click **Start**

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Screenshot

![Screenshot 2026-02-24 124927](./Screenshot%202026-02-24%20124927.png)
