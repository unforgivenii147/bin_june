#!/data/data/com.termux/files/usr/bin/python
import multiprocessing
import os
import sys
import threading
import time
import zipfile
from itertools import islice


class StatusReporter:
    """
    Handles periodic status reporting during brute force attack.
    """

    def __init__(self, total_passwords, start_time, update_interval=60):
        self.total_passwords = total_passwords
        self.start_time = start_time
        self.update_interval = update_interval
        self.passwords_tested = 0
        self.last_update_time = start_time
        self.running = True
        self.password_found = False
        self.found_password = None
        self.lock = threading.Lock()

    def update(self, count=1):
        """Update the number of passwords tested."""
        with self.lock:
            self.passwords_tested += count

    def report_status(self):
        """Report current status periodically."""
        while self.running:
            time.sleep(self.update_interval)
            with self.lock:
                if not self.running or self.password_found:
                    break

                current_time = time.time()
                elapsed = current_time - self.start_time

                # Calculate passwords per second
                if elapsed > 0:
                    pps = self.passwords_tested / elapsed
                else:
                    pps = 0

                # Calculate remaining passwords
                remaining = self.total_passwords - self.passwords_tested

                # Estimate time remaining
                if pps > 0:
                    eta_seconds = remaining / pps
                    eta = self.format_time(eta_seconds)
                else:
                    eta = "Unknown"

                # Calculate progress percentage
                progress = (self.passwords_tested / self.total_passwords) * 100 if self.total_passwords > 0 else 0

                # Print status
                print(f"\n{'=' * 60}")
                print(f"STATUS UPDATE - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'=' * 60}")
                print(f"📊 Progress:     {progress:.2f}%")
                print(f"🔑 Tested:       {self.passwords_tested:,} passwords")
                print(f"⏳ Remaining:    {remaining:,} passwords")
                print(f"⚡ Speed:        {pps:.1f} pwd/sec")
                print(f"⏱️  Elapsed:      {self.format_time(elapsed)}")
                print(f"⏰ ETA:          {eta}")
                print(f"{'=' * 60}\n")

                self.last_update_time = current_time

    def format_time(self, seconds):
        """Format seconds into human-readable time."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def stop(self, password=None):
        """Stop the status reporter."""
        with self.lock:
            self.running = False
            if password:
                self.password_found = True
                self.found_password = password

    def final_report(self, success=False):
        """Print final report."""
        elapsed = time.time() - self.start_time

        print(f"\n{'=' * 60}")
        print("FINAL REPORT")
        print(f"{'=' * 60}")
        print(f"✅ Success:       {'Yes' if success else 'No'}")
        if success:
            print(f"🔑 Password:      {self.found_password}")
        print(f"🔢 Total tested:  {self.passwords_tested:,} passwords")
        print(f"⏱️  Total time:    {self.format_time(elapsed)}")
        if elapsed > 0 and self.passwords_tested > 0:
            print(f"⚡ Avg speed:     {self.passwords_tested / elapsed:.1f} pwd/sec")
        print(f"{'=' * 60}\n")


def check_password(zip_file, password, status_reporter=None):
    """
    Attempt to extract the zip file with the given password.
    Returns password if successful, None otherwise.
    """
    try:
        with zipfile.ZipFile(zip_file, "r") as zf:
            zf.extractall(pwd=password.encode("utf-8"))
            return password
    except:
        return None


def worker(args):
    """
    Worker function for multiprocessing.
    Tests a batch of passwords.
    """
    zip_file, password_batch, status_reporter = args

    for password in password_batch:
        password = password.strip()
        if not password:
            continue

        result = check_password(zip_file, password)

        # Update status reporter if provided
        if status_reporter:
            status_reporter.update(1)

        if result:
            return result
    return None


def read_passwords_in_batches(wordlist_file, batch_size):
    """
    Read passwords from wordlist file in batches.
    """
    with open(wordlist_file, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            batch = list(islice(f, batch_size))
            if not batch:
                break
            yield batch


def count_passwords(wordlist_file):
    """
    Count total passwords in wordlist file efficiently.
    """
    count = 0
    try:
        with open(wordlist_file, "r", encoding="utf-8", errors="ignore") as f:
            for _ in f:
                count += 1
    except Exception as e:
        print(f"Error counting passwords: {e}")
        return 0
    return count


def brute_force_zip(zip_file, wordlist_file, num_processes=None, batch_size=1000, update_interval=60):
    """
    Main function to brute force a zip file using multiprocessing.
    """
    # Check if files exist
    if not os.path.exists(zip_file):
        print(f"❌ Error: Zip file '{zip_file}' not found!")
        return None

    if not os.path.exists(wordlist_file):
        print(f"❌ Error: Wordlist file '{wordlist_file}' not found!")
        return None

    # Validate zip file
    try:
        with zipfile.ZipFile(zip_file, "r") as zf:
            if not any(info.flag_bits & 0x1 for info in zf.infolist()):
                print("⚠️  Warning: Zip file is not password protected!")
                return None
    except zipfile.BadZipFile:
        print("❌ Error: Invalid zip file!")
        return None
    except Exception as e:
        print(f"❌ Error opening zip file: {e}")
        return None

    # Determine number of processes
    if num_processes is None:
        num_processes = multiprocessing.cpu_count()

    print(f"\n{'=' * 60}")
    print("ZIP BRUTE FORCE ATTACK")
    print(f"{'=' * 60}")
    print(f"📁 Target:      {zip_file}")
    print(f"📝 Wordlist:    {wordlist_file}")
    print(f"⚙️  Processes:   {num_processes}")
    print(f"📦 Batch size:  {batch_size}")
    print(f"⏱️  Update:      Every {update_interval} seconds")
    print(f"{'=' * 60}\n")

    # Count total passwords
    print("Counting passwords in wordlist...")
    total_passwords = count_passwords(wordlist_file)

    if total_passwords == 0:
        print("❌ Error: No passwords found in wordlist!")
        return None

    print(f"📊 Total passwords: {total_passwords:,}\n")

    # Initialize status reporter
    start_time = time.time()
    status_reporter = StatusReporter(total_passwords, start_time, update_interval)

    # Start status reporter thread
    reporter_thread = threading.Thread(target=status_reporter.report_status, daemon=True)
    reporter_thread.start()

    # Create a pool of workers
    pool = multiprocessing.Pool(processes=num_processes)

    # Create arguments for workers
    password_batches = read_passwords_in_batches(wordlist_file, batch_size)
    args = [(zip_file, batch, status_reporter) for batch in password_batches]

    # Process batches
    found_password = None
    try:
        for result in pool.imap_unordered(worker, args):
            if result:
                found_password = result
                status_reporter.stop(password=result)
                pool.terminate()
                pool.join()
                break
    except KeyboardInterrupt:
        print("\n⚠️  Brute force interrupted by user!")
        status_reporter.stop()
        pool.terminate()
        pool.join()
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        status_reporter.stop()
        pool.terminate()
        pool.join()
    finally:
        pool.close()
        pool.join()
        status_reporter.stop(found_password)
        reporter_thread.join(timeout=2)

    # Print final report
    status_reporter.final_report(success=bool(found_password))

    if found_password:
        print(f"🎉 Success! Password found: {found_password}")
        return found_password
    else:
        print("❌ Password not found in wordlist.")
        return None


def main():
    """
    Main execution function with command line arguments.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Brute force password protected zip files using multiprocessing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python zip_bruteforce.py protected.zip -w wordlist.txt
  python zip_bruteforce.py protected.zip -w wordlist.txt -p 4 -b 500 -i 30
        """,
    )
    parser.add_argument("zip_file", help="Path to the zip file")
    parser.add_argument(
        "-w",
        "--wordlist",
        default="wordlist.txt",
        help="Path to wordlist file (default: wordlist.txt)",
    )
    parser.add_argument(
        "-p",
        "--processes",
        type=int,
        default=None,
        help="Number of processes to use (default: CPU count)",
    )
    parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=1000,
        help="Number of passwords per batch (default: 1000)",
    )
    parser.add_argument(
        "-i",
        "--update-interval",
        type=int,
        default=60,
        help="Status update interval in seconds (default: 60)",
    )

    args = parser.parse_args()

    password = brute_force_zip(
        args.zip_file,
        args.wordlist,
        num_processes=args.processes,
        batch_size=args.batch_size,
        update_interval=args.update_interval,
    )

    sys.exit(0 if password else 1)


if __name__ == "__main__":
    main()
