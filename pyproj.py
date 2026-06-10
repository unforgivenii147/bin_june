#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import append_text


def create_initpy(current_dir, pkg_name):
    src_dir = current_dir / "src"
    pkg_dir = src_dir / pkg_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    init_file = pkg_dir / "__init__.py"
    init_content = f"""

__version__ = (1, 4, 7)
from contextlib import suppress
from importlib.metadata import PackageNotFoundError,version
with suppress(PackageNotFoundError):
    __version__ = version(__name__)

"""
    if not init_file.exists():
        init_file.write_text(init_content, encoding="utf-8")
    else:
        print("__init__.py exists")
        append_text(init_file, init_content)


def create_readme(current_dir, pkg_name):
    readme_file = current_dir / "README.md"
    readme_content = f"""
# {pkg_name}

A Python package named {pkg_name}.
```bash
pip install -e .
```

Usage
```python
import {pkg_name}

```

"""
    if not readme_file.exists():
        readme_file.write_text(readme_content, encoding="utf-8")


def create_pyproject(current_dir, pkg_name):
    pyproject_file = current_dir / "pyproject.toml"
    pyproject_content = f"""
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
[project]
name = "{pkg_name}"
version = "1.4.7"
description = "A Python package named {pkg_name}"\)
readme = "README.md"
authors = [{{name = "Isaac Onagh", email = "mkalafsaz@gmail.com"}},
]
classifiers = [
    "Programming Language :: Python :: 3",
    "Operating System :: OS Independent",
]
requires-python = ">=3.9"

[tool.setuptools.packages.find]
where = ["src"]

"""
    if not pyproject_file.exists():
        pyproject_file.write_text(pyproject_content, encoding="utf-8")


def create_setuppy(current_dir, pkg_name):
    setuppy_file = current_dir / "setup.py"
    setuppy_content = f"""
from pathlib import Path
from setuptools import setup, find_packages
import re
here = Path(__file__).parent
version_re = re.compile(r"__version__ = (\(.*?\))")
version = "1.4.7"
for line in Path("src/{pkg_name}/__init__.py").read_text().splitlines():
    match = version_re.search(line)
    if match:
        version = eval(match.group(1))
        break

setup(
    name="{pkg_name}",
    version=".".join(map(str, version)),
    description=f"python pkg named {pkg_name}",
    packages=find_packages(),
)

"""

    if not setuppy_file.exists():
        setuppy_file.write_text(setuppy_content, encoding="utf-8")


def create_python_project(pkg_name):
    cwd = Path.cwd()
    create_initpy(cwd, pkg_name)
    create_readme(cwd, pkg_name)
    create_pyproject(cwd, pkg_name)
    create_setuppy(cwd, pkg_name)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    pkg = sys.argv[1]
    create_python_project(pkg)


if __name__ == "__main__":
    main()
