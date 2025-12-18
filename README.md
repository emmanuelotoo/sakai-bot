# Sakai Bot

Monitors Sakai LMS for new announcements, assignments, and exams — sends WhatsApp notifications automatically.

## Features

- Tracks announcements across all courses
- Monitors assignments and deadlines
- Detects exams from announcements/calendar
- Sends WhatsApp alerts (Meta Cloud API)
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
WHATSAPP_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_RECIPIENT_PHONE=233XXXXXXXXX
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
- `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_RECIPIENT_PHONE`

The bot runs every 2 hours automatically. Trigger manually via **Actions → Sakai Monitor → Run workflow**.

## WhatsApp Setup

1. Create app at [Meta Developers](https://developers.facebook.com/)
2. Add WhatsApp product
3. Copy access token and phone number ID
4. Add your number to allowed recipients

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request
