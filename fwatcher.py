#!/data/data/com.termux/files/usr/bin/python
import time
import os


def watch_tor_log(log_path: str = "~/.tor/tor.log") -> None:
    """Watch Tor log file and display last 5 lines, exit on 100% bootstrap"""

    # Expand user path (handles ~)
    log_path = os.path.expanduser(log_path)

    # Check if file exists
    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        print("Waiting for file to be created...")

    # Get initial last 5 lines if file exists
    last_position = 0

    try:
        # If file exists, show last 5 lines and get current size
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                lines = f.readlines()
                print("=== Last 5 lines of Tor log ===")
                for line in lines[-5:]:
                    print(line.rstrip())
                last_position = f.tell()  # Get current position
                f.close()
    except Exception as e:
        print(f"Error reading file: {e}")

    print("\n=== Watching for '100% (done)' ===")

    try:
        while True:
            # Check if file exists
            if not os.path.exists(log_path):
                time.sleep(0.5)
                continue

            # Open file and read from last position
            with open(log_path, "r") as f:
                f.seek(last_position)
                new_lines = f.readlines()
                last_position = f.tell()

                # Display new lines (but only last 5 lines total when new data arrives)
                if new_lines:
                    # Get the actual last 5 lines from the file
                    f.seek(0, os.SEEK_END)
                    file_size = f.tell()

                    # Read last 5 lines efficiently
                    f.seek(max(0, file_size - 4096))  # Read last 4KB
                    content = f.read()
                    lines = content.splitlines()

                    # Show last 5 lines
                    print(f"\n--- Update at {time.strftime('%H:%M:%S')} ---")
                    for line in lines[-5:]:
                        print(line)

                    # Check for bootstrap completion (case insensitive)
                    for line in lines[-10:]:  # Check recent lines
                        if "100%" in line.lower() or "(done)" in line.lower():
                            print("\n✓ Bootstrap complete! Exiting...")
                            return

                time.sleep(0.5)  # Check every half second

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        return


def main() -> None:
    """Main function with optional command line argument"""
    import sys

    # Allow custom path from command line
    log_path = sys.argv[1] if len(sys.argv) > 1 else "~/.tor/tor.log"

    watch_tor_log(log_path)


if __name__ == "__main__":
    main()
