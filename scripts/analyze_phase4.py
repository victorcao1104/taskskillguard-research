"""Publish Phase 4 analysis only after the full frozen 384-job grid exists."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tsg.analysis_v4 import publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(publish(args.root))
    except ValueError as error:
        parser.exit(2, f"Analysis not published: {error}\n")


if __name__ == "__main__":
    main()
