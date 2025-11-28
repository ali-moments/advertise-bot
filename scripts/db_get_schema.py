#!/usr/bin/python3
import sqlite3
import sys

def get_schema(db_file):
    """Get complete schema from SQLite database file"""
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        print("=== DATABASE SCHEMA ===\n")
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            print(f"--- Table: {table_name} ---")
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            print("Columns:")
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, pk = col
                pk_str = " PRIMARY KEY" if pk else ""
                not_null_str = " NOT NULL" if not_null else ""
                default_str = f" DEFAULT {default_val}" if default_val else ""
                print(f"  {col_name} {col_type}{pk_str}{not_null_str}{default_str}")
            
            # Get indexes
            cursor.execute(f"PRAGMA index_list({table_name});")
            indexes = cursor.fetchall()
            
            if indexes:
                print("Indexes:")
                for idx in indexes:
                    idx_name = idx[1]
                    cursor.execute(f"PRAGMA index_info({idx_name});")
                    idx_info = cursor.fetchall()
                    idx_cols = [info[2] for info in idx_info]
                    print(f"  {idx_name} ({', '.join(idx_cols)})")
            
            print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python db_get_schema.py database.db")
        print("Example: python db_get_schema.py data.db")
        sys.exit(1)
    
    db_file = sys.argv[1]
    get_schema(db_file)

if __name__ == "__main__":
    main()