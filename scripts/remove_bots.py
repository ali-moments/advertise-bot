#!/usr/bin/env python3
"""Remove users whose username.lower().endswith('bot') from CSV files.

Usage examples:
  python3 scripts/remove_bots.py data/members_None_20251124_004631.csv
  python3 scripts/remove_bots.py data/*.csv --inplace
  python3 scripts/remove_bots.py data/members_*.csv --dry-run

The script preserves the CSV header and writes cleaned files with suffix
`_cleaned.csv` by default, or overwrites the original file when `--inplace`
is provided (a timestamped backup is created).
"""
import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path
import sys


def clean_file(path: Path, inplace: bool = False, dry_run: bool = False) -> int:
    path = path.expanduser()
    if not path.exists():
        print(f"Skipping missing file: {path}")
        return 0

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print(f"No header found in {path}, skipping.")
            return 0
        kept_rows = []
        removed = 0
        for row in reader:
            username = (row.get("username") or "").strip()
            if username.lower().endswith("bot") and username != "":
                removed += 1
                continue
            kept_rows.append(row)

    if dry_run:
        print(f"{path}: would remove {removed} rows (dry-run).")
        return removed

    if inplace:
        # backup original
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_suffix(path.suffix + f".bak.{ts}")
        shutil.copy2(path, backup)
        out_path = path
    else:
        out_path = path.with_name(path.stem + "_cleaned" + path.suffix)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in kept_rows:
            writer.writerow(r)

    print(f"{path}: removed={removed}, wrote {out_path}")
    return removed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Remove users whose username ends with 'bot' from CSV files.")
    parser.add_argument("paths", nargs="+", help="One or more CSV files or glob patterns")
    parser.add_argument("--inplace", action="store_true", help="Overwrite original files (creates timestamped .bak) ")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files; just report how many rows would be removed")
    args = parser.parse_args(argv)

    total_removed = 0
    files_processed = 0
    for pattern in args.paths:
        for p in sorted(Path().glob(pattern)):
            if p.is_file():
                try:
                    removed = clean_file(p, inplace=args.inplace, dry_run=args.dry_run)
                    total_removed += removed
                    files_processed += 1
                except Exception as e:
                    print(f"Error processing {p}: {e}", file=sys.stderr)

    if files_processed == 0:
        print("No files processed. Did you pass a glob pattern or file path?", file=sys.stderr)
        return 2

    print(f"Processed {files_processed} file(s). Total removed: {total_removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
