#!/data/data/com.termux/files/usr/bin/env python

import sys

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def runcmd(
    cmd: list[str],
    run_silently: bool = False,
    show_output: bool = True,
    timeout: float | None = None,
) -> tuple[int, str, str]:
    from subprocess import DEVNULL as _DEVNULL
    from subprocess import TimeoutExpired as subprocess_TimeoutExpired
    from subprocess import run as subprocess_run
    from sys import stderr as sys_stderr
    from sys import stdout as sys_stdout

    if not cmd:
        msg = "cmd must be a non-empty list (e.g., ['ls', '-l'])"
        raise ValueError(msg)
    try:
        if run_silently:
            result = subprocess_run(cmd, stdout=_DEVNULL, stderr=_DEVNULL, timeout=timeout)
            return result.returncode, "", ""
        result = subprocess_run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout, stderr = result.stdout, result.stderr
        if show_output:
            if stdout:
                sys_stdout.write(stdout)
                sys_stdout.flush()
            if stderr:
                sys_stderr.write(stderr)
                sys_stderr.flush()
        return result.returncode, stdout, stderr
    except FileNotFoundError:
        msg = f"Command not found: '{cmd[0]}'"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 127, "", msg
    except PermissionError:
        msg = f"Permission denied: '{cmd[0]}'"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 126, "", msg
    except subprocess_TimeoutExpired:
        msg = f"Command timed out after {timeout}s: {' '.join(cmd)}"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 124, "", msg
    except Exception as e:
        msg = f"Unexpected error running '{cmd[0]}': {e}"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 1, "", msg


def get_installed_packages() -> list[str]:
    try:
        ret, txt, _err = runcmd(["dpkg-query", "-W", "-f='${Package}\t${Status}\t${Version}\n'"], show_output=True)
        return txt.splitlines()
    except:
        print(f"Error listing installed packages")
        sys.exit(1)


def check_package_health(package_name: str):
    try:
        ret, txt, _err = runcmd(["dpkg", "-l", package_name], show_output=True)
        lines = txt.splitlines()
        for line in lines:
            if package_name in line:
                status = line.split()[0]
                if status.startswith("ii"):
                    return True, "OK"
                return False, f"Status: {status}"
    except:
        return False, f"Error checking package"


def check_for_updates() -> str:
    try:
        res, txt, _err = runcmd(["apt-get", "-s", "upgrade"], show_output=True)
        return txt
    except:
        return f"Error checking for updates"


def main() -> None:
    print("=== Installed Packages Sanity Check ===")
    installed_pkgs = get_installed_packages()
    print(f"Found {len(installed_pkgs)} installed packages.\n")
    issues_found = 0
    for pkg_info in installed_pkgs:
        pkg_name, _status, _version = pkg_info.split("\t")
        pkg_name = pkg_name.strip("'")
        is_ok, msg = check_package_health(pkg_name)
        if not is_ok:
            print(f"[!] {pkg_name}: {msg}")
            issues_found += 1
    print("\n=== Update Check ===")
    update_info = check_for_updates()
    if "0 upgraded, 0 newly installed" in update_info:
        print("All packages are up to date.")
    else:
        print("Updates are available. Run 'sudo apt-get upgrade' to update.")
        print("--- Update Info ---")
        print(update_info)
    print("\n=== Summary ===")
    print(f"Issues found: {issues_found}")
    if issues_found == 0:
        print("All packages are properly installed.")
    else:
        print("Some packages may need attention.")


if __name__ == "__main__":
    main()
