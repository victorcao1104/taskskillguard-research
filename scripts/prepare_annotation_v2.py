"""Prepare blank human packets, validate imports, and resolve disagreements."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tsg.annotation_v2 import (prepare_packets, import_reviews, make_adjudication,
                               finalize_adjudication, write_packet_html,
                               submission_from_csv)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--output', type=Path)
    prepare.add_argument('--real-tasks', type=Path)
    convert = sub.add_parser('csv-to-json')
    convert.add_argument('--csv', type=Path, required=True)
    convert.add_argument('--identity', type=Path, required=True)
    convert.add_argument('--output', type=Path, required=True)
    imp = sub.add_parser('import')
    imp.add_argument('--key', type=Path, required=True)
    imp.add_argument('--rater-a', type=Path, required=True)
    imp.add_argument('--rater-b', type=Path, required=True)
    imp.add_argument('--output', type=Path, required=True)
    adjudicate = sub.add_parser('adjudicate')
    adjudicate.add_argument('--key', type=Path, required=True)
    adjudicate.add_argument('--imported', type=Path, required=True)
    adjudicate.add_argument('--submission', type=Path)
    adjudicate.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare_packets(args.root, args.output or args.root / 'data/annotation_v2',
                                 args.real_tasks or args.root / 'data/tasks/phase2_real_task_triples.jsonl')
        print(json.dumps({k: v for k, v in result.items() if k != 'source_verification'}, indent=2))
    elif args.command == 'csv-to-json':
        write(args.output, submission_from_csv(args.csv, args.identity))
    elif args.command == 'import':
        key = read(args.key)
        result = import_reviews(key, [read(args.rater_a), read(args.rater_b)])
        args.output.mkdir(parents=True, exist_ok=True)
        write(args.output / 'imported.json', result)
        packet = make_adjudication(key, result)
        source_packet = read(args.key.parent.parent / 'rater_a/packet.json')
        packet['evidence_documents'] = source_packet['evidence_documents']
        write(args.output / 'adjudication_packet.json', packet)
        write_packet_html(args.output / 'adjudication.html', packet)
        print(result['status'], result['n_disputed_units'])
    else:
        result = finalize_adjudication(read(args.key), read(args.imported), read(args.submission) if args.submission else None)
        write(args.output, result)
        print(result['status'])
