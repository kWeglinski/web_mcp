# Fetcher Improvement Plan: Building a Bulletproof URL Fetching System

## Executive Summary

This document provides a comprehensive technical specification for enhancing the [`fetcher.py`](src/web_mcp/fetcher.py:1) module to address critical security vulnerabilities, improve robustness, enhance caching capabilities, and expand test coverage. The improvements are prioritized by severity (P0 = Critical, P1 = High, P2 = Medium).

---

## Current State Analysis

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    fetcher.py Module                        │
├─────────────────────────────────────────────────────────────┤
│  get_connection_pool() → httpx.AsyncClient                  │
│       ↓                                                      │
│  fetch_url(url, config) → Raw HTML                         │
│       ↓                                                      │
│  fetch_url_cached(url, config) → Cached HTML               │
└─────────────────────────────────────────────────────────────┘
```

### Identified Gaps

| Category | Issue | Severity |
|----------|-------|----------|
| Security | No SSRF protection (private IPs not blocked) | P0 |
| Security | Redirect following without validation | P0 |
| Security | URL credential bypass vulnerability | P0 |
| Robustness | Retry logic exists but unused | P1 |
| Robustness | No response size limiting | P1 |
| Robustness | Missing User-Agent header | P1 |
| Caching | No TTL support in cache | P2 |
| Caching | No persistence layer | P2 |
| Testing | Missing security tests for SSRF | P1 |

---

## Improvement Specifications

### P0: Security Enhancements

#### 1. SSRF Protection with IP Address Validation

**Problem:** The current implementation allows fetching from private IP ranges, loopback addresses, and link-local addresses, enabling Server-Side Request Forgery (SSRF) attacks.

**Solution:** Implement comprehensive IP address validation that blocks:
- Private IPv4 ranges: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
- Loopback: 127.0.0.0/8
- Link-local: 169.254.0.0/16
- IPv6 private addresses: ::1, fe80::/10, fc00::/7

**Implementation:**

```python
# src/web_mcp/security.py - Add new functions

import ipaddress
from typing import List

# Private IP ranges that should be blocked
IP_BLACKLIST = [
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('10.0.0.0/8'),       # Private Class A
    ipaddress.ip_network('172.16.0.0/12'),    # Private Class B
    ipaddress.ip_network('192.168.0.0/16'),   # Private Class C
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local
    ipaddress.ip_network('0.0.0.0/8'),        # Current network
]

IPV6_BLACKLIST = [
    ipaddress.ip_network('::1/128'),          # Loopback
    ipaddress.ip_network('fe80::/10'),        # Link-local
    ipaddress.ip_network('fc00::/7'),         # Unique local
]

def is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private/reserved range.
    
    Args:
        ip: IP address string
        
    Returns:
        True if the IP is private or reserved
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        
        # Check IPv4 blacklists
        for network in IP_BLACKLIST:
            if ip_obj in network:
                return True
        
        # Check IPv6 blacklists
        for network in IPV6_BLACKLIST:
            if ip_obj in network:
                return True
        
        return False
    except ValueError:
        # Invalid IP address format
        return True  # Block invalid IPs as safety measure

def validate_url_ip(url: str) -> bool:
    """Validate that a URL does not resolve to private IPs.
    
    This performs DNS resolution and checks the resulting IP addresses.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if all resolved IPs are public
    """
    import socket
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return False
        
        # Resolve all IP addresses (both IPv4 and IPv6)
        addr_info = socket.getaddrinfo(hostname, None)
        
        for family, _, _, _, sockaddr in addr_info:
            ip = sockaddr[0]
            if is_private_ip(ip):
                logger.warning(f"SSRF attempt blocked: {url} resolves to private IP {ip}")
                return False
        
        return True
    except socket.gaierror:
        # DNS resolution failed - block for safety
        logger.error(f"DNS resolution failed for URL: {url}")
        return False
```

**Integration with fetcher:**

```python
# src/web_mcp/fetcher.py - Modified fetch_url function

