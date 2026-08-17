#!/data/data/com.termux/files/home/.local/bin/python
"""
Detect files in system site-packages directories that don't belong to any packages.
"""
import email.parser
import importlib.metadata
import json
import os
import site
from pathlib import Path
from typing import List, Set
from loguru import logger
logger.remove()
log_path = Path.home() / "tmp" / "log" / "apps" / "orphan_files.log"
logger.add(log_path)
class OrphanFileDetector:
    def __init__(self):
        self.site_dirs = self._get_site_dirs()
        self.package_files: Set[Path] = set()
        self.package_dirs: Set[Path] = set()
    def _get_site_dirs(self) -> List[Path]:
        """Get system site-packages directories"""
        dirs = []
        # Get system site-packages (not user site-packages)
        for path in site.getsitepackages():
            if "user" not in path.lower():  # Exclude user site-packages
                dirs.append(Path(path))
        # Also add the main site-packages if not already included
        try:
            site_packages = Path(sysconfig.get_paths()["purelib"])
            if site_packages not in dirs and "user" not in str(site_packages).lower():
                dirs.append(site_packages)
        except:
            pass
        return dirs
    def get_installed_packages(self) -> List[importlib.metadata.Distribution]:
        """Get all installed packages"""
        return list(importlib.metadata.distributions())
    def get_package_files_from_dist(self, dist) -> Set[Path]:
        """Get files belonging to a distribution"""
        files = set()
        # Try to get files from RECORD
        if dist.files:
            for file in dist.files:
                # Get the full path
                full_path = Path(dist.locate_file(file))
                files.add(full_path.resolve())
        # Try to get files from dist-info
        dist_info_dir = Path(dist._path)
        if dist_info_dir.exists():
            # Add dist-info directory itself
            files.add(dist_info_dir.resolve())
            # Try to read RECORD file directly
            record_file = dist_info_dir / "RECORD"
            if record_file.exists():
                try:
                    import csv
                    with open(record_file, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if row:
                                file_path = row[0]
                                if not file_path.startswith(".."):
                                    full_path = (dist_info_dir.parent / file_path).resolve()
                                    files.add(full_path)
                except:
                    pass
            # Try to read installed-files.txt (for older packages)
            installed_files = dist_info_dir / "installed-files.txt"
            if installed_files.exists():
                try:
                    with open(installed_files, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                full_path = (dist_info_dir.parent / line).resolve()
                                files.add(full_path)
                except:
                    pass
        # Also add the top-level directory/package
        try:
            top_level = dist.read_text("top_level.txt")
            if top_level:
                for line in top_level.splitlines():
                    line = line.strip()
                    if line:
                        pkg_path = dist_info_dir.parent / line
                        if pkg_path.exists():
                            files.add(pkg_path.resolve())
                            # If it's a package directory, add all files in it
                            if pkg_path.is_dir():
                                for file in pkg_path.rglob("*"):
                                    if file.is_file():
                                        files.add(file.resolve())
        except:
            pass
        return files
    def collect_package_files(self):
        """Collect all files that belong to installed packages"""
        logger.info("Collecting package files...")
        packages = self.get_installed_packages()
        for dist in packages:
            try:
                files = self.get_package_files_from_dist(dist)
                self.package_files.update(files)
                # Also track package directories
                for file in files:
                    # Add parent directories for namespace packages
                    if "dist-info" in str(file) or "egg-info" in str(file):
                        self.package_dirs.add(file.parent)
            except Exception as e:
                logger.info(f"Warning: Could not process package {dist.metadata['Name']}: {e}")
        logger.info(f"Found {len(self.package_files)} files belonging to packages")
    def scan_site_dirs(self) -> List[Path]:
        """Scan site-packages directories for orphan files"""
        orphan_files = []
        logger.info("\nScanning site-packages directories:")
        for site_dir in self.site_dirs:
            logger.info(f"  - {site_dir}")
            if not site_dir.exists():
                logger.info(f"    (does not exist)")
                continue
            # Walk through all files in site-packages
            for root, dirs, files in os.walk(site_dir):
                root_path = Path(root)
                # Skip __pycache__ directories (they're generated, not installed)
                if "__pycache__" in dirs:
                    dirs.remove("__pycache__")
                # Check if this directory belongs to a package
                try:
                    root_resolved = root_path.resolve()
                    if root_resolved in self.package_dirs:
                        continue
                except:
                    pass
                # Check files
                for file in files:
                    file_path = (root_path / file).resolve()
                    # Skip if file belongs to a package
                    if file_path in self.package_files:
                        continue
                    # Skip certain file types that are always generated
                    if self._should_skip_file(file_path):
                        continue
                    orphan_files.append(file_path)
        return sorted(set(orphan_files))
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped (generated files, etc.)"""
        skip_patterns = [
            "__pycache__",
            ".pyc",
            ".pyo",
            ".pyd",  # These might be compiled, but often belong to packages
            ".so",  # These might be compiled, but often belong to packages
            ".egg-link",
            ".pth",
            "easy-install.pth",
            "site.py",
        ]
        file_str = str(file_path).lower()
        for pattern in skip_patterns:
            if pattern in file_str:
                return True
        # Skip .dist-info and .egg-info directories (they're package metadata)
        if ".dist-info" in file_str or ".egg-info" in file_str:
            return True
        return False
    def analyze_orphan_files(self, orphan_files: List[Path]):
        """Analyze and categorize orphan files"""
        categories = {
            "Python packages/modules": [],
            "Data files": [],
            "Executables/scripts": [],
            "Libraries": [],
            "Other": [],
        }
        for file_path in orphan_files:
            ext = file_path.suffix.lower()
            name = file_path.name.lower()
            if (
                ext in [".py", ".pyw"]
                or file_path.is_dir()
                and "__init__.py" in [f.name for f in file_path.iterdir() if f.is_file()]
            ):
                categories["Python packages/modules"].append(file_path)
            elif ext in [".txt", ".md", ".json", ".xml", ".csv", ".ini", ".cfg", ".yaml", ".yml", ".toml"]:
                categories["Data files"].append(file_path)
            elif ext in [".exe", ".bat", ".cmd", ".sh", ".bash"] or (
                file_path.is_file() and os.access(file_path, os.X_OK)
            ):
                categories["Executables/scripts"].append(file_path)
            elif ext in [".so", ".dll", ".dylib", ".a", ".lib"]:
                categories["Libraries"].append(file_path)
            else:
                categories["Other"].append(file_path)
        return categories
    def run(self, verbose: bool = False):
        """Run the orphan file detection"""
        logger.info("=" * 60)
        logger.info("Orphan File Detector for Python Site-Packages")
        logger.info("=" * 60)
        # Collect package files
        self.collect_package_files()
        # Scan for orphan files
        orphan_files = self.scan_site_dirs()
        # Analyze results
        categories = self.analyze_orphan_files(orphan_files)
        # logger.info results
        logger.info("\n" + "=" * 60)
        logger.info("RESULTS")
        logger.info("=" * 60)
        logger.info(f"\nFound {len(orphan_files)} orphan files/directories:")
        for category, files in categories.items():
            if files:
                logger.info(f"\n{category} ({len(files)}):")
                for file_path in sorted(files):
                    if verbose:
                        # Get file size if it's a file
                        if file_path.is_file():
                            size = file_path.stat().st_size
                            size_str = self._format_size(size)
                            logger.info(f"  {file_path} ({size_str})")
                        else:
                            logger.info(f"  {file_path} (directory)")
                    else:
                        logger.info(f"  {file_path}")
        # logger.info summary
        logger.info("\n" + "-" * 60)
        logger.info("SUMMARY:")
        for category, files in categories.items():
            if files:
                logger.info(f"  {category}: {len(files)}")
        logger.info("\nWARNING: Review these files carefully before removing them.")
        logger.info("Some may be intentionally installed or required by other tools.")
        return orphan_files
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    def export_to_file(self, orphan_files: List[Path], output_file: str = "orphan_files.json"):
        """Export orphan files list to a JSON file"""
        data = {
            "total_orphan_files": len(orphan_files),
            "site_directories": [str(d) for d in self.site_dirs],
            "files": [str(f) for f in orphan_files],
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"\nOrphan files list exported to: {output_file}")
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Detect orphan files in Python site-packages directories")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output with file sizes")
    parser.add_argument("-e", "--export", action="store_true", help="Export results to JSON file")
    parser.add_argument(
        "-o", "--output", default="orphan_files.json", help="Output file for export (default: orphan_files.json)"
    )
    args = parser.parse_args()
    detector = OrphanFileDetector()
    orphan_files = detector.run(verbose=args.verbose)
    if args.export:
        detector.export_to_file(orphan_files, args.output)
if __name__ == "__main__":
    import sysconfig
    main()
