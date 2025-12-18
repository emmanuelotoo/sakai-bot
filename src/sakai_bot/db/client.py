"""
Supabase client initialization.

Provides a configured Supabase client for database operations.
"""

from functools import lru_cache

from supabase import Client, create_client

from sakai_bot.config import get_settings


@lru_cache()
def get_supabase_client() -> Client:
    """
    Get a cached Supabase client instance.
    
    Returns:
        Client: Configured Supabase client
        
    Raises:
        Exception: If connection fails or credentials are invalid
    """
    settings = get_settings()
    
    client = create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )
    
    return client
