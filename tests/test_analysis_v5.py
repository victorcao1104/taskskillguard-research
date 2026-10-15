"""Offline analysis tests use fabricated outcomes, never the live campaign."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "scripts" / "analyze_phase5.py"
    assert path.exists(), "prospective offline analyzer is not implemented"
    spec = importlib.util.spec_from_file_location("analysis_phase5_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


AXES = ("action_valid", "authorized", "implementation_necessary", "task_necessary")


def case():
    labels = dict.fromkeys(AXES, "yes")
    labels["authorized"] = "unknown"
    return {"case_id":"q001", "family":"family_one", "split":"dev",
            "public":{"canonical_nodes":[{"id":"n123","candidate":True,"claim":{"operation":"file.read","resource":"in","resource_status":"resolved"}}],
                      "contexts":{"missing":{"grant":{"mode":"underspecified","rules":[]}}}},
            "private":{"truth":{"missing":{"n123":{"labels":labels,"unknowns":[{"dimension":"authorized","reason":"missing_scope"}]}}}}}


def job(view="table", rep=0):
    return {"job_id":f"job-{view}-{rep}", "track":"synthetic", "case_id":"q001", "family":"family_one", "split":"dev",
            "context":"missing", "model":"test-model", "view":view, "replicate":rep,
            "ids":["n123"], "expected_request_hash":"abc"}


def observation(planned, auth="unknown"):
    j={"candidate_id":"n123", **dict.fromkeys(AXES,"yes"), "authorized":auth,
       "reason":"source and grant", "unknowns":[]}
    if auth == "unknown":
        j["unknowns"]=[{"dimension":"authorized","reason":"missing_scope","missing_evidence":"exact grant","next_action":"obtain grant"}]
    return {**{k:v for k,v in planned.items() if k not in ("ids","expected_request_hash")},
            "request_hash":"abc", "raw_status":"completed", "usage":{"input_tokens":100},
            "parsed":{"protocol_valid":True,"diagnostic_codes":[],"judgments":[j]}}


def test_planned_grid_keeps_missing_and_checks_nested_truth():
    a=module(); jobs=[job(),job("oracle")]
    rows,status=a.score_grid(jobs,[observation(jobs[0])],[case()])
    assert len(rows)==8 and sum(r["prediction"] is None for r in rows)==4
    assert a.metric_summary(rows)["exact_accuracy"]==.5
    assert [s["status"] for s in status]==["valid","missing"]
    with pytest.raises(ValueError): a.score_grid(jobs,[observation(job("auto"))],[case()])
    changed=copy.deepcopy(jobs); changed[0]["ids"]=["wrong"]
    with pytest.raises(ValueError): a.score_grid(changed,[],[case()])


def test_unknown_metrics_distinguish_avoidable_and_unsupported_decisions():
    a=module()
    rows=[{"gold":"yes","prediction":"unknown"}, {"gold":"unknown","prediction":"yes","gold_reason":"missing_scope"},
          {"gold":"unknown","prediction":"unknown","gold_reason":"missing_scope","predicted_reason":"missing_scope","evidence_fields_present":True},
          {"gold":"no","prediction":None}]
    score=a.metric_summary(rows)
    assert score["avoidable_unknown_count"]==1 and score["avoidable_unknown_rate_known"]==.5
    assert score["unsupported_decision_count"]==1 and score["unsupported_decision_rate_unknown"]==.5
    assert score["unknown_reason_correct"]==1 and score["unknown_reason_accuracy_planned"]==.5
    assert score["unknown_evidence_presence_is_semantic_validity"] is False


def test_invalid_unknown_records_cannot_receive_partial_credit():
    a=module(); j=job(); obs=observation(j)
    obs["parsed"]["judgments"][0]["unknowns"]=[]
    rows,status=a.score_grid([j],[obs],[case()])
    assert status[0]["status"]=="protocol_invalid"
    assert all(r["prediction"] is None for r in rows)
    obs=observation(j); obs["context"]="deny"
    rows,status=a.score_grid([j],[obs],[case()])
    assert "OBSERVATION_METADATA_MISMATCH" in status[0]["diagnostics"]


def test_family_bootstrap_is_paired_deterministic_and_not_label_resampling():
    a=module()
    rows=[{"family":"large","gold":"yes","left_prediction":"yes","right_prediction":"no"}]*100
    rows += [{"family":"small","gold":"yes","left_prediction":"no","right_prediction":"yes"}]
    result=a.cluster_difference(rows, replicates=2000)
    assert result==a.cluster_difference(rows,replicates=2000)
    assert result["difference_left_minus_right"]==99/101
    assert result["family_macro_difference"]==0
    assert result["families"]==2 and result["ci95_percentile"]==[-1,1]
    assert "eight" not in result["caution"]
    assert a.cluster_difference(rows,"unknown_truth_accuracy",20)["difference_left_minus_right"] is None


def test_pairing_keeps_contexts_and_replicates_out_of_main_estimate():
    a=module(); jobs=[job(v,r) for v in ("table","oracle") for r in (0,1,2)]
    rows,_=a.score_grid(jobs,[observation(j) for j in jobs],[case()])
    paired=a.pair_labels(rows,"oracle","table")
    assert len(paired)==4 and {r["context"] for r in paired}=={"missing"}
    assert all(r["left_prediction"]==r["right_prediction"] for r in paired)


def test_reliability_counts_invalid_replicates_in_planned_denominator():
    a=module(); jobs=[job(rep=i) for i in range(3)]
    observations=[observation(jobs[0]),observation(jobs[1])]
    rows,status=a.score_grid(jobs,observations,[case()])
    result=a.reliability(rows,status)
    assert result["overall"]["planned_groups"]==1
    assert result["overall"]["planned_runs"]==3 and result["overall"]["valid_runs"]==2
    assert result["overall"]["all_valid_consistent_groups"]==0
    assert result["overall"]["planned_replicate_pairs"]==3
    assert result["overall"]["available_pair_agreement"]==1


def test_symbolic_comparator_uses_public_claims_exact_rules_and_dynamic_abstention():
    a=module(); claim={"operation":"network.post","resource":"https://a.invalid","payload":{"kind":"constant","value":"a"}}
    grant={"mode":"closed_deny","rules":[copy.deepcopy(claim)]}
    assert a.symbolic_authorization(claim,grant)=="yes"
    altered=copy.deepcopy(claim); altered["payload"]["value"]="b"
    assert a.symbolic_authorization(altered,grant)=="no"
    assert a.symbolic_authorization({**claim,"resource":None},grant)=="unknown"
    assert a.symbolic_authorization(claim,{"mode":"underspecified","rules":[]})=="unknown"


def test_graph_audit_recomputes_counts_and_token_audit_does_not_assume_billed_equality():
    a=module(); edge={"source":"a","target":"b","type":"DATA"}
    rows=[{"case_id":"q001","family":"f","split":"dev","auto_edges":[edge],"oracle_edges":[edge],"true_positive":99}]
    audit=a.graph_audit(rows,{"q001":{"nodes":[{},{}],"edges":[edge,{"source":"a","target":"b","type":"ORDER"}]}})
    assert audit["overall"]["true_positive"]==1 and not audit["cases"][0]["stored_counts_match"]
    assert audit["cases"][0]["raw_extractor_edges"]==2
    jobs=[job("oracle"),job("length_control")]
    observed=[observation(j) for j in jobs]; observed[1]["usage"]["input_tokens"]=103
    controls=[{"case_id":"q001","context":"missing","local_tokens":{"oracle":50,"length_control":50},"base_equal":True}]
    tokens=a.token_audit(jobs,observed,controls)
    assert tokens["pairs"][0]["local_equal"] is True
    assert tokens["pairs"][0]["actual_oracle_minus_control"]==-3


def test_publication_is_create_only_and_serialization_deterministic(tmp_path):
    a=module(); out=tmp_path/"analysis"
    package={"summary.json":{"b":2,"a":1},"rows.jsonl":[{"id":"x"}]}
    a.publish_package(out,package)
    before={p.name:p.read_bytes() for p in out.iterdir()}
    with pytest.raises(FileExistsError): a.publish_package(out,package)
    assert before=={p.name:p.read_bytes() for p in out.iterdir()}


def test_complete_package_separates_main_from_repeat_and_retains_missing():
    a=module()
    jobs=[job(v) for v in a.VIEWS]
    jobs += [job(v,r) for v in ("table","oracle") for r in (1,2)]
    observed=[observation(j) for j in jobs if j["view"] != "auto"]
    package=a.analyze_inputs(jobs,observed,[case()],[],[],{},replicates=20,expected_jobs=None)
    summary=package["summary.json"]
    assert summary["planned_jobs"]==9 and summary["main_jobs"]==5 and summary["repeat_jobs"]==4
    assert summary["main_protocol"]["overall"]["missing_jobs"]==1
    assert summary["complete_observation_grid"] is False
    assert len(package["label_scores.jsonl"])==20
    assert len(package["repeat_label_scores.jsonl"])==16
    assert len({(r["left"],r["right"]) for r in package["paired_comparisons.jsonl"]})==6


def test_unknown_reason_code_and_malformed_judgment_rechecked_independently():
    a=module(); j=job(); obs=observation(j)
    obs["parsed"]["judgments"][0]["unknowns"][0]["reason"]="invented_reason"
    _,status=a.score_grid([j],[obs],[case()])
    assert not status[0]["valid"]
    obs=observation(j); obs["parsed"]["judgments"]=[None]
    _,status=a.score_grid([j],[obs],[case()])
    assert not status[0]["valid"]


def test_full_588_grid_integration_on_fabricated_outcomes_has_exact_denominators():
    a=module()
    cases=a.read_rows(ROOT/"data/phase5/reasoning_cases_v2.jsonl")
    jobs=[]; observations=[]
    repeats={c["case_id"]:("allow","deny","missing")[i%3] for i,c in enumerate(cases[:6])}
    for c in cases:
        for context in ("allow","deny","missing"):
            ids=list(c["private"]["truth"][context])
            for view in a.VIEWS:
                for model in ("fabricated-A","fabricated-B"):
                    reps=(0,1,2) if repeats.get(c["case_id"])==context and view in ("table","oracle") else (0,)
                    for rep in reps:
                        j={"job_id":f'{c["case_id"]}-{context}-{view}-{model}-{rep}',"track":"synthetic",
                           "case_id":c["case_id"],"family":c["family"],"split":c["split"],"context":context,
                           "model":model,"view":view,"replicate":rep,"ids":ids,"expected_request_hash":"fabricated",
                           "prompt":json.dumps({"candidate_ids":ids,"goal":"fixture"})}
                        judgments=[]
                        for cid,t in c["private"]["truth"][context].items():
                            judgments.append({"candidate_id":cid,**t["labels"],"reason":"fabricated test oracle",
                                "unknowns":[{k:u[k] for k in ("dimension","reason","missing_evidence","next_action")} for u in t["unknowns"]]})
                        jobs.append(j)
                        observations.append({**{k:j[k] for k in ("job_id",*a.META)},"request_hash":"fabricated","raw_status":"completed",
                            "parsed":{"protocol_valid":True,"diagnostic_codes":[],"judgments":judgments}})
    edges=[{"case_id":c["case_id"],"family":c["family"],"split":c["split"],"auto_edges":c["private"]["oracle_edges"],"oracle_edges":c["private"]["oracle_edges"]} for c in cases]
    package=a.analyze_inputs(jobs,observations,cases,edges,[],{},replicates=5)
    assert package["summary.json"]["planned_jobs"]==588
    assert package["summary.json"]["main_protocol"]["overall"]["valid_jobs"]==540
    assert len(package["label_scores.jsonl"])==6000
    assert package["reliability.json"]["overall"]["planned_runs"]==72
    assert package["reliability.json"]["overall"]["all_valid_consistent_groups"]==24
    assert all(r["exact_accuracy"]==1 for r in package["summary.json"]["synthetic"]["overall_by_axis"])
    assert package["graph_audit.json"]["overall"]["true_positive"]==42
    sensitivity=package["sensitivity_q017_excluded.json"]
    assert sensitivity["excluded_case_ids"]==["q017"]
    assert sensitivity["families"]==17 and sensitivity["main_protocol"]["planned_jobs"]==510
    assert sensitivity["main_labels"]==5760
    assert all(r["families"]==17 for r in package["sensitivity_q017_paired_comparisons.jsonl"] if r["split"]=="all")


def test_clarified_q017_has_abstract_sentinel_and_preserves_independent_labels():
    a=module()
    path=ROOT/"data/phase5/reasoning_q017_clarified.jsonl"
    assert path.is_file(), "The clarification must be separate from the frozen original"
    clarified=a.read_rows(path)
    original=next(c for c in a.read_rows(ROOT/"data/phase5/reasoning_cases_v2.jsonl") if c["case_id"]=="q017")
    assert len(clarified)==1
    updated=clarified[0]
    assert updated["private"]["truth"]==original["private"]["truth"]
    assert updated["public"]["files"]==original["public"]["files"]
    node=next(n for n in updated["public"]["canonical_nodes"] if n["id"]=="n430")
    assert node["omission_value"]["kind"]=="unknown_abstract_sentinel"
    assert "not a runtime value" in updated["public"]["finite_semantics"]["abstract_unknown"]
