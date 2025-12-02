"""Scan writeup directory for digest markdown files."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import re


class DigestFile:
    """Represents a digest markdown file."""

    def __init__(self, path: Path, date: datetime):
        """
        Initialize DigestFile.

        Args:
            path: Path to the markdown file
            date: Publication date parsed from filename
        """
        self.path = path
        self.date = date
        self._content: Optional[str] = None

    def load_content(self) -> str:
        """
        Load markdown content from file.

        Returns:
            Markdown content as string
        """
        if self._content is None:
            self._content = self.path.read_text(encoding='utf-8')
        return self._content

    def __repr__(self) -> str:
        return f"DigestFile(path={self.path.name}, date={self.date.strftime('%Y-%m-%d')})"


class DigestScanner:
    """Scan writeup directory for digest markdown files."""

    def __init__(self, writeup_dir: Path):
        """
        Initialize scanner.

        Args:
            writeup_dir: Path to writeup directory (e.g., Path("writeup"))
        """
        self.writeup_dir = Path(writeup_dir)

    def scan(
        self,
        limit: Optional[int] = 30,
        file_pattern: str = "signals_*.md",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[DigestFile]:
        """
        Scan writeup directory for digest files.

        Args:
            limit: Maximum number of files to return (newest first). None = unlimited
            file_pattern: Glob pattern for matching files (signals_*.md, digest_*.md, or *.md)
            start_date: Only include files after this date (optional)
            end_date: Only include files before this date (optional)

        Returns:
            List of DigestFile objects, sorted by date (newest first)
        """
        digest_files = []

        # Walk through YYYY/MM/DD structure in reverse chronological order
        for year_dir in sorted(self.writeup_dir.glob("[0-9][0-9][0-9][0-9]"), reverse=True):
            if not year_dir.is_dir():
                continue

            for month_dir in sorted(year_dir.glob("[0-9][0-9]"), reverse=True):
                if not month_dir.is_dir():
                    continue

                for day_dir in sorted(month_dir.glob("[0-9][0-9]"), reverse=True):
                    if not day_dir.is_dir():
                        continue

                    # Find matching files in this day
                    for md_file in day_dir.glob(file_pattern):
                        if not md_file.is_file():
                            continue

                        # Extract date from filename
                        date = self._parse_date_from_filename(md_file)
                        if not date:
                            continue

                        # Check date filters
                        if start_date and date < start_date:
                            continue
                        if end_date and date > end_date:
                            continue

                        digest_files.append(DigestFile(md_file, date))

                        # Early exit if we hit limit
                        if limit and len(digest_files) >= limit:
                            return digest_files

        # Sort by date (newest first) and apply limit
        digest_files.sort(key=lambda d: d.date, reverse=True)
        return digest_files[:limit] if limit else digest_files

    def _parse_date_from_filename(self, file_path: Path) -> Optional[datetime]:
        """
        Parse date from filename.

        Supports formats:
        - signals_YYYY-MM-DD.md
        - digest_YYYY-MM-DD.md

        Args:
            file_path: Path to markdown file

        Returns:
            Parsed datetime or None if parsing fails
        """
        # Pattern: signals_2025-11-29.md or digest_2025-11-29.md
        match = re.search(r'(signals|digest)_(\d{4})-(\d{2})-(\d{2})\.md', file_path.name)
        if match:
            year = int(match.group(2))
            month = int(match.group(3))
            day = int(match.group(4))
            try:
                return datetime(year, month, day)
            except ValueError:
                # Invalid date (e.g., February 30)
                return None
        return None
