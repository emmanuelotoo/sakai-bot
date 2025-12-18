"""Sakai scrapers module."""

from sakai_bot.scrapers.courses import CourseScraper
from sakai_bot.scrapers.announcements import AnnouncementScraper
from sakai_bot.scrapers.assignments import AssignmentScraper
from sakai_bot.scrapers.exams import ExamDetector

__all__ = [
    "CourseScraper",
    "AnnouncementScraper",
    "AssignmentScraper",
    "ExamDetector",
]
