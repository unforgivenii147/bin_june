#!/data/data/com.termux/files/usr/bin/python

import os
import sqlite3
from pathlib import Path


def get_current_folder_name():
    return Path(Path.cwd()).name


def folder_exists_in_db(cursor, folder_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (folder_name,))
    return cursor.fetchone() is not None


def create_folder_table(cursor, folder_name):
    cursor.execute(
        f'\n        CREATE TABLE IF NOT EXISTS "{folder_name}" (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            filename TEXT NOT NULL,\n            file_contents TEXT\n        )\n    '
    )


def read_file_contents(filepath):
    try:
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
        for encoding in encodings:
            try:
                with Path(filepath).open(encoding=encoding) as f:
                    return f.read(1024 * 1024)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "[Binary file content not stored]"
    except PermissionError:
        return "[Permission denied - cannot read file]"
    except Exception as e:
        return f"[Error reading file: {e!s}]"


def get_files_in_cwd():
    cwd = Path.cwd()
    files = []
    try:
        for item in os.listdir(cwd):
            item_path = os.path.join(cwd, item)
            if Path(item_path).is_file():
                print(f"  Reading: {item}")
                contents = read_file_contents(item_path)
                files.append({"filename": item, "contents": contents})
    except PermissionError:
        print("Warning: Permission denied accessing some files")
    return files


def insert_files(cursor, folder_name, files):
    for file_info in files:
        cursor.execute(
            f'\n            INSERT INTO "{folder_name}" (filename,  file_contents)\n            VALUES (?, ?)\n        ',
            (file_info["filename"], file_info["contents"]),
        )


def main():
    db_path = "/sdcard/pkg.db"
    folder_name = get_current_folder_name()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if folder_exists_in_db(cursor, folder_name):
        folder_name = folder_name + "_new"
    create_folder_table(cursor, folder_name)
    files = get_files_in_cwd()
    if not files:
        print("No files found in current directory!")
    else:
        insert_files(cursor, folder_name, files)
        conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
