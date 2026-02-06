"""
Announcement scraper for Sakai.

Extracts announcements from all enrolled courses.
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Announcement, Course
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AnnouncementScraper(BaseScraper):
    """
    Scrapes announcements from Sakai courses.
    
    Extracts announcement title, content, author, and posted date
    from the Announcements tool for each course.
    """
    
    def __init__(self, session: SakaiSession):
        """Initialize announcement scraper."""
        super().__init__(session)
    
    def scrape(self, courses: List[Course]) -> List[Announcement]:
        """
        Scrape announcements from all provided courses.
        
        Args:
            courses: List of courses to scrape
            
        Returns:
            List[Announcement]: All found announcements
        """
        all_announcements: List[Announcement] = []
        
        for course in courses:
            try:
                announcements = self._scrape_course_announcements(course)
                all_announcements.extend(announcements)
                logger.debug(f"Found {len(announcements)} announcements in {course.code}")
            except Exception as e:
                logger.error(f"Error scraping announcements for {course.code}: {e}")
                continue
        
        logger.info(f"Total announcements scraped: {len(all_announcements)}")
        return all_announcements
    
    def _scrape_course_announcements(self, course: Course) -> List[Announcement]:
        """
        Scrape announcements from a single course.
        
        Args:
            course: Course to scrape
            
        Returns:
            List[Announcement]: Announcements from this course
        """
        announcements: List[Announcement] = []
        
        # Try the announcements tool URL
        # Sakai uses a tool placement URL pattern
        ann_url = f"/portal/site/{course.site_id}/tool/sakai.announcements"
        
        try:
            soup = self.session.get_soup(ann_url)
        except Exception:
            # Try alternative URL patterns
            try:
                ann_url = f"/portal/site/{course.site_id}"
                soup = self.session.get_soup(ann_url)
            except Exception as e:
                logger.debug(f"Could not access {course.code}: {e}")
                return []
        
        # Find announcement entries
        # Sakai has various HTML structures depending on version
        
        # Pattern 1: Standard announcement list
        ann_items = soup.select('.announcementList li, #announcementList li, .announcement-item')
        
        if not ann_items:
            # Pattern 2: Table-based layout
            ann_items = soup.select('table.listHier tr, .itemListHighlite')
        
        if not ann_items:
            # Pattern 3: Direct announcements on site page
            ann_items = soup.select('.portletBody .portletMainWrap .announcements li')
        
        for item in ann_items:
            announcement = self._parse_announcement_item(item, course)
            if announcement:
                announcements.append(announcement)
        
        # Also check for merged announcements view
        merged = self._scrape_merged_view(soup, course)
        announcements.extend(merged)
        
        return announcements
    
    def _parse_announcement_item(
        self, 
        item: Tag, 
        course: Course
    ) -> Optional[Announcement]:
        """
        Parse a single announcement item from HTML.
        
        Args:
            item: BeautifulSoup tag containing announcement
            course: Course this announcement belongs to
            
        Returns:
            Announcement or None if parsing fails
        """
        try:
            # Extract title - look for link or header
            title_elem = (
                item.select_one('a.subject, a.title, h3, h4, .subject, .title') or
                item.select_one('a')
            )
            
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            if not title:
                return None
            
            # Extract ID from link or generate from title
            href = title_elem.get("href", "") if title_elem.name == "a" else ""
            ann_id = self._extract_announcement_id(href) or self._generate_id(title, course.site_id)
            
            # Extract content
            content_elem = item.select_one('.content, .body, .message, .announcementBody')
            content = self.clean_text(content_elem.get_text()) if content_elem else ""
            
            # Extract author
            author_elem = item.select_one('.author, .createdBy, .creator')
            author = self.clean_text(author_elem.get_text()) if author_elem else None
            
            # Extract date
            date_elem = item.select_one('.date, .time, .announcementDate, .createdOn')
            posted_at = None
            if date_elem:
                posted_at = self.parse_date(date_elem.get_text())
            
            # Build URL
            url = None
            if href:
                url = urljoin(self.session.base_url, href)
            
            return Announcement(
                id=ann_id,
                course_code=course.code,
                course_title=course.title,
                title=title,
                content=content,
                author=author,
                posted_at=posted_at,
                url=url,
            )
            
        except Exception as e:
            logger.debug(f"Could not parse announcement item: {e}")
            return None
    
    def _scrape_merged_view(
        self, 
        soup: BeautifulSoup, 
        course: Course
    ) -> List[Announcement]:
        """
        Scrape announcements from merged/recent view.
        
        Some Sakai pages show recent announcements in a merged view.
        
        Args:
            soup: Parsed HTML
            course: Current course context
            
        Returns:
            List[Announcement]: Found announcements
        """
        announcements: List[Announcement] = []
        
        # Look for recent announcements section
        recent_section = soup.select_one('#recentAnnouncements, .recentAnnouncements')
        if not recent_section:
            return []
        
        items = recent_section.select('li, .announcement-item, tr')
        for item in items:
            ann = self._parse_announcement_item(item, course)
            if ann:
                announcements.append(ann)
        
        return announcements
    
    def _extract_announcement_id(self, url: str) -> Optional[str]:
        """
        Extract announcement ID from URL.
        
        Args:
            url: URL that may contain announcement ID
            
        Returns:
            str or None: Announcement ID
        """
        # Pattern: announcements/msg/SITE_ID/main/ID
        match = re.search(r'/msg/[^/]+/[^/]+/([a-f0-9-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern: itemId=ID or id=ID
        match = re.search(r'(?:itemId|id)=([a-f0-9-]+)', url)
        if match:
            return match.group(1)
        
        return None
    
    def _generate_id(self, title: str, site_id: str) -> str:
        """
        Generate a stable ID from title and site.
        
        Args:
            title: Announcement title
            site_id: Course site ID
            
        Returns:
            str: Generated ID
        """
        from hashlib import md5
        content = f"{site_id}:{title}"
        return md5(content.encode()).hexdigest()[:12]