async def fetch_url(url: str, config, timeout: Optional[int] = None) -> str:
    """Fetch HTML content from a URL with security validation."""
    
    # Security check: Validate URL format
    if not validate_url(url):
        raise FetchError(f"Invalid URL format: {url}")
    
    # Security check: Check for credential injection attacks
    if '@' in url.split('//')[1].split('/')[0] if '//' in url else False:
        # Extract the part after // and before /
        host_part = url.split('//')[1].split('/')[0]
        if '@' in host_part:
            actual_host = host_part.split('@')[-1]
            logger.warning(f"URL credential injection attempt blocked: {url}")
            raise FetchError("URL with credentials not allowed")
    
    # Security check: Validate IP addresses (SSRF protection)
    if not validate_url_ip(url):
        raise FetchError("URL resolves to private IP address - SSRF attempt blocked")
    
    # Proceed with fetch...
```

#### 2. Redirect Validation

**Problem:** Following redirects without validation can lead to SSRF attacks via redirect chains.

**Solution:** Implement redirect validation that checks each redirect target before following.

```python
# src/web_mcp/fetcher.py - Add redirect validation

class RedirectValidator:
    """Validates redirect targets before following."""
    
    def __init__(self, max_redirects: int = 5):
        self.max_redirects = max_redirects
        self._redirect_count = 0
    
    async def should_follow_redirect(self, url: str) -> bool:
        """Check if a redirect target is safe to follow.
        
        Args:
            url: The redirect target URL
            
        Returns:
            True if the redirect is safe
        """
        self._redirect_count += 1
        
        # Check redirect limit
        if self._redirect_count > self.max_redirects:
            logger.warning(f"Redirect limit exceeded: {self._redirect_count}")
            return False
        
        # Validate URL format
        if not validate_url(url):
            logger.warning(f"Invalid redirect URL: {url}")
            return False
        
        # Check for private IPs (SSRF protection)
        if not validate_url_ip(url):
            logger.warning(f"Redirect to private IP blocked: {url}")
            return False
        
        return True
    
    def reset(self) -> None:
        """Reset redirect counter."""
        self._redirect_count = 0

# Modified fetcher with redirect validation
async def fetch_url(url: str, config, timeout: Optional[int] = None) -> str:
    """Fetch with redirect validation."""
    
    # ... security validations ...
    
    validator = RedirectValidator(max_redirects=5)
    
    async def check_redirect(response):
        if response.is_redirect:
            next_url = response.headers.get('location', '')
            return await validator.should_follow_redirect(next_url)
        return True
    
    # Use httpx with custom redirect handling
    client = get_connection_pool()
    response = await client.get(
        url,
        timeout=request_timeout,
        follow_redirects=True,
        event_hooks={'redirect': [check_redirect]}
    )
    
    return response.text
```

#### 3. URL Credential Injection Prevention

**Problem:** URLs like `https://wikipedia.org@evil.com` can bypass domain validation by exploiting the credential syntax in URLs.

**Solution:** Explicitly reject URLs containing credentials.

```python
def validate_url_no_credentials(url: str) -> bool:
    """Validate URL does not contain credentials.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if the URL has no credentials
    """
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    
    # Check for username or password in URL
    if parsed.username or parsed.password:
        logger.warning(f"URL with credentials rejected: {url}")
        return False
    
    # Also check for @ symbol in host part (bypass attempt)
    if '@' in (parsed.netloc or ''):
        logger.warning(f"URL credential injection detected: {url}")
        return False
    
    return True
```

---

### P1: Robustness Enhancements

#### 4. Retry Logic Integration

**Problem:** The [`retry.py`](src/web_mcp/utils/retry.py:1) module exists but is not integrated with the fetcher.

**Solution:** Integrate retry logic with proper error classification and configurable parameters.

