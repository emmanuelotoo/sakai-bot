"""Create the sent_notifications table in Supabase."""

import requests
from sakai_bot.config import get_settings

settings = get_settings()

# Use the Supabase Management API to run SQL
# We'll use the REST API with RPC or direct SQL
# Supabase service role key gives us admin access

# First, let's try creating via the PostgREST rpc endpoint
url = f"{settings.supabase_url}/rest/v1/rpc/exec_sql"
headers = {
    "apikey": settings.supabase_service_role_key,
    "Authorization": f"Bearer {settings.supabase_service_role_key}",
    "Content-Type": "application/json",
}

# The SQL to create the table
sql = """
CREATE TABLE IF NOT EXISTS sent_notifications (
    id BIGSERIAL PRIMARY KEY,
    notification_type TEXT NOT NULL,
    dedup_key TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    course_code TEXT,
    title TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sent_notifications_dedup_key
    ON sent_notifications (dedup_key);
"""

print("Trying to create table via RPC...")
resp = requests.post(url, headers=headers, json={"query": sql})
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

if resp.status_code != 200:
    print("\nRPC method didn't work. You need to create the table manually.")
    print("Go to https://supabase.com/dashboard, select your project,")
    print("go to SQL Editor, and run this SQL:\n")
    print(sql)
    print("\nAlternatively, the bot will work without it -")
    print("it just won't be able to deduplicate notifications.")
