#!/usr/bin/python3

import sqlite3
import os
import csv
import sys
from pathlib import Path

def check_sessions_and_clean_db(db_path, sessions_dir, corrupted_csv_path):
    """
    Check session files against database and remove accounts with missing/corrupted sessions
    """

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False

    sessions_path = Path(sessions_dir)
    if not sessions_path.exists():
        print(f"❌ Sessions directory not found: {sessions_dir}")
        return False

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🔍 Checking session files against database...")

        # Get all accounts from database
        cursor.execute("SELECT id, number, proxy, session_string, password, user_id FROM accounts;")
        accounts = cursor.fetchall()

        print(f"📊 Total accounts in database: {len(accounts)}")

        # Track accounts to keep and remove
        accounts_to_keep = []
        accounts_to_remove = []

        # Check each account
        for account in accounts:
            account_id, number, proxy, session_string, password, user_id = account
            session_file = sessions_path / f"{number}.session"

            if not session_file.exists():
                # Session file doesn't exist
                print(f"❌ Missing: {number}.session")
                accounts_to_remove.append(account + ('missing',))
            else:
                # Check if session file is not empty
                if session_file.stat().st_size == 0:
                    print(f"⚠️  Empty: {number}.session")
                    accounts_to_remove.append(account + ('empty',))
                else:
                    print(f"✅ Valid: {number}.session")
                    accounts_to_keep.append(account)

        print(f"\n📊 RESULTS:")
        print(f"✅ Valid accounts: {len(accounts_to_keep)}")
        print(f"❌ Problematic accounts: {len(accounts_to_remove)}")

        # Save corrupted accounts to CSV
        if accounts_to_remove:
            with open(corrupted_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['id', 'number', 'proxy', 'session_string', 'password', 'user_id', 'issue'])
                writer.writerows(accounts_to_remove)
            print(f"📄 Saved problematic accounts to: {corrupted_csv_path}")

            # Remove problematic accounts from database
            numbers_to_remove = [account[1] for account in accounts_to_remove]
            placeholders = ','.join(['?' for _ in numbers_to_remove])
            cursor.execute(f"DELETE FROM accounts WHERE number IN ({placeholders})", numbers_to_remove)
            conn.commit()
            print(f"🗑️  Removed {len(accounts_to_remove)} accounts from database")
        else:
            print("✅ No problematic accounts found!")

        # Show final count
        cursor.execute("SELECT COUNT(*) FROM accounts;")
        remaining = cursor.fetchone()[0]
        print(f"📊 Remaining accounts: {remaining}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    if len(sys.argv) != 4:
        print("Usage: python db_check_sessions.py database.db sessions_dir corrupted.csv")
        print("Example: python db_check_sessions.py data.db sessions corrupted.csv")
        sys.exit(1)

    db_path = sys.argv[1]
    sessions_dir = sys.argv[2]
    corrupted_csv = sys.argv[3]

    success = check_sessions_and_clean_db(db_path, sessions_dir, corrupted_csv)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
