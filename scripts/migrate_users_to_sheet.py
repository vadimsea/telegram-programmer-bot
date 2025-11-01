"""One-off utility to upload existing users.json data into Google Sheets."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from database import DEFAULT_DB_FILE, UserDatabase  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload a local users.json snapshot into the configured storage backend (Google Sheets or JSON)."
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_DB_FILE,
        help="Path to the users.json file to import (default: users.json)",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        raise SystemExit(f"Source file {source_path} does not exist.")

    print(f"Loading user data from {source_path} ...")
    with source_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise SystemExit("Invalid JSON structure: expected an object mapping user IDs to records.")

    db = UserDatabase()
    db.users_data = {str(k): v for k, v in data.items()}
    db._save_data()
    print(f"Uploaded {len(db.users_data)} users to {('Google Sheets' if db._use_sheets else db.db_file)}")


if __name__ == "__main__":
    required_env = ["GOOGLE_SHEETS_CREDENTIALS", "GOOGLE_SHEETS_SPREADSHEET"]
    missing = [name for name in required_env if not os.getenv(name)]
    if missing:
        print(f"Warning: missing env vars {missing}. The script will fall back to local JSON if Sheets is not configured.")
    main()