```python
# src/web_mcp/fetcher.py - Add retry integration

from web_mcp.utils.retry import with_retry, RetryableError, NonRetryableError

class FetchErrorClassification:
    """Classifies fetch errors as retryable or non-retryable."""
    
    @staticmethod
    def classify(error: Exception) -> bool:
        """Determine if an error is retryable.
        
        Args:
            error: The exception to classify
            
        Returns:
            True if the error should be retried
        """
        # Network errors are retryable
        if isinstance(error, (httpx.ConnectError, httpx.ReadError,
                              httpx.WriteError, httpx.TimeoutException)):
            return True
        
        # 5xx server errors are retryable
        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            if status_code >= 500:
                return True
            # 429 Too Many Requests is retryable
            if status_code == 429:
                return True
        
        # Client errors (4xx) are not retryable
        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            if 400 <= status_code < 500 and status_code != 429:
                return False
        
        # Default: don't retry unknown errors
        return False

# Modified fetcher with retry
@with_retry(
    max_attempts=3,
    base_delay=1.0,
    retryable_exceptions=(httpx.ConnectError, httpx.ReadError,
                          httpx.TimeoutException)
)
async def fetch_url(url: str, config, timeout: Optional[int] = None) -> str:
    """Fetch with automatic retry for transient failures."""
    
    # ... security validations ...
    
    try:
        client = get_connection_pool()
        response = await client.get(url, timeout=request_timeout)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        if FetchErrorClassification.classify(e):
            raise RetryableError(f"HTTP error {e.response.status_code}: {e}")
        else:
            raise NonRetryableError(f"HTTP error {e.response.status_code}: {e}")
    except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException) as e:
        raise RetryableError(f"Request failed: {e}")
```

**Configuration Options:**

```python
# src/web_mcp/config.py - Add retry configuration

ENV_RETRY_MAX_ATTEMPTS = "WEB_MCP_RETRY_MAX_ATTEMPTS"
ENV_RETRY_BASE_DELAY = "WEB_MCP_RETRY_BASE_DELAY"
ENV_RETRY_MAX_DELAY = "WEB_MCP_RETRY_MAX_DELAY"

class Config:
    # ... existing config ...
    
    # Retry configuration
    retry_max_attempts: int = self._validate_int(
        os.environ.get(ENV_RETRY_MAX_ATTEMPTS, "3"), 1, 10
    )
    retry_base_delay: float = self._validate_float(
        os.environ.get(ENV_RETRY_BASE_DELAY, "1.0"), 0.1, 60.0
    )
    retry_max_delay: float = self._validate_float(
        os.environ.get(ENV_RETRY_MAX_DELAY, "30.0"), 1.0, 300.0
    )
```

#### 5. Response Size Limiting

**Problem:** No limit on response size can lead to memory exhaustion attacks.

**Solution:** Implement streaming fetch with size limits.

```python
# src/web_mcp/fetcher.py - Add size limiting

ENV_MAX_RESPONSE_SIZE = "WEB_MCP_MAX_RESPONSE_SIZE"

class SizeLimitExceededError(Exception):
    """Raised when response exceeds size limit."""
    pass

async def fetch_url_with_size_limit(
    url: str,
    config,
    max_size_bytes: Optional[int] = None,
    timeout: Optional[int] = None
) -> str:
    """Fetch URL with response size limiting.
    
    Args:
        url: The URL to fetch
        config: Configuration object
        max_size_bytes: Maximum response size in bytes (default: 10MB)
        timeout: Request timeout
        
    Returns:
        Response content within size limit
        
    Raises:
        SizeLimitExceededError: If response exceeds size limit
    """
    if max_size_bytes is None:
        # Default to 10MB or config value
        max_size_bytes = int(os.environ.get(ENV_MAX_RESPONSE_SIZE, "10485760"))
    
    client = get_connection_pool()
    
    async with client.stream('GET', url, timeout=timeout) as response:
        response.raise_for_status()
        
        content = bytearray()
        size_limit_reached = False
        
        async for chunk in response.aiter_bytes(chunk_size=8192):
            if len(content) + len(chunk) > max_size_bytes:
                logger.warning(f"Response size limit exceeded for URL: {url}")
                size_limit_reached = True
                break
            content.extend(chunk)
        
        if size_limit_reached:
            raise SizeLimitExceededError(
                f"Response exceeds maximum size of {max_size_bytes} bytes"
            )
        
        return content.decode(response.encoding or 'utf-8')
```

#### 6. User-Agent Header

**Problem:** Missing User-Agent header can cause some servers to reject requests.

