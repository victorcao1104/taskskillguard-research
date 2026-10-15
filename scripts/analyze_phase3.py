"""Read saved phase-three evidence and write an explicitly partial/final summary."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.analysis_v3 import build_summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--allow-partial',action='store_true')
    args=parser.parse_args()
    summary=build_summary(args.root,allow_partial=args.allow_partial)
    output=args.output or args.root/'results/phase3/analysis/summary.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp')
    temporary.write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(output)
    print(json.dumps({'output':str(output),'complete':summary['complete'],
                      'incomplete_items':summary['incomplete_items']}))


if __name__=='__main__':
    main()
