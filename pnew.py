#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path


def main():
    path = Path(sys.argv[1])
    template = '#!/data/data/com.termux/files/usr/bin/python\nfrom pathlib import Path\nimport sys\nfrom dh import get_files\nfrom pbar import Pbar\ndef process_file(fp) -> None:\n    pass\n\ndef main():\n    cwd = Path.cwd()\n    args = sys.argv[1:]\n    if args:\n        for arg in args:\n            p = Path(arg)\n            if p.is_file():\n                files.append(p)\n            if p.is_dir():\n                files.extend(get_files(p))\n    else:\n        files = get_files(cwd)\n    with Pbar("") as pbar:\n        for f in pbar.wrap(files):\n            process_file(f)\nif __name__ == "__main__":\n    sys.exit(main())\n'
    path.write_text(template, encoding="utf-8")
    print(f"{path.name} created.")


if __name__ == "__main__":
    sys.exit(main())
