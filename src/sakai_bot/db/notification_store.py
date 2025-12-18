"""
Notification store for deduplication.

Stores records of sent notifications in Supabase to prevent
sending duplicate alerts for the same content.
"""

import logging
from datetime import datetime
from typing import Optional, Union

from supabase import Client

from sakai_bot.db.client import get_supabase_client
from sakai_bot.models import (
    Announcement,
    Assignment,
    Exam,
    NotificationType,
    SentNotification,
)

logger = logging.getLogger(__name__)

# Type alias for items that can be deduplicated
NotifiableItem = Union[Announcement, Assignment, Exam]

# Table name in Supabase
TABLE_NAME = "sent_notifications"


class NotificationStore:
    """
    Manages sent notification records in Supabase for deduplication.
    
    Uses a combination of:
    - dedup_key: Stable identifier (e.g., "announcement:12345")
    - content_hash: Hash of content to detect updates
    
    A notification is considered "new" if:
    1. The dedup_key doesn't exist in the database, OR
    2. The dedup_key exists but content_hash has changed (content was updated)
    """
    
    def __init__(self, client: Optional[Client] = None):
        """
        Initialize the notification store.
        
        Args:
            client: Optional Supabase client, will use default if not provided
        """
        self.client = client or get_supabase_client()
        self.table = self.client.table(TABLE_NAME)
    
    def has_been_sent(self, item: NotifiableItem) -> bool:
        """
        Check if a notification has already been sent for this item.
        
        Args:
            item: The item to check (Announcement, Assignment, or Exam)
            
        Returns:
            bool: True if this exact content has already been sent
        """
        try:
            result = (
                self.table
                .select("dedup_key, content_hash")
                .eq("dedup_key", item.dedup_key)
                .execute()
            )
            
            if not result.data:
                # Never sent before
                return False
            
            # Check if content has changed (updated item)
            existing = result.data[0]
            if existing["content_hash"] != item.content_hash:
                logger.info(
                    f"Content updated for {item.dedup_key}: "
                    f"{existing['content_hash']} -> {item.content_hash}"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking notification status: {e}")
            # Fail open - assume not sent to avoid missing notifications
            return False
    
    def mark_as_sent(self, item: NotifiableItem) -> bool:
        """
        Record that a notification has been sent for this item.
        
        Uses upsert to handle both new items and updates.
        
        Args:
            item: The item that was sent
            
        Returns:
            bool: True if successfully recorded
        """
        try:
            record = SentNotification(
                notification_type=item.notification_type,
                dedup_key=item.dedup_key,
                content_hash=item.content_hash,
                course_code=getattr(item, "course_code", None),
                title=item.title,
                sent_at=datetime.utcnow(),
            )
            
            # Upsert based on dedup_key
            self.table.upsert(
                record.model_dump(exclude={"id"}),
                on_conflict="dedup_key"
            ).execute()
            
            logger.debug(f"Marked as sent: {item.dedup_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking notification as sent: {e}")
            return False
    
    def get_sent_count(self, notification_type: Optional[NotificationType] = None) -> int:
        """
        Get count of sent notifications.
        
        Args:
            notification_type: Optional filter by type
            
        Returns:
            int: Number of sent notifications
        """
        try:
            query = self.table.select("id", count="exact")
            
            if notification_type:
                query = query.eq("notification_type", notification_type.value)
            
            result = query.execute()
            return result.count or 0
            
        except Exception as e:
            logger.error(f"Error getting sent count: {e}")
            return 0
    
    def clear_old_records(self, days: int = 90) -> int:
        """
        Clear notification records older than specified days.
        
        Useful for periodic cleanup to keep the table manageable.
        
        Args:
            days: Delete records older than this many days
            
        Returns:
            int: Number of records deleted
        """
        try:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            result = (
                self.table
                .delete()
                .lt("sent_at", cutoff.isoformat())
                .execute()
            )
            
            deleted = len(result.data) if result.data else 0
            logger.info(f"Cleared {deleted} notification records older than {days} days")
            return deleted
            
        except Exception as e:
            logger.error(f"Error clearing old records: {e}")
            return 0


# SQL for creating the Supabase table (run this in Supabase SQL Editor)
CREATE_TABLE_SQL = """
-- Create sent_notifications table for deduplication
CREATE TABLE IF NOT EXISTS sent_notifications (
    id BIGSERIAL PRIMARY KEY,
    notification_type TEXT NOT NULL,
    dedup_key TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    course_code TEXT,
    title TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Index for fast dedup lookups
    CONSTRAINT sent_notifications_dedup_key_unique UNIQUE (dedup_key)
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_sent_notifications_dedup_key 
    ON sent_notifications(dedup_key);

CREATE INDEX IF NOT EXISTS idx_sent_notifications_type 
    ON sent_notifications(notification_type);

CREATE INDEX IF NOT EXISTS idx_sent_notifications_sent_at 
    ON sent_notifications(sent_at);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE sent_notifications ENABLE ROW LEVEL SECURITY;

-- Create policy for service role (full access)
CREATE POLICY "Service role has full access" ON sent_notifications
    FOR ALL
    USING (true)
    WITH CHECK (true);
"""