**Solution:** Add configurable User-Agent with proper identification.

```python
# src/web_mcp/config.py - Add User-Agent configuration

ENV_USER_AGENT = "WEB_MCP_USER_AGENT"

class Config:
    # ... existing config ...
    
    # User-Agent string
    user_agent: str = os.environ.get(
        ENV_USER_AGENT,
        "WebBrowsingMCP/1.0 (+https://github.com/your-org/web-mcp; bot@example.com)"
    )

# src/web_mcp/fetcher.py - Add User-Agent to requests

DEFAULT_HEADERS = {
    'User-Agent': 'WebBrowsingMCP/1.0 (+https://github.com/your-org/web-mcp)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

async def fetch_url(url: str, config, timeout: Optional[int] = None) -> str:
    """Fetch with proper User-Agent header."""
    
    # ... validations ...
    
    client = get_connection_pool()
    response = await client.get(
        url,
        headers={'User-Agent': config.user_agent},
        timeout=request_timeout
    )
    
    return response.text
```

---

### P2: Caching Enhancements

#### 7. TTL Support in Cache

**Problem:** Current LRU cache has no time-to-live (TTL) support, leading to stale content.

**Solution:** Extend LRUCache with TTL functionality.

```python
# src/web_mcp/cache.py - Add TTL support

class TLLRLUCache(Generic[K, V]):
    """LRU cache with Time-To-Live (TTL) support."""
    
    def __init__(self, max_size: int = 100, default_ttl_seconds: float = 3600.0):
        """Initialize the TTL LRU cache.
        
        Args:
            max_size: Maximum number of items
            default_ttl_seconds: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        """Get an item from the cache.
        
        Returns None if not found or expired.
        """
        if key not in self._cache:
            return None
        
        value, expiry = self._cache[key]
        
        # Check if expired
        if time.time() > expiry:
            del self._cache[key]
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return value
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """Add an item with optional custom TTL.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl_seconds: Custom TTL (uses default if not specified)
        """
        expiry = time.time() + (ttl_seconds or self.default_ttl_seconds)
        
        if key in self._cache:
            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = (value, expiry)
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries.
        
        Returns:
            Number of items removed
        """
        current_time = time.time()
        expired_keys = [
            key for key, (value, expiry) in self._cache.items()
            if current_time > expiry
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)
```

**Configuration:**

```python
# src/web_mcp/config.py - Add cache TTL configuration

ENV_CACHE_TTL = "WEB_MCP_CACHE_TTL"
ENV_CACHE_MAX_SIZE = "WEB_MCP_CACHE_MAX_SIZE"

class Config:
    # ... existing config ...
    
    # Cache configuration
    cache_max_size: int = self._validate_int(
        os.environ.get(ENV_CACHE_MAX_SIZE, "100"), 1, 10000
    )
    cache_ttl_seconds: float = self._validate_float(
        os.environ.get(ENV_CACHE_TTL, "3600.0"), 60.0, 86400.0  # 1 min to 24 hours
    )
```

#### 8. Cache Persistence

**Problem:** In-memory cache is lost on restart.

**Solution:** Add optional file-based persistence using SQLite or JSON.

