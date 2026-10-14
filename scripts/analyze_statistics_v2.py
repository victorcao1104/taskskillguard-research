"""Recompute retrospective paired statistics without contacting any model API."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tsg.statistics_v2 import analyze_saved

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--bootstrap-samples', type=int, default=2000)
    args = parser.parse_args()
    result = analyze_saved(args.root, args.output or args.root / 'results/phase2/statistics', bootstrap_samples=args.bootstrap_samples)
    print(f"Saved {result['n_comparisons']} paired comparisons; {result['n_total_template_families']} template families; human ground truth remains pending.")
