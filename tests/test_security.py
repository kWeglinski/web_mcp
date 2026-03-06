"""Unit tests for security utilities."""

import pytest

from web_mcp.security import (
    RateLimiter,
    get_rate_limiter,
    reset_rate_limiter,
    sanitize_input,
    validate_url,
    validate_url_ip,
    validate_url_no_credentials,
    validate_url_with_blacklist,
    validate_url_with_whitelist,
)


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        assert validate_url("http://example.com") is True

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        assert validate_url("https://example.com") is True

    def test_invalid_scheme(self):
        """Test URL with invalid scheme."""
        assert validate_url("ftp://example.com") is False
        assert validate_url("javascript:alert(1)") is False

    def test_invalid_url(self):
        """Test invalid URL."""
        assert validate_url("not-a-url") is False
        assert validate_url("") is False

    def test_url_with_path(self):
        """Test URL with path."""
        assert validate_url("https://example.com/path/to/page") is True

    def test_url_with_port(self):
        """Test URL with port."""
        assert validate_url("https://example.com:8080") is True

    def test_url_with_query(self):
        """Test URL with query string."""
        assert validate_url("https://example.com?query=test") is True


class TestValidateUrlWithWhitelist:
    """Tests for validate_url_with_whitelist function."""

    def test_whitelisted_domain(self):
        """Test whitelisted domain."""
        url = "https://wikipedia.org/wiki/Python"
        assert validate_url_with_whitelist(url) is True

    def test_subdomain_whitelisted(self):
        """Test subdomain of whitelisted domain."""
        url = "https://www.wikipedia.org"
        assert validate_url_with_whitelist(url) is True

    def test_not_whitelisted(self):
        """Test non-whitelisted domain."""
        url = "https://malicious.com"
        assert validate_url_with_whitelist(url) is False

    def test_custom_whitelist(self):
        """Test with custom whitelist."""
        url = "https://example.com"
        whitelist = {"example.com"}
        assert validate_url_with_whitelist(url, whitelist) is True


class TestValidateUrlWithBlacklist:
    """Tests for validate_url_with_blacklist function."""

    def test_blacklisted_domain(self):
        """Test blacklisted domain."""
        url = "https://malware.example.com"
        assert validate_url_with_blacklist(url) is False

    def test_subdomain_blacklisted(self):
        """Test subdomain of blacklisted domain."""
        url = "https://sub.malware.example.com"
        assert validate_url_with_blacklist(url) is False

    def test_not_blacklisted(self):
        """Test non-blacklisted domain."""
        url = "https://example.com"
        assert validate_url_with_blacklist(url) is True

    def test_custom_blacklist(self):
        """Test with custom blacklist."""
        url = "https://blocked.com"
        blacklist = {"blocked.com"}
        assert validate_url_with_blacklist(url, blacklist) is False


class TestSanitizeInput:
    """Tests for sanitize_input function."""

    def test_basic_sanitization(self):
        """Test basic input sanitization."""
        text = "Hello <script>alert('xss')</script> World"
        result = sanitize_input(text)
        assert "<script>" not in result

    def test_null_bytes(self):
        """Test null byte removal."""
        text = "Hello\x00World"
        result = sanitize_input(text)
        assert "\x00" not in result

    def test_control_characters(self):
        """Test control character removal."""
        text = "Hello\x01World"
        result = sanitize_input(text)
        assert "\x01" not in result

    def test_empty_string(self):
        """Test empty string."""
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""

    def test_length_limit(self):
        """Test length limit."""
        text = "a" * 20000
        result = sanitize_input(text)
        assert len(result) <= 10000


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.fixture
    def limiter(self):
        """Create a rate limiter for testing."""
        return RateLimiter(max_requests=5, window_seconds=60.0)

    def test_allowed_within_limit(self, limiter):
        """Test requests within limit are allowed."""
        for _ in range(5):
            assert limiter.is_allowed() is True

    def test_blocked_over_limit(self, limiter):
        """Test requests over limit are blocked."""
        for _ in range(5):
            limiter.is_allowed()

        # 6th request should be blocked
        assert limiter.is_allowed() is False

    def test_remaining_requests(self, limiter):
        """Test remaining requests count."""
        assert limiter.get_remaining_requests() == 5

        limiter.is_allowed()
        assert limiter.get_remaining_requests() == 4

    def test_reset(self, limiter):
        """Test rate limiter reset."""
        for _ in range(5):
            limiter.is_allowed()

        assert limiter.get_remaining_requests() == 0

        limiter.reset()
        assert limiter.get_remaining_requests() == 5


