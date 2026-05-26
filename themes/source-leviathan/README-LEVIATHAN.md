# source-leviathan

A minimal fork of Ghost's official **Source** theme that customizes the
homepage layout for [digest.leviathannews.xyz](https://digest.leviathannews.xyz).

## What's customized

Only **two files** differ from upstream Source `v1.6.1`:

| File | Change |
|---|---|
| `home.hbs` | Replaces the default paginated post-list with three curated sections: latest Daily Digest → 3 Recent Updates → latest Monthly $SQUID Drop. Each section uses Source's native `gh-container is-grid` wrapper so it inherits the theme's typography, spacing, and grid behavior. |
| `package.json` | Identity renamed `source-leviathan`; version `1.6.1-leviathan.<N>`; description updated. |

Every other file is byte-identical to `TryGhost/Source@v1.6.1`. `index.hbs`,
`post.hbs`, `tag.hbs`, `author.hbs`, partials, locales, prebuilt assets —
untouched. So all tag/author/post pages behave exactly like stock Source.

## How the homepage sections work

`home.hbs` uses three `{{#get "posts" filter=... limit=... order=...}}` blocks:

1. **Latest Daily Digest** — `tag:digest+status:published`, limit 1
2. **Recent Updates** — `tag:leviathan-updates+tag:-monthly-drop+status:published`, limit 3
3. **Latest Monthly Drop** — `tag:monthly-drop+status:published`, limit 1

These queries run server-side in Ghost at every page render; the page is
always fresh. Posts must be tagged appropriately in Ghost admin for them
to appear.

## How to update

1. Edit `home.hbs` (or whichever file).
2. Bump the patch revision in `package.json` (e.g. `1.6.1-leviathan.2` → `1.6.1-leviathan.3`).
3. **Validate against your Ghost version's gscan**:
   ```
   cd themes/source-leviathan
   npx --yes gscan@latest --v5 .          # for Ghost 5.x — current production
   npx --yes gscan@latest --v5 --fatal .  # extra strict
   ```
   Both must pass with `✓ Your theme is compatible with Ghost 5.x`.
   **⚠️ Important:** gscan's default is `--v6`. Production Ghost is 5.129
   as of 2026-05-26. Always explicitly pass `--v5` until production
   upgrades; otherwise you'll validate against the wrong target and ship
   a theme that fails upload (this happened once — see git log).
4. Package the zip with contents at root (not in a wrapper folder):
   ```
   cd themes/source-leviathan
   zip -qr ../source-leviathan.zip . -x ".*" "*.DS_Store" "node_modules/*"
   ```
5. Upload via Ghost admin: **Settings → Theme → Upload theme** → drag the zip → Activate.
6. Verify the live homepage (a `curl https://digest.leviathannews.xyz/`
   should contain the three section emoji headers `📰`, `⚓`, `🦑`).

## Reverting

In Ghost admin → Settings → Theme: the original Source theme stays
installed alongside this one. Click **Activate** on Source to revert
instantly. No reupload needed.

## Upstream sync

If TryGhost/Source ships a new tagged release worth picking up:

```
git clone https://github.com/TryGhost/Source upstream
cd upstream && git checkout vX.Y.Z
# port our home.hbs + package.json changes onto upstream's tree
# (only home.hbs is non-trivial; the diff against upstream/home.hbs is
#  small and additive)
```

**Do NOT clone with `--depth 1` and use master.** Master can contain
unreleased helpers (e.g. `social_accounts` was added to master before
any v6 release and tripped a "missing helper" error on Ghost 5.x; this
happened once — see git log). Always pin to a released tag.
