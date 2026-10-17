"""Read-only checks of research evidence plus paper-specific PDF checks.

Writes only verification/report_checks.json in this new paper directory.
Requires pypdf; no credentials, network, experiment execution, or API calls.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import re
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
checks = []
inputs = {}

def check(name, actual, expected):
    equal = math.isclose(actual, expected, abs_tol=1e-10) if isinstance(expected, float) else actual == expected
    if not equal:
        raise AssertionError((name, actual, expected))
    checks.append({"name": name, "actual": actual, "expected": expected})

def read(rel):
    path = ROOT / rel
    inputs[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text(encoding="utf-8"))

def table(rel):
    path = ROOT / rel
    inputs[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return list(csv.DictReader(path.open(encoding="utf-8")))

def row(rows, **filters):
    hits = [r for r in rows if all(r.get(k) == str(v) for k, v in filters.items())]
    check("unique row: " + str(filters), len(hits), 1)
    return hits[0]

release = read("results/phase11/provenance/release_hashes.json")
baseline = read("results/phase11/provenance/baseline.json")["files"]
for label, hashes in [("Phase 11 release", release), ("earlier baseline", baseline)]:
    print(f"Checking {len(hashes)} {label} files...", flush=True)
    mismatches = [rel for rel, expected in hashes.items()
                  if not (ROOT/rel).is_file() or hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() != expected]
    check(label + " mismatches", mismatches, [])
    check(label + " count", len(hashes), 8115 if label == "Phase 11 release" else 37907)
    print(f"Preserved: {len(hashes)} {label} files.", flush=True)

summary = read("results/phase11/analysis/summary.json")
check("semantic comparisons", summary["input_rows"]["semantics"], 1006)
for k, v in {"policies":12320, "recovery":15696, "integrated":13824, "streams":288, "matched_prefix":670}.items():
    check(k, summary["input_rows"][k], v)
api = read("results/phase11/api/summary.json")
for key, value in {"confirmed_provider_responses":1605, "valid_decisions":1603,
                   "valid_streams":286, "increment_upper_usd":3.765178875,
                   "remaining_usd":6.898587}.items():
    check(key, api[key], value)
check("certificate statuses", api["certificate_statuses"], {"certified":230, "infeasible":43, "unknown":15})
streams = table("results/phase11/analysis/stream_detail.csv")
check("certifiable unknown", sum(int(r["budget_limited_certifiable"]) for r in streams), 10)
check("infeasible unknown", sum(int(r["unresolved_robust_infeasibility"]) for r in streams), 5)

policies = table("results/phase11/analysis/policy_conditions.csv")
for stop, metric, expected in [(False,"query_count",7.75),(True,"query_count",3.013888888888889),
                               (False,"completion",.8194444444444444),(True,"completion",.8194444444444444),
                               (False,"interpreter_steps",29.),(True,"interpreter_steps",6.111111111111111)]:
    r = row(policies, cohort="combined", budget=12, policy="observe_cover", stop=stop, metric=metric)
    check(f"observe-cover {stop} {metric}", float(r["estimate"]), expected)
cmp = table("results/phase11/figures/matched_model_comparison.csv")
for model, side, completed, queries in [("gpt-6-luna","heuristic",30,3.),
                                       ("gpt-6-luna","model",29,4.583333333333333),
                                       ("gpt-4.1-mini","model",28,5.638888888888889)]:
    for metric, value in [("completion", completed/36), ("query_count", queries)]:
        r = row(cmp, cohort="combined", model=model, side=side, metric=metric)
        check(f"matched {model} {side} {metric}", float(r["estimate"]), value)
physical = table("results/phase11/physical_goal/conditions.csv")
for policy, metric, expected in [("strict_stop","physical_goal",.3888888888888889),
                                 ("terminal_status","physical_goal",.8194444444444444),
                                 ("strict_stop","authorized_goal",0.),
                                 ("terminal_status","authorized_goal",.8194444444444444)]:
    r = row(physical, cohort="combined", fault="ambiguous_after", status_budget=1, policy=policy, metric=metric)
    check(f"recovery {policy} {metric}", float(r["estimate"]), expected)

audit = read("results/phase11/trace_audit/summary.json")["all_rows"]
for k,v in {"rows":42846,"non_null_executions":28482,"null_executions":14364}.items():
    check(k,audit[k],v)
for k,v in {"observed_committed_events":63622,"observed_mutation_commits":50608,
            "observed_unauthorized_commits":0,"observed_duplicate_logical_mutations":0}.items():
    check(k,audit["totals"][k],v)

tex = (HERE/"paper.tex").read_text(encoding="utf-8")
refs = (HERE/"references.tex").read_text(encoding="utf-8")
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}",tex,re.S).group(1).strip()
abstract_words = len(abstract.split())
check("abstract 150-200 whitespace words", 150 <= abstract_words <= 200, True)
check("abstract one paragraph", "\n\n" in abstract, False)
keys = re.findall(r"\\bibitem\{(.*?)\}",refs)
citations = []
for group in re.findall(r"\\cite\{(.*?)\}",tex):
    for key in group.split(","):
        if key not in citations: citations.append(key)
check("20 references", len(keys), 20)
check("reference order matches first citation", citations, keys)
check("IEEE class", r"\documentclass[conference]{IEEEtran}" in tex, True)

pdf = PdfReader(HERE/"output"/"paper.pdf")
texts = [p.extract_text() for p in pdf.pages]
ref_start = next(i for i,s in enumerate(texts) if s.lstrip().startswith("REFERENCES"))
check("body 10-12 pages", 10 <= ref_start <= 12, True)
check("references at most one page", len(pdf.pages)-ref_start, 1)
check("no unresolved references", any("??" in s for s in texts), False)
check("no replacement glyphs", any("\ufffd" in s for s in texts), False)
check("no draft placeholders", any(w in tex for w in ["TODO", "TBD", "PLACEHOLDER"]), False)
log=(HERE/"output"/"paper.log").read_text(encoding="utf-8",errors="replace")
check("no overfull horizontal boxes", "Overfull \\hbox" in log, False)
check("no undefined citations", "Citation" in log and "undefined" in log, False)

result={"status":"pass", "checks":checks,"abstract_whitespace_words":abstract_words,
        "body_pages":ref_start,"reference_pages":len(pdf.pages)-ref_start,
        "references":len(keys),"peer_reviewed_references":14,
        "peer_reviewed_status_basis":"literature-audit.md; primary-source manual audit",
        "source_sha256":inputs,
        "paper_source_sha256":hashlib.sha256(tex.encode()).hexdigest(),
        "pdf_sha256":hashlib.sha256((HERE/"output"/"paper.pdf").read_bytes()).hexdigest(),
        "scope":"Checks transcription, selected statistics, layout invariants and preserved hashes; not a new experiment or complete semantic proof."}
(HERE/"verification"/"report_checks.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps({k:result[k] for k in ["status","abstract_whitespace_words","body_pages","reference_pages","references"]}))
print(f"{len(checks)} checks passed; old research files unchanged; no network or provider calls.")
