#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path


def create_initpy(current_dir, pkg_name):
    src_dir = current_dir / "src"
    pkg_dir = src_dir / pkg_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    init_file = pkg_dir / "__init__.py"
    init_content = "__version__ = (1, 4, 7)\nfrom contextlib import suppress\nfrom importlib.metadata import PackageNotFoundError,version\nwith suppress(PackageNotFoundError):\n    __version__ = version(__name__)\n"
    if not init_file.exists():
        init_file.write_text(init_content, encoding="utf-8")


def create_readme(current_dir, pkg_name):
    readme_file = current_dir / "README.md"
    readme_content = f"# {pkg_name}\nA Python package named {pkg_name}.\n```bash\npip install -e .\n```\nUsage\n```python\nimport {pkg_name}\n```\n"
    if not readme_file.exists():
        readme_file.write_text(readme_content, encoding="utf-8")


def create_pyproject(current_dir, pkg_name):
    pyproject_file = current_dir / "pyproject.toml"
    pyproject_content = f'[build-system]\nrequires = ["setuptools>=61.0", "wheel"]\nbuild-backend = "setuptools.build_meta"\n[project]\nname = "{pkg_name}"\nversion = "1.4.7"\ndescription = "A Python package named {pkg_name}"\nreadme = "README.md"\nauthors = [\n{{name = "Isaac Onagh", email = "mkalafsaz@gmail.com"}},\n]\nclassifiers = [\n"Programming Language :: Python :: 3",\n"Operating System :: OS Independent",\n]\nrequires-python = ">=3.9"\n[tool.setuptools.packages.find]\nwhere = ["src"]\n'
    if not pyproject_file.exists():
        pyproject_file.write_text(pyproject_content, encoding="utf-8")


def create_setuppy(current_dir, pkg_name):
    setuppy_file = current_dir / "setup.py"
    setuppy_content = f'from pathlib import Path\\nfrom setuptools import setup, find_packages\\nimport re\\nhere = Path(__file__).parent\\nversion_re = re.compile(r"__version__ = (\\(.*?\\))")\\nversion = "1.4.7"\\nfor line in Path("src/{pkg_name}/__init__.py").read_text().splitlines():\\n    match = version_re.search(line)\\n    if match:\\n        version = eval(match.group(1))\\n        break\\nsetup(\\n    name="{pkg_name}",\\n    version=".".join(map(str, version)),\\n    description=f"python pkg named {pkg_name}",\\n    packages=find_packages(),\\n)\\n'
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
