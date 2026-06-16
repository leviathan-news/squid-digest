#!/usr/bin/env python3
"""
Migrate non-digest Substack posts → Ghost (digest.leviathannews.xyz).

One-time recovery: the Ghost DB was lost (CVE-2026-26980 box death). The daily
trading-signal digests were rebuilt from the squid-digest repo, but the
hand-authored posts (monthly SQUID Drops, governance proposals, editorial
essays) only ever lived in Ghost's DB and on Substack. This pulls them from
the public Substack archive API and republishes to Ghost AS-IS.

Source : https://leviathannews.substack.com  (archive + single-post API, public)
Target : Ghost Admin API (GHOST_URL + GHOST_ADMIN_API_KEY env, or
         ~/.config/leviathan/ghost-new-box.env)

Tag mapping (drives the custom homepage sections):
  - monthly SQUID Drops      -> tag "monthly-drop"
  - everything else non-daily -> tag "leviathan-updates"
Daily "Crypto Trading Signals" / "Daily Digest" posts are SKIPPED (already
rebuilt from the repo). SDP-01 is skipped if its slug already exists in Ghost.

SAFETY: never sends newsletter email (no ?newsletter= / ?email_segment=).
Idempotent: skips any slug already present in Ghost. --dry-run is the default.

Images: Substack bodies reference substackcdn.com URLs. Left hotlinked AS-IS
(content-as-is per operator). Re-hosting to Ghost is a separate future pass.

Usage:
    python scripts/migrate_substack_to_ghost.py --dry-run          # default, no writes
    python scripts/migrate_substack_to_ghost.py --apply            # publish to Ghost
    python scripts/migrate_substack_to_ghost.py --apply --only june-squid-drop-covering-may
"""

import argparse
import json
import os
import re
import sys
import time
import hashlib
import hmac
import base64
import urllib.request
import urllib.error
from pathlib import Path

SUBSTACK = "https://leviathannews.substack.com"
UA = {"User-Agent": "Mozilla/5.0 (leviathan-migration)"}

# Posts to SKIP entirely (already covered by the digest rebuild).
SKIP_TITLE_PATTERNS = [
    r"crypto trading signals",
    r"daily digest",
]


# --------------------------------------------------------------------------
# Substack source
# --------------------------------------------------------------------------

def fetch_archive():
    """Return all posts in the Substack archive (list of dicts; no body_html)."""
    posts, offset = [], 0
    while True:
        url = f"{SUBSTACK}/api/v1/archive?sort=new&search=&offset={offset}&limit=50"
        req = urllib.request.Request(url, headers=UA)
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        if not data:
            break
        posts.extend(data)
        if len(data) < 50:
            break
        offset += 50
        time.sleep(0.4)
    return posts


def fetch_post_html(slug):
    """Return the full body_html for one post via the single-post API."""
    url = f"{SUBSTACK}/api/v1/posts/{slug}"
    req = urllib.request.Request(url, headers=UA)
    detail = json.loads(urllib.request.urlopen(req, timeout=30).read())
    return detail.get("body_html", ""), detail.get("audience", "")


# --------------------------------------------------------------------------
# Clean Substack chrome out of the body HTML
# --------------------------------------------------------------------------

def strip_substack_chrome(html):
    """Remove subscribe widgets, share buttons, comment CTAs, paywall divs.

    Conservative: only removes known Substack UI blocks, leaves editorial
    content (text, images, links, headings) untouched.
    """
    patterns = [
        # subscription / subscribe-widget blocks
        r'<div class="subscription-widget[^"]*"[^>]*>.*?</div>\s*',
        r'<div class="subscribe-widget[^>]*>.*?</div>\s*',
        r'<p class="button-wrapper"[^>]*>.*?</p>\s*',
        # share / comment / like footers
        r'<div class="post-ufi[^"]*"[^>]*>.*?</div>\s*',
        r'<div class="[^"]*share[^"]*"[^>]*>.*?</div>\s*',
        # "Leave a comment" / "Share this post" CTA anchors
        r'<p[^>]*>\s*<a[^>]*comment[^>]*>.*?</a>\s*</p>\s*',
        # paywall / gift markers
        r'<div class="paywall[^"]*"[^>]*>.*?</div>\s*',
        # captioned-button blocks (Substack "Subscribe now" buttons)
        r'<div class="captioned-button-wrapper"[^>]*>.*?</div>\s*',
    ]
    out = html
    for p in patterns:
        out = re.sub(p, "", out, flags=re.S | re.I)
    # collapse leftover empty paragraphs
    out = re.sub(r'<p>\s*(&nbsp;)?\s*</p>', "", out)
    return out.strip()


# --------------------------------------------------------------------------
# Categorize -> tag
# --------------------------------------------------------------------------

def tag_for(title):
    t = title.lower()
    if "squid drop" in t:
        return "monthly-drop"
    if re.search(r"\bsdp-?\d|dao reconstruction|debt recovery", t):
        return "governance"
    return "leviathan-updates"


def should_skip(title):
    t = title.lower()
    return any(re.search(p, t) for p in SKIP_TITLE_PATTERNS)


# --------------------------------------------------------------------------
# Ghost target
# --------------------------------------------------------------------------