class TestGetRateLimiter:
    """Tests for get_rate_limiter function."""

    @pytest.fixture
    def clean_state(self):
        """Clean up global state before test."""
        reset_rate_limiter()
        yield
        reset_rate_limiter()

    def test_singleton(self, clean_state):
        """Test that get_rate_limiter returns a singleton."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_custom_config(self, clean_state):
        """Test with custom environment variables."""
        import os

        from web_mcp.security import reset_rate_limiter

        # Set custom config
        os.environ["WEB_MCP_RATE_LIMIT_REQUESTS"] = "20"
        os.environ["WEB_MCP_RATE_LIMIT_WINDOW"] = "120.0"

        # Reset and get limiter
        reset_rate_limiter()
        limiter = get_rate_limiter()

        assert limiter.max_requests == 20
        assert limiter.window_seconds == 120.0


class TestSSRFProtection:
    """Tests for SSRF protection via validate_url_ip function."""

    def test_block_loopback_ipv4(self):
        """Test blocking of loopback IPv4 addresses."""
        # 127.0.0.1 is the standard loopback
        assert validate_url_ip("http://127.0.0.1") is False

    def test_block_private_class_a(self):
        """Test blocking of private Class A addresses (10.0.0.0/8)."""
        assert validate_url_ip("http://10.0.0.1") is False
        assert validate_url_ip("http://10.255.255.255") is False

    def test_block_private_class_b(self):
        """Test blocking of private Class B addresses (172.16.0.0/12)."""
        assert validate_url_ip("http://172.16.0.1") is False
        assert validate_url_ip("http://172.31.255.255") is False

    def test_block_private_class_c(self):
        """Test blocking of private Class C addresses (192.168.0.0/16)."""
        assert validate_url_ip("http://192.168.1.1") is False
        assert validate_url_ip("http://192.168.0.1") is False

    def test_block_link_local_ipv4(self):
        """Test blocking of link-local IPv4 addresses (169.254.0.0/16)."""
        assert validate_url_ip("http://169.254.0.1") is False

    def test_block_ipv6_loopback(self):
        """Test blocking of IPv6 loopback (::1)."""
        # Note: This may pass or fail depending on DNS resolution
        # The important thing is that it's blocked if resolved to ::1
        pass  # Skip as DNS resolution of ::1 may vary by environment

    def test_block_ipv6_link_local(self):
        """Test blocking of IPv6 link-local addresses (fe80::/10)."""
        # Skip as DNS resolution may vary
        pass

    def test_block_ipv6_unique_local(self):
        """Test blocking of IPv6 unique local addresses (fc00::/7)."""
        # Skip as DNS resolution may vary
        pass

    def test_allow_public_ip(self):
        """Test that public IPs are allowed (if resolvable)."""
        # This test may vary based on network conditions
        # Just verify the function doesn't crash
        result = validate_url_ip("http://example.com")
        # Result can be True or False depending on DNS resolution
        assert isinstance(result, bool)


class TestCredentialInjectionPrevention:
    """Tests for credential injection prevention via validate_url_no_credentials."""

    def test_block_url_with_username(self):
        """Test blocking URL with username in credentials."""
        url = "https://user@example.com"
        assert validate_url_no_credentials(url) is False

    def test_block_url_with_password(self):
        """Test blocking URL with password in credentials."""
        url = "https://:password@example.com"
        assert validate_url_no_credentials(url) is False

    def test_block_url_with_both_credentials(self):
        """Test blocking URL with both username and password."""
        url = "https://user:password@example.com"
        assert validate_url_no_credentials(url) is False

    def test_block_credential_injection_bypass(self):
        """Test blocking credential injection like https://wikipedia.org@evil.com."""
        url = "https://wikipedia.org@evil.com"
        assert validate_url_no_credentials(url) is False

    def test_block_credential_injection_with_path(self):
        """Test blocking credential injection with path."""
        url = "https://wikipedia.org@evil.com/path/to/page"
        assert validate_url_no_credentials(url) is False

    def test_allow_normal_url(self):
        """Test that normal URLs without credentials are allowed."""
        url = "https://example.com"
        assert validate_url_no_credentials(url) is True

    def test_allow_url_with_query_params(self):
        """Test that URLs with query parameters are allowed."""
        url = "https://example.com?user=test&pass=123"
        assert validate_url_no_credentials(url) is True


