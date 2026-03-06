# Security Policy

## Commitment to Security

The web-mcp project is committed to providing a secure and reliable MCP server for web automation and scraping. We take security seriously and appreciate responsible disclosure of any vulnerabilities.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

We actively maintain and provide security updates for the current major version (1.x). Older versions may not receive security patches.

---

## Reporting a Vulnerability

We appreciate responsible disclosure and will work with you to understand and address security issues promptly.

### How to Report

- **Email**: Send details to [security@example.com](mailto:security@example.com)
- **GitHub Security Advisory**: Use GitHub's [private vulnerability reporting](https://github.com/kweg/web_mcp/security/advisories/new) feature

### What to Include

Please provide as much of the following information as possible:

- Description of the vulnerability
- Steps to reproduce the issue
- Affected versions
- Potential impact
- Proof-of-concept or exploit code (if available)
- Suggested mitigation (if any)

### Response Timeline

| Stage | Timeframe |
|-------|-----------|
| Initial Response | 24-48 hours |
| Vulnerability Assessment | Within 7 days |
| Fix Development | Depends on complexity |
| Patch Release | As soon as possible after fix |

### Disclosure Policy

We follow **coordinated disclosure**:

1. Report is received and acknowledged
2. Vulnerability is verified and assessed
3. Fix is developed and tested
4. Patch is released
5. Public disclosure (after patch is available, typically 30 days)

We request that reporters:
- Do not disclose the vulnerability publicly until a fix is available
- Allow reasonable time for us to address the issue
- Provide details privately first

---

## Security Features

web-mcp includes multiple layers of security protection:

### SSRF Protection (Private IP Blocking)

- Blocks requests to private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Blocks loopback addresses (127.0.0.0/8)
- Blocks link-local addresses (169.254.0.0/16)
- Prevents access to internal network resources
- Configurable via `WEB_MCP_PRIVATE_IP_CONFIG`

### Credential Injection Prevention

- Strips credentials from URLs before making requests
- Prevents accidental credential exposure in logs and responses
- Uses `strip_credentials_from_url()` utility

### Redirect Validation

- Validates all HTTP redirects against security policies
- Blocks redirects to private IPs
- Respects redirect whitelists when configured
- Prevents open redirect vulnerabilities

### Rate Limiting

- Configurable request rate limits
- Prevents abuse and resource exhaustion
- Default limits can be adjusted via environment variables
- Per-client rate limiting support

### Content Size Limits

- Maximum response size limits
- Prevents memory exhaustion from large responses
- Configurable via `WEB_MCP_MAX_CONTENT_LENGTH`

### URL Validation

- Strict URL parsing and validation
- Blocks malformed or dangerous URLs
- Validates schemes (http/https only)
- DNS rebinding protection

### JavaScript Sandbox with Resource Limits

- Isolated browser context for JavaScript execution
- Configurable execution timeouts
- Memory and CPU limits
- Network access restrictions within sandbox

---

## Security Best Practices

When deploying web-mcp, follow these recommendations:

### Keep Dependencies Updated

```bash
# Regularly update dependencies
uv sync --upgrade

# Check for security vulnerabilities
uv audit
```

### Use Environment Variables for Secrets

Never hardcode secrets in configuration files:

```bash
# Good - use environment variables
export WEB_MCP_AUTH_TOKEN="your-secure-token"

# Bad - don't hardcode in code
auth_token = "your-secure-token"
```

### Enable Authentication

Always enable authentication in production:

```bash
export WEB_MCP_AUTH_TOKEN="your-secure-random-token"
```

Generate a secure token:

```bash
# Generate a secure random token
openssl rand -hex 32
```

### Configure Rate Limiting

Set appropriate rate limits for your use case:

```bash
export WEB_MCP_RATE_LIMIT_REQUESTS=100
export WEB_MCP_RATE_LIMIT_WINDOW=60  # seconds
```

### Review Redirect Whitelist

If using redirect whitelists, regularly review and update:

```bash
export WEB_MCP_REDIRECT_WHITELIST="https://trusted-domain.com,https://another-trusted.com"
```

### Run with Minimal Privileges

- Run the server as a non-root user
- Use container security contexts (if using Docker)
- Limit network access to necessary endpoints only

### Monitor and Log

- Enable logging for security-relevant events
- Monitor for unusual patterns
- Set up alerts for failed authentication attempts

---

## Known Security Considerations

### JavaScript Execution

- JavaScript is executed in a sandboxed Playwright browser context
- Resource-intensive operations may impact server performance
- Consider disabling JavaScript for untrusted sources
- Set appropriate timeouts to prevent hanging

### Playwright Browser Rendering

- Playwright renders potentially untrusted web content
- Browser instances consume significant resources
- Consider containerization for additional isolation
- Keep Playwright and browsers updated

### Public URL Exposure

The `render_html` tool can fetch and render arbitrary URLs:
- Ensure proper authentication is enabled
- Review and restrict which users can access this tool
- Consider implementing URL allowlists for sensitive deployments

### DNS Rebinding

- DNS rebinding attacks could potentially bypass IP-based restrictions
- Mitigated through URL validation and redirect checking
- Consider additional network-level protections for high-security environments

---

## Security Updates

### How We Handle Security Patches

1. **Assessment**: Vulnerabilities are assessed for severity and impact
2. **Prioritization**: Critical issues are addressed immediately
3. **Development**: Fixes are developed with minimal changes
4. **Testing**: Security patches undergo thorough testing
5. **Release**: Patches are released as soon as verified
6. **Advisory**: Security advisories are published with details

### Where to Find Security Advisories

- **GitHub Security Advisories**: [github.com/kweg/web_mcp/security/advisories](https://github.com/kweg/web_mcp/security/advisories)
- **Release Notes**: Security fixes are noted in release notes
- **CHANGELOG**: Security-related changes are documented

### Staying Updated

- Watch the GitHub repository for security advisories
- Subscribe to release notifications
- Regularly check for updates: `uv sync`

---

## Contact

### Security Team

- **Email**: [security@example.com](mailto:security@example.com)
- **GitHub**: [@kweg](https://github.com/kweg)

### For General Questions

For non-security related questions, please use:
- **GitHub Issues**: [github.com/kweg/web_mcp/issues](https://github.com/kweg/web_mcp/issues)
- **Discussions**: [github.com/kweg/web_mcp/discussions](https://github.com/kweg/web_mcp/discussions)

---

## Acknowledgments

We thank all security researchers and users who responsibly report vulnerabilities. Your efforts help make web-mcp more secure for everyone.