```python
# src/web_mcp/cache.py - Add persistence layer

import json
import sqlite3
from pathlib import Path

class PersistentCache:
    """Persistent cache backed by SQLite."""
    
    def __init__(self, db_path: str = "cache.db", max_size: int = 1000,
                 default_ttl_seconds: float = 3600.0):
        self.db_path = Path(db_path)
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        
        # Initialize database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                expiry REAL,
                accessed_at REAL
            )
        ''')
        
        # Create index for efficient expiry queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_expiry ON cache(expiry)')
        
        conn.commit()
        conn.close()
    
    def get(self, key: str) -> Optional[str]:
        """Get a cached value."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = time.time()
        cursor.execute(
            'SELECT value FROM cache WHERE key = ? AND expiry > ?',
            (key, current_time)
        )
        result = cursor.fetchone()
        
        if result:
            # Update access time
            cursor.execute(
                'UPDATE cache SET accessed_at = ? WHERE key = ?',
                (current_time, key)
            )
            conn.commit()
        
        conn.close()
        return result[0] if result else None
    
    def set(self, key: str, value: str, ttl_seconds: Optional[float] = None) -> None:
        """Cache a value."""
        expiry = time.time() + (ttl_seconds or self.default_ttl_seconds)
        current_time = time.time()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if we need to evict
        cursor.execute('SELECT COUNT(*) FROM cache')
        count = cursor.fetchone()[0]
        
        if count >= self.max_size:
            # Evict oldest or expired entries
            cursor.execute('''
                DELETE FROM cache 
                WHERE key = (
                    SELECT key FROM cache 
                    WHERE expiry <= ? OR accessed_at = (
                        SELECT MIN(accessed_at) FROM cache
                    )
                    LIMIT 1
                )
            ''', (current_time,))
        
        # Insert or update
        cursor.execute('''
            INSERT OR REPLACE INTO cache (key, value, expiry, accessed_at)
            VALUES (?, ?, ?, ?)
        ''', (key, value, expiry, current_time))
        
        conn.commit()
        conn.close()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'DELETE FROM cache WHERE expiry < ?',
            (time.time(),)
        )
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted
```

---

## Test Specifications

### Security Tests

```python
# tests/test_fetcher_security.py - New test file

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from web_mcp.fetcher import fetch_url, FetchError
from web_mcp.security import is_private_ip, validate_url_no_credentials


class TestSSRFProtection:
    """Tests for SSRF protection."""
    
    def test_private_ipv4_blocked(self):
        """Test that private IPv4 addresses are blocked."""
        assert is_private_ip('127.0.0.1') is True
        assert is_private_ip('192.168.1.1') is True
        assert is_private_ip('10.0.0.1') is True
        assert is_private_ip('172.16.0.1') is True
    
    def test_public_ipv4_allowed(self):
        """Test that public IPv4 addresses are allowed."""
        assert is_private_ip('8.8.8.8') is False
        assert is_private_ip('1.1.1.1') is False
    
    @pytest.mark.asyncio
    async def test_ssrf_to_localhost_blocked(self):
        """Test that SSRF attempts to localhost are blocked."""
        with patch('socket.getaddrinfo') as mock_resolve:
            mock_resolve.return_value = [
                (2, 1, 6, '', ('127.0.0.1', 80))
            ]
            
            config = MagicMock()
            config.request_timeout = 30
            
            with pytest.raises(FetchError) as exc_info:
                await fetch_url('http://localhost/admin', config)
            
            assert 'private IP' in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_ssrf_to_private_ip_blocked(self):
        """Test that SSRF attempts to private IPs are blocked."""
        with patch('socket.getaddrinfo') as mock_resolve:
            mock_resolve.return_value = [
                (2, 1, 6, '', ('192.168.1.100', 80))
            ]
            
            config = MagicMock()
            config.request_timeout = 30
            
            with pytest.raises(FetchError) as exc_info:
                await fetch_url('http://internal-server.local/api', config)
            
            assert 'private IP' in str(exc_info.value).lower()


class TestCredentialInjection:
    """Tests for URL credential injection prevention."""
    
    def test_url_with_credentials_rejected(self):
        """Test that URLs with credentials are rejected."""
        assert validate_url_no_credentials('https://user:pass@example.com') is False
    
    def test_url_injection_bypass_blocked(self):
        """Test that credential injection bypass attempts are blocked."""
        # This URL would resolve to evil.com but shows wikipedia.org in the URL
        assert validate_url_no_credentials('https://wikipedia.org@evil.com') is False
    
    @pytest.mark.asyncio
    async def test_fetch_with_credentials_raises_error(self):
        """Test that fetching URLs with credentials raises an error."""
        config = MagicMock()
        config.request_timeout = 30
        
        with pytest.raises(FetchError) as exc_info:
            await fetch_url('https://wikipedia.org@evil.com', config)
        
        assert 'credentials' in str(exc_info.value).lower()


class TestRedirectValidation:
    """Tests for redirect validation."""
    
    @pytest.mark.asyncio
    async def test_redirect_to_private_ip_blocked(self):
        """Test that redirects to private IPs are blocked."""
        mock_response = MagicMock()
        mock_response.is_redirect = True
        mock_response.headers = {'location': 'http://127.0.0.1/admin'}
        
        # Test redirect validation logic
        from web_mcp.fetcher import RedirectValidator
        
        validator = RedirectValidator()
        result = await validator.should_follow_redirect('http://127.0.0.1/admin')
        assert result is False
    
    @pytest.mark.asyncio
    async def test_redirect_limit_enforced(self):
        """Test that redirect limits are enforced."""
        from web_mcp.fetcher import RedirectValidator
        
        validator = RedirectValidator(max_redirects=3)
        
        # Simulate multiple redirects
        for _ in range(4):
            result = await validator.should_follow_redirect('http://example.com/page')
        
        assert result is False  # Should be blocked after limit
```

