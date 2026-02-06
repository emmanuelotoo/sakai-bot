"""
Exam and quiz detector for Sakai.

Detects exams and quizzes from:
- Announcements containing exam-related keywords
- Tests & Quizzes tool (via REST API if available)
"""

import logging
import re
from datetime import datetime
from hashlib import md5
from typing import List, Optional

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Announcement, Course, Exam
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ExamDetector(BaseScraper):
    """
    Detects exams and quizzes from Sakai content.

    Uses keyword matching on announcements and checks the
    Tests & Quizzes tool via REST API.
    """

    EXAM_KEYWORDS = [
        "exam", "examination", "midterm", "mid-term", "mid term",
        "final", "finals", "quiz", "quizz", "test", "assessment",
        "practical", "lab exam", "oral exam", "viva", "defense",
        "end of semester", "end-of-semester", "eos exam",
        "continuous assessment", "ca test", "ca exam",
    ]

    DATE_PATTERNS = [
        # January 15, 2024
        r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}',
        # 15/01/2024
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
    ]

    TIME_PATTERNS = [
        r'\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?',
        r'\d{1,2}\s*(?:am|pm|AM|PM)',
    ]

    def __init__(self, session: SakaiSession):
        """Initialize exam detector."""
        super().__init__(session)

    def scrape(
        self,
        courses: List[Course],
        announcements: Optional[List[Announcement]] = None,
    ) -> List[Exam]:
        """
        Detect exams from courses and announcements.

        Args:
            courses: List of enrolled courses
            announcements: Optional pre-scraped announcements

        Returns:
            List[Exam]: Detected exams
        """
        all_exams: List[Exam] = []

        # Detect from announcements
        if announcements:
            for announcement in announcements:
                exam = self._detect_from_announcement(announcement)
                if exam:
                    all_exams.append(exam)

        # Deduplicate by ID
        seen_ids: set = set()
        unique_exams: List[Exam] = []
        for exam in all_exams:
            if exam.id not in seen_ids:
                seen_ids.add(exam.id)
                unique_exams.append(exam)

        logger.info(f"Detected {len(unique_exams)} exams/quizzes")
        return unique_exams

    def _detect_from_announcement(
        self, announcement: Announcement
    ) -> Optional[Exam]:
        """
        Detect exam from announcement content.

        Args:
            announcement: Announcement to analyze

        Returns:
            Exam or None if not exam-related
        """
        full_text = f"{announcement.title} {announcement.content}".lower()

        if not self._contains_exam_keywords(full_text):
            return None

        exam_type = self._determine_exam_type(full_text)
        exam_date = self._extract_exam_date(announcement.content)
        exam_time = self._extract_exam_time(announcement.content)
        location = self._extract_location(announcement.content)

        exam_id = f"ann-{announcement.id}"

        return Exam(
            id=exam_id,
            course_code=announcement.course_code,
            course_title=announcement.course_title,
            title=announcement.title,
            exam_type=exam_type,
            exam_date=exam_date,
            exam_time=exam_time,
            location=location,
            source="announcement",
            source_id=announcement.id,
            url=announcement.url,
            notes=announcement.content[:300] if announcement.content else None,
        )

    def _contains_exam_keywords(self, text: str) -> bool:
        """Check if text contains exam-related keywords."""
        for keyword in self.EXAM_KEYWORDS:
            if keyword in text:
                return True
        return False

    def _determine_exam_type(self, text: str) -> str:
        """Determine the type of exam from text."""
        if "midterm" in text or "mid-term" in text or "mid term" in text:
            return "midterm"
        if "final" in text:
            return "final"
        if "quiz" in text:
            return "quiz"
        if "practical" in text or "lab exam" in text:
            return "practical"
        if "oral" in text or "viva" in text:
            return "oral"
        if "continuous assessment" in text or "ca test" in text:
            return "continuous_assessment"
        return "exam"

    def _extract_exam_date(self, text: str) -> Optional[datetime]:
        """Extract date from text using patterns."""
        if not text:
            return None
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self.parse_date(match.group(0))
        return None

    def _extract_exam_time(self, text: str) -> Optional[str]:
        """Extract time from text."""
        if not text:
            return None
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location/venue from text."""
        if not text:
            return None
        patterns = [
            r'(?:venue|location|room|hall|lab)[\s:]+([^\n,.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
