"""
Exam and quiz detector for Sakai.

Detects exams and quizzes from:
- Announcements containing exam-related keywords
- Calendar events
- Tests & Quizzes tool
"""

import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple
from hashlib import md5

from bs4 import BeautifulSoup

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Announcement, Course, Exam
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ExamDetector(BaseScraper):
    """
    Detects exams and quizzes from Sakai content.
    
    Uses keyword matching and pattern recognition to identify
    exam-related content from announcements and calendar.
    """
    
    # Keywords that indicate exam-related content
    EXAM_KEYWORDS = [
        "exam", "examination", "midterm", "mid-term", "mid term",
        "final", "finals", "quiz", "quizz", "test", "assessment",
        "practical", "lab exam", "oral exam", "viva", "defense",
        "end of semester", "end-of-semester", "eos exam",
        "continuous assessment", "ca test", "ca exam",
    ]
    
    # Keywords for time/schedule
    TIME_KEYWORDS = [
        "scheduled", "will be held", "takes place", "is on",
        "date:", "time:", "venue:", "location:", "room:",
    ]
    
    # Regex patterns for date extraction
    DATE_PATTERNS = [
        # January 15, 2024 or Jan 15, 2024
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}\b',
        
        # 15/01/2024 or 15-01-2024
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        
        # Monday, January 15 or Monday 15th January
        r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
        r'(?:\d{1,2}(?:st|nd|rd|th)?\s+)?'
        r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'(?:\s+\d{1,2}(?:st|nd|rd|th)?)?\b',
    ]
    
    # Time patterns
    TIME_PATTERNS = [
        r'\b\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?\b',
        r'\b\d{1,2}\s*(?:am|pm|AM|PM)\b',
        r'\b\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?\b',
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
        
        # Detect from calendar
        for course in courses:
            try:
                calendar_exams = self._scrape_calendar(course)
                all_exams.extend(calendar_exams)
            except Exception as e:
                logger.debug(f"Could not scrape calendar for {course.code}: {e}")
        
        # Detect from Tests & Quizzes tool
        for course in courses:
            try:
                quiz_exams = self._scrape_quizzes(course)
                all_exams.extend(quiz_exams)
            except Exception as e:
                logger.debug(f"Could not scrape quizzes for {course.code}: {e}")
        
        # Deduplicate by ID
        seen_ids = set()
        unique_exams = []
        for exam in all_exams:
            if exam.id not in seen_ids:
                seen_ids.add(exam.id)
                unique_exams.append(exam)
        
        logger.info(f"Detected {len(unique_exams)} exams/quizzes")
        return unique_exams
    
    def _detect_from_announcement(
        self, 
        announcement: Announcement
    ) -> Optional[Exam]:
        """
        Detect exam from announcement content.
        
        Args:
            announcement: Announcement to analyze
            
        Returns:
            Exam or None if not exam-related
        """
        # Combine title and content for analysis
        full_text = f"{announcement.title} {announcement.content}".lower()
        
        # Check if this contains exam keywords
        if not self._contains_exam_keywords(full_text):
            return None
        
        # Determine exam type
        exam_type = self._determine_exam_type(full_text)
        
        # Extract date and time
        exam_date = self._extract_exam_date(announcement.content)
        exam_time = self._extract_exam_time(announcement.content)
        
        # Extract location if mentioned
        location = self._extract_location(announcement.content)
        
        # Generate ID from announcement
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
            notes=announcement.content[:500] if announcement.content else None,
        )
    
    def _scrape_calendar(self, course: Course) -> List[Exam]:
        """
        Scrape exams from course calendar.
        
        Args:
            course: Course to scrape
            
        Returns:
            List[Exam]: Detected exams from calendar
        """
        exams: List[Exam] = []
        
        try:
            # Try calendar tool URL
            soup = self.session.get_soup(
                f"/portal/site/{course.site_id}/tool/sakai.schedule"
            )
            
            # Look for calendar events
            events = soup.select('.calendar-event, .eventTitle, .event-item')
            
            for event in events:
                title = event.get_text(strip=True)
                
                # Check if this event is exam-related
                if not self._contains_exam_keywords(title.lower()):
                    continue
                
                # Extract date from event
                date_elem = event.select_one('.date, .event-date')
                exam_date = self.parse_date(date_elem.get_text()) if date_elem else None
                
                exam_id = md5(f"cal-{course.site_id}-{title}".encode()).hexdigest()[:12]
                
                exams.append(Exam(
                    id=exam_id,
                    course_code=course.code,
                    course_title=course.title,
                    title=title,
                    exam_type=self._determine_exam_type(title.lower()),
                    exam_date=exam_date,
                    source="calendar",
                ))
            
        except Exception as e:
            logger.debug(f"Calendar scrape failed for {course.code}: {e}")
        
        return exams
    
    def _scrape_quizzes(self, course: Course) -> List[Exam]:
        """
        Scrape from Tests & Quizzes tool.
        
        Args:
            course: Course to scrape
            
        Returns:
            List[Exam]: Quizzes and tests
        """
        exams: List[Exam] = []
        
        try:
            # Try Tests & Quizzes tool
            soup = self.session.get_soup(
                f"/portal/site/{course.site_id}/tool/sakai.samigo"
            )
            
            # Look for assessment list
            assessments = soup.select(
                '.assessmentListHeader, .assessment-listing tr, .samigo-listing li'
            )
            
            for assessment in assessments:
                title_elem = assessment.select_one('a, .title')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                if not title:
                    continue
                
                # Extract dates
                date_elem = assessment.select_one('.due, .date')
                due_date = self.parse_date(date_elem.get_text()) if date_elem else None
                
                # Extract duration
                duration = None
                duration_match = re.search(
                    r'(\d+)\s*(?:minutes?|mins?|hours?|hrs?)', 
                    assessment.get_text(),
                    re.I
                )
                if duration_match:
                    duration = int(duration_match.group(1))
                    if "hour" in duration_match.group(0).lower():
                        duration *= 60
                
                exam_id = md5(f"quiz-{course.site_id}-{title}".encode()).hexdigest()[:12]
                
                exams.append(Exam(
                    id=exam_id,
                    course_code=course.code,
                    course_title=course.title,
                    title=title,
                    exam_type="quiz",
                    exam_date=due_date,
                    duration_minutes=duration,
                    source="samigo",
                ))
            
        except Exception as e:
            logger.debug(f"Quiz scrape failed for {course.code}: {e}")
        
        return exams
    
    def _contains_exam_keywords(self, text: str) -> bool:
        """Check if text contains exam-related keywords."""
        return any(keyword in text for keyword in self.EXAM_KEYWORDS)
    
    def _determine_exam_type(self, text: str) -> str:
        """
        Determine the type of exam from text.
        
        Args:
            text: Text to analyze (lowercase)
            
        Returns:
            str: Exam type
        """
        type_priority = [
            ("final", "final"),
            ("midterm", "midterm"),
            ("mid-term", "midterm"),
            ("mid term", "midterm"),
            ("quiz", "quiz"),
            ("practical", "practical"),
            ("oral", "oral"),
            ("viva", "oral"),
            ("test", "test"),
        ]
        
        for keyword, exam_type in type_priority:
            if keyword in text:
                return exam_type
        
        return "exam"
    
    def _extract_exam_date(self, text: str) -> Optional[datetime]:
        """
        Extract exam date from text.
        
        Args:
            text: Text containing potential date
            
        Returns:
            datetime or None
        """
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.I)
            if match:
                return self.parse_date(match.group(0))
        return None
    
    def _extract_exam_time(self, text: str) -> Optional[str]:
        """
        Extract exam time from text.
        
        Args:
            text: Text containing potential time
            
        Returns:
            str or None: Time string
        """
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(0)
        return None
    
    def _extract_location(self, text: str) -> Optional[str]:
        """
        Extract exam location from text.
        
        Args:
            text: Text containing potential location
            
        Returns:
            str or None: Location string
        """
        # Look for venue/location patterns
        patterns = [
            r'venue[:\s]+([^\n.]+)',
            r'location[:\s]+([^\n.]+)',
            r'room[:\s]+([^\n.]+)',
            r'hall[:\s]+([^\n.]+)',
            r'(?:held|take place)\s+(?:at|in)\s+([^\n.]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                location = match.group(1).strip()
                # Clean up
                location = re.sub(r'\s+', ' ', location)
                if len(location) < 100:  # Sanity check
                    return location
        
        return None
