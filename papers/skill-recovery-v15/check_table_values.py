"""Check literal manuscript Tables II--VII and citation/bibliography consistency.

Standard library only; no API, experiment imports, replay, or evidence writes.
Default writes only qa/table_checks.json. --check verifies the saved QA report.
The evidence is read from evidence/key_results.json, produced separately by
prepare_evidence.py. This checks table transcription, not scientific validity.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
EXPECTED_CITATIONS = {
    "liu", "skillinject", "injecagent", "agentdojo", "struq", "camel", "progent",
    "skillscope", "lifty", "sketch", "selfrefine", "reflexion", "pase", "memtx",
    "rifl", "shielding", "ifc", "quickcheck", "metamorphic",
}
MODEL_NAMES = {"Luna": "gpt-6-luna", "Mini": "gpt-4.1-mini"}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def uncomment(text):
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def cell_text(text):
    # The tables deliberately contain literal values, not computed TeX macros.
    text = re.sub(r"\\multicolumn\{\d+\}\{[^{}]*\}\{([^{}]*)\}", r"\1", text)
    return normalize(text.replace("$", ""))


def extract_tables(tex):
    tables = {}
    for ordinal, match in enumerate(re.finditer(r"\\begin\{table\}(?:\[[^\]]*\])?(.*?)\\end\{table\}", tex, re.S), 1):
        body = match.group(1)
        label = re.search(r"\\label\{([^{}]+)\}", body)
        require(label is not None, "Every manuscript table must have a label")
        key = label.group(1)
        require(key not in tables, "Duplicate table label: " + key)
        tabular = re.search(r"\\begin\{tabular\}[^\n]*\n(.*?)\\end\{tabular\}", body, re.S)
        require(tabular is not None, "Literal tabular block missing: " + key)
        content = re.sub(r"\\(?:toprule|midrule|bottomrule)\b", "", tabular.group(1))
        rows = [[cell_text(c) for c in re.split(r"(?<!\\)&", line)]
                for line in re.split(r"\\\\(?:\[[^\]]*\])?", content) if "&" in line]
        tables[key] = {"number": ordinal, "source_line": tex[:match.start()].count("\n") + 1,
                       "body": body, "rows": rows}
    return tables


def bibliography_block(text):
    matches = re.findall(r"\\begin\{thebibliography\}\{[^{}]*\}(.*?)\\end\{thebibliography\}", uncomment(text), re.S)
    require(len(matches) == 1, "Exactly one embedded bibliography expected")
    # IEEE's column balancing directive is layout, not bibliography content.
    return normalize(re.sub(r"\\IEEEtriggeratref\{\d+\}", "", matches[0]))


def audit(tex, references, evidence):
    tex = uncomment(tex)
    tables = extract_tables(tex)
    expected_order = {"tab:source": 2, "tab:state": 3, "tab:contrasts": 4,
                      "tab:protection": 5, "tab:causal": 6, "tab:validation": 7}
    checks = []
    details = {}
    for label, number in expected_order.items():
        require(label in tables and tables[label]["number"] == number, f"{label} must be Table {number}")
        details[label] = {"number": number, "source_line": tables[label]["source_line"], "checked_rows": 0}

    def eq(label, row, field, literal, expected):
        expected = str(expected)
        require(literal == expected, f"{label}, {row}, {field}: source {literal!r}, evidence {expected!r}")
        checks.append({"table": label, "row": row, "field": field,
                       "source_literal": literal, "expected_literal": expected})

    def find_row(label, name):
        matches = [row for row in tables[label]["rows"] if row[0] == name]
        require(len(matches) == 1, f"Expected one row {name!r} in {label}")
        return matches[0]

    def evidence_one(rows, **keys):
        matches = [r for r in rows if all(r.get(k) == v for k, v in keys.items())]
        require(len(matches) == 1, "Evidence row identity: " + str(keys))
        return matches[0]

    label = "tab:source"
    source_names = [("Intact computation", "intact"), ("Partial damage", "partial"),
                    ("Key algorithm removed", "destroyed"), ("No source", "absent"),
                    ("Irrelevant source", "irrelevant")]
    require(len(tables[label]["rows"]) == 9, "Unexpected source table rows")
    for name, level in source_names:
        row = find_row(label, name)
        require(len(row) == 5, "Source table column count")
        for index, (model, method) in enumerate((("gpt-6-luna", "full"), ("gpt-6-luna", "repair"),
                                               ("gpt-4.1-mini", "full"), ("gpt-4.1-mini", "repair")), 1):
            value = evidence_one(evidence["source"], model=model, method=method, source_level=level)
            require(value["episodes"] == value["feasible_episodes"] == 16, "Source cell denominator")
            eq(label, name, model + "/" + method, row[index], value["safe_complete_feasible"])
    require("Each cell has sixteen templates" in tables[label]["body"], "Source denominator caption")
    row = find_row(label, "Source-free replan")
    require(len(row) == 3, "Replan table columns")
    for index, model in enumerate(("gpt-6-luna", "gpt-4.1-mini"), 1):
        value = evidence_one(evidence["source"], model=model, method="replan")
        eq(label, "Source-free replan", model, row[index], f'{value["safe_complete_feasible"]}/{value["episodes"]}')
    specialist = evidence["specialist_controls"]["specialist_compiler"]
    eq(label, "Specialist solver", "final and scale", find_row(label, "Specialist solver")[1],
       f'{specialist["final"]}/{specialist["cases"]}; also {specialist["scale"]}/{specialist["cases"]} at scale')
    details[label]["checked_rows"] = 7

    label = "tab:state"
    rows = tables[label]["rows"]
    require(len(rows) == 9 and rows[0] == ["Model", "Support", "Complete/48", "Stop/16", "Requests"], "State table headings/denominators")
    model = None
    seen = set()
    for row in rows[1:]:
        require(len(row) == 5, "State table column count")
        if row[0]:model = MODEL_NAMES.get(row[0])
        require(model is not None, "State model label")
        method = row[1].split(":")[0]
        require((model, method) not in seen, "Duplicate state row")
        seen.add((model, method))
        value = evidence_one(evidence["strict_state"], model=model, method=method)
        require((value["feasible_episodes"], value["boundary_episodes"]) == (48, 16), "Strict evidence denominators")
        for index, field in enumerate(("safe_complete_feasible", "correct_stop_boundary", "model_requests"), 2):
            eq(label, model + "/" + method, field, row[index], value[field])
    require(seen == {(m, s) for m in MODEL_NAMES.values() for s in "ABCD"}, "Strict table grid")
    details[label]["checked_rows"] = 8

    label = "tab:contrasts"
    rows = tables[label]["rows"]
    require(len(rows) == 7, "Contrast table row count")
    require("percentage points" in tables[label]["body"], "Contrast scale caption")
    model, seen = None, set()
    for row in rows[1:]:
        require(len(row) == 4, "Contrast column count")
        if row[0]:model = MODEL_NAMES.get(row[0])
        require(model is not None, "Contrast model label")
        comparison = row[1].replace("--", "-")
        require((model, comparison) not in seen, "Duplicate contrast row")
        seen.add((model, comparison))
        value = evidence_one(evidence["strict_contrasts"], model=model, contrast=comparison)
        interval = re.fullmatch(r"\[([^,]+),\s*([^\]]+)\]", row[3])
        require(interval is not None, "Contrast interval syntax")
        literals = [row[2], *interval.groups()]
        values = [value["difference"], *value["bootstrap_95"]]
        for field, literal, raw in zip(("difference_pp", "lower_pp", "upper_pp"), literals, values):
            expected = (Decimal(str(raw)) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
            require(re.fullmatch(r"[+-]?\d+\.\d", literal) is not None, "One decimal contrast formatting")
            # Positive signs are optional; zero has no required positive sign.
            eq(label, model + "/" + comparison, field, str(Decimal(literal)), str(expected))
    require(seen == {(m, c) for m in MODEL_NAMES.values() for c in ("B-A", "C-B", "D-C")}, "Paired-contrast grid")
    details[label]["checked_rows"] = 6

    label = "tab:protection"
    rows = tables[label]["rows"]
    require(len(rows) == 4 and rows[0][1:3] == ["Complete/160", "Stop/64"], "Protection headings/denominators")
    for name, method in (("Full", "full"), ("No cache check", "no_cache_check"), ("No receipt handling", "no_receipt_handling")):
        row = find_row(label, name)
        require(len(row) == 4, "Protection column count")
        value = evidence_one(evidence["protections"], intervention=method)
        require(value["cases"] == 224 and value["duplicates_executed_cases"] == 0, "Protection case count/gateway qualification")
        for index, field in enumerate(("safe_complete_cases", "correct_stop_cases", "duplicate_attempts_cases"), 1):
            eq(label, name, field, row[index], value[field])
    details[label]["checked_rows"] = 3

    label = "tab:causal"
    require(len(tables[label]["rows"]) == 7 and tables[label]["rows"][0][1] == "Passing programs/7", "Causal rows/denominator")
    causal_rows = [("Original, 20,000-step limit", "original", 20000), ("Original, 80,000-step limit", "original", 80000),
                   ("Remove only inactive dependencies", "dependencies", 20000), ("Remove only inactive conflicts", "conflicts", 20000),
                   ("Remove both inactive relations", "both", 20000), ("Correct reference plus extra relations", "injected_reference", 20000)]
    for name, variant, budget in causal_rows:
        value = evidence_one(evidence["causal"]["aggregate_rows"], variant=variant, per_execution_step_limit=budget)
        require(value["cases"] == 7, "Causal evidence denominator")
        eq(label, name, "passing", find_row(label, name)[1], value["safe"])
    details[label]["checked_rows"] = 6

    label = "tab:validation"
    require(len(tables[label]["rows"]) == 4 and tables[label]["rows"][0][1] == "Detected/96", "Validation rows/denominator")
    require("false rejection is 0/16" in tables[label]["body"], "Correct-reference false-rejection caption")
    for name, method in (("Random fresh inputs", "random"), ("Larger inputs", "larger_input"), ("Order, labels, decoys", "targeted")):
        value = evidence_one(evidence["validation_main"]["strategy_rows"], strategy=method)
        require((value["variants"], value["correct_controls"], value["false_rejections"]) == (96, 16, 0), "Validation evidence denominators/control result")
        row = find_row(label, name)
        require(len(row) == 4, "Validation column count")
        eq(label, name, "detected", row[1], value["detected"])
        eq(label, name, "accepted", row[2], value["accepted"])
        eq(label, name, "accepted_final_failure_fraction", row[3], f'{value["accepted_final_failures"]}/{value["accepted"]}')
    details[label]["checked_rows"] = 3

    embedded = bibliography_block(tex)
    separate = bibliography_block(references)
    require(embedded == separate, "Embedded bibliography differs from references.tex (ignoring whitespace/comments/layout trigger)")
    bibkeys = re.findall(r"\\bibitem\{([^{}]+)\}", embedded)
    require(len(bibkeys) == len(set(bibkeys)) == 19, "Exactly 19 unique bibliography keys required")
    require(set(bibkeys) == EXPECTED_CITATIONS, "Unexpected/missing bibliography keys")
    cited = {key.strip() for group in re.findall(r"\\cite(?:\[[^\]]*\])*\{([^{}]*)\}", tex) for key in group.split(",")}
    require(cited == EXPECTED_CITATIONS, "All 19 keys must be cited; no undefined citations")
    return {"table_count_checked": len(details), "table_rows_checked": sum(v["checked_rows"] for v in details.values()),
            "literal_cell_checks": len(checks), "tables": details, "cells": checks,
            "rounding": "Table IV probabilities multiplied by 100, then rounded to one decimal percentage point with Decimal ROUND_HALF_EVEN; optional leading plus signs ignored. All other cells exact.",
            "citations": {"expected_keys": sorted(EXPECTED_CITATIONS), "cited_keys": sorted(cited),
                          "bibliography_keys_in_order": bibkeys, "unique_cited_keys": len(cited),
                          "undefined_keys": [], "uncited_entries": [], "duplicate_entries": [],
                          "embedded_bibliography_matches_references": True,
                          "comparison": "Whitespace and TeX comments normalized; IEEEtriggeratref ignored"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check saved QA without writing")
    args = parser.parse_args()
    paths = {"paper": HERE / "paper.tex", "references": HERE / "references.tex",
             "evidence": HERE / "evidence/key_results.json"}
    data = {key: path.read_bytes() for key, path in paths.items()}
    result = audit(data["paper"].decode("utf-8-sig"), data["references"].decode("utf-8-sig"), json.loads(data["evidence"]))
    require(all(path.read_bytes() == data[key] for key, path in paths.items()), "Inputs changed during QA")
    report = {"schema": "skill-recovery-v15-table-qa-v1", "status": "passed", **result,
              "inputs": {key: {"path": path.relative_to(HERE).as_posix(), "sha256": sha(data[key])} for key, path in paths.items()},
              "checker_sha256": sha(Path(__file__).read_bytes()), "network_requests": 0,
              "experiment_execution": False,
              "scope": "Checks manuscript literal table transcription and citation/bibliography consistency against saved evidence; does not independently validate external references or re-run experiments."}
    output = HERE / "qa/table_checks.json"
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.check:require(output.read_bytes() == encoded, "Saved table QA is stale")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(encoded)
    print(json.dumps({"status": "passed", "mode": "check" if args.check else "write",
                      "tables": result["table_count_checked"], "rows": result["table_rows_checked"],
                      "literal_cell_checks": result["literal_cell_checks"], "citations": result["citations"]["unique_cited_keys"],
                      "embedded_bibliography_matches": True, "network_requests": 0}, indent=2))


if __name__ == "__main__":
    main()
