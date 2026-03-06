# Docker Hub Publishing Setup Guide

This guide provides step-by-step instructions for setting up automated Docker image publishing to Docker Hub from GitHub Actions.

---

## 1. Prerequisites

Before starting, ensure you have:

- [ ] A Docker Hub account (create one at [hub.docker.com](https://hub.docker.com) if needed)
- [ ] Access to the GitHub repository that will publish images
- [ ] Docker installed locally for testing (optional but recommended)
- [ ] Appropriate permissions on Docker Hub to create repositories and tokens

---

## 2. Create Docker Hub Access Token

### 2.1 Navigate to Security Settings

1. Log in to [Docker Hub](https://hub.docker.com)
2. Click your username in the top-right corner
3. Select **Account Settings** from the dropdown menu
4. Click **Security** in the left sidebar

### 2.2 Create New Access Token

1. Click **New Access Token** button
2. Configure the token:
   - **Name**: Enter a descriptive name (e.g., `github-actions-web-mcp`)
   - **Permissions**: Select **Read, Write, Delete** (required for pushing images)
   - **Expiration**: Set an appropriate expiration (90 days recommended, or custom)
3. Click **Generate**

### 2.3 Save the Token

**IMPORTANT**: Copy the token immediately!

- The token is only shown once
- Store it in a secure password manager
- You will need this for the GitHub secret configuration

**Screenshot Description**: The token generation page shows a form with fields for token name, permissions dropdown (Read/Write/Delete options), and expiration date picker. After generation, a modal displays the token with a copy button.

### 2.4 Security Best Practices for Tokens

- Use a unique token per repository or project
- Never commit tokens to source code
- Set appropriate expiration dates
- Use the minimum required permissions
- Rotate tokens regularly (every 90 days recommended)
- Revoke tokens immediately if compromised

---

## 3. Configure GitHub Secrets

### 3.1 Required Secrets

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `DOCKER_USERNAME` | Your Docker Hub username | `johndoe` |
| `DOCKER_PASSWORD` | Docker Hub access token (NOT your password) | `dckr_pat_xxxx...` |

### 3.2 Add Secrets to GitHub Repository

1. Navigate to your GitHub repository
2. Click **Settings** tab
3. In the left sidebar, expand **Secrets and variables**
4. Click **Actions**
5. Click **New repository secret**

#### Adding DOCKER_USERNAME

1. **Name**: `DOCKER_USERNAME`
2. **Secret**: Enter your Docker Hub username (case-sensitive)
3. Click **Add secret**

#### Adding DOCKER_PASSWORD

1. **Name**: `DOCKER_PASSWORD`
2. **Secret**: Paste the access token created in Section 2
3. Click **Add secret**

### 3.3 Verify Secrets

After adding both secrets, you should see them listed under "Repository secrets" (values are masked).

**Screenshot Description**: The Actions secrets page shows a list of repository secrets with names like DOCKER_USERNAME and DOCKER_PASSWORD. Each entry shows when it was last updated but hides the actual values.

### 3.4 Using Secrets in Workflow

```yaml
- name: Log in to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKER_USERNAME }}
    password: ${{ secrets.DOCKER_PASSWORD }}
```

---

## 4. First Time Setup

### 4.1 Create Repository on Docker Hub

1. Log in to [Docker Hub](https://hub.docker.com)
2. Click **Create** (top menu) → **Repository**
3. Configure the repository:
   - **Namespace**: Your username or organization
   - **Repository Name**: `web-mcp` (or your preferred name)
   - **Visibility**: 
     - **Public**: Anyone can pull the image (free)
     - **Private**: Only authorized users can pull (limited free tier)
   - **Description**: Brief description of the image
4. Click **Create**

### 4.2 Configure Repository Settings

After creating the repository:

1. Go to repository **Settings** tab
2. Configure:
   - **Description**: Add detailed description
   - **Full Description**: Add markdown documentation (optional)
   - **Category**: Select appropriate category (e.g., Developer Tools)
3. Save changes

### 4.3 Set Up Automated Builds (Optional)

> Note: Automated builds on Docker Hub are deprecated. Use GitHub Actions instead.

If you prefer Docker Hub's legacy automated builds:

1. Go to **Builds** tab in repository settings
2. Click **Link to GitHub**
3. Authorize Docker Hub to access your GitHub account
4. Select the repository and branch
5. Configure build rules:
   - **Source Type**: Branch
   - **Source**: `main`
   - **Docker Tag**: `latest`
   - **Dockerfile Location**: `Dockerfile`
6. Click **Create**

---

## 5. Testing the Workflow

### 5.1 Manual Trigger

If your workflow supports manual triggers (`workflow_dispatch`):

1. Go to **Actions** tab in GitHub
2. Select the Docker publishing workflow
3. Click **Run workflow**
4. Select the branch (usually `main`)
5. Click **Run workflow** button

### 5.2 Trigger via Push

Alternatively, push a commit to trigger the workflow:

```bash
git commit --allow-empty -m "trigger: test docker publish"
git push origin main
```

### 5.3 Check Build Status

1. Go to **Actions** tab in GitHub
2. Click on the running/completed workflow
3. Monitor each step:
   - **Build** step: Should complete without errors
   - **Push** step: Should show successful image push
4. Expand logs for detailed output

### 5.4 Verify Image on Docker Hub

1. Go to [Docker Hub](https://hub.docker.com)
2. Navigate to your repository
3. Check **Tags** tab for the new image tag
4. Verify:
   - Tag name matches expected (e.g., `latest`, `v1.0.0`)
   - Image size is reasonable
   - Last updated timestamp is recent

### 5.5 Pull and Test the Image

```bash
# Pull the image
docker pull <username>/web-mcp:latest

# Run the image
docker run --rm <username>/web-mcp:latest --help

# Verify image details
docker inspect <username>/web-mcp:latest
```

---

## 6. Troubleshooting

### 6.1 Common Issues

#### Issue: "unauthorized: authentication required"

**Causes:**
- Incorrect username or token
- Token expired
- Token has insufficient permissions

**Solutions:**
1. Verify `DOCKER_USERNAME` matches your Docker Hub username exactly
2. Regenerate the access token and update `DOCKER_PASSWORD` secret
3. Ensure token has Read, Write, Delete permissions

#### Issue: "denied: requested access to the resource is denied"

**Causes:**
- No write permission to the repository
- Repository doesn't exist
- Wrong namespace

**Solutions:**
1. Create the repository on Docker Hub first
2. Verify namespace matches your username or organization
3. Check token permissions include Write access

#### Issue: "manifest unknown"

**Causes:**
- Image tag doesn't exist
- Build failed before push step

**Solutions:**
1. Check build logs for errors
2. Verify build step completed successfully
3. Ensure tag naming is correct

### 6.2 Authentication Errors

#### Error: "Error: login attempt failed"

```bash
# Test credentials locally first
echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin
```

If this fails locally:
1. Verify username is correct (case-sensitive)
2. Regenerate access token
3. Check if account is locked or suspended

#### Error: "Error response from daemon: Get https://registry-1.docker.io/v2/: unauthorized"

**Solutions:**
1. Check Docker Hub service status
2. Verify network connectivity
3. Try logging out and back in:
   ```bash
   docker logout
   docker login
   ```

### 6.3 Build Failures

#### Error: "COPY failed: file not found"

**Causes:**
- Incorrect path in Dockerfile
- File not committed to repository
- .dockerignore excluding necessary files

**Solutions:**
1. Verify file paths in Dockerfile are relative to build context
2. Ensure files are committed and pushed
3. Review .dockerignore file

#### Error: "no space left on device"

**Solutions:**
1. Clean up Docker resources:
   ```bash
   docker system prune -a
   ```
2. Increase disk space on runner (for self-hosted)
3. Use GitHub-hosted runners with more storage

#### Error: "buildx failed with: error: failed to solve"

**Solutions:**
1. Check Dockerfile syntax
2. Verify base image exists and is accessible
3. Review build arguments and environment variables

### 6.4 Debug Mode

Enable debug logging in workflow:

```yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ${{ steps.meta.outputs.tags }}
  env:
    DOCKER_BUILDKIT: 1
    BUILDKIT_PROGRESS: plain
```

---

## 7. Security Best Practices

### 7.1 Use Access Tokens (Not Passwords)

- Never use your Docker Hub password in GitHub secrets
- Access tokens can be revoked without changing your password
- Tokens can have limited scope and expiration

### 7.2 Limit Token Permissions

Grant only the permissions needed:

| Use Case | Required Permission |
|----------|---------------------|
| Pull images only | Read |
| Push images | Read, Write |
| Delete images | Read, Write, Delete |

### 7.3 Regular Token Rotation

Recommended rotation schedule:

| Token Type | Rotation Frequency |
|------------|-------------------|
| CI/CD tokens | Every 90 days |
| Development tokens | Every 30 days |
| Production tokens | Every 90 days |

**Rotation Process:**

1. Create new access token
2. Update GitHub secret with new token
3. Verify workflows still work
4. Revoke old token

### 7.4 Additional Security Measures

#### Use Organization Secrets (for teams)

1. Store secrets at organization level
2. Limit which repositories can access secrets
3. Centralize secret management

#### Enable 2FA on Docker Hub

1. Go to Account Settings → Security
2. Enable Two-Factor Authentication
3. Use an authenticator app (recommended over SMS)

#### Audit Token Usage

1. Regularly review active tokens in Docker Hub
2. Revoke unused or suspicious tokens
3. Monitor Docker Hub audit logs (Business plan)

#### Use Minimal Base Images

- Prefer `alpine` or `distroless` base images
- Reduces attack surface
- Smaller image size

#### Scan Images for Vulnerabilities

```yaml
- name: Scan image for vulnerabilities
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ steps.meta.outputs.tags }}
    format: 'table'
    exit-code: '1'  # Fail on vulnerabilities
    severity: 'CRITICAL,HIGH'
```

### 7.5 Secret Management Checklist

- [ ] Use access tokens, not passwords
- [ ] Set token expiration dates
- [ ] Use unique tokens per repository
- [ ] Rotate tokens regularly
- [ ] Enable 2FA on Docker Hub account
- [ ] Review and revoke unused tokens
- [ ] Use organization secrets for team access
- [ ] Never commit secrets to source code
- [ ] Audit secret access periodically

---

## Quick Reference

### Essential Commands

```bash
# Login to Docker Hub
docker login

# Pull image
docker pull <username>/web-mcp:latest

# Push image
docker push <username>/web-mcp:latest

# List local images
docker images | grep web-mcp

# Remove local image
docker rmi <username>/web-mcp:latest
```

### Workflow Example

```yaml
name: Docker Publish

on:
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ secrets.DOCKER_USERNAME }}/web-mcp

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## Support

- [Docker Hub Documentation](https://docs.docker.com/docker-hub/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Login Action](https://github.com/docker/login-action)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
