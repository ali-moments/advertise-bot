#!/usr/bin/python
import sqlite3
import os
import sys

def quick_merge_skip_duplicates(db1, db2, output):
    """Quick merge that skips duplicate accounts based on 'number' field"""
    if not os.path.exists(db1):
        print(f"❌ Error: {db1} not found!")
        return False
    if not os.path.exists(db2):
        print(f"❌ Error: {db2} not found!")
        return False
    if os.path.exists(output):
        response = input(f"⚠️  {output} exists. Overwrite? (y/n): ").lower()
        if response != 'y':
            return False
        os.remove(output)
    
    try:
        conn1 = sqlite3.connect(db1)
        conn2 = sqlite3.connect(db2)
        conn_out = sqlite3.connect(output)
        
        c1, c2, cout = conn1.cursor(), conn2.cursor(), conn_out.cursor()
        
        # Get all tables
        c1.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [t[0] for t in c1.fetchall()]
        
        print(f"🔄 Merging {len(tables)} tables: {', '.join(tables)}")
        
        for table in tables:
            # Create table
            c1.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
            cout.execute(c1.fetchone()[0])
            
            if table == "accounts":
                # Special handling for accounts - skip duplicates based on 'number'
                merge_accounts_quick(c1, c2, cout)
            else:
                # Normal copy for other tables
                copy_table_quick(c1, c2, cout, table)
        
        conn_out.commit()
        conn1.close()
        conn2.close()
        conn_out.close()
        
        # Show final counts
        conn_out = sqlite3.connect(output)
        cout = conn_out.cursor()
        cout.execute("SELECT COUNT(*) FROM accounts;")
        count = cout.fetchone()[0]
        conn_out.close()
        
        print(f"\n🎉 SUCCESS: Merged {count} unique accounts into: {output}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def merge_accounts_quick(c1, c2, cout):
    """Quick merge accounts skipping duplicates"""
    # Get column info
    c1.execute("PRAGMA table_info(accounts)")
    columns = [col[1] for col in c1.fetchall()]
    
    # Create insert without id (let it auto-increment)
    insert_cols = [col for col in columns if col != 'id']
    insert_str = ", ".join(insert_cols)
    placeholders = ", ".join(["?" for _ in insert_cols])
    
    existing_numbers = set()
    total_added = 0
    
    # Process both databases
    for cursor, db_name in [(c1, "DB1"), (c2, "DB2")]:
        cursor.execute("SELECT * FROM accounts")
        rows = cursor.fetchall()
        added = 0
        skipped = 0
        
        for row in rows:
            # Find number value (assuming it's the second column based on your schema)
            number_value = row[1]  # row[0] is id, row[1] is number
            
            if number_value not in existing_numbers:
                # Create row without id
                insert_row = [row[i] for i, col in enumerate(columns) if col != 'id']
                cout.execute(f"INSERT INTO accounts ({insert_str}) VALUES ({placeholders})", insert_row)
                existing_numbers.add(number_value)
                added += 1
            else:
                skipped += 1
        
        print(f"   ✅ {added} accounts from {db_name} ({skipped} duplicates skipped)")
        total_added += added

def copy_table_quick(c1, c2, cout, table):
    """Quick copy for non-accounts tables"""
    for cursor, db_name in [(c1, "DB1"), (c2, "DB2")]:
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        if rows:
            # Get column count for placeholders
            placeholders = ",".join(["?" for _ in range(len(rows[0]))])
            cout.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
        print(f"   ✅ {len(rows)} rows from {db_name} for {table}")

def main():
    if len(sys.argv) != 4:
        print("🚀 SQLite Database Merger - Duplicate Account Handler")
        print("Usage: python merge_db.py db1.db db2.db output.db")
        print("Example: python merge_db.py data.db data2.db merged.db")
        sys.exit(1)
    
    db1, db2, output = sys.argv[1], sys.argv[2], sys.argv[3]
    success = quick_merge_skip_duplicates(db1, db2, output)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