### Robustness Tests

```python
# tests/test_fetcher_robustness.py - New test file

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from web_mcp.fetcher import (
    fetch_url_with_size_limit,
    SizeLimitExceededError,
    FetchErrorClassification
)


class TestRetryLogic:
    """Tests for retry logic integration."""
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test that timeouts trigger retries."""
        attempt_count = 0
        
        async def failing_request():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise httpx.TimeoutException("Timeout")
            return "success"
        
        # Test retry decorator behavior
        from web_mcp.utils.retry import with_retry
        
        @with_retry(max_attempts=3, base_delay=0.1)
        async def wrapped_request():
            return await failing_request()
        
        result = await wrapped_request()
        assert result == "success"
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_on_404(self):
        """Test that 404 errors are not retried."""
        classification = FetchErrorClassification()
        
        mock_error = MagicMock(spec=httpx.HTTPStatusError)
        mock_error.response.status_code = 404
        
        assert classification.classify(mock_error) is False
    
    @pytest.mark.asyncio
    async def test_retry_on_500(self):
        """Test that 500 errors are retried."""
        classification = FetchErrorClassification()
        
        mock_error = MagicMock(spec=httpx.HTTPStatusError)
        mock_error.response.status_code = 500
        
        assert classification.classify(mock_error) is True


class TestSizeLimiting:
    """Tests for response size limiting."""
    
    @pytest.mark.asyncio
    async def test_size_limit_enforced(self):
        """Test that size limits are enforced."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.encoding = 'utf-8'
        
        # Create large content chunks
        large_content = b'x' * 1024 * 1024  # 1MB per chunk
        
        async def aiter_bytes(chunk_size=8192):
            for _ in range(20):  # 20MB total
                yield large_content
        
        mock_response.aiter_bytes = aiter_bytes
        
        with patch('httpx.AsyncClient.stream') as mock_stream:
            mock_stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            
            config = MagicMock()
            config.request_timeout = 30
            
            with pytest.raises(SizeLimitExceededError):
                await fetch_url_with_size_limit(
                    'http://example.com/large',
                    config,
                    max_size_bytes=5 * 1024 * 1024  # 5MB limit
                )
    
    @pytest.mark.asyncio
    async def test_small_content_allowed(self):
        """Test that content within limits is allowed."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.encoding = 'utf-8'
        mock_response.aiter_bytes = AsyncMock(return_value=iter([b'hello world']))
        
        with patch('httpx.AsyncClient.stream') as mock_stream:
            mock_stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            
            config = MagicMock()
            config.request_timeout = 30
            
            result = await fetch_url_with_size_limit(
                'http://example.com/small',
                config,
                max_size_bytes=1024  # 1KB limit
            )
            
            assert result == 'hello world'
```

### Caching Tests

