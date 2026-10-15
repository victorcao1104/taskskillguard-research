"""Freeze an additive matched line-ID repair before explicitly acquiring it.

Without --execute this script reads no credential and makes no API request.
Acquisition uses the existing corrected campaign ledger and retains first raw
responses; retries or failure-conditioned resampling are prohibited.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tsg.budget_v4 import initialize_campaign, UPPER_PRICES
from tsg.discovery_v4b import SYSTEM_PROMPT, build_payload, schema, parse_record
from tsg.models import load_key, make_request
from tsg.models_v3 import ClientV3

MODELS = ('gpt-6-luna', 'gpt-4.1-mini')
FOLLOWUP_SUBCAP_USD = 1.5
ACQUISITION = Path('results/phase4_discovery_followup/acquisition')
API = Path('results/phase4_discovery_followup/api')
LEDGER = Path('results/phase4/api/budget.jsonl')
SOURCE_FILES = ('scripts/run_discovery_phase4b.py', 'src/tsg/discovery_v4b.py',
                'docs/phase4_discovery_followup_design.md', 'src/tsg/discovery_v4.py',
                'src/tsg/budget_v4.py', 'src/tsg/models.py', 'src/tsg/models_v3.py',
                'src/tsg/phase_protocol_v3.py', 'results/phase4/acquisition/jobs.jsonl',
                'data/phase4/real_prepared.jsonl')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def rows_bytes(rows):
    return ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows).encode('utf-8')


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def immutable(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('PRESERVED_FILE_MISMATCH: ' + str(path))
        return
    with path.open('xb') as stream:
        stream.write(data)


def request_hash(request, replicate=0):
    # Exactly the ClientV3 fingerprint, including intentional JSON whitespace.
    return sha(json.dumps({'request': request, 'replicate': replicate},
                          sort_keys=True, ensure_ascii=False).encode('utf-8'))


def exact_request(job):
    request = make_request(job['model'], job['system'], job['prompt'], job['max_output'])
    request['text']['format'] = {'type': 'json_schema', 'name': 'tsg_response_v3',
                                 'strict': True, 'schema': job['schema']}
    return request


def build_jobs(primary_jobs, prepared):
    original = [job for job in primary_jobs if job.get('track') == 'discovery']
    if len(original) != 24 or len({job['job_id'] for job in original}) != 24:
        raise ValueError('MATCHED_GRID_REQUIRES_ORIGINAL_24_JOBS')
    by_case = defaultdict(dict)
    for job in original:
        if job['model'] not in MODELS or job['model'] in by_case[job['case_id']]:
            raise ValueError('MATCHED_GRID_MODEL_DUPLICATE')
        by_case[job['case_id']][job['model']] = job
    if len(by_case) != 12 or any(set(value) != set(MODELS) for value in by_case.values()):
        raise ValueError('MATCHED_GRID_REQUIRES_TWELVE_MODEL_PAIRS')
    sources_by_id = {row['skill_id']: row for row in prepared}
    if len(sources_by_id) != len(prepared):
        raise ValueError('MATCHED_GRID_DUPLICATE_SOURCE_ID')
    jobs, sources = [], []
    for case_id in sorted(by_case, key=lambda value: sha(value.encode())):
        if case_id not in sources_by_id:
            raise ValueError('MATCHED_GRID_MISSING_SOURCE')
        source = sources_by_id[case_id]
        if source['actions']:
            raise ValueError('MATCHED_GRID_NOT_ZERO_CANDIDATE_SOURCE')
        files = source['files']
        prompt, response_schema = build_payload(files), schema(files)
        source_id = 's_' + sha(('phase4b-source:' + case_id).encode())[:16]
        hashes = {file: sha(text.encode('utf-8')) for file, text in sorted(files.items())}
        originals = by_case[case_id]
        for model in MODELS:
            old = originals[model]
            old_source = json.loads(old['prompt']).get('source')
            if old_source != files:
                raise ValueError('MATCHED_SOURCE_MISMATCH')
            job = {'job_id': 'discovery4b_' + sha(old['job_id'].encode())[:20],
                   'track': 'discovery_followup', 'case_id': case_id, 'source_id': source_id,
                   'original_job_id': old['job_id'], 'original_request_hash': old['expected_request_hash'],
                   'family': source['family_id'], 'split': source['split'], 'model': model,
                   'context': 'nonexecuting_candidate_discovery_protocol_repair', 'view': 'line_ids',
                   'system': SYSTEM_PROMPT, 'prompt': prompt, 'schema': deepcopy(response_schema),
                   'max_output': 4000, 'replicate': 0, 'source_sha256': hashes}
            request = exact_request(job)
            upper = len(json.dumps(request, ensure_ascii=False).encode('utf-8')) + 4096
            if upper > 272000:
                raise ValueError('SHORT_CONTEXT_BOUND_EXCEEDED')
            ip, op = UPPER_PRICES[model]
            job.update(request=request, expected_request_hash=request_hash(request), input_token_upper=upper,
                       reservation_upper_usd=(upper * ip + 4000 * op) / 1e6)
            jobs.append(job)
        sources.append({'case_id': case_id, 'source_id': source_id, 'files': files, 'source_sha256': hashes,
                        'original_job_ids': {model: originals[model]['job_id'] for model in MODELS}})
    jobs.sort(key=lambda job: sha(job['job_id'].encode()))
    if len({job['expected_request_hash'] for job in jobs}) != 24:
        raise ValueError('MATCHED_GRID_DUPLICATE_REQUEST_HASH')
    return jobs, sources


def validate_reservation(jobs, before, cap):
    total = sum(job['reservation_upper_usd'] for job in jobs)
    if total > FOLLOWUP_SUBCAP_USD:
        raise ValueError('FOLLOWUP_SUBCAP_EXCEEDED')
    if before + total > cap:
        raise ValueError('CAMPAIGN_REMAINDER_EXCEEDED')
    return total


def load_frozen(root, budget):
    out = root / ACQUISITION
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    jobs, sources = rows(out / 'jobs.jsonl'), rows(out / 'sources.jsonl')
    if (sha((out / 'jobs.jsonl').read_bytes()) != manifest['jobs_sha256']
            or sha((out / 'sources.jsonl').read_bytes()) != manifest['sources_sha256']
            or sha((out / 'grid.jsonl').read_bytes()) != manifest['grid_sha256']):
        raise ValueError('FROZEN_GRID_MISMATCH')
    for file, digest in manifest['source_sha256'].items():
        if sha((root / file).read_bytes()) != digest:
            raise ValueError('SOURCE_SNAPSHOT_MISMATCH: ' + file)
    ledger = (root / LEDGER).read_bytes()
    if sha(ledger[:manifest['ledger_prefix_bytes']]) != manifest['ledger_prefix_sha256']:
        raise ValueError('SHARED_LEDGER_PREFIX_MISMATCH')
    if len(jobs) != 24 or len(sources) != 12:
        raise ValueError('MATCHED_GRID_INCOMPLETE')
    for job in jobs:
        if job['request'] != exact_request(job) or job['expected_request_hash'] != request_hash(job['request'], job['replicate']):
            raise ValueError('FROZEN_REQUEST_MISMATCH')
    # A resume only needs new reservations for requests without preserved raw
    # evidence. Cached errors/incomplete responses are reused, never retried.
    pending = [job for job in jobs if not (root / API / 'raw' / (job['expected_request_hash'] + '.json')).exists()]
    validate_reservation(jobs, 0, float('inf'))
    validate_reservation(pending, budget.total_cost, budget.limit)
    return jobs, manifest, budget


def prepare(root=ROOT):
    root = Path(root)
    budget, revision = initialize_campaign(root)
    out = root / ACQUISITION
    if (out / 'manifest.json').exists():
        return load_frozen(root, budget)
    jobs, sources = build_jobs(rows(root / 'results/phase4/acquisition/jobs.jsonl'),
                               rows(root / 'data/phase4/real_prepared.jsonl'))
    total = validate_reservation(jobs, budget.total_cost, budget.limit)
    grid = [{key: value for key, value in job.items() if key not in {'request', 'system', 'prompt', 'schema'}} for job in jobs]
    ledger = (root / LEDGER).read_bytes()
    manifest = {'version': 'phase4-discovery-followup-acquisition-v1', 'planned_jobs': 24,
                'sources': 12, 'models': list(MODELS), 'max_output': 4000, 'automatic_retries': 0,
                'registration': 'posthoc_protocol_repair_exploratory',
                'selection': 'all original 24 discovery jobs, same 12 sources and both models, without conditioning on outcomes',
                'max_workers': 4, 'followup_subcap_usd': FOLLOWUP_SUBCAP_USD,
                'additional_reservation_upper_usd': total, 'budget_before_upper_usd': budget.total_cost,
                'campaign_cap_usd': budget.limit, 'budget_ledger': LEDGER.as_posix(),
                'budget_revision': revision,
                'upper_prices_usd_per_million': {model: list(price) for model, price in UPPER_PRICES.items()},
                'ledger_prefix_bytes': len(ledger), 'ledger_prefix_sha256': sha(ledger),
                'source_sha256': {file: sha((root / file).read_bytes()) for file in SOURCE_FILES},
                'jobs_sha256': sha(rows_bytes(jobs)), 'grid_sha256': sha(rows_bytes(grid)),
                'sources_sha256': sha(rows_bytes(sources)), 'request_hashes_unique': 24,
                'opaque_source_mapping': {source['source_id']: source['case_id'] for source in sources},
                'opaque_job_mapping': {job['job_id']: job['original_job_id'] for job in jobs},
                'claim_limit': 'response validity and source anchoring by construction only; semantic accuracy is unverified'}
    immutable(out / 'sources.jsonl', rows_bytes(sources))
    immutable(out / 'jobs.jsonl', rows_bytes(jobs))
    immutable(out / 'grid.jsonl', rows_bytes(grid))
    immutable(out / 'manifest.json', json_bytes(manifest))
    return jobs, manifest, budget


def summarize(jobs, observations, primary):
    expected = {job['job_id'] for job in jobs}
    by_id = {row['job_id']: row for row in observations}
    if len(by_id) != len(observations) or not set(by_id) <= expected:
        raise ValueError('OBSERVATION_GRID_MISMATCH')
    original_ids = {job['original_job_id'] for job in jobs}
    original = [row for row in primary if row.get('job_id') in original_ids]
    def counts(rows):
        known = [row['usage'] for row in rows if isinstance(row.get('usage'), dict)
                 and all(type(row['usage'].get(key)) is int and row['usage'][key] >= 0
                         for key in ('input_tokens', 'output_tokens'))]
        return {'completed': len(rows), 'protocol_valid': sum(row['parsed']['protocol_valid'] for row in rows),
                'source_anchored_actions': sum(len(row['parsed'].get('actions', [])) for row in rows
                                                if row['parsed']['protocol_valid']),
                'input_tokens_observed': sum(usage['input_tokens'] for usage in known),
                'output_tokens_observed': sum(usage['output_tokens'] for usage in known),
                'usage_unavailable_jobs': len(rows) - len(known),
                'raw_statuses': dict(Counter(row.get('raw_status') or 'unknown' for row in rows)),
                'diagnostic_codes': dict(Counter(code for row in rows for code in set(row['parsed']['diagnostic_codes'])))}
    return {**counts(observations), 'planned': len(jobs), 'missing_jobs': sorted(expected - set(by_id)),
            'original_matched': {'planned': len(original_ids), **counts(original),
                                 'missing_jobs': sorted(original_ids - {row['job_id'] for row in original})},
            'by_model': {model: {'planned': sum(job['model'] == model for job in jobs),
                                 **counts([row for row in observations if row['model'] == model])} for model in MODELS},
            'registration': 'posthoc_protocol_repair_exploratory', 'semantic_accuracy': None,
            'source_anchoring': 'constructed from cited supplied line IDs, not semantic validation',
            'human_annotated': False, 'source_executed': False, 'coverage_complete': False}


def execute(jobs, budget, env_file, workers=4, root=ROOT):
    root, env_file = Path(root), Path(env_file)
    if not env_file.is_file() or not 1 <= workers <= 4:
        raise ValueError('EXPLICIT_EXISTING_ENV_FILE_AND_BOUNDED_WORKERS_REQUIRED')
    frozen_jobs, _, _ = load_frozen(root, budget)
    if jobs != frozen_jobs:
        raise ValueError('FROZEN_JOB_ARGUMENT_MISMATCH')
    sources = {source['case_id']: source['files'] for source in rows(root / ACQUISITION / 'sources.jsonl')}
    def check_raw(raw, job):
        if (raw.get('request_hash') != job['expected_request_hash'] or raw.get('request') != job['request']
                or raw.get('replicate') != job['replicate']):
            raise ValueError('ACTUAL_REQUEST_HASH_OR_CONTENT_MISMATCH')
    def preserved(job):
        saved = json.loads((root / API / 'jobs' / (job['job_id'] + '.json')).read_text(encoding='utf-8'))
        raw_path = root / API / 'raw' / (job['expected_request_hash'] + '.json')
        if not raw_path.exists():
            raise ValueError('PRESERVED_JOB_RAW_MISSING')
        raw = json.loads(raw_path.read_text(encoding='utf-8'))
        check_raw(raw, job)
        if (saved['request_hash'] != job['expected_request_hash']
                or any(saved.get(key) != job[key] for key in ('job_id', 'case_id', 'source_id', 'original_job_id', 'model'))
                or saved['parsed'] != parse_record(raw, sources[job['case_id']])):
            raise ValueError('PRESERVED_JOB_MISMATCH')
        return saved
    summary_path, observations_path = root / API / 'summary.json', root / API / 'observations.jsonl'
    if summary_path.exists() and observations_path.exists():
        old_observations = rows(observations_path)
        by_id = {row['job_id']: row for row in old_observations}
        if len(by_id) != len(jobs) or len(old_observations) != len(jobs):
            raise ValueError('PRESERVED_OBSERVATIONS_INCOMPLETE')
        for job in jobs:
            if by_id.get(job['job_id']) != preserved(job):
                raise ValueError('PRESERVED_OBSERVATIONS_MISMATCH')
        # Keep the first completed summary's spend snapshot even when another
        # authorized campaign later appends to the shared ledger.
        return json.loads(summary_path.read_text(encoding='utf-8'))
    client = ClientV3(load_key(env_file), root / API / 'raw', budget)
    def one(job):
        out = root / API / 'jobs' / (job['job_id'] + '.json')
        if out.exists():
            return preserved(job)
        if exact_request(job) != job['request']:
            raise ValueError('ACTUAL_REQUEST_CONTENT_MISMATCH')
        raw = client.call(job['model'], job['system'], job['prompt'], tag=job['job_id'],
                          max_output=job['max_output'], replicate=job['replicate'], response_schema=job['schema'])
        check_raw(raw, job)
        parsed = parse_record(raw, sources[job['case_id']])
        result = {key: job[key] for key in ('job_id', 'track', 'case_id', 'source_id', 'original_job_id',
                                           'family', 'split', 'context', 'view', 'model')}
        result.update(request_hash=raw['request_hash'], raw_ref=(API / 'raw' / (raw['request_hash'] + '.json')).as_posix(),
                      raw_status=raw.get('status'), usage=raw.get('usage'), parsed=parsed,
                      elapsed_seconds=raw.get('elapsed_seconds'))
        immutable(out, json_bytes(result))
        return result
    completed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, job) for job in jobs]
        for future in as_completed(futures):
            completed.append(future.result())
            print(json.dumps({'completed': len(completed), 'planned': len(jobs),
                              'cumulative_upper_usd': budget.total_cost}), flush=True)
    completed.sort(key=lambda row: row['job_id'])
    original_path = root / 'results/phase4/api/observations.jsonl'
    summary = summarize(jobs, completed, rows(original_path) if original_path.exists() else [])
    summary.update(cumulative_upper_usd=budget.total_cost, campaign_cap_usd=budget.limit)
    immutable(root / API / 'observations.jsonl', rows_bytes(completed))
    immutable(root / API / 'summary.json', json_bytes(summary))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    jobs, manifest, budget = prepare()
    print(json.dumps({key: manifest[key] for key in ('planned_jobs', 'sources', 'additional_reservation_upper_usd',
                                                  'budget_before_upper_usd', 'campaign_cap_usd')}), flush=True)
    if args.execute:
        if args.env_file is None:
            raise ValueError('EXPLICIT_EXISTING_ENV_FILE_REQUIRED')
        print(json.dumps(execute(jobs, budget, args.env_file, args.workers)), flush=True)
