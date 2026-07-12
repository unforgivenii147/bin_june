#!/data/data/com.termux/files/usr/bin/env python
import sys
import sqlite3
import json
import base64
from pathlib import Path
from multiprocessing import Pool, cpu_count
from functools import partial


def serialize_value(v):
    """Convert bytes (BLOB) to base64 string, leave other types as-is"""
    if isinstance(v, (bytes, bytearray)):
        return {"__blob_base64": base64.b64encode(v).decode("ascii")}
    return v


def row_to_dict(row):
    """Convert sqlite3.Row to dict with serialized values"""
    try:
        return {k: serialize_value(row[k]) for k in row.keys()}
    except UnicodeDecodeError as e:
        # If a single row fails, encode problematic values as base64
        result = {}
        for k in row.keys():
            try:
                result[k] = serialize_value(row[k])
            except UnicodeDecodeError:
                # Fallback: encode as base64
                try:
                    result[k] = {
                        "__blob_base64": base64.b64encode(str(row[k]).encode("utf-8", errors="replace")).decode("ascii")
                    }
                except:
                    result[k] = {"__decode_error": "Could not process value"}
        return result


def fetch_table_data(args):
    """Fetch data from a single table (for parallel processing)"""
    db_path, table_name = args
    try:
        # First attempt: standard UTF-8
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Validate table exists
        cur.execute(f'PRAGMA table_info("{table_name}");')
        cols = cur.fetchall()
        if not cols:
            conn.close()
            return table_name, [], f"Table '{table_name}' has no columns"

        try:
            cur.execute(f'SELECT * FROM "{table_name}";')
            rows = [row_to_dict(row) for row in cur.fetchall()]
            conn.close()
            return table_name, rows, None
        except UnicodeDecodeError as decode_err:
            conn.close()

            # Second attempt: replace invalid UTF-8 bytes with hex encoding
            conn = sqlite3.connect(db_path)
            conn.text_factory = lambda x: x.decode("utf-8", errors="replace") if isinstance(x, bytes) else x
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            try:
                cur.execute(f'SELECT * FROM "{table_name}";')
                rows = [row_to_dict(row) for row in cur.fetchall()]
                conn.close()
                return table_name, rows, f"UTF-8 decoding errors replaced in '{table_name}'"
            except Exception as e2:
                conn.close()

                # Third attempt: fetch as BLOB and encode to base64
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                try:
                    cur.execute(f'SELECT * FROM "{table_name}";')
                    rows = []
                    for row in cur.fetchall():
                        row_dict = {}
                        for k in row.keys():
                            val = row[k]
                            if isinstance(val, bytes):
                                row_dict[k] = {"__blob_base64": base64.b64encode(val).decode("ascii")}
                            elif isinstance(val, str):
                                # Try to encode as UTF-8, if fails encode the whole string as base64
                                try:
                                    val.encode("utf-8")
                                    row_dict[k] = val
                                except UnicodeEncodeError:
                                    row_dict[k] = {
                                        "__blob_base64": base64.b64encode(
                                            val.encode("utf-8", errors="surrogateescape")
                                        ).decode("ascii")
                                    }
                            else:
                                row_dict[k] = val
                        rows.append(row_dict)
                    conn.close()
                    return table_name, rows, f"Table '{table_name}' had encoding issues; binary data base64-encoded"
                except Exception as e3:
                    conn.close()
                    return table_name, [], f"Error processing table '{table_name}': {str(e3)}"

    except Exception as e:
        return table_name, [], f"Error processing table '{table_name}': {str(e)}"


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_sqlite_to_json.py <sqlite-file>")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    if not db_path.is_file():
        print(f"File not found: {db_path}")
        sys.exit(1)

    out_path = db_path.with_suffix(db_path.suffix + ".json")

    # Get list of user tables
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        print(f"Error reading database: {e}")
        sys.exit(1)

    if not tables:
        print("No tables found in database")
        sys.exit(1)

    # Process tables in parallel
    num_processes = min(cpu_count(), len(tables))
    print(f"Processing {len(tables)} tables using {num_processes} processes...")

    with Pool(processes=num_processes) as pool:
        results = pool.map(fetch_table_data, [(db_path, table) for table in tables])

    # Compile output and collect warnings
    output = {}
    warnings = []

    for table_name, rows, warning in results:
        output[table_name] = rows
        if warning:
            warnings.append(warning)

    # Write JSON with UTF-8 error handling
    try:
        with open(out_path, "w", encoding="utf-8", errors="replace") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        print(f"✓ Wrote {len(tables)} tables to {out_path}")
    except Exception as e:
        print(f"Error writing JSON: {e}")
        sys.exit(1)

    # Print any warnings
    if warnings:
        print("\n⚠ Warnings:")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()
