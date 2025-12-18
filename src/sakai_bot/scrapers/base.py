"""
Base scraper class with shared utilities.

Provides common functionality for all Sakai scrapers.
"""

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from dateutil import parser as date_parser
from dateutil.tz import gettz

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.config import get_settings

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Base class for Sakai scrapers.
    
    Provides common utilities for date parsing, URL building,
    and HTML extraction.
    """
    
    def __init__(self, session: SakaiSession):
        """
        Initialize scraper with authenticated session.
        
        Args:
            session: Authenticated Sakai session
        """
        self.session = session
        self.settings = get_settings()
        self.timezone = gettz(self.settings.timezone)
    
    @abstractmethod
    def scrape(self, *args, **kwargs) -> Any:
        """Scrape data - implemented by subclasses."""
        pass
    
    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string to datetime.
        
        Handles various date formats commonly used in Sakai.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            datetime or None if parsing fails
        """
        if not date_str:
            return None
        
        # Clean up the string
        date_str = date_str.strip()
        date_str = re.sub(r'\s+', ' ', date_str)
        
        # Remove common prefixes
        for prefix in ["Due:", "Posted:", "Opens:", "Closes:", "Date:"]:
            date_str = date_str.replace(prefix, "").strip()
        
        try:
            # Use dateutil parser for flexibility
            parsed = date_parser.parse(date_str, fuzzy=True)
            
            # Apply timezone if not present
            if parsed.tzinfo is None and self.timezone:
                parsed = parsed.replace(tzinfo=self.timezone)
            
            return parsed
            
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse date '{date_str}': {e}")
            return None
    
    def clean_text(self, text: Optional[str]) -> str:
        """
        Clean and normalize text content.
        
        Args:
            text: Text to clean
            
        Returns:
            str: Cleaned text
        """
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def extract_course_code(self, text: str) -> str:
        """
        Extract course code from text.
        
        Looks for patterns like:
        - CSCD 101
        - CS101
        - DCIT-103
        
        Args:
            text: Text that may contain course code
            
        Returns:
            str: Extracted course code or original text
        """
        # Common course code patterns
        patterns = [
            r'([A-Z]{2,4}[- ]?\d{3}[A-Z]?)',  # CSCD 101, CS101, DCIT-103
            r'([A-Z]{2,4}\s+\d{3})',  # CSCD 101
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        # Return first part of text as fallback
        parts = text.split(' - ')
        return parts[0].strip() if parts else text
    
    def build_tool_url(self, site_id: str, tool: str) -> str:
        """
        Build URL for a specific Sakai tool.
        
        Args:
            site_id: Course site ID
            tool: Tool name (announcements, assignments, etc.)
            
        Returns:
            str: Full URL to the tool
        """
        return f"{self.session.base_url}/portal/site/{site_id}/tool-reset/{tool}"
