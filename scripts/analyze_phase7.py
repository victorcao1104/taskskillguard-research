"""Analyze available frozen Phase 7 evidence, without opening fixture programs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from tsg.analysis_v7 import analyze


def read_input(root, relative):
    path = root / relative
    if not path.is_file():
        return [], {"path": relative, "present": False, "rows": 0, "sha256": None}
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.decode("utf-8-sig").splitlines() if line.strip()]
    return rows, {"path": relative, "present": True, "rows": len(rows),
                  "sha256": hashlib.sha256(data).hexdigest()}


def write_immutable_outputs(output, report):
    """Preflight every existing artifact before any write; preserve old evidence."""
    encoded = {"summary.json": (json.dumps(report["summary"], ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()}
    for name in ("candidate_scores", "case_scores", "paired_details", "execution_failures"):
        encoded[name + ".jsonl"] = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in report[name]).encode()
    for name, data in encoded.items():
        path = output / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError("IMMUTABLE_MISMATCH " + str(path))
    output.mkdir(parents=True, exist_ok=True)
    for name, data in encoded.items():
        path = output / name
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT, help="Evidence project root; defaults to this repository")
    parser.add_argument("--output", type=Path, help="Fresh analysis directory; defaults to ROOT/results/phase7/analysis")
    args = parser.parse_args(argv)
    inputs = {"truth": "results/phase7/semantics/truth.jsonl",
              "observations": "results/phase7/api/observations.jsonl",
              "recovery": "results/phase7/recovery/vm_results.jsonl",
              "integrated": "results/phase7/integrated/vm_results.jsonl"}
    rows, manifest = {}, {}
    for name, path in inputs.items():
        rows[name], manifest[name] = read_input(args.root, path)
    report = analyze(rows["truth"], rows["observations"], rows["recovery"], rows["integrated"])
    report["summary"]["input_manifest"] = manifest
    output = args.output or args.root / "results/phase7/analysis"
    write_immutable_outputs(output, report)
    print(json.dumps({"output": str(output), **{k: report["summary"][k] for k in
                     ("cases", "main_conditions", "all_conditions", "recovery_conditions", "integrated_conditions")}}))


if __name__ == "__main__":
    main()
