#!/data/data/com.termux/files/usr/bin/python

import multiprocessing as mp
import sys
import time
import zipfile
from pathlib import Path


def attempt_password2(args):
    zip_file_path, password_candidate = args
    try:
        with AESZipFile(zip_file_path, "r") as zf:
            zf.setpassword(password_candidate.encode("utf-8"))
            zf.testzip()
            return password_candidate
    except RuntimeError as e:
        if "Bad password" in str(e) or "Incorrect password" in str(e):
            return None
        return None
    except Exception as e:
        return None


def attempt_password(args):
    zip_file_path, password_candidate = args
    zip_file_path = Path(zip_file_path)
    try:
        with zipfile.ZipFile(zip_file_path, "r") as zf:
            zf.testzip()
            return password_candidate
    except RuntimeError as e:
        if "Incorrect password" in str(e):
            return None
        return None
    except Exception as e:
        return None


def crack_zip_password_multiprocess(zip_file_path: Path, password_list_path: Path, extract_dir="extracted_files"):
    if not Path(zip_file_path).exists():
        return None
    if not Path(password_list_path).exists():
        return None
    try:
        with Path(password_list_path).open(encoding="utf-8", errors="ignore") as p_list:
            passwords = [p.strip() for p in p_list if p.strip()]
        total_passwords = len(passwords)
        start_time = time.time()
        tasks = [(zip_file_path, p) for p in passwords]
        num_processes = mp.cpu_count()
        with mp.Pool(num_processes) as pool:
            results = pool.imap_unordered(attempt_password, tasks, chunksize=100)
            found_password = None
            for i, result in enumerate(results):
                if result:
                    found_password = result
                    break
                (i + 1) % 1000 == 0 or i + 1 == total_passwords
            pool.terminate()
            pool.join()
        end_time = time.time()
        elapsed_time = end_time - start_time
        if found_password:
            try:
                Path(extract_dir).mkdir(exist_ok=True, parents=True)
                with zipfile.ZipFile(zip_file_path, "r") as zf_final:
                    zf_final.extractall(path=extract_dir, pwd=found_password.encode("utf-8"))
            except Exception as e:
                pass
            return found_password
        return None
    except Exception as e:
        return None


if __name__ == "__main__":
    zip_file = Path(sys.argv[1])
    pass_file = Path.home() / "isaac" / "wordlist.txt"
    found_password_mp = crack_zip_password_multiprocess(zip_file, pass_file)
    if found_password_mp:
        print(f"\npassword: {found_password_mp}")
    else:
        print("\nnot found.")
