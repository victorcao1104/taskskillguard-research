"""Launch an unchanged study entry point using Windows extended-length paths.

This changes filesystem addressing only. Arguments, frozen source bytes, request
identifiers, prompts, cached responses and experimental semantics are unchanged.
"""
import os
from pathlib import Path
import runpy
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python windows_long_paths.py SCRIPT [arguments]")
    target = Path(sys.argv[1]).resolve()
    path = str(target)
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        path = "\\\\?\\" + path
    sys.path.insert(0, str(Path(path).parent))
    sys.argv = [path, *sys.argv[2:]]
    runpy.run_path(path, run_name="__main__")


if __name__ == "__main__":
    main()
