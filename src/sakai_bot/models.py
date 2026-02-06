"""
Data models for Sakai Monitoring Bot.

Defines Pydantic models for all scraped entities:
- Course
- Announcement
- Assignment
- Exam/Quiz
"""

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class NotificationType(str, Enum):
    """Types of notifications the bot can send."""
    ANNOUNCEMENT = "announcement"
    ASSIGNMENT = "assignment"
    EXAM = "exam"


class AssignmentStatus(str, Enum):
    """Status of an assignment."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"
    LATE = "late"
    CLOSED = "closed"


class Course(BaseModel):
    """
    Represents an enrolled course in Sakai.
    
    Attributes:
        site_id: Unique Sakai site identifier
        code: Course code (e.g., "CSCD 101")
        title: Full course title
        url: Direct URL to the course site
    """
    site_id: str
    code: str
    title: str
    url: str
    
    @computed_field
    @property
    def display_name(self) -> str:
        """Formatted course name for display."""
        return f"{self.code}: {self.title}" if self.code else self.title


class Announcement(BaseModel):
    """
    Represents a course announcement.
    
    Attributes:
        id: Unique announcement identifier from Sakai
        course_code: Code of the course this belongs to
        course_title: Title of the course
        title: Announcement title
        content: Full announcement content/body
        author: Name of the person who posted
        posted_at: When the announcement was posted
        url: Direct link to the announcement
    """
    id: str
    course_code: str
    course_title: str
    title: str
    content: str
    author: Optional[str] = None
    posted_at: Optional[datetime] = None
    url: Optional[str] = None
    
    @computed_field
    @property
    def dedup_key(self) -> str:
        """Unique key for deduplication."""
        return f"announcement:{self.id}"
    
    @computed_field
    @property
    def content_hash(self) -> str:
        """Hash of content for change detection."""
        content_str = f"{self.title}|{self.content}"
        return sha256(content_str.encode()).hexdigest()[:16]
    
    @property
    def notification_type(self) -> NotificationType:
        return NotificationType.ANNOUNCEMENT


class Assignment(BaseModel):
    """
    Represents a course assignment.
    
    Attributes:
        id: Unique assignment identifier from Sakai
        course_code: Code of the course this belongs to
        course_title: Title of the course
        title: Assignment title
        description: Assignment instructions/description
        due_date: When the assignment is due
        open_date: When the assignment opens for submission
        close_date: When submissions close
        status: Current status of the assignment
        url: Direct link to the assignment
    """
    id: str
    course_code: str
    course_title: str
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    open_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    status: AssignmentStatus = AssignmentStatus.NOT_STARTED
    max_points: Optional[float] = None
    url: Optional[str] = None
    
    @computed_field
    @property
    def dedup_key(self) -> str:
        """Unique key for deduplication."""
        return f"assignment:{self.id}"
    
    @computed_field
    @property
    def content_hash(self) -> str:
        """Hash of content for change detection."""
        content_str = f"{self.title}|{self.due_date}|{self.status}"
        return sha256(content_str.encode()).hexdigest()[:16]
    
    @property
    def notification_type(self) -> NotificationType:
        return NotificationType.ASSIGNMENT
    
    @property
    def is_upcoming(self) -> bool:
        """Check if assignment is still upcoming (not past due)."""
        if self.due_date is None:
            return True
        return self.due_date > datetime.now(timezone.utc)


class Exam(BaseModel):
    """
    Represents an exam or quiz.
    
    Exams can be detected from:
    - Announcements containing exam-related keywords
    - Calendar events
    - Assignment tool (Sakai tests/quizzes)
    
    Attributes:
        id: Unique identifier (may be derived from source)
        course_code: Code of the course
        course_title: Title of the course
        title: Exam/quiz title
        exam_type: Type (exam, quiz, test, midterm, final)
        exam_date: When the exam takes place
        exam_time: Specific time of the exam
        location: Where the exam takes place (if in-person)
        duration_minutes: Duration in minutes
        source: Where this was detected from (announcement, calendar, etc.)
        source_id: ID from the source for dedup
        url: Link to more information
    """
    id: str
    course_code: str
    course_title: str
    title: str
    exam_type: str = "exam"
    exam_date: Optional[datetime] = None
    exam_time: Optional[str] = None
    location: Optional[str] = None
    duration_minutes: Optional[int] = None
    source: str = "announcement"
    source_id: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None
    
    @computed_field
    @property
    def dedup_key(self) -> str:
        """Unique key for deduplication."""
        return f"exam:{self.id}"
    
    @computed_field
    @property
    def content_hash(self) -> str:
        """Hash of content for change detection."""
        content_str = f"{self.title}|{self.exam_date}|{self.exam_time}"
        return sha256(content_str.encode()).hexdigest()[:16]
    
    @property
    def notification_type(self) -> NotificationType:
        return NotificationType.EXAM


class SentNotification(BaseModel):
    """
    Record of a sent notification for deduplication.
    
    Stored in Supabase to prevent duplicate alerts.
    """
    id: Optional[int] = None
    notification_type: NotificationType
    dedup_key: str = Field(..., description="Unique identifier for this notification")
    content_hash: str = Field(..., description="Hash of content for change detection")
    course_code: Optional[str] = None
    title: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
