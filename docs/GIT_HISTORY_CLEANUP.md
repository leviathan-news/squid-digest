# Git History Cleanup Instructions 🏴‍☠️

## Overview

This repository's git history contains a temporary key recovery script (commit `03e376a640f147ffde0a53f9348702cdee336bcc`) that should be removed before making the repo public. While the script itself doesn't contain secrets, it demonstrates a pattern that could be concerning.

## Files to Remove from History

- `.github/workflows/recover-key.yml`
- `temp_recover_key.py`

## Option 1: Using BFG Repo Cleaner (Recommended)

BFG Repo Cleaner is faster and easier than `git filter-branch`.

### Step 1: Install BFG

**macOS (via Homebrew):**
```bash
brew install bfg
```

**Manual installation:**
```bash
# Download latest release
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar
# Or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Create alias (add to ~/.zshrc or ~/.bashrc)
alias bfg='java -jar /path/to/bfg-1.14.0.jar'
```

### Step 2: Create a Fresh Clone

```bash
# Clone a fresh mirror of the repository
cd /tmp
git clone --mirror https://github.com/YOUR_USERNAME/squid-digest.git squid-digest-mirror.git
cd squid-digest-mirror.git
```

### Step 3: Delete Files from History

```bash
# Remove the recovery script files from all commits
bfg --delete-files recover-key.yml
bfg --delete-files temp_recover_key.py
```

### Step 4: Clean Up and Verify

```bash
# Clean up the repository
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Verify the files are gone
git log --all --oneline -- .github/workflows/recover-key.yml
git log --all --oneline -- temp_recover_key.py
# These should return nothing
```

### Step 5: Push the Cleaned History

⚠️ **WARNING**: This will **force-push** and rewrite history. Make sure you have a backup!

```bash
# Push the cleaned history
git push --force

# Alternatively, push to a new branch first to verify
git push origin --all --force
```

### Step 6: Update Your Local Repository

```bash
# Go back to your working directory
cd /Users/gerrithall/dev/leviathan/squid-digest

# Fetch the cleaned history
git fetch origin

# Reset your local main to match
git reset --hard origin/main

# Clean up local refs
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## Option 2: Using git filter-repo

`git filter-repo` is a modern alternative to `filter-branch`.

### Install

```bash
pip install git-filter-repo
```

### Clean History

```bash
# Create a fresh clone
cd /tmp
git clone https://github.com/YOUR_USERNAME/squid-digest.git squid-digest-clean
cd squid-digest-clean

# Remove specific files
git filter-repo --path .github/workflows/recover-key.yml --invert-paths
git filter-repo --path temp_recover_key.py --invert-paths

# Push
git push origin --force --all
```

## Option 3: Manual with git filter-branch (Not Recommended)

Only use if BFG and filter-repo are unavailable.

```bash
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .github/workflows/recover-key.yml temp_recover_key.py" \
  --prune-empty --tag-name-filter cat -- --all

git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force --all
```

## After Cleanup

1. **Verify on GitHub**: Check the commit history on GitHub to ensure the files are gone
2. **Update team members**: If others have clones, they'll need to re-clone or fetch/reset
3. **Check Actions**: Verify GitHub Actions still work after the history rewrite

## What If I Don't Want to Rewrite History?

If rewriting history is too risky or complex, you can document the situation instead:

1. Add a note in SECURITY.md (already done ✅)
2. Mention in README that git history contains artifacts
3. Ensure all keys have been rotated (critical!)

The transparency approach is valid since:
- No actual secrets were in the commit
- All keys have been rotated
- The script was explicitly marked as temporary
- This demonstrates good security practices going forward

## Need Help?

If you run into issues:
1. Create a backup branch first: `git branch backup-before-cleanup`
2. Test on a separate clone before touching your main repo
3. If something goes wrong, you can always restore from the backup

---

**Remember**: Git history rewrites are irreversible. Always backup first! 🦑🏴‍☠️
