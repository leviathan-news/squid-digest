# Substack RSS Import Automation

This document describes how to set up automated RSS feed import to Substack using browser automation.

## Overview

The automation uses Playwright to interact with Substack's RSS import page (`/publish/import`). It supports two authentication methods:

1. **Session Cookies** (Primary, Recommended) - Most persistent, can last weeks/months
2. **Email/Password Login** (Fallback) - Used if cookies expire or fail

## RSS Feed URL

The default RSS feed URL is:
```
https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup/feed.xml
```

This feed is automatically updated when digests are generated.

## Setup Instructions

### Step 1: Export Session Cookies (Recommended)

Session cookies are the "stickiest" authentication method and can last for weeks or months.

#### Using Browser DevTools:

1. **Log in to Substack** in your browser
   - Go to https://leviathannews.substack.com
   - Log in with your credentials

2. **Open Browser DevTools**
   - Chrome/Edge: Press `F12` or `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)
   - Firefox: Press `F12` or `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)

3. **Go to Application/Storage Tab**
   - Chrome/Edge: Click "Application" tab → "Cookies" → `https://leviathannews.substack.com`
   - Firefox: Click "Storage" tab → "Cookies" → `https://leviathannews.substack.com`

4. **Export Cookies**
   - Look for cookies with domain `.substack.com` or `leviathannews.substack.com`
   - Important cookies to include:
     - `substack.sid` (session ID - most important)
     - Any other cookies with `substack` in the name
   - Copy the cookie values

5. **Format as JSON**
   Create a JSON array with cookie objects. Each cookie should have:
   ```json
   [
     {
       "name": "substack.sid",
       "value": "your-session-id-value",
       "domain": ".substack.com",
       "path": "/",
       "expires": -1,
       "httpOnly": true,
       "secure": true,
       "sameSite": "Lax"
     }
   ]
   ```

   **Note**: You can use `-1` for `expires` if the cookie doesn't expire, or omit fields you're unsure about. The minimum required fields are: `name`, `value`, `domain`.

#### Using Browser Extension (Easier):

1. Install a cookie export extension:
   - Chrome: "Get cookies.txt LOCALLY" or "Cookie-Editor"
   - Firefox: "Cookie-Editor"

2. Export cookies for `substack.com` domain

3. Convert to JSON format (some extensions export as JSON directly)

### Step 2: Set Up GitHub Secrets

Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**

Add the following secrets:

#### Required (at least one authentication method):

**Option A: Session Cookies (Recommended)**
- **Name**: `SUBSTACK_SESSION_COOKIES`
- **Value**: JSON string with cookies array (from Step 1)
- **Example**:
  ```json
  [{"name":"substack.sid","value":"your-session-id","domain":".substack.com","path":"/","expires":-1,"httpOnly":true,"secure":true}]
  ```

**Option B: Email/Password (Fallback)**
- **Name**: `SUBSTACK_EMAIL`
- **Value**: Your Substack account email

- **Name**: `SUBSTACK_PASSWORD`
- **Value**: Your Substack account password

#### Optional:

- **Name**: `SUBSTACK_URL`
- **Value**: Your Substack publication URL (defaults to `https://leviathannews.substack.com`)

### Step 3: Verify Setup

1. **Test Locally** (Optional but Recommended):
   ```bash
   # Set environment variables
   export SUBSTACK_SESSION_COOKIES='[{"name":"substack.sid","value":"...","domain":".substack.com"}]'
   export SUBSTACK_URL="https://leviathannews.substack.com"
   
   # Run the script
   python scripts/import_to_substack.py --no-headless
   ```

2. **Test in GitHub Actions**:
   - Go to **Actions** tab in GitHub
   - Find "Import RSS to Substack" workflow
   - Click "Run workflow" → "Run workflow"
   - Monitor the logs for success/failure

## How It Works

### Workflow Schedule

The automation runs daily at **6:15 AM PT (14:15 UTC)**, 15 minutes after digest generation. This gives time for the RSS feed to be updated.

### Authentication Flow

1. **First Attempt**: Try session cookie authentication
   - Loads cookies from `SUBSTACK_SESSION_COOKIES` secret
   - Navigates to Substack and adds cookies
   - Verifies authentication by checking if logged in

2. **Fallback**: If cookies fail, use email/password
   - Navigates to login page
   - Fills in email and password from secrets
   - Submits login form
   - Verifies authentication

3. **RSS Import**: Once authenticated
   - Navigates to `/publish/import`
   - Pastes RSS feed URL
   - Clicks import button
   - Waits for import to complete