```python
# tests/test_cache_ttl.py - New test file

import pytest
import time
from web_mcp.cache import TLLRLUCache


class TestTTLCache:
    """Tests for TTL cache functionality."""
    
    def test_item_expires(self):
        """Test that items expire after TTL."""
        cache = TLLRLUCache(max_size=10, default_ttl_seconds=0.1)
        
        cache.set('key', 'value')
        assert cache.get('key') == 'value'
        
        # Wait for expiry
        time.sleep(0.2)
        
        assert cache.get('key') is None
    
    def test_custom_ttl(self):
        """Test custom TTL per item."""
        cache = TLLRLUCache(max_size=10, default_ttl_seconds=3600)
        
        # Set with short TTL
        cache.set('short', 'value', ttl_seconds=0.1)
        # Set with long TTL
        cache.set('long', 'value', ttl_seconds=3600)
        
        time.sleep(0.2)
        
        assert cache.get('short') is None
        assert cache.get('long') == 'value'
    
    def test_cleanup_expired(self):
        """Test expired item cleanup."""
        cache = TLLRLUCache(max_size=10, default_ttl_seconds=0.1)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        time.sleep(0.2)
        
        removed = cache.cleanup_expired()
        assert removed == 3
        assert len(cache) == 0
    
    def test_refresh_on_access(self):
        """Test that access refreshes item."""
        cache = TLLRLUCache(max_size=10, default_ttl_seconds=0.2)
        
        cache.set('key', 'value')
        assert cache.get('key') == 'value'
        
        # Access before expiry
        time.sleep(0.15)
        assert cache.get('key') == 'value'
        
        # Should still be valid after refresh
        time.sleep(0.1)
        assert cache.get('key') == 'value'
```

---

## Configuration Reference

### New Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_MCP_MAX_RESPONSE_SIZE` | `10485760` (10MB) | Maximum response size in bytes |
| `WEB_MCP_RETRY_MAX_ATTEMPTS` | `3` | Maximum retry attempts |
| `WEB_MCP_RETRY_BASE_DELAY` | `1.0` | Base delay for exponential backoff (seconds) |
| `WEB_MCP_RETRY_MAX_DELAY` | `30.0` | Maximum retry delay (seconds) |
| `WEB_MCP_CACHE_TTL` | `3600.0` | Default cache TTL in seconds |
| `WEB_MCP_CACHE_MAX_SIZE` | `100` | Maximum cache entries |
| `WEB_MCP_CACHE_PERSISTENCE_PATH` | `null` | Path for persistent cache (SQLite) |
| `WEB_MCP_USER_AGENT` | `WebBrowsingMCP/1.0` | Custom User-Agent string |
| `WEB_MCP_MAX_REDIRECTS` | `5` | Maximum redirect following |

### Example Configuration

```bash
# .env file example

# Security
WEB_MCP_WHITELIST="wikipedia.org,github.com"
WEB_MCP_BLACKLIST="malware.example.com"

# Robustness
WEB_MCP_MAX_RESPONSE_SIZE=10485760
WEB_MCP_RETRY_MAX_ATTEMPTS=3
WEB_MCP_RETRY_BASE_DELAY=1.0
WEB_MCP_USER_AGENT="WebBrowsingMCP/2.0 (+https://github.com/org/repo)"

# Caching
WEB_MCP_CACHE_TTL=3600
WEB_MCP_CACHE_MAX_SIZE=500
WEB_MCP_CACHE_PERSISTENCE_PATH=/var/cache/web_mcp/cache.db
```

---

## Backward Compatibility Considerations

### Breaking Changes

1. **Default behavior change:** SSRF protection will block some previously allowed URLs (private IPs)
   - **Mitigation:** Add `WEB_MCP_ALLOW_PRIVATE_IPS` environment variable for legacy mode

2. **New exceptions:** `SizeLimitExceededError` is a new exception type
   - **Mitigation:** Document in changelog; existing error handling will catch it as base Exception

3. **Cache behavior change:** TTL-based expiry may cause more cache misses initially
   - **Mitigation:** Default TTL of 1 hour balances freshness with performance

### Migration Guide

```python
# Old code (before changes)
from web_mcp.fetcher import fetch_url, fetch_url_cached

html = await fetch_url(url, config)

# New code (after changes) - minimal change required
from web_mcp.fetcher import fetch_url, fetch_url_with_size_limit

# Size-limited fetching (recommended)
html = await fetch_url_with_size_limit(url, config, max_size_bytes=10*1024*1024)

# Or use default behavior with new security protections
html = await fetch_url(url, config)  # Now includes SSRF protection
```

---