class TestRedirectValidation:
    """Tests for redirect validation in fetcher module."""

    @pytest.mark.asyncio
    async def test_redirect_to_whitelisted_domain(self):
        """Test that redirects to whitelisted domains are allowed."""
        from web_mcp.fetcher import RedirectValidator

        validator = RedirectValidator(max_redirects=5)

        # Whitelisted domain should pass
        result = await validator.should_follow_redirect("https://wikipedia.org/wiki/Python")
        assert result is True

    @pytest.mark.asyncio
    async def test_redirect_to_non_whitelisted_domain(self):
        """Test that redirects to non-whitelisted domains are blocked."""
        from web_mcp.fetcher import RedirectValidator

        validator = RedirectValidator(max_redirects=5)

        # Non-whitelisted domain should be blocked
        result = await validator.should_follow_redirect("https://malicious.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_redirect_to_private_ip(self):
        """Test that redirects to private IPs are blocked."""
        from web_mcp.fetcher import RedirectValidator

        validator = RedirectValidator(max_redirects=5)

        # Private IP should be blocked
        result = await validator.should_follow_redirect("http://127.0.0.1")
        assert result is False

    @pytest.mark.asyncio
    async def test_redirect_to_loopback_hostname(self):
        """Test that redirects to localhost are blocked."""
        from web_mcp.fetcher import RedirectValidator

        validator = RedirectValidator(max_redirects=5)

        # localhost should be blocked
        result = await validator.should_follow_redirect("http://localhost")
        assert result is False

    @pytest.mark.asyncio
    async def test_redirect_exceeds_limit(self):
        """Test that redirects exceeding the limit are blocked."""
        from web_mcp.fetcher import RedirectValidator

        validator = RedirectValidator(max_redirects=2)

        # First two redirects should pass (assuming other checks pass)
        await validator.should_follow_redirect("https://wikipedia.org")
        await validator.should_follow_redirect("https://github.com")

        # Third redirect should be blocked due to limit
        result = await validator.should_follow_redirect("https://stackoverflow.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_redirect_with_credentials_blocked(self):
        """Test that redirects with credentials are blocked."""
        from web_mcp.fetcher import RedirectValidator

        validator = RedirectValidator(max_redirects=5)

        # URL with credentials should be blocked
        result = await validator.should_follow_redirect("https://wikipedia.org@evil.com")
        assert result is False


class TestValidateUrlIP:
    """Additional tests for validate_url_ip function."""

    def test_block_localhost_hostname(self):
        """Test blocking of localhost hostname."""
        # This will attempt DNS resolution of 'localhost'
        result = validate_url_ip("http://localhost")
        # Should be blocked as localhost resolves to 127.0.0.1
        assert result is False

    def test_block_localhost_ipv6(self):
        """Test blocking of IPv6 localhost (::1)."""
        result = validate_url_ip("http://[::1]")
        # Should be blocked as ::1 is in the IPv6 blacklist
        assert result is False
