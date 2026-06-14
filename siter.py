#!/data/data/com.termux/files/usr/bin/python

import argparse
import base64
import csv
import hashlib
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


class WheelBuilder:
    def __init__(self, site_packages: Path, output_dir: Path) -> None:
        self.site_packages = site_packages.resolve()
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.venv_root = self._find_venv_root()
        self.bin_dir = self._find_bin_dir()
        self.share_dir = self.venv_root / "share" if self.venv_root else None

    def _find_venv_root(self) -> Path | None:
        current = self.site_packages
        for _ in range(5):
            if (current / "pyvenv.cfg").exists():
                return current
            if (current / "bin" / "activate").exists():
                return current
            if (current / "Scripts" / "activate.bat").exists():
                return current
            current = current.parent
        return None

    def _find_bin_dir(self) -> Path | None:
        if not self.venv_root:
            return None
        for name in ["bin", "Scripts"]:
            d = self.venv_root / name
            if d.exists():
                return d
        return Path("/data/data/com.termux/files/usr/bin")

    def _compute_hash(self, path: Path) -> str:
        h = hashlib.sha256()
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        digest = h.digest()
        return f"sha256={base64.urlsafe_b64encode(digest).decode().rstrip('=')} "

    def _read_record(self, dist_info: Path) -> dict[str, dict]:
        record_file = dist_info / "RECORD"
        if not record_file.exists():
            return {}
        records = {}
        with Path(record_file).open(encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or not row[0]:
                    continue
                path = row[0]
                records[path] = {"hash": row[1] if len(row) > 1 else "", "size": row[2] if len(row) > 2 else ""}
        return records

    def _read_installer(self, dist_info: Path) -> str:
        installer_file = dist_info / "INSTALLER"
        if installer_file.exists():
            return installer_file.read_text().strip()
        return "unknown"

    def _find_scripts_for_package(self, records: dict) -> list[Path]:
        if not self.bin_dir or not self.bin_dir.exists():
            return []
        scripts = []
        entry_points_file = None
        for path_str in records:
            if path_str.endswith("entry_points.txt"):
                entry_points_file = self.site_packages / path_str
                break
        if entry_points_file and entry_points_file.exists():
            script_names = set()
            in_console_scripts = False
            for line in entry_points_file.read_text().splitlines():
                line = line.strip()
                if line == "[console_scripts]":
                    in_console_scripts = True
                    continue
                if line.startswith("["):
                    in_console_scripts = False
                elif in_console_scripts and "=" in line:
                    script_name = line.split("=")[0].strip()
                    script_names.add(script_name)
            for script_name in script_names:
                script_path = self.bin_dir / script_name
                if script_path.exists():
                    scripts.append(script_path)
                exe_path = self.bin_dir / f"{script_name}.exe"
                if exe_path.exists():
                    scripts.append(exe_path)
        return scripts

    def _find_data_for_package(self, package_name: str) -> list[tuple[Path, str]]:
        if not self.share_dir or not self.share_dir.exists():
            return []
        data_files = []
        pkg_normalized = package_name.lower().replace("-", "_")
        for item in self.share_dir.rglob("*"):
            if not item.is_file():
                continue
            if any((pkg_normalized in p.name.lower() for p in item.parents)):
                try:
                    rel_path = item.relative_to(self.share_dir)
                    data_files.append((item, str(rel_path)))
                except ValueError:
                    pass
        return data_files

    def _get_wheel_tags(self) -> tuple[str, str, str, bool]:
        try:
            from packaging.tags import sys_tags

            tag = next(sys_tags())
            return (tag.interpreter, tag.abi, tag.platform, False)
        except ImportError:
            import platform

            py_ver = sys.version_info
            python_tag = f"cp{py_ver.major}{py_ver.minor}"
            abi_tag = python_tag
            plat = platform.system().lower()
            machine = platform.machine().lower()
            platform_tag = f"{plat}_{machine}"
            return (python_tag, abi_tag, platform_tag, False)

    def _detect_purity(self, records: dict) -> bool:
        return all((not path.endswith((".so", ".pyd", ".dll")) for path in records))

    def build_wheel(self, dist_info_dir: Path) -> Path | None:
        if not dist_info_dir.is_dir():
            return None
        parts = dist_info_dir.stem.split("-")
        if len(parts) < 2:
            print(f"Invalid dist-info name: {dist_info_dir.name}")
            return None
        pkg_name = parts[0]
        version = parts[1] if len(parts) > 1 else "0.0.0"
        print(f"Building wheel for {pkg_name} {version}")
        records = self._read_record(dist_info_dir)
        if not records:
            print("No RECORD file for %s", pkg_name)
            return None
        is_pure = self._detect_purity(records)
        if is_pure:
            python_tag, abi_tag, platform_tag = ("py3", "none", "any")
        else:
            python_tag, abi_tag, platform_tag, _ = self._get_wheel_tags()
        scripts = self._find_scripts_for_package(records=records)
        data_files = self._find_data_for_package(pkg_name)
        if scripts:
            print(f"  Found {len(scripts)} script(s)")
        if data_files:
            print(f"  Found {len(data_files)} data file(s)")
        wheel_name = f"{pkg_name.replace('-', '_')}-{version}-{python_tag}-{abi_tag}-{platform_tag}.whl"
        wheel_path = self.output_dir / wheel_name
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            dist_info_name = f"{pkg_name}-{version}.dist-info"
            dist_info_dest = tmp_path / dist_info_name
            dist_info_dest.mkdir(parents=True)
            data_dir_name = f"{pkg_name}-{version}.data"
            data_dir = None
            new_record = []
            for path_str in records:
                src = self.site_packages / path_str
                if not src.exists():
                    continue
                dest = dist_info_dest / Path(path_str).name if ".dist-info" in path_str else tmp_path / path_str
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(src, dest)
                rel_path = dest.relative_to(tmp_path)
                file_hash = self._compute_hash(dest)
                get_size = dest.stat().st_size
                new_record.append((str(rel_path), file_hash, str(get_size)))
            if scripts:
                data_dir = tmp_path / data_dir_name
                scripts_dir = data_dir / "scripts"
                scripts_dir.mkdir(parents=True, exist_ok=True)
                for script in scripts:
                    dest = scripts_dir / script.name
                    shutil.copy2(script, dest)
                    rel_path = dest.relative_to(tmp_path)
                    file_hash = self._compute_hash(dest)
                    get_size = dest.stat().st_size
                    new_record.append((str(rel_path), file_hash, str(get_size)))
            if data_files:
                if not data_dir:
                    data_dir = tmp_path / data_dir_name
                data_data_dir = data_dir / "data"
                data_data_dir.mkdir(parents=True, exist_ok=True)
                for src, rel_data_path in data_files:
                    dest = data_data_dir / rel_data_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    rel_path = dest.relative_to(tmp_path)
                    file_hash = self._compute_hash(dest)
                    get_size = dest.stat().st_size
                    new_record.append((str(rel_path), file_hash, str(get_size)))
            wheel_file = dist_info_dest / "WHEEL"
            with Path(wheel_file).open("w", encoding="utf-8") as f:
                f.write("Wheel-Version: 1.0\n")
                f.write("Generator: wheel-builder 1.0\n")
                f.write(f"Root-Is-Purelib: {('true' if is_pure else 'false')}\n")
                f.write(f"Tag: {python_tag}-{abi_tag}-{platform_tag}\n")
            rel_path = wheel_file.relative_to(tmp_path)
            file_hash = self._compute_hash(wheel_file)
            get_size = wheel_file.stat().st_size
            new_record.append((str(rel_path), file_hash, str(get_size)))
            record_file = dist_info_dest / "RECORD"
            with Path(record_file).open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for row in new_record:
                    writer.writerow(row)
                writer.writerow([f"{dist_info_name}/RECORD", "", ""])
            with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as whl:
                for file in tmp_path.rglob("*"):
                    if file.is_file():
                        arcname = file.relative_to(tmp_path)
                        whl.write(file, arcname)
        print(f"  Created: {wheel_path.name}")
        return wheel_path

    def build_all(self) -> int:
        dist_infos = sorted(self.site_packages.glob("*.dist-info"))
        if not dist_infos:
            print(f"No packages found in {self.site_packages}")
            return 0
        print(f"Found {len(dist_infos)} package(s) in {self.site_packages}")
        if self.venv_root:
            print(f"Virtual environment: {self.venv_root}")
        built = 0
        for dist_info in dist_infos:
            try:
                if self.build_wheel(dist_info):
                    built += 1
            except Exception as e:
                print(f"Failed to build {dist_info.name}: {e}")
        print(f"\nBuilt {built}/{len(dist_infos)} wheels in {self.output_dir}")
        return built


def find_site_packages() -> list[Path]:
    candidates = []
    import site

    for sp in site.getsitepackages():
        p = Path(sp)
        if p.exists():
            candidates.append(p)
    user_site = site.getusersitepackages()
    if user_site:
        p = Path(user_site)
        if p.exists():
            candidates.append(p)
    cwd = Path.cwd()
    for pattern in [".venv", "venv", "env"]:
        for venv in cwd.rglob(pattern):
            if venv.is_dir():
                for sp in venv.rglob("site-packages"):
                    if sp.is_dir() and sp not in candidates:
                        candidates.append(sp)
    return sorted(set(candidates))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build proper wheel files from installed packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n  %(prog)s\n  %(prog)s --site-packages /path/to/venv/lib/python3.11/site-packages\n  %(prog)s --output ./wheels\n  %(prog)s --package requests\n        ",
    )
    parser.add_argument(
        "--site-packages", "-s", type=Path, help="Path to site-packages directory (auto-detect if not specified)"
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=Path("/sdcard/whl"), help="Output directory for wheels (default: ./wheels)"
    )
    parser.add_argument("--package", "-p", help="Build only this package (by name)")
    parser.add_argument("--list", "-l", action="store_true", help="List available site-packages directories and exit")
    args = parser.parse_args()
    if args.list:
        sites = find_site_packages()
        print(f"Found {len(sites)} site-packages:")
        for i, sp in enumerate(sites, 1):
            print(f"  {i}. {sp}")
        return 0
    if args.site_packages:
        site_packages = args.site_packages.resolve()
        if not site_packages.exists():
            print("Site-packages not found: %s", site_packages)
            return 1
    else:
        sites = find_site_packages()
        if not sites:
            print("No site-packages found. Use --site-packages to specify.")
            return 1
        if len(sites) == 1:
            site_packages = sites[0]
        else:
            print("Multiple site-packages found:")
            for i, sp in enumerate(sites, 1):
                print(f"  {i}. {sp}")
            try:
                choice = int(input("\nSelect site-packages [1]: ") or "1")
                site_packages = sites[choice - 1]
            except (ValueError, IndexError):
                print("Invalid selection")
                return 1
    print("Using site-packages: %s", site_packages)
    builder = WheelBuilder(site_packages, args.output)
    if args.package:
        dist_info = site_packages / f"{args.package}-*.dist-info"
        matches = list(site_packages.glob(f"{args.package}*.dist-info"))
        if not matches:
            print(f"Package not found: {args.package}")
            return 1
        if len(matches) > 1:
            print(f"Multiple matches for '{args.package}':")
            for m in matches:
                print(f"  - {m.name}")
            print("Building all matches...")
        built = 0
        for dist_info in matches:
            if builder.build_wheel(dist_info):
                built += 1
        return 0 if built > 0 else 1
    built = builder.build_all()
    return 0 if built > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
