"""Utility functions for Aiko backend."""

import logging
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any
import json


logger = logging.getLogger(__name__)


# ID Generation
def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    unique_id = str(uuid.uuid4()).replace("-", "")
    if prefix:
        return f"{prefix}-{unique_id}"
    return unique_id


def generate_message_id() -> str:
    """Generate a unique message ID."""
    return generate_id("msg")


def generate_conversation_id() -> str:
    """Generate a unique conversation ID."""
    return generate_id("conv")


def generate_user_id() -> str:
    """Generate a unique user ID."""
    return generate_id("user")


# Timestamp Utilities
def get_current_timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
    return int(datetime.now().timestamp() * 1000)


def get_current_timestamp() -> int:
    """Get current timestamp in seconds."""
    return int(datetime.now().timestamp())


def datetime_to_timestamp_ms(dt: datetime) -> int:
    """Convert datetime to milliseconds timestamp."""
    return int(dt.timestamp() * 1000)


def timestamp_ms_to_datetime(ts: int) -> datetime:
    """Convert milliseconds timestamp to datetime."""
    return datetime.fromtimestamp(ts / 1000)


# Text Processing
def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    import re
    # Remove or replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return filename[:255]  # Max filename length


def extract_first_sentence(text: str) -> str:
    """Extract first sentence from text."""
    import re
    match = re.search(r'[^.!?]*[.!?]', text)
    if match:
        return match.group(0).strip()
    return text[:100].strip()


def derive_conversation_title(messages: list) -> str:
    """Derive conversation title from first user message."""
    for msg in messages:
        if msg.get("role") == "user":
            text = msg.get("text", "Nueva conversación")
            return truncate_text(extract_first_sentence(text), 50)
    return "Nueva conversación"


# Hashing
def hash_text(text: str) -> str:
    """Create SHA256 hash of text."""
    return hashlib.sha256(text.encode()).hexdigest()


def hash_file_content(content: bytes) -> str:
    """Create SHA256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


# JSON Utilities
def safe_json_dumps(obj: Any, indent: int = 2) -> str:
    """Safely serialize object to JSON."""
    try:
        return json.dumps(obj, indent=indent, default=str)
    except Exception as e:
        logger.error(f"JSON serialization error: {e}")
        return "{}"


def safe_json_loads(json_str: str) -> dict:
    """Safely deserialize JSON string."""
    try:
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"JSON deserialization error: {e}")
        return {}


# Validation
def is_valid_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def is_valid_url(url: str) -> bool:
    """Validate URL format."""
    import re
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return re.match(pattern, url) is not None


def is_valid_uuid(value: str) -> bool:
    """Check if string is valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


# Rate Limiting
class SimpleRateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for key."""
        now = datetime.now()
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.requests[key] = [
            ts for ts in self.requests[key]
            if ts > cutoff
        ]
        
        # Check if allowed
        if len(self.requests[key]) < self.max_requests:
            self.requests[key].append(now)
            return True
        
        return False


# Formatting
def format_file_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def format_duration(seconds: float) -> str:
    """Format seconds to human-readable duration."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_timestamp(ts: int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format timestamp to readable string."""
    return datetime.fromtimestamp(ts).strftime(format_str)


# Language Detection
def detect_language(text: str) -> str:
    """Simple language detection (Spanish/English)."""
    # Simple heuristic-based detection
    spanish_words = ["el", "la", "de", "que", "y", "a", "en", "los"]
    english_words = ["the", "is", "and", "to", "a", "in", "of", "for"]
    
    text_lower = text.lower()
    spanish_count = sum(1 for word in spanish_words if f" {word} " in f" {text_lower} ")
    english_count = sum(1 for word in english_words if f" {word} " in f" {text_lower} ")
    
    if spanish_count > english_count:
        return "es"
    elif english_count > spanish_count:
        return "en"
    else:
        return "en"  # Default


# Logging Utilities
def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Setup a logger with consistent formatting."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(level)
    return logger


# Retry Utilities
def retry_async(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
):
    """Async retry decorator."""
    import asyncio
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = delay_seconds
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed, "
                            f"retrying in {delay}s: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_multiplier
                    else:
                        logger.error(f"All {max_attempts} attempts failed: {str(e)}")
            
            raise last_error
        
        return wrapper
    return decorator


# Cache Utilities
class SimpleCache:
    """Simple in-memory cache with TTL."""
    
    def __init__(self):
        self.cache = {}
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Set cache value with TTL."""
        self.cache[key] = {
            "value": value,
            "expires_at": datetime.now() + timedelta(seconds=ttl_seconds)
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get cache value if not expired."""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if datetime.now() > entry["expires_at"]:
            del self.cache[key]
            return None
        
        return entry["value"]
    
    def clear(self):
        """Clear all cache."""
        self.cache.clear()


# Statistics
class Statistics:
    """Collect and report statistics."""
    
    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.total_time = 0.0
        self.start_time = datetime.now()
    
    def record_request(self, time_ms: float, error: bool = False):
        """Record a request."""
        self.total_requests += 1
        self.total_time += time_ms
        if error:
            self.total_errors += 1
    
    def get_stats(self) -> dict:
        """Get statistics summary."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        avg_time = self.total_time / self.total_requests if self.total_requests > 0 else 0
        error_rate = (self.total_errors / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            "uptime_seconds": uptime,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "average_response_time_ms": avg_time,
            "error_rate_percent": error_rate,
        }


# Module-level statistics instance
_stats = Statistics()


def record_request(time_ms: float, error: bool = False):
    """Record request in global statistics."""
    _stats.record_request(time_ms, error)


def get_global_stats() -> dict:
    """Get global statistics."""
    return _stats.get_stats()
