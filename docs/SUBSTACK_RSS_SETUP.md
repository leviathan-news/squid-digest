# Substack RSS Auto-Posting Setup

## RSS Feed URL
```
https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup/feed.xml
```

## Method 1: Zapier Automation (Recommended if Substack RSS import unavailable)

### Setup Steps

1. **Sign up for Zapier** (free tier works)
   - Go to https://zapier.com
   - Create free account

2. **Create New Zap**
   - Click **"Create Zap"**
   - Name it: "Squid Digest to Substack"

3. **Configure Trigger (RSS Feed)**
   - **App:** RSS by Zapier
   - **Trigger Event:** "New Item in Feed"
   - **Feed URL:** `https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup/feed.xml`
   - **Test trigger** - should show recent digests

4. **Configure Action (Substack Post)**
   - **App:** Webhooks by Zapier (Substack doesn't have native integration)
   - **Action:** POST request to Substack API

   **OR use Email integration:**
   - **App:** Email by Zapier
   - **Action:** Send email to your Substack publish-by-email address
   - **To:** `your-publication@substack.com` (get from Substack settings)
   - **Subject:** `{{title}}` (from RSS feed)
   - **Body:** `{{content:encoded}}` (full HTML content)

5. **Test and Enable**
   - Test the Zap with a recent digest
   - Enable the Zap
   - New digests will auto-post when RSS updates

### Zapier Mapping

| RSS Field | Substack Field |
|-----------|----------------|
| `title` | Post Title |
| `content:encoded` | Post Body (HTML) |
| `pubDate` | Publication Date |
| `category` | Tags (optional) |

---

## Method 2: IFTTT Automation

### Setup Steps

1. **Sign up for IFTTT** (free tier works)
   - Go to https://ifttt.com
   - Create account

2. **Create New Applet**
   - Click **"Create"**

3. **Configure "If This" (RSS Trigger)**
   - Search for **"RSS Feed"**
   - Choose **"New feed item"**
   - Enter URL: `https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup/feed.xml`

4. **Configure "Then That" (Email Action)**
   - Search for **"Email"** or **"Gmail"**
   - Choose **"Send an email"**
   - **To:** Your Substack publish-by-email address
   - **Subject:** `{{EntryTitle}}`
   - **Body:** `{{EntryContent}}`

5. **Save and Enable**

---

## Method 3: Direct Substack RSS Import (Beta Feature)

### If Available in Your Account

1. **Substack Dashboard** → **Settings**
2. Look for **"Import"** or **"RSS feed"** section
3. Enter feed URL: `https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup/feed.xml`
4. Configure:
   - Auto-import: **Enabled**
   - Check frequency: **Daily**
   - Post status: **Draft** (review before publishing)
5. Save settings

### Not Available?
Substack RSS import is still in beta and may not be available for all account tiers. Use Method 1 (Zapier) or Method 2 (IFTTT) instead.

---

## Testing Your Setup

### 1. Test RSS Feed First
Visit in browser: https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup/feed.xml

Or test in RSS reader:
- Feedly: https://feedly.com
- Inoreader: https://www.inoreader.com

### 2. Verify Content
Check that RSS items include:
- ✅ Title with date
- ✅ Market snapshot (BTC/ETH prices)
- ✅ Trading signals count
- ✅ Full HTML content
- ✅ Images loading

### 3. Test Import
- Wait for next digest (generated daily at 13:00 UTC)
- Check Substack drafts for new post
- Verify formatting matches your expectations

---

## Publish-by-Email Address

To get your Substack publish-by-email address:

1. **Substack Dashboard** → **Settings**
2. Look for **"Email publishing"** or **"Post by email"**
3. You'll see an address like: `your-publication-name@substack.com`
4. Copy this address for use in Zapier/IFTTT

**Note:** Some Substack accounts may not have this feature enabled. If you don't see it, contact Substack support.

---

## Troubleshooting

### RSS Feed Not Loading
- Check URL is exactly: `https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup/feed.xml`
- Verify feed.xml exists in GitHub repo
- Test in browser to see XML content

### Images Not Displaying
- Images are hosted on Leviathan News CDN
- Should work in all RSS readers
- If not loading, check internet connection

### HTML Formatting Issues
- RSS uses `<content:encoded>` with full HTML
- Some readers strip certain HTML tags
- Test in multiple readers (Feedly, Inoreader, Substack)

### Substack Not Importing
- Verify RSS URL is correct
- Check Substack account tier supports RSS import
- Try email-based publishing instead (more reliable)
- Use Zapier/IFTTT as fallback

---

## Daily Schedule

- **Generation:** 13:00 UTC (5 AM PT) via GitHub Actions
- **RSS Update:** Automatic when digest is generated
- **Import:** Depends on your automation settings
  - Zapier: Checks every 15 minutes (free tier)
  - IFTTT: Checks hourly (free tier)
  - Substack RSS: Check frequency you configured

---

## Support

If you run into issues:
1. Test RSS feed URL in browser first
2. Verify RSS feed contains recent digests
3. Check Zapier/IFTTT logs for errors
4. Contact Substack support if RSS import unavailable
