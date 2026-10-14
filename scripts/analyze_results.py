"""Analyze saved results without an API key or network access."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tsg.evaluation import analyze_directory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--bootstrap-samples', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=76420261015)
    args = parser.parse_args()
    if args.bootstrap_samples < 0:
        parser.error('--bootstrap-samples must be nonnegative')
    result = analyze_directory(args.root, bootstrap_samples=args.bootstrap_samples, seed=args.seed)
    print(json.dumps({'summary_directory': str(args.root.resolve() / 'results/summary'),
                      'n_cases': result['coverage']['n_benchmark_cases'],
                      'phase_status': {k: v['status'] for k, v in result['coverage']['phases'].items()},
                      'detection_responses': result['coverage']['formal_detection_records'],
                      'budget_exposure_upper_usd': result['budget']['total_exposure_upper_usd']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
