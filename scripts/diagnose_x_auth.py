#!/usr/bin/env python3
"""Run a bounded, non-posting X OAuth diagnostic.

The command calls only ``GET /2/users/me``.  It does not create, reply to,
search for, like, or delete a post.  Its JSON output is deliberately limited
to a public account identity or a redacted provider error projection.
"""

import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.x import XClient


def main() -> int:
    try:
        diagnostic = XClient().diagnose_authenticated_user()
    except ValueError as exc:
        diagnostic = {"ok": False, "operation": "get_authenticated_user", "failure_class": type(exc).__name__}

    print(json.dumps(diagnostic, sort_keys=True))
    return 0 if diagnostic["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
