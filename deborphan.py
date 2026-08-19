#!/data/data/com.termux/files/home/.local/bin/python
import re
from pathlib import Path

STATUS_PATH = Path("/var/lib/dpkg/status")


def parse_installed_packages(status_text: str):
    """
    Parse /var/lib/dpkg/status into:
      installed[pkg] = {"depends": [...], "provides": [...], "status": "installed"/...}
    We only keep packages that are in state "install ok installed".
    """
    installed = {}

    # Split by blank lines between paragraphs
    blocks = re.split(r"\n\s*\n", status_text.strip(), flags=re.M)

    for b in blocks:
        pkg = re.search(r"^Package:\s*(.+)$", b, flags=re.M)
        status = re.search(r"^Status:\s*(.+)$", b, flags=re.M)
        provides = re.findall(r"^Provides:\s*(.+)$", b, flags=re.M)
        depends = re.findall(r"^Depends:\s*(.+)$", b, flags=re.M)

        if not pkg or not status:
            continue

        pkg_name = pkg.group(1).strip()
        status_line = status.group(1).strip()

        # dpkg status line looks like:
        # "install ok installed"
        if "install ok installed" not in status_line:
            continue

        # Depends may continue on subsequent lines in dpkg format; handle simple cases only.
        # For robust parsing, you'd need a full dpkg control-file parser.
        deps = []
        for d in depends:
            # dependencies separated by commas; each dep may have alternatives with '|'
            for part in d.split(","):
                part = part.strip()
                if not part:
                    continue
                # take first alternative token as package name base
                # e.g. "libc6 (>= 2.34)" => "libc6"
                alt = part.split("|", 1)[0].strip()
                m = re.match(r"^([A-Za-z0-9+_.:-]+)\s*(?:\(|$)", alt)
                if m:
                    deps.append(m.group(1))

        # Simple provides handling (optional)
        provs = []
        for p in provides:
            for tok in p.split(","):
                tok = tok.strip()
                if tok:
                    # name (version) format; take name
                    m = re.match(r"^([A-Za-z0-9+_.:-]+)", tok)
                    if m:
                        provs.append(m.group(1))

        installed[pkg_name] = {"depends": deps, "provides": provs}

    return installed


def build_reverse_deps(installed):
    # providers: a dependency token can be satisfied by the package itself or a "Provides"
    providers = {}
    for pkg, meta in installed.items():
        providers.setdefault(pkg, set()).add(pkg)
        for pr in meta["provides"]:
            providers.setdefault(pr, set()).add(pkg)

    reverse = {pkg: set() for pkg in installed.keys()}

    # For each package, add edges from its dependencies -> packages that depend on it
    for pkg, meta in installed.items():
        for dep in meta["depends"]:
            for provider_pkg in providers.get(dep, []):
                reverse.setdefault(provider_pkg, set()).add(pkg)

    return reverse


def is_candidate_library(pkg_name: str):
    """
    Deborphan mainly targets 'leaf' shared libraries.
    Heuristics here:
      - contains 'lib' prefix and typical soname patterns
      - or name starts with 'lib' and includes digits/dots later
    Adjust as needed.
    """
    return pkg_name.startswith("lib")


def find_orphans(installed, reverse):
    orphans = []
    for pkg in installed.keys():
        if not is_candidate_library(pkg):
            continue
        # If nobody depends on it (reverse_deps empty), mark as orphan-ish
        users = reverse.get(pkg, set())
        if not users:
            orphans.append(pkg)
    return sorted(orphans)


def main():
    if not STATUS_PATH.exists():
        raise SystemExit(
            f"Missing {STATUS_PATH}. This script expects a Debian-style dpkg database.\n"
            f"On Termux, you may need a Debian/Ubuntu rootfs that includes /var/lib/dpkg/status."
        )

    status_text = STATUS_PATH.read_text(errors="replace")
    installed = parse_installed_packages(status_text)

    reverse = build_reverse_deps(installed)
    orphans = find_orphans(installed, reverse)

    print("Orphan-ish libraries (no installed package depends on them):")
    for p in orphans:
        print(p)


if __name__ == "__main__":
    main()
