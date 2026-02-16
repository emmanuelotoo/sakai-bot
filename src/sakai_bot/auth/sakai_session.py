"""
Sakai session management and authentication.

Handles login to Sakai LMS at sakai.ug.edu.gh using the native
HTML form login at /portal/xlogin.
"""

import logging
import re
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from sakai_bot.config import Settings, get_settings

logger = logging.getLogger(__name__)


class SakaiAuthError(Exception):
    """Raised when Sakai authentication fails."""
    pass


class SakaiSession:
    """
    Manages authenticated sessions with Sakai LMS.
    
    Handles:
    - HTML form login with username/password
    - Session cookie management
    - CSRF token extraction
    - Session validation
    
    Designed as a pluggable auth module - can be extended for
    CAS/Shibboleth if the institution changes auth providers.
    """
    
    # User agent to mimic a real browser
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize Sakai session.
        
        Args:
            settings: Optional settings instance, will use default if not provided
        """
        self.settings = settings or get_settings()
        self.base_url = self.settings.sakai_base_url
        
        # Create session with default headers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        self._authenticated = False
        self._user_id: Optional[str] = None
    
    @property
    def is_authenticated(self) -> bool:
        """Check if session is authenticated."""
        return self._authenticated
    
    @property
    def user_id(self) -> Optional[str]:
        """Get the authenticated user's ID."""
        return self._user_id
    
    def _get_url(self, path: str) -> str:
        """Build full URL from path."""
        return urljoin(self.base_url, path)
    
    def _extract_csrf_token(self, html: str) -> Optional[str]:
        """
        Extract CSRF token from HTML page if present.
        
        Args:
            html: HTML content to search
            
        Returns:
            str or None: CSRF token if found
        """
        soup = BeautifulSoup(html, "lxml")
        
        # Look for common CSRF token patterns
        # Sakai uses various names for CSRF tokens
        csrf_patterns = [
            {"name": "sakai_csrf_token"},
            {"name": "_csrf"},
            {"name": "csrf_token"},
            {"id": "sakai_csrf_token"},
        ]
        
        for pattern in csrf_patterns:
            token_input = soup.find("input", pattern)
            if token_input and token_input.get("value"):
                return token_input["value"]
        
        # Also check meta tags
        csrf_meta = soup.find("meta", {"name": "csrf-token"})
        if csrf_meta and csrf_meta.get("content"):
            return csrf_meta["content"]
        
        return None
    
    # Retry configuration for transient network errors
    LOGIN_MAX_RETRIES = 3
    LOGIN_RETRY_BACKOFF = 30  # seconds, doubles each retry

    def login(self) -> bool:
        """
        Authenticate with Sakai using username/password.
        
        Performs HTML form login at /portal/xlogin.
        Retries up to LOGIN_MAX_RETRIES times on connection/timeout errors.
        
        Returns:
            bool: True if login successful
            
        Raises:
            SakaiAuthError: If login fails after all retries
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self.LOGIN_MAX_RETRIES + 1):
            try:
                return self._attempt_login(attempt)
            except requests.exceptions.ConnectionError as e:
                last_error = e
            except requests.exceptions.Timeout as e:
                last_error = e
            except SakaiAuthError:
                raise  # credential / structural errors are not retryable

            if attempt < self.LOGIN_MAX_RETRIES:
                wait = self.LOGIN_RETRY_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    f"Login attempt {attempt}/{self.LOGIN_MAX_RETRIES} failed "
                    f"(transient network error). Retrying in {wait}s…"
                )
                time.sleep(wait)

        raise SakaiAuthError(
            f"Login failed after {self.LOGIN_MAX_RETRIES} attempts: {last_error}"
        )

    def _attempt_login(self, attempt: int = 1) -> bool:
        """
        Single login attempt to Sakai.
        
        Args:
            attempt: Current attempt number (for logging)
            
        Returns:
            bool: True if login successful
            
        Raises:
            SakaiAuthError: If login fails due to credentials/structure
            requests.exceptions.ConnectionError: On network errors
            requests.exceptions.Timeout: On timeout errors
        """
        logger.info(
            f"Attempting login to {self.base_url} "
            f"(attempt {attempt}/{self.LOGIN_MAX_RETRIES})"
        )
        
        try:
            # Step 1: GET the login page to establish session and get any tokens
            login_page_url = self._get_url("/portal/xlogin")
            response = self.session.get(login_page_url, timeout=30)
            response.raise_for_status()
            
            # Extract any CSRF token
            csrf_token = self._extract_csrf_token(response.text)
            
            # Extract the actual form action URL from the page
            soup = BeautifulSoup(response.text, "lxml")
            form = soup.find("form")
            form_action = login_page_url  # default
            if form and form.get("action"):
                form_action = form["action"]
                if not form_action.startswith("http"):
                    form_action = self._get_url(form_action)
            
            # Step 2: Prepare login form data
            login_data = {
                "eid": self.settings.sakai_username,
                "pw": self.settings.sakai_password,
                "submit": "Log in",  # Match exactly what the form uses
            }
            
            if csrf_token:
                login_data["sakai_csrf_token"] = csrf_token
            
            # Step 3: POST login credentials to the form action URL
            response = self.session.post(
                form_action,
                data=login_data,
                timeout=30,
                allow_redirects=True,
            )
            response.raise_for_status()
            
            # Step 4: Verify login success
            if self._verify_login(response):
                self._authenticated = True
                logger.info(f"Login successful for user: {self.settings.sakai_username}")
                return True
            else:
                raise SakaiAuthError(
                    "Login failed - credentials may be incorrect or login page structure changed"
                )
                
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise  # let the retry loop in login() handle these
        except requests.exceptions.RequestException as e:
            logger.error(f"Login request failed: {e}")
            raise SakaiAuthError(f"Login request failed: {e}")
    
    def _verify_login(self, response: requests.Response) -> bool:
        """
        Verify that login was successful by checking the session API.
        
        Args:
            response: Response from login POST
            
        Returns:
            bool: True if login appears successful
        """
        # Primary check: use Sakai's REST session API
        try:
            session_resp = self.session.get(
                self._get_url("/direct/session/current.json"),
                timeout=15,
            )
            if session_resp.status_code == 200:
                import json
                data = json.loads(session_resp.text)
                if data.get("userId"):
                    self._user_id = data.get("userEid") or data.get("userId")
                    return True
        except Exception:
            pass
        
        # Fallback: check for failure indicators in the response
        failure_indicators = [
            "Invalid login",
            "invalid credentials",
            "Login failed",
            "incorrect password",
            "authentication failed",
            "Login Required",
        ]
        
        response_text = response.text.lower()
        for indicator in failure_indicators:
            if indicator.lower() in response_text:
                return False
        
        # Fallback: check for success indicators
        success_indicators = [
            "logout",
            "my workspace",
            "my sites",
        ]
        
        for indicator in success_indicators:
            if indicator.lower() in response_text:
                self._extract_user_info(response.text)
                return True
        
        return False
    
    def _extract_user_info(self, html: str) -> None:
        """Extract user information from authenticated page."""
        soup = BeautifulSoup(html, "lxml")
        
        # Try to find user ID/name in the page
        # Sakai typically shows the logged-in user somewhere
        user_element = soup.find(class_="currentUser") or soup.find(id="loginUser")
        if user_element:
            self._user_id = user_element.get_text(strip=True)
    
    def get(self, path: str, **kwargs) -> requests.Response:
        """
        Make authenticated GET request.
        
        Args:
            path: URL path (will be joined with base URL)
            **kwargs: Additional arguments passed to requests.get
            
        Returns:
            Response object
            
        Raises:
            SakaiAuthError: If not authenticated
        """
        if not self._authenticated:
            raise SakaiAuthError("Not authenticated. Call login() first.")
        
        url = self._get_url(path)
        kwargs.setdefault("timeout", 30)
        
        response = self.session.get(url, **kwargs)
        
        # Check if session expired (redirected to login)
        if "/xlogin" in response.url and "/portal/xlogin" not in path:
            logger.warning("Session expired, attempting re-login")
            self._authenticated = False
            self.login()
            response = self.session.get(url, **kwargs)
        
        return response
    
    def get_soup(self, path: str, **kwargs) -> BeautifulSoup:
        """
        Make authenticated GET request and return parsed BeautifulSoup.
        
        Args:
            path: URL path
            **kwargs: Additional arguments passed to requests.get
            
        Returns:
            BeautifulSoup: Parsed HTML
        """
        response = self.get(path, **kwargs)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    
    def get_json(self, path: str, **kwargs) -> dict:
        """
        Make authenticated GET request and return parsed JSON.
        
        Args:
            path: URL path (e.g., "/direct/announcement/user.json")
            **kwargs: Additional arguments passed to requests.get
            
        Returns:
            dict: Parsed JSON response
        """
        response = self.get(path, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def logout(self) -> None:
        """Log out from Sakai session."""
        if self._authenticated:
            try:
                self.session.get(self._get_url("/portal/logout"), timeout=10)
            except requests.exceptions.RequestException:
                pass  # Ignore logout errors
            finally:
                self._authenticated = False
                self._user_id = None
                self.session.cookies.clear()
                logger.info("Logged out from Sakai")
    
    def __enter__(self) -> "SakaiSession":
        """Context manager entry - login."""
        self.login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - logout."""
        self.logout()
