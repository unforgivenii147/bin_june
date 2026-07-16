#!/data/data/com.termux/files/usr/bin/env python


import base64
import json
import sqlite3
import sys
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path


def serialize_value(v):
    if isinstance(v, (bytes, bytearray)):
        return {"__blob_base64": base64.b64encode(v).decode("ascii")}
    return v


def row_to_dict(row):
    try:
        return {k: serialize_value(row[k]) for k in row.keys()}
    except UnicodeDecodeError as e:
        result = {}
        for k in row.keys():
            try:
                result[k] = serialize_value(row[k])
            except UnicodeDecodeError:
                try:
                    result[k] = {
                        "__blob_base64": base64.b64encode(str(row[k]).encode("utf-8", errors="replace")).decode("ascii")
                    }
                except:
                    result[k] = {"__decode_error": "Could not process value"}
        return result


def fetch_table_data(args):
    db_path, table_name = args
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(f'PRAGMA table_info("{table_name}");')
        cols = cur.fetchall()
        if not cols:
            conn.close()
            return (table_name, [], f"Table '{table_name}' has no columns")
        try:
            cur.execute(f'SELECT * FROM "{table_name}";')
            rows = [row_to_dict(row) for row in cur.fetchall()]
            conn.close()
            return (table_name, rows, None)
        except UnicodeDecodeError as decode_err:
            conn.close()
            conn = sqlite3.connect(db_path)
            conn.text_factory = lambda x: x.decode("utf-8", errors="replace") if isinstance(x, bytes) else x
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            try:
                cur.execute(f'SELECT * FROM "{table_name}";')
                rows = [row_to_dict(row) for row in cur.fetchall()]
                conn.close()
                return (table_name, rows, f"UTF-8 decoding errors replaced in '{table_name}'")
            except Exception as e2:
                conn.close()
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
                    return (table_name, rows, f"Table '{table_name}' had encoding issues; binary data base64-encoded")
                except Exception as e3:
                    conn.close()
                    return (table_name, [], f"Error processing table '{table_name}': {str(e3)}")
    except Exception as e:
        return (table_name, [], f"Error processing table '{table_name}': {str(e)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_sqlite_to_json.py <sqlite-file>")
        sys.exit(1)
    db_path = Path(sys.argv[1])
    if not db_path.is_file():
        print(f"File not found: {db_path}")
        sys.exit(1)
    out_path = db_path.with_suffix(db_path.suffix + ".json")
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
    num_processes = min(cpu_count(), len(tables))
    print(f"Processing {len(tables)} tables using {num_processes} processes...")
    with Pool(processes=num_processes) as pool:
        results = pool.map(fetch_table_data, [(db_path, table) for table in tables])
    output = {}
    warnings = []
    for table_name, rows, warning in results:
        output[table_name] = rows
        if warning:
            warnings.append(warning)
    try:
        with open(out_path, "w", encoding="utf-8", errors="replace") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        print(f"✓ Wrote {len(tables)} tables to {out_path}")
    except Exception as e:
        print(f"Error writing JSON: {e}")
        sys.exit(1)
    if warnings:
        print("\n⚠ Warnings:")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()