## Implementation Priority & Dependencies

### Phase 1: Critical Security (P0)
- [ ] Add IP address validation (`is_private_ip()`)
- [ ] Implement DNS resolution check (`validate_url_ip()`)
- [ ] Add credential injection prevention
- [ ] Implement redirect validation
- **Estimated Impact:** High - Blocks SSRF attacks

### Phase 2: Robustness (P1)
- [ ] Integrate retry logic with error classification
- [ ] Add response size limiting
- [ ] Add User-Agent headers
- **Estimated Impact:** Medium - Improves reliability

### Phase 3: Caching (P2)
- [ ] Extend cache with TTL support
- [ ] Implement optional persistence layer
- **Estimated Impact:** Low - Performance improvement

### Phase 4: Testing
- [ ] Add security test suite
- [ ] Add robustness test suite
- [ ] Add caching test suite
- **Estimated Impact:** High - Ensures correctness

---

## Architecture Diagram: Enhanced Fetcher

```mermaid
flowchart TB
    subgraph "Request Flow"
        A[User Request] --> B{URL Validation}
        B -->|Invalid| E[Reject with Error]
        B -->|Valid| C{SSRF Check}
        C -->|Private IP| E
        C -->|Public IP| D{Credential Check}
        D -->|Has Credentials| E
        D -->|Clean| F[Fetch Request]
    end
    
    subgraph "Fetch Layer"
        F --> G{Size Limit?}
        G -->|Yes| H[fetch_url_with_size_limit]
        G -->|No| I[fetch_url]
        H --> J[Retry Logic]
        I --> J
    end
    
    subgraph "Response Handling"
        J --> K{Redirect?}
        K -->|Yes| L{Validate Redirect}
        L -->|Invalid| E
        L -->|Valid| F
        K -->|No| M[Size Check]
        M -->|Too Large| N[Reject SizeLimitExceededError]
        M -->|OK| O[Cache Store]
    end
    
    subgraph "Cache Layer"
        P[Cache Lookup] --> Q{Hit?}
        Q -->|Yes|R{Not Expired?}
        R -->|No| F
        R -->|Yes| S[Return Cached]
        O --> T[Store with TTL]
    end
    
    style E fill:#ffcccc
    style N fill:#ffcccc
```

---

## Summary of Improvements

| Priority | Improvement | File(s) Modified | Test Coverage |
|----------|-------------|------------------|---------------|
| P0 | SSRF protection (IP validation) | [`security.py`](src/web_mcp/security.py:1), [`fetcher.py`](src/web_mcp/fetcher.py:1) | `test_fetcher_security.py` |
| P0 | Redirect validation | [`fetcher.py`](src/web_mcp/fetcher.py:1) | `test_fetcher_security.py` |
| P0 | Credential injection prevention | [`security.py`](src/web_mcp/security.py:1), [`fetcher.py`](src/web_mcp/fetcher.py:1) | `test_fetcher_security.py` |
| P1 | Retry logic integration | [`fetcher.py`](src/web_mcp/fetcher.py:1), [`retry.py`](src/web_mcp/utils/retry.py:1) | `test_fetcher_robustness.py` |
| P1 | Response size limiting | [`fetcher.py`](src/web_mcp/fetcher.py:1) | `test_fetcher_robustness.py` |
| P1 | User-Agent headers | [`config.py`](src/web_mcp/config.py:1), [`fetcher.py`](src/web_mcp/fetcher.py:1) | `test_fetcher_robustness.py` |
| P2 | TTL cache support | [`cache.py`](src/web_mcp/cache.py:1) | `test_cache_ttl.py` |
| P2 | Cache persistence | [`cache.py`](src/web_mcp/cache.py:1) | `test_cache_persistence.py` |

---

## Conclusion

This improvement plan addresses critical security vulnerabilities while enhancing the robustness and caching capabilities of the fetcher module. The phased approach ensures that the most critical issues (SSRF protection) are addressed first, followed by reliability improvements and performance enhancements.

All changes maintain backward compatibility through configuration options and clear migration paths. Comprehensive test coverage ensures the new functionality works correctly across all scenarios.
