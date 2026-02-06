"""
Course scraper for Sakai.

Extracts list of enrolled courses from the Sakai portal.
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Course
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class CourseScraper(BaseScraper):
    """
    Scrapes enrolled courses from Sakai.
    
    Extracts course information from the main portal page
    including course codes, titles, and site URLs.
    """
    
    def __init__(self, session: SakaiSession):
        """Initialize course scraper."""
        super().__init__(session)
    
    def scrape(self) -> List[Course]:
        """
        Scrape all enrolled courses.
        
        Returns:
            List[Course]: List of enrolled courses
        """
        logger.info("Scraping enrolled courses...")
        
        courses: List[Course] = []
        
        # Try multiple approaches to get course list
        # Method 1: Portal favorites/sites sidebar
        courses = self._scrape_from_portal()
        
        if not courses:
            # Method 2: Direct site listing
            courses = self._scrape_from_site_list()
        
        logger.info(f"Found {len(courses)} enrolled courses")
        return courses
    
    def _scrape_from_portal(self) -> List[Course]:
        """
        Scrape courses from main portal page.
        
        Returns:
            List[Course]: Found courses
        """
        courses: List[Course] = []
        
        try:
            soup = self.session.get_soup("/portal")
            
            # Look for course links in the sidebar/favorites
            # Sakai typically has courses listed as links with site IDs
            
            # Pattern 1: Standard Sakai site links
            site_links = soup.select('a[href*="/portal/site/"]')
            
            for link in site_links:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                
                # Skip non-course links
                if not title or "~" in href or "admin" in href.lower():
                    continue
                
                # Extract site ID from URL
                site_id = self._extract_site_id(href)
                if not site_id:
                    continue
                
                # Skip if this looks like a tool or admin page
                if site_id.startswith("!") or site_id == "~":
                    continue
                
                course = Course(
                    site_id=site_id,
                    code=self.extract_course_code(title),
                    title=title,
                    url=urljoin(self.session.base_url, f"/portal/site/{site_id}"),
                )
                
                # Avoid duplicates
                if not any(c.site_id == course.site_id for c in courses):
                    courses.append(course)
            
            # Pattern 2: Look for course tabs/buttons
            tab_links = soup.select('.Mrphs-sitesNav__menuitem a, .fav-sites-entry a')
            for link in tab_links:
                href = link.get("href", "")
                title = link.get("title") or link.get_text(strip=True)
                
                site_id = self._extract_site_id(href)
                if site_id and not any(c.site_id == site_id for c in courses):
                    courses.append(Course(
                        site_id=site_id,
                        code=self.extract_course_code(title),
                        title=title,
                        url=urljoin(self.session.base_url, f"/portal/site/{site_id}"),
                    ))
            
        except Exception as e:
            logger.error(f"Error scraping portal: {e}")
        
        return courses
    
    def _scrape_from_site_list(self) -> List[Course]:
        """
        Scrape courses from explicit site listing page.
        
        Returns:
            List[Course]: Found courses
        """
        courses: List[Course] = []
        
        try:
            # Try the membership/sites page
            soup = self.session.get_soup("/portal/site/~?sakai.tool.placement.id=sakai.membership")
            
            # Look for site entries
            site_entries = soup.select('.site-listing tr, .siteList tr, table.listHier tr')
            
            for entry in site_entries:
                link = entry.select_one('a[href*="/portal/site/"]')
                if not link:
                    continue
                
                href = link.get("href", "")
                title = link.get_text(strip=True)
                
                site_id = self._extract_site_id(href)
                if site_id:
                    courses.append(Course(
                        site_id=site_id,
                        code=self.extract_course_code(title),
                        title=title,
                        url=urljoin(self.session.base_url, f"/portal/site/{site_id}"),
                    ))
            
        except Exception as e:
            logger.debug(f"Site list scrape failed (this is often normal): {e}")
        
        return courses
    
    def _extract_site_id(self, url: str) -> Optional[str]:
        """
        Extract site ID from Sakai URL.
        
        Args:
            url: URL containing site ID
            
        Returns:
            str or None: Site ID
        """
        # Pattern: /portal/site/SITE_ID or /portal/site/SITE_ID/...
        match = re.search(r'/portal/site/([^/?#]+)', url)
        if match:
            site_id = match.group(1)
            # Skip special sites
            if site_id and not site_id.startswith(('~', '!')):
                return site_id
        return None
    
    def get_course_by_code(self, code: str) -> Optional[Course]:
        """
        Find a specific course by code.
        
        Args:
            code: Course code to find
            
        Returns:
            Course or None if not found
        """
        courses = self.scrape()
        code_upper = code.upper().replace(" ", "")
        
        for course in courses:
            course_code_clean = course.code.upper().replace(" ", "")
            if code_upper in course_code_clean or course_code_clean in code_upper:
                return course
        
        return None
