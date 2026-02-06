"""
Assignment scraper for Sakai.

Extracts assignments and their deadlines from all enrolled courses.
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import Tag

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Assignment, AssignmentStatus, Course
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AssignmentScraper(BaseScraper):
    """
    Scrapes assignments from Sakai courses.
    
    Extracts assignment title, due date, status, and other details
    from the Assignments tool for each course.
    """
    
    def __init__(self, session: SakaiSession):
        """Initialize assignment scraper."""
        super().__init__(session)
    
    def scrape(self, courses: List[Course]) -> List[Assignment]:
        """
        Scrape assignments from all provided courses.
        
        Args:
            courses: List of courses to scrape
            
        Returns:
            List[Assignment]: All found assignments
        """
        all_assignments: List[Assignment] = []
        
        for course in courses:
            try:
                assignments = self._scrape_course_assignments(course)
                all_assignments.extend(assignments)
                logger.debug(f"Found {len(assignments)} assignments in {course.code}")
            except Exception as e:
                logger.error(f"Error scraping assignments for {course.code}: {e}")
                continue
        
        logger.info(f"Total assignments scraped: {len(all_assignments)}")
        return all_assignments
    
    def _scrape_course_assignments(self, course: Course) -> List[Assignment]:
        """
        Scrape assignments from a single course.
        
        Args:
            course: Course to scrape
            
        Returns:
            List[Assignment]: Assignments from this course
        """
        assignments: List[Assignment] = []
        
        # Try multiple URL patterns for the assignments tool
        url_patterns = [
            f"/portal/site/{course.site_id}/tool/sakai.assignment.grades",
            f"/portal/site/{course.site_id}/tool/sakai.assignment",
            f"/direct/assignment/site/{course.site_id}.json",  # Direct API
        ]
        
        soup = None
        for url in url_patterns:
            try:
                if url.endswith('.json'):
                    # Try JSON API endpoint
                    assignments = self._scrape_from_api(url, course)
                    if assignments:
                        return assignments
                else:
                    soup = self.session.get_soup(url)
                    break
            except Exception:
                continue
        
        if not soup:
            return []
        
        # Parse HTML-based assignment list
        # Pattern 1: Table-based layout (common in Sakai)
        rows = soup.select(
            'table.listHier tbody tr, '
            '.itemListHighlite, '
            '.assignment-list-item, '
            '#assignmentList tr'
        )
        
        for row in rows:
            assignment = self._parse_assignment_row(row, course)
            if assignment:
                assignments.append(assignment)
        
        # Pattern 2: List-based layout
        if not assignments:
            items = soup.select('.portletBody ul li, .assignment-item')
            for item in items:
                assignment = self._parse_assignment_item(item, course)
                if assignment:
                    assignments.append(assignment)
        
        return assignments
    
    def _scrape_from_api(self, url: str, course: Course) -> List[Assignment]:
        """
        Try to scrape assignments from Sakai's direct API.
        
        Args:
            url: API endpoint URL
            course: Course context
            
        Returns:
            List[Assignment]: Assignments if API is available
        """
        try:
            response = self.session.get(url.replace("/portal/", "/"))
            if response.status_code != 200:
                return []
            
            data = response.json()
            assignments = []
            
            # Parse API response
            for item in data.get("assignment_collection", []):
                assignment = Assignment(
                    id=item.get("id", ""),
                    course_code=course.code,
                    course_title=course.title,
                    title=item.get("title", ""),
                    description=item.get("instructions", ""),
                    due_date=self.parse_date(item.get("dueTimeString")),
                    open_date=self.parse_date(item.get("openTimeString")),
                    close_date=self.parse_date(item.get("closeTimeString")),
                    status=self._map_api_status(item.get("status", "")),
                    max_points=item.get("gradeScale"),
                    url=item.get("entityURL"),
                )
                if assignment.id and assignment.title:
                    assignments.append(assignment)
            
            return assignments
            
        except Exception as e:
            logger.debug(f"API scrape failed: {e}")
            return []
    
    def _parse_assignment_row(
        self, 
        row: Tag, 
        course: Course
    ) -> Optional[Assignment]:
        """
        Parse assignment from table row.
        
        Args:
            row: BeautifulSoup tag containing table row
            course: Course this assignment belongs to
            
        Returns:
            Assignment or None if parsing fails
        """
        try:
            # Skip header rows
            if row.select_one('th'):
                return None
            
            cells = row.select('td')
            if len(cells) < 2:
                return None
            
            # Extract title (usually first cell with a link)
            title_link = row.select_one('a')
            if not title_link:
                return None
            
            title = self.clean_text(title_link.get_text())
            if not title:
                return None
            
            href = title_link.get("href", "")
            assign_id = self._extract_assignment_id(href) or self._generate_id(title, course.site_id)
            
            # Extract dates from cells
            due_date = None
            open_date = None
            status = AssignmentStatus.NOT_STARTED
            
            for cell in cells:
                cell_text = cell.get_text(strip=True).lower()
                cell_class = " ".join(cell.get("class", []))
                
                # Look for due date
                if "due" in cell_class or "due" in cell_text[:20]:
                    due_date = self.parse_date(cell.get_text())
                
                # Look for open date
                elif "open" in cell_class or "open" in cell_text[:20]:
                    open_date = self.parse_date(cell.get_text())
                
                # Look for status
                elif "status" in cell_class:
                    status = self._parse_status(cell.get_text())
            
            # Try to find description
            description_elem = row.select_one('.description, .instructions')
            description = self.clean_text(description_elem.get_text()) if description_elem else None
            
            # Extract points if available
            max_points = None
            points_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:points?|pts?)', row.get_text(), re.I)
            if points_match:
                max_points = float(points_match.group(1))
            
            url = urljoin(self.session.base_url, href) if href else None
            
            return Assignment(
                id=assign_id,
                course_code=course.code,
                course_title=course.title,
                title=title,
                description=description,
                due_date=due_date,
                open_date=open_date,
                status=status,
                max_points=max_points,
                url=url,
            )
            
        except Exception as e:
            logger.debug(f"Could not parse assignment row: {e}")
            return None
    
    def _parse_assignment_item(
        self, 
        item: Tag, 
        course: Course
    ) -> Optional[Assignment]:
        """
        Parse assignment from list item.
        
        Args:
            item: BeautifulSoup tag containing list item
            course: Course this assignment belongs to
            
        Returns:
            Assignment or None if parsing fails
        """
        try:
            title_elem = item.select_one('a, .title, h3, h4')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            if not title:
                return None
            
            href = title_elem.get("href", "") if title_elem.name == "a" else ""
            assign_id = self._extract_assignment_id(href) or self._generate_id(title, course.site_id)
            
            # Extract due date
            due_elem = item.select_one('.due, .dueDate, .deadline')
            due_date = self.parse_date(due_elem.get_text()) if due_elem else None
            
            # If no specific element, try to parse from full text
            if not due_date:
                due_match = re.search(r'due[:\s]+(.+?)(?:\s*-|$)', item.get_text(), re.I)
                if due_match:
                    due_date = self.parse_date(due_match.group(1))
            
            url = urljoin(self.session.base_url, href) if href else None
            
            return Assignment(
                id=assign_id,
                course_code=course.code,
                course_title=course.title,
                title=title,
                due_date=due_date,
                url=url,
            )
            
        except Exception as e:
            logger.debug(f"Could not parse assignment item: {e}")
            return None
    
    def _extract_assignment_id(self, url: str) -> Optional[str]:
        """
        Extract assignment ID from URL.
        
        Args:
            url: URL that may contain assignment ID
            
        Returns:
            str or None: Assignment ID
        """
        # Pattern: assignmentId=ID or /a/ID
        patterns = [
            r'assignmentId=([a-f0-9-]+)',
            r'/assignment/([a-f0-9-]+)',
            r'/a/([a-f0-9-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.I)
            if match:
                return match.group(1)
        
        return None
    
    def _generate_id(self, title: str, site_id: str) -> str:
        """Generate stable ID from title and site."""
        from hashlib import md5
        content = f"{site_id}:assignment:{title}"
        return md5(content.encode()).hexdigest()[:12]
    
    def _parse_status(self, status_text: str) -> AssignmentStatus:
        """
        Parse status text into AssignmentStatus enum.
        
        Args:
            status_text: Status string from page
            
        Returns:
            AssignmentStatus: Parsed status
        """
        status_lower = status_text.lower().strip()
        
        status_map = {
            "submitted": AssignmentStatus.SUBMITTED,
            "graded": AssignmentStatus.GRADED,
            "in progress": AssignmentStatus.IN_PROGRESS,
            "draft": AssignmentStatus.IN_PROGRESS,
            "late": AssignmentStatus.LATE,
            "closed": AssignmentStatus.CLOSED,
            "not started": AssignmentStatus.NOT_STARTED,
            "new": AssignmentStatus.NOT_STARTED,
        }
        
        for key, value in status_map.items():
            if key in status_lower:
                return value
        
        return AssignmentStatus.NOT_STARTED
    
    def _map_api_status(self, status: str) -> AssignmentStatus:
        """Map API status string to enum."""
        status_lower = status.lower()
        if "submitted" in status_lower:
            return AssignmentStatus.SUBMITTED
        elif "graded" in status_lower:
            return AssignmentStatus.GRADED
        elif "closed" in status_lower:
            return AssignmentStatus.CLOSED
        return AssignmentStatus.NOT_STARTED