def load_ghost_creds():
    url = os.getenv("GHOST_URL")
    key = os.getenv("GHOST_ADMIN_API_KEY")
    if not (url and key):
        envf = Path.home() / ".config/leviathan/ghost-new-box.env"
        if envf.exists():
            for line in envf.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k == "GHOST_URL" and not url:
                        url = v.strip()
                    if k == "GHOST_ADMIN_API_KEY" and not key:
                        key = v.strip()
    if not (url and key):
        sys.exit("ERROR: set GHOST_URL + GHOST_ADMIN_API_KEY (env or ghost-new-box.env)")
    return url.rstrip("/"), key


def ghost_token(key):
    kid, secret = key.split(":")
    def b64(b):
        return base64.urlsafe_b64encode(b).rstrip(b"=")
    now = int(time.time())
    head = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": kid}, separators=(",", ":")).encode())
    payload = b64(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}, separators=(",", ":")).encode())
    seg = head + b"." + payload
    sig = hmac.new(bytes.fromhex(secret), seg, hashlib.sha256).digest()
    return (seg + b"." + b64(sig)).decode()


def ghost_request(ghost_url, key, method, path, payload=None):
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        ghost_url + path, data=data, method=method,
        headers={"Authorization": f"Ghost {ghost_token(key)}", "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=40).read())


def ghost_slug_exists(ghost_url, key, slug):
    try:
        r = ghost_request(ghost_url, key, "GET", f"/ghost/api/admin/posts/slug/{slug}/")
        return bool(r.get("posts"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def ghost_create(ghost_url, key, title, slug, html, published_at, tag, feature_image=None):
    post = {
        "title": title,
        "slug": slug,
        "html": html,
        "status": "published",
        "published_at": published_at,
        # Reference the EXISTING tag by SLUG, not name. Ghost matches incoming
        # tags by name; the live tags have display names ("Monthly Drop") that
        # differ from their slugs ("monthly-drop"), so passing {"name": slug}
        # creates a DUPLICATE tag (monthly-drop-2). Slug-keyed attach reuses it.
        "tags": [{"slug": tag}],
        # NO newsletter/email_segment params -> silent publish, no email.
    }
    # Substack's cover_image -> Ghost feature_image (the homepage-card thumbnail).
    # Without this the post still has body images but the homepage card is bare.
    if feature_image:
        post["feature_image"] = feature_image
    payload = {"posts": [post]}
    # ?source=html -> Ghost converts html field to lexical
    r = ghost_request(ghost_url, key, "POST", "/ghost/api/admin/posts/?source=html", payload)
    return r["posts"][0]


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true", default=False)
    ap.add_argument("--only", metavar="SLUG", help="migrate just this one slug")
    args = ap.parse_args()
    dry = not args.apply

    print("Fetching Substack archive…")
    archive = fetch_archive()
    print(f"  {len(archive)} posts in archive\n")

    # Build the migration list
    targets = []
    for p in archive:
        title = (p.get("title") or "").strip()
        slug = p.get("slug")
        if not slug:
            continue
        if args.only and slug != args.only:
            continue
        if should_skip(title):
            continue
        targets.append({
            "title": title,
            "slug": slug,
            "published_at": p.get("post_date"),
            "tag": tag_for(title),
            "feature_image": p.get("cover_image"),
        })

    by_tag = {}
    for t in targets:
        by_tag.setdefault(t["tag"], []).append(t)
    print(f"{'DRY RUN — ' if dry else ''}{len(targets)} post(s) to migrate "
          f"({', '.join(f'{k}:{len(v)}' for k, v in by_tag.items())})\n")

    ghost_url = key = None
    if not dry:
        ghost_url, key = load_ghost_creds()
        print(f"Ghost: {ghost_url}\n")

    created = skipped = errors = 0
    for i, t in enumerate(sorted(targets, key=lambda x: x["published_at"] or ""), 1):
        title, slug, tag = t["title"], t["slug"], t["tag"]
        date = (t["published_at"] or "")[:10]
        print(f"[{i:2d}/{len(targets)}] {date}  [{tag}]  {title[:55]}")

        if dry:
            try:
                body, audience = fetch_post_html(slug)
                cleaned = strip_substack_chrome(body)
                print(f"          slug={slug}  body={len(body)}→{len(cleaned)} chars  audience={audience}")
            except Exception as e:
                print(f"          (preview fetch failed: {e})")
            created += 1
            time.sleep(0.3)
            continue

        # apply
        try:
            if ghost_slug_exists(ghost_url, key, slug):
                print(f"          SKIPPED — slug exists in Ghost")
                skipped += 1
                continue
            body, audience = fetch_post_html(slug)
            if not body:
                print(f"          ERROR — empty body from Substack")
                errors += 1
                continue
            cleaned = strip_substack_chrome(body)
            post = ghost_create(ghost_url, key, title, slug, cleaned,
                                t["published_at"], tag, feature_image=t.get("feature_image"))
            print(f"          CREATED  {post.get('url')}")
            created += 1
            time.sleep(0.5)
        except urllib.error.HTTPError as e:
            print(f"          ERROR {e.code}: {e.read().decode()[:160]}")
            errors += 1
        except Exception as e:
            print(f"          ERROR: {e}")
            errors += 1

    print("\n" + "=" * 60)
    if dry:
        print(f"DRY RUN: would migrate {created} posts. Run --apply to publish.")
    else:
        print(f"Created {created}, skipped {skipped} (exists), errors {errors}")
    print("=" * 60)


if __name__ == "__main__":
    main()