### Isolation

This workflow is **completely isolated** from other workflows:
- Failures here **do not affect** email delivery (`send-digest.yml`)
- Failures here **do not affect** digest generation (`draft-digest.yml`)
- The workflow uses `continue-on-error: true` to prevent blocking

## Troubleshooting

### Authentication Failures

**Problem**: "Cookie authentication failed - redirected to login"

**Solutions**:
1. **Refresh Cookies**: Cookies may have expired. Re-export cookies from a fresh login session.
2. **Check Cookie Format**: Ensure JSON is valid and includes required fields (`name`, `value`, `domain`).
3. **Use Email/Password Fallback**: If cookies keep failing, rely on email/password authentication.

**Problem**: "Login failed - still on login page"

**Solutions**:
1. **Verify Credentials**: Check that `SUBSTACK_EMAIL` and `SUBSTACK_PASSWORD` are correct.
2. **Check for 2FA**: If you have 2FA enabled, you may need to use session cookies instead.
3. **Account Locked**: Too many failed login attempts may temporarily lock your account.

### Import Failures

**Problem**: "Could not find RSS feed input field"

**Solutions**:
1. **Substack UI Changed**: Substack may have updated their import page. Check the page structure.
2. **Not Logged In**: Authentication may have failed silently. Check authentication logs.
3. **Wrong URL**: Verify you're using the correct Substack publication URL.

**Problem**: "Import button not found"

**Solutions**:
1. **Page Not Loaded**: The page may need more time to load. Increase timeout in workflow.
2. **UI Changed**: Substack may have updated their import page. Update selectors in code.

### Browser Automation Issues

**Problem**: "Timeout during RSS import"

**Solutions**:
1. **Increase Timeout**: Edit workflow to increase `--timeout` value (default: 60000ms = 60s).
2. **Check Network**: GitHub Actions runner may have slow network. This is usually transient.

**Problem**: "Browser failed to start"

**Solutions**:
1. **Playwright Not Installed**: Ensure `playwright` is in `pyproject.toml` dependencies.
2. **Browser Dependencies**: The workflow installs browser dependencies automatically, but if it fails, check GitHub Actions logs.

## Cookie Refresh Process

Session cookies will eventually expire. When they do:

1. **Re-export Cookies**: Follow Step 1 above to get fresh cookies
2. **Update GitHub Secret**: Update `SUBSTACK_SESSION_COOKIES` with new cookie values
3. **Test**: Run the workflow manually to verify new cookies work

**How Often to Refresh**:
- Typically every 1-3 months (depends on Substack's session policy)
- When you see authentication failures in workflow logs
- After changing your Substack password

## Manual Testing

### Test Locally with Visible Browser

```bash
# Set environment variables
export SUBSTACK_SESSION_COOKIES='[{"name":"substack.sid","value":"...","domain":".substack.com"}]'
export SUBSTACK_URL="https://leviathannews.substack.com"

# Run with visible browser (for debugging)
python scripts/import_to_substack.py --no-headless
```

### Test with Email/Password

```bash
export SUBSTACK_EMAIL="your-email@example.com"
export SUBSTACK_PASSWORD="your-password"
export SUBSTACK_URL="https://leviathannews.substack.com"

python scripts/import_to_substack.py --no-headless
```

### Test RSS URL Only

```bash
# Use custom RSS URL
python scripts/import_to_substack.py \
  --rss-url "https://example.com/feed.xml" \
  --no-headless
```

## Security Considerations

1. **Never Commit Secrets**: Cookies and passwords should only be in GitHub Secrets
2. **Rotate Credentials**: Periodically update passwords and refresh cookies
3. **Monitor Logs**: Check GitHub Actions logs regularly for authentication issues
4. **Limit Access**: Only trusted team members should have access to repository secrets

## Support

If you encounter issues:

1. **Check Workflow Logs**: Go to Actions → Import RSS to Substack → View logs
2. **Test Locally**: Run the script locally with `--no-headless` to see what's happening
3. **Verify Secrets**: Ensure all required secrets are set correctly
4. **Check Substack Status**: Verify Substack's import page is accessible and working

## Related Documentation

- [GitHub Actions Email Setup](GITHUB_ACTIONS_EMAIL_SETUP.md) - Email delivery workflow
- [Substack RSS Setup](SUBSTACK_RSS_SETUP.md) - Manual RSS import instructions
- [Technical Documentation](TECHNICAL.md) - General technical details

