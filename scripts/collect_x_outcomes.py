#!/usr/bin/env python3
"""Collect or report bounded digest-link experiment outcomes."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.x.outcomes import collect, collection_lock, due_digests, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="perform paid X reads and persist snapshots")
    parser.add_argument("--max-digests", type=int, default=2)
    parser.add_argument("--report", action="store_true", help="print the aggregate report without X I/O")
    args = parser.parse_args()
    if not 1 <= args.max_digests <= 7:
        parser.error("--max-digests must be between 1 and 7")
    if args.report:
        print(json.dumps(report(), indent=2, sort_keys=True))
        return
    now = datetime.now(timezone.utc)
    due = due_digests(now, max_digests=args.max_digests)
    if not args.execute:
        print(json.dumps([
            {"date": row.day.date().isoformat(), "age_hours": round(row.age_hours, 3)} for row in due
        ], indent=2))
        return
    from squid_digest.x import XClient
    with collection_lock():
        results = collect(XClient(), now, max_digests=args.max_digests)
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
