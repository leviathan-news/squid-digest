# GitHub Actions Email Setup

## Overview

The daily digest email workflow is now **fully configured and working**! Here's how it operates:

### Daily Schedule

1. **5:00 AM PT (13:00 UTC)** - `draft-digest.yml`
   - Generates the daily trading signals digest
   - Creates a Ghost draft post for admin review
   - Posts to Telegram channel (if configured)
   - Commits the digest to the repository

2. **6:00 AM PT (14:00 UTC)** - `send-digest.yml`
   - Sends the digest email to all newsletter subscribers via Ghost
   - Uses the fixed Ghost API integration

### Required GitHub Secrets

Go to: **Repository Settings → Secrets and variables → Actions**

**Required:**
- `GHOST_URL` - Your Ghost site URL (e.g., `https://your-ghost-site.com`)
- `GHOST_ADMIN_API_KEY` - Your Ghost Admin API key (format: `id:secret`)
- `PERPLEXITY_API_KEY` - For digest generation

**Optional:**
- `PUBLIC_EMAILS` - Fallback emails if Ghost subscribers aren't available
- `ADMIN_EMAILS` - For admin notifications (defaults to `squid@leviathannews.xyz`)
- `TELEGRAM_BOT_TOKEN` - For Telegram notifications
- `TELEGRAM_CHANNEL_ID` - For Telegram channel

## How Email Sending Works

The workflow now uses the **corrected Ghost API method**:

1. Creates a draft post in Ghost
2. Publishes the post with newsletter query parameters:
   - `?newsletter=default-newsletter`
   - `&email_segment=all`
3. Ghost automatically queues the email for delivery to all subscribers

### Ghost Configuration Required

In your Ghost admin panel, ensure:

1. **Newsletter is configured:**
   - Go to Settings → Email newsletter
   - Configure email service (Mailgun, SendGrid, etc.)
   - Verify newsletter is active

2. **Members are subscribed:**
   - Members with `subscriber` label will receive emails
   - The script automatically fetches all Ghost subscribers

## Manual Testing

Test the email sending locally:

```bash
# Send to all newsletter subscribers
python scripts/send_email.py --type public --digest-file writeup/signals_2025-11-14.md

# Dry run (no actual sending)
python scripts/send_email.py --type public --digest-file writeup/signals_2025-11-14.md --dry-run

# Send test email to admins
python scripts/send_email.py --type test --digest-file writeup/signals_2025-11-14.md
```

## Manual Workflow Trigger

You can manually trigger the workflows from GitHub:

1. Go to **Actions** tab in your repository
2. Select `Send Daily Digest` workflow
3. Click **Run workflow** button
4. Choose the branch and click **Run workflow**

## Troubleshooting

### Email not sending?

1. **Check GitHub Actions logs:**
   - Go to Actions tab
   - Click on the failed workflow run
   - Check the "Send digest email" step for errors

2. **Verify Ghost newsletter:**
   - Login to Ghost admin panel
   - Settings → Email newsletter
   - Ensure newsletter is configured and active

3. **Check Ghost members:**
   - Members → All members
   - Verify members are subscribed to newsletter
   - Check for `subscriber` label

4. **Test locally:**
   - Run the send_email.py script locally
   - Check for API errors in the output

### Common Issues

**404 Errors:** Fixed! The workflow now uses the correct Ghost API endpoints with query parameters.

**No subscribers found:** The script will fallback to `PUBLIC_EMAILS` env variable if no Ghost subscribers are found.

**Email service not configured:** Ghost requires an email service (Mailgun/SendGrid) to be set up in the admin panel.

## Recent Changes

✅ Fixed Ghost API integration to use correct newsletter parameters
✅ Updated `send_email_to_members()` to publish with `?newsletter=slug&email_segment=all`
✅ Improved error handling and logging in workflows
✅ Simplified email sending flow by removing complex fallback logic

The workflow is now ready to send daily digest emails automatically!
