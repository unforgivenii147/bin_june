#!/data/data/com.termux/files/usr/bin/python
"""
PyPI Package Update Checker with Multiprocessing & Resume Capability
- Checks installed packages against PyPI for updates
- Saves results to pkgs_state.json with resume support
- Generates requirements.txt for upgradable packages
- Uses multiprocessing for concurrent API queries (Linux/Termux)
"""

import json
import sys
import time
from pathlib import Path
from subprocess import run, CalledProcessError
from typing import Optional, Dict, Any
from multiprocessing import Pool, cpu_count
from dataclasses import dataclass, asdict
import logging

# ============================================================================
# LOGGING SETUP
# ============================================================================


def setup_logging(verbose: bool = True) -> logging.Logger:
    """Configure verbose logging to stdout and file."""
    logger = logging.getLogger("pkg_updater")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    # File handler
    file_handler = logging.FileHandler("pkg_updater.log")
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("[%(asctime)s] %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging(verbose=True)

# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class PackageInfo:
    """Represents a package and its update status."""

    pkgname: str
    installed_version: str
    latest_version: Optional[str] = None
    upgradable: bool = False
    checked_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageInfo":
        """Create instance from dict."""
        return cls(**data)


# ============================================================================
# STATE MANAGEMENT
# ============================================================================


class PackageStateManager:
    """Handle JSON state persistence and resume capability."""

    def __init__(self, state_file: Path = Path("pkgs_state.json")) -> None:
        self.state_file = state_file
        self.state: Dict[str, PackageInfo] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load existing state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    raw_state = json.load(f)
                self.state = {name: PackageInfo.from_dict(data) for name, data in raw_state.items()}
                logger.info(f"✓ Resumed state: {len(self.state)} packages loaded from {self.state_file}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"✗ Failed to load state: {e}. Starting fresh.")
                self.state = {}
        else:
            logger.info(f"📁 No existing state file. Starting fresh.")

    def save_state(self) -> None:
        """Persist state to JSON file."""
        state_dict = {name: pkg.to_dict() for name, pkg in self.state.items()}
        with open(self.state_file, "w") as f:
            json.dump(state_dict, f, indent=2)
        logger.debug(f"💾 State saved: {self.state_file}")

    def update_package(self, pkg_info: PackageInfo) -> None:
        """Update or add package info."""
        self.state[pkg_info.pkgname] = pkg_info

    def get_pending_packages(self, all_packages: list[str]) -> list[str]:
        """Return packages not yet checked."""
        return [p for p in all_packages if p not in self.state]

    def get_upgradable_packages(self) -> list[PackageInfo]:
        """Return list of upgradable packages."""
        return [pkg for pkg in self.state.values() if pkg.upgradable]


# ============================================================================
# PACKAGE DETECTION
# ============================================================================


def get_installed_packages() -> list[tuple[str, str]]:
    """Fetch installed packages and versions via pip list."""
    try:
        result = run(["pip", "list", "--format=json"], capture_output=True, text=True, check=True, timeout=30)
        packages = json.loads(result.stdout)
        logger.info(f"✓ Found {len(packages)} installed packages")
        return [(p["name"], p["version"]) for p in packages]
    except (CalledProcessError, json.JSONDecodeError, TimeoutError) as e:
        logger.error(f"✗ Failed to get installed packages: {e}")
        sys.exit(1)


# ============================================================================
# PyPI API QUERY (Multiprocessing Worker)
# ============================================================================


def query_pypi(package_name: str, installed_version: str, retries: int = 2) -> PackageInfo:
    """
    Query PyPI API for latest version of a package.
    Worker function for multiprocessing.
    """
    import requests

    url = f"https://pypi.org/pypi/{package_name}/json"
    pkg_info = PackageInfo(
        pkgname=package_name, installed_version=installed_version, checked_at=time.strftime("%Y-%m-%d %H:%M:%S")
    )

    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            latest_version = data["info"]["version"]
            pkg_info.latest_version = latest_version

            # Compare versions (simple semver comparison)
            pkg_info.upgradable = _is_upgradable(installed_version, latest_version)

            status = "🔄 upgradable" if pkg_info.upgradable else "✓ up-to-date"
            logger.debug(f"{status:20} | {package_name:30} {installed_version} → {latest_version}")

            return pkg_info

        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            pkg_info.error = "Timeout"
            logger.warning(f"⏱ Timeout: {package_name}")
            return pkg_info

        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                pkg_info.error = "Not found on PyPI"
                logger.warning(f"❌ Not found: {package_name}")
            else:
                pkg_info.error = f"HTTP {response.status_code}"
                logger.warning(f"⚠ HTTP error: {package_name} ({response.status_code})")
            return pkg_info

        except Exception as e:
            pkg_info.error = str(e)
            logger.warning(f"⚠ Error: {package_name} - {e}")
            return pkg_info

    return pkg_info


def _is_upgradable(installed: str, latest: str) -> bool:
    """
    Simple version comparison using packaging.version.
    Returns True if latest > installed.
    """
    try:
        from packaging import version

        return version.parse(latest) > version.parse(installed)
    except Exception:
        # Fallback: tuple comparison (naive but works for most cases)
        try:
            installed_parts = [int(x) for x in installed.split(".")[:3]]
            latest_parts = [int(x) for x in latest.split(".")[:3]]
            return tuple(latest_parts) > tuple(installed_parts)
        except (ValueError, IndexError):
            return False


# ============================================================================
# MAIN WORKFLOW
# ============================================================================


def main() -> None:
    """Main execution flow."""
    logger.info("=" * 80)
    logger.info("🚀 PyPI Package Update Checker (Multiprocessing Enabled)")
    logger.info("=" * 80)

    # Step 1: Initialize state manager
    state_manager = PackageStateManager()

    # Step 2: Get installed packages
    installed = get_installed_packages()
    all_package_names = [name for name, _ in installed]

    # Step 3: Identify pending packages (resume capability)
    pending = state_manager.get_pending_packages(all_package_names)
    already_checked = len(all_package_names) - len(pending)

    logger.info(f"📊 Status: {already_checked} checked, {len(pending)} pending")

    if not pending:
        logger.info("✓ All packages already checked. Skipping PyPI queries.")
    else:
        # Step 4: Query PyPI concurrently
        pending_packages = [(name, next(v for n, v in installed if n == name)) for name in pending]

        num_workers = min(cpu_count(), 8)  # Cap at 8 to avoid overwhelming PyPI
        logger.info(f"🔄 Spawning {num_workers} workers to query PyPI...")

        with Pool(processes=num_workers) as pool:
            results = pool.starmap(query_pypi, pending_packages, chunksize=max(1, len(pending_packages) // num_workers))

        # Step 5: Update state with results
        for pkg_info in results:
            state_manager.update_package(pkg_info)

        logger.info(f"✓ Completed {len(results)} PyPI queries")

    # Step 6: Save state
    state_manager.save_state()

    # Step 7: Generate requirements.txt for upgradable packages
    upgradable = state_manager.get_upgradable_packages()
    if upgradable:
        req_file = Path("requirements_upgradable.txt")
        with open(req_file, "w") as f:
            for pkg in sorted(upgradable, key=lambda x: x.pkgname):
                f.write(f"{pkg.pkgname}=={pkg.latest_version}\n")
        logger.info(f"📝 {len(upgradable)} upgradable packages saved to {req_file}")
    else:
        logger.info("✓ All packages are up-to-date!")

    # Step 8: Summary
    logger.info("=" * 80)
    logger.info(f"📈 SUMMARY")
    logger.info(f"   Total packages: {len(state_manager.state)}")
    logger.info(f"   Upgradable: {len(upgradable)}")
    logger.info(f"   Up-to-date: {len(state_manager.state) - len(upgradable)}")
    logger.info("=" * 80)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⏹ Interrupted by user. State saved.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"✗ Fatal error: {e}", exc_info=True)
        sys.exit(1)
