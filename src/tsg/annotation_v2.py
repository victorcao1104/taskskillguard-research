"""Blind, provenance-linked HUMAN review packets and strict adjudication import.

This module never assigns labels. Identity and independence are attestations,
not remote identity verification. The coordinator must distribute one packet to
each person and keep the private key, model results and other reviews hidden.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

LABELS = {
    'skill': {'skill_unauthorized': ['yes', 'no', 'unknown']},
    'action': {'privilege_relevant': ['yes', 'no', 'unknown']},
    'action_in_task': {'authorized': ['authorized', 'unauthorized', 'unknown'],
                       'necessary': ['necessary', 'unnecessary', 'unknown'],
                       'triggered': ['yes', 'no', 'unknown']},
}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def neutral_trace(trace):
    """Allowlist observations; never expose oracle authorization/risk conclusions."""
    result = {}
    if 'events' in trace:
        result['events'] = [{k: e[k] for k in ('action_id', 'operation', 'resource', 'step', 'executed', 'sources', 'value_sha256') if k in e}
                            for e in trace['events']]
    for k in ('outputs', 'sink_events', 'goal_satisfied', 'local_goal_satisfied', 'execution_kind'):
        if k in trace:
            result[k] = trace[k]
    return result


def build_blind_packets(units, *, seed=76420261015, evidence_documents=None, scope='full'):
    units = list(units)
    if len({u['unit_id'] for u in units}) != len(units):
        raise ValueError('duplicate annotation unit')
    coordinator = {'schema_version': 2, 'scope': scope, 'units': {u['unit_id']: u for u in units}, 'packets': {}}
    packets = []
    for slot in ('rater_a', 'rater_b'):
        rows, mapping = [], {}
        for u in units:
            rid = _digest([seed, scope, slot, u['unit_id']])[:20]
            mapping[rid] = u['unit_id']
            rows.append({'row_id': rid, 'level': u['level'], 'evidence': u['evidence'],
                         'label_options': LABELS[u['level']]})
        random.Random(f'{seed}-{slot}-{scope}').shuffle(rows)
        packet_id = _digest([slot, scope, rows])[:24]
        packet = {'schema_version': 2, 'packet_id': packet_id, 'slot': slot, 'scope': scope, 'rows': rows,
                  'evidence_documents': evidence_documents or {}, 'labels_status': 'blank_human_work_pending'}
        coordinator['packets'][packet_id] = {'slot': slot, 'row_to_unit': mapping}
        packets.append(packet)
    return packets, coordinator


def _identity(identity, *, adjudicator=False):
    if identity.get('reviewer_kind') != 'human':
        raise ValueError('only a human reviewer attestation is accepted')
    for key in ('independent', 'no_ai_labels', 'no_prior_labels_seen'):
        if identity.get(key) is not True:
            raise ValueError(f'human independence attestation required: {key}')
    # At adjudication, no_prior_labels_seen means no model/generator labels; the
    # two blinded human judgments are intentionally disclosed for resolution.
    for key in ('reviewer_id', 'signed_name', 'completed_utc'):
        if not isinstance(identity.get(key), str) or not identity[key].strip():
            raise ValueError(f'missing identity field: {key}')
    try:
        stamp = datetime.fromisoformat(identity['completed_utc'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('timezone missing')
    except ValueError as exc:
        raise ValueError('completed_utc must be an ISO timestamp with timezone') from exc
    return identity['reviewer_id'].strip().casefold(), identity['signed_name'].strip().casefold()


def _validate_response(response, unit):
    labels = response.get('labels', {})
    if set(labels) != set(LABELS[unit['level']]):
        raise ValueError('all labels for the unit level are required; no extra labels')
    for key, options in LABELS[unit['level']].items():
        if labels[key] not in options:
            raise ValueError(f'invalid or blank human label: {key}')
    for key in ('evidence_reference', 'rationale'):
        if not isinstance(response.get(key), str) or not response[key].strip():
            raise ValueError(f'human {key} required')
    return {'labels': labels, 'evidence_reference': response['evidence_reference'],
            'rationale': response['rationale'], 'additional_actions': response.get('additional_actions', '')}


def _agreement(pairs):
    grouped = defaultdict(list)
    for item in pairs:
        for field in item['left']['labels']:
            grouped[item['level'], field].append((item['left']['labels'][field], item['right']['labels'][field]))
    result = []
    for (level, field), values in sorted(grouped.items()):
        n = len(values)
        a, b = Counter(x for x, _ in values), Counter(y for _, y in values)
        observed = sum(x == y for x, y in values) / n
        expected = sum(a[k] * b[k] for k in a.keys() | b.keys()) / n**2
        decided = [(x, y) for x, y in values if x != 'unknown' and y != 'unknown']
        result.append({'level': level, 'field': field, 'n': n, 'agreement_including_unknown': observed,
                       'cohen_kappa_including_unknown': (observed - expected) / (1 - expected) if expected < 1 else None,
                       'kappa_note': 'unknown is an explicit third category; undefined when expected agreement is one',
                       'n_unknown_pairs': n - len(decided), 'n_both_decided': len(decided),
                       'agreement_both_decided': sum(x == y for x, y in decided) / len(decided) if decided else None})
    return result


def import_reviews(key, submissions):
    if len(submissions) != 2:
        raise ValueError('two independent human submissions required')
    identities = [_identity(s.get('identity', {})) for s in submissions]
    if identities[0][0] == identities[1][0] or identities[0][1] == identities[1][1]:
        raise ValueError('two distinct human identities required')
    reviews, seen_packets = {}, set()
    for s in submissions:
        pid = s.get('packet_id')
        if pid not in key['packets'] or pid in seen_packets:
            raise ValueError('unknown or duplicate packet')
        seen_packets.add(pid)
        p = key['packets'][pid]
        rows = s.get('responses', [])
        ids = [r.get('row_id') for r in rows]
        if len(set(ids)) != len(ids) or set(ids) != set(p['row_to_unit']):
            raise ValueError('complete packet with exactly one response per row required')
        reviews[p['slot']] = {p['row_to_unit'][r['row_id']]: _validate_response(r, key['units'][p['row_to_unit'][r['row_id']]]) for r in rows}
    if set(reviews) != {'rater_a', 'rater_b'}:
        raise ValueError('one submission per independent rater slot required')
    paired = []
    for uid, unit in key['units'].items():
        left, right = reviews['rater_a'][uid], reviews['rater_b'][uid]
        paired.append({'unit_id': uid, 'level': unit['level'], 'left': left, 'right': right,
                       'disputed': left['labels'] != right['labels'] or bool(left['additional_actions']) or bool(right['additional_actions'])})
    n_disputes = sum(r['disputed'] for r in paired)
    return {'schema_version': 2, 'scope': key.get('scope', 'full'),
            'status': 'awaiting_third_human_adjudication' if n_disputes else 'independent_reviews_agree',
            'n_units_complete': len(paired), 'n_disputed_units': n_disputes,
            'identities': [s['identity'] for s in submissions], 'submission_sha256': [_digest(s) for s in submissions],
            'paired_reviews': paired, 'agreement': _agreement(paired),
            'identity_assurance': 'distinct normalized IDs/names and signed attestations; no biometric or external identity verification'}


def make_adjudication(key, imported):
    rows = []
    for item in imported['paired_reviews']:
        if not item['disputed']:
            continue
        unit = key['units'][item['unit_id']]
        rows.append({'row_id': _digest(['adjudication', item['unit_id']])[:20], 'level': unit['level'],
                     'evidence': unit['evidence'], 'label_options': LABELS[unit['level']],
                     'review_1': item['left'], 'review_2': item['right']})
    return {'schema_version': 2, 'packet_id': _digest(['adjudication', imported['submission_sha256']])[:24],
            'slot': 'adjudicator', 'scope': key.get('scope', 'full'), 'rows': rows}


def finalize_adjudication(key, imported, submission=None):
    disputed = [r for r in imported['paired_reviews'] if r['disputed']]
    resolutions = {}
    if disputed:
        if submission is None:
            raise ValueError('third human adjudication remains pending')
        ident = _identity(submission.get('identity', {}), adjudicator=True)
        earlier = [_identity(i) for i in imported['identities']]
        if any(ident[0] == old[0] or ident[1] == old[1] for old in earlier):
            raise ValueError('adjudicator must be a third distinct human')
        packet = make_adjudication(key, imported)
        expected = {_digest(['adjudication', r['unit_id']])[:20]: r['unit_id'] for r in disputed}
        rows = submission.get('responses', [])
        ids = [r.get('row_id') for r in rows]
        if submission.get('packet_id') != packet['packet_id'] or len(set(ids)) != len(ids) or set(ids) != set(expected):
            raise ValueError('complete matching adjudication packet required')
        for row in rows:
            uid = expected[row['row_id']]
            resolutions[uid] = _validate_response(row, key['units'][uid])
    labels = []
    for item in imported['paired_reviews']:
        unit = key['units'][item['unit_id']]
        value = resolutions.get(item['unit_id'], item['left'])
        labels.append({'unit_id': item['unit_id'], 'level': unit['level'], **unit.get('coordinator', {}),
                       **value, 'human_annotated': True,
                       'label_source': 'third_human_adjudication' if item['disputed'] else 'two_independent_humans_agree'})
    return {'schema_version': 2, 'scope': key.get('scope', 'full'), 'status': 'human_review_complete',
            'labels': labels, 'agreement_before_adjudication': imported['agreement'],
            'identities': imported['identities'] + ([submission['identity']] if disputed else []),
            'additional_action_note': 'Any newly identified missed actions require added units and a new independent two-rater review before accuracy/recall claims.'}


def collect_units(root, real_tasks_path):
    root = Path(root)
    cases = _read_jsonl(root / 'data/benchmark/synthetic_cases.jsonl')
    manifests = {r['skill_id']: r for r in _read_jsonl(root / 'data/manifests/skills_manifest.jsonl')}
    tasks = _read_jsonl(real_tasks_path)
    tasks_by_skill = defaultdict(list)
    for task in tasks:
        tasks_by_skill[task['skill_id']].append(task)
    # One real source per observed heuristic category is a bounded first review,
    # not a representative sample and not a replacement for the full packet.
    chosen = {}
    for sid in sorted(tasks_by_skill):
        chosen.setdefault(manifests[sid].get('category_heuristic', 'unknown'), sid)
    critical_real = set(chosen.values())
    replays = defaultdict(list)
    for row in _read_jsonl(root / 'results/mechanistic/replays.jsonl'):
        replays[row['case_id']].append(row)
    evidence, units, source_checks = {}, [], []
    def add(uid, level, ev, coord):
        units.append({'unit_id': uid, 'level': level, 'evidence': ev, 'coordinator': coord})
    for case in cases:
        cid = case['case_id']
        ref = 'source-' + _digest(['synthetic', cid])[:16]
        task_ref = 'task-' + _digest(cid)[:16]
        traces = []
        for replay in replays[cid]:
            traces.append({'target_action_id': replay['action_id'],
                           **{name: neutral_trace(replay[name]) for name in ('original', 'replay', 'reference') if name in replay}})
        evidence[ref] = {'source_kind': 'researcher_authored_synthetic_bundle_variant',
                         'files': {'SKILL.md': {'text': case['skill_text'], 'sha256': hashlib.sha256(case['skill_text'].encode()).hexdigest()}},
                         'trusted_tasks': [{'task_ref': task_ref, 'text': case['trusted_prompt']}],
                         'fixture': {'input_text': case['input_text'], 'requested_output': case['expected_output'],
                                     'oracle_version': case['oracle_version']},
                         'traces': traces,
                         'trace_note': 'Observed fixture execution and goal checks; not authorization labels. Replay failure alone does not establish necessity.'}
        critical = '-0-' in cid and case['scenario'] in {'high', 'optional_cache', 'post_task_reuse'}
        coord = {'track': 'synthetic', 'case_id': cid, 'skill_id': case['skill_id'],
                 'family_id': case['family_id'], 'critical': critical,
                 'critical_reason': 'authorized send / optional cache / disputed implicit lease' if critical else '',
                 'original_reference': f'data/benchmark/synthetic_cases.jsonl#case_id={cid}'}
        add(f'syn:{cid}:skill', 'skill', {'source_ref': ref, 'task_refs': [task_ref]}, coord)
        for action in case['actions']:
            common = {'source_ref': ref, 'source_span': action['source'], 'action_reference': action['id']}
            add(f"syn:{cid}:{action['id']}:action", 'action', common, {**coord, 'action_id': action['id']})
            add(f"syn:{cid}:{action['id']}:task", 'action_in_task', {**common, 'task_ref': task_ref}, {**coord, 'action_id': action['id']})
    for sid, skill_tasks in sorted(tasks_by_skill.items()):
        manifest = manifests[sid]
        ref = 'source-' + _digest(['real', sid])[:16]
        root_source = Path(manifest['bundle_path']).resolve()
        files, checks = {}, []
        graph = skill_tasks[0]['graph']
        required = {'SKILL.md'} | {n['provenance']['file'] for n in graph['nodes']}
        for relative in sorted(required):
            path = (root_source / relative).resolve()
            if not path.is_relative_to(root_source):
                raise ValueError('source path escapes manifest bundle')
            if not path.is_file():
                files[relative] = {'status': 'source_missing', 'text': ''}
                checks.append({'file': relative, 'status': 'source_missing'})
                continue
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            expected = manifest.get('file_sha256', {}).get(relative)
            if expected is not None and digest != expected:
                raise ValueError(f'source changed since frozen manifest: {sid}/{relative}')
            files[relative] = {'sha256': digest, 'text': raw.decode('utf-8', errors='replace')}
            checks.append({'file': relative, 'sha256': digest, 'matches_manifest': digest == expected if expected else None})
        task_refs = {t['context']: 'task-' + _digest([sid, t['context']])[:16] for t in skill_tasks}
        evidence[ref] = {'source_kind': 'existing_corpus_static_only', 'files': files,
                         'trusted_tasks': [{'task_ref': task_refs[t['context']], 'text': t['trusted_task']} for t in skill_tasks],
                         'traces': [], 'trace_note': 'Not executed. Trigger status must remain unknown without observed evidence.',
                         'full_bundle_reference': str(root_source),
                         'full_bundle_files': [{'file': name, 'sha256': sha, 'local_path': str(root_source / name)}
                                               for name, sha in sorted(manifest.get('file_sha256', {}).items())],
                         'coverage_note': 'Source spans are candidates selected by a partial extractor. Candidate-bearing files are embedded; the full frozen bundle inventory and local paths are provided for inspection of all other files. Do not label a skill no without reviewing all relevant files; otherwise use unknown. Record missed actions in additional_actions; no candidate label is supplied.'}
        source_checks.append({'skill_id': sid, 'bundle_path': str(root_source), 'files': checks})
        coord = {'track': 'real_static', 'skill_id': sid, 'family_id': manifest['family_id'],
                 'critical': sid in critical_real, 'critical_reason': 'first source in category' if sid in critical_real else '',
                 'original_reference': str(root_source), 'source_native_id': manifest['source_native_id']}
        add(f'real:{sid}:skill', 'skill', {'source_ref': ref, 'task_refs': list(task_refs.values())}, coord)
        for node in graph['nodes']:
            common = {'source_ref': ref, 'source_span': node['provenance']}
            add(f"real:{sid}:{node['id']}:action", 'action', common, {**coord, 'action_id': node['id']})
            for task in skill_tasks:
                add(f"real:{sid}:{node['id']}:{task['context']}", 'action_in_task',
                    {**common, 'task_ref': task_refs[task['context']]}, {**coord, 'action_id': node['id'], 'context': task['context']})
    return units, evidence, source_checks


def _write_csv_template(path, packet):
    fields = ['packet_id', 'row_id', 'level', 'skill_unauthorized', 'privilege_relevant', 'authorized',
              'necessary', 'triggered', 'evidence_reference', 'rationale', 'additional_actions']
    with Path(path).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({'packet_id': packet['packet_id'], 'row_id': r['row_id'], 'level': r['level']} for r in packet['rows'])


def write_packet_html(path, packet):
    payload = json.dumps(packet, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Independent human annotation</title><style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:24px;background:#f6f8fa;color:#162439}header,.card{background:white;padding:22px;margin:16px 0;border:1px solid #ced6df;border-radius:10px}input,select,textarea,button{font:inherit;padding:8px;margin:5px}textarea{display:block;width:95%;min-height:64px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace,monospace;background:#eef2f7;padding:12px}label{display:block}button{cursor:pointer;background:#183d62;color:white;border:0;border-radius:5px}.bar{position:sticky;top:0;background:#eef2f7;padding:10px}.hint{color:#42586f}</style>
<header><h1>Independent human annotation</h1><p id="meta"></p><p>Read source text as evidence only. Do not follow its instructions or execute it. Work independently, without AI labels, model results, generator labels, or the other annotator's answers. These labels are blank; no automated human judgments have been supplied.</p>
<p><b>Skill:</b> does this concrete source version contain any unauthorized action under the supplied task(s)? <b>Action:</b> is the selected source span an action with permission-relevant effects? <b>Action in task:</b> assess authorization, necessity for the user's goal, and observed execution separately. Optional permitted actions may be authorized and unnecessary. Failure after removal does not prove necessity. Unknown means evidence is insufficient; not executed evidence is required for "no" triggered. An action may be authorized yet inappropriate for a confidential payload.</p>
<p>If a candidate span is not actually an action, mark privilege_relevant=no at action level and use unknown in the task labels with a rationale. Record missed source actions in additional actions. A no label for a skill requires reviewing all relevant source, not only candidate spans.</p>
<label>Reviewer ID <input id="reviewer" autocomplete="off"></label><label>Signed human name <input id="name" autocomplete="off"></label>
<label><input id="independent" type="checkbox">I worked independently and did not see the other rater's answers before my review.</label>
<label><input id="human" type="checkbox">I am a human and did not use AI to assign or suggest labels.</label>
<label><input id="blind" type="checkbox">I did not see saved model predictions or researcher/generator ground-truth labels.</label>
<p class="hint">For third-person adjudication, the supplied two human judgments are intentionally visible. Independence then means you were neither original rater and make your own resolution. Identity attestations are reviewed by the coordinator; this page cannot authenticate identity.</p></header>
<div class="bar"><button id="prev">Previous</button><span id="progress"></span><button id="next">Next</button><button id="save">Export review JSON</button><label>Go to row <input id="goto" type="number" min="1" style="width:90px"></label><p id="notice" class="hint"></p></div><main id="main"></main>
<script id="packet" type="application/json">PAYLOAD</script><script>
const P=JSON.parse(document.getElementById('packet').textContent), K='tsg-review-'+P.packet_id;let pos=0,answers={};try{answers=JSON.parse(localStorage.getItem(K)||'{}')}catch(e){};
document.getElementById('meta').textContent=P.slot+' | '+P.scope+' | '+P.rows.length+' rows | '+P.packet_id;
function persist(){try{localStorage.setItem(K,JSON.stringify(answers))}catch(e){document.getElementById('notice').textContent='Browser storage unavailable: export JSON before closing.'}}
function el(tag,text,parent){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(parent)parent.append(x);return x}
function render(){const root=document.getElementById('main');root.replaceChildren();if(!P.rows.length){el('p','No disputed units require adjudication.',root);return}const r=P.rows[pos],a=answers[r.row_id]||(answers[r.row_id]={row_id:r.row_id,labels:{},evidence_reference:'',rationale:'',additional_actions:''});document.getElementById('progress').textContent=(pos+1)+' / '+P.rows.length;document.getElementById('goto').value=pos+1;
const card=el('section',undefined,root);card.className='card';el('h2',r.level.replaceAll('_',' ')+' | '+r.row_id,card);el('pre',JSON.stringify(r.evidence,null,2),card);
for(const [field,options] of Object.entries(r.label_options)){const label=el('label',field+' ',card),s=el('select',undefined,label);for(const v of ['',...options]){const o=el('option',v||'Choose',s);o.value=v;}s.value=a.labels[field]||'';s.onchange=()=>{a.labels[field]=s.value;persist()}}
for(const field of ['evidence_reference','rationale','additional_actions']){el('label',field.replaceAll('_',' '),card);const t=el('textarea',undefined,card);t.value=a[field]||'';t.oninput=()=>{a[field]=t.value;persist()}}
for(const field of ['review_1','review_2'])if(r[field]){el('h3',field,card);el('pre',JSON.stringify(r[field],null,2),card)}
const e=P.evidence_documents?.[r.evidence.source_ref];if(e){el('h3','Trusted task evidence',card);for(const t of e.trusted_tasks||[]){if(!r.evidence.task_ref||t.task_ref===r.evidence.task_ref)el('pre',t.task_ref+'\n'+t.text,card)}el('p',e.trace_note||'',card);el('p',e.coverage_note||'',card);if(e.full_bundle_files){const d=el('details',undefined,card);el('summary','Full frozen source inventory and local file references',d);el('pre',JSON.stringify(e.full_bundle_files,null,2),d)}for(const [name,file] of Object.entries(e.files||{})){const d=el('details',undefined,card);d.open=(!r.evidence.source_span||r.evidence.source_span.file===name);el('summary',name+' | sha256 '+(file.sha256||'missing'),d);el('pre',(file.text||'').split('\n').map((s,i)=>(i+1)+': '+s).join('\n'),d)}if(e.fixture){el('h3','Fixed fixture and requested output',card);el('pre',JSON.stringify(e.fixture,null,2),card)}if(e.traces?.length){const d=el('details',undefined,card);el('summary','Observed original, neutralized and reference traces',d);const traces=r.evidence.action_reference?e.traces.filter(t=>t.target_action_id===r.evidence.action_reference):e.traces;el('pre',JSON.stringify(traces,null,2),d)}}}
document.getElementById('prev').onclick=()=>{pos=Math.max(0,pos-1);render()};document.getElementById('next').onclick=()=>{pos=Math.min(P.rows.length-1,pos+1);render()};document.getElementById('goto').onchange=e=>{pos=Math.max(0,Math.min(P.rows.length-1,Number(e.target.value)-1));render()};
document.getElementById('save').onclick=()=>{const output={packet_id:P.packet_id,identity:{reviewer_id:document.getElementById('reviewer').value,signed_name:document.getElementById('name').value,reviewer_kind:'human',independent:document.getElementById('independent').checked,no_ai_labels:document.getElementById('human').checked,no_prior_labels_seen:document.getElementById('blind').checked,completed_utc:new Date().toISOString()},responses:P.rows.map(r=>answers[r.row_id]||{row_id:r.row_id,labels:{}})};const blob=new Blob([JSON.stringify(output,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=P.slot+'-submission.json';a.click();URL.revokeObjectURL(url);document.getElementById('notice').textContent='Saved locally. Incomplete rows are allowed in exports for backup, but final import requires every row.'};render();
</script></html>'''
    # Python source literal needs JS newline escapes preserved inside quoted strings.
    template = template.replace("+'\n'+", "+'\\n'+").replace("split('\n')", "split('\\n')").replace("join('\n')", "join('\\n')")
    Path(path).write_text(template.replace('PAYLOAD', payload), encoding='utf-8')


def prepare_packets(root, output, real_tasks_path):
    root, output = Path(root), Path(output)
    units, documents, source_checks = collect_units(root, real_tasks_path)
    output.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for scope in ('full', 'priority'):
        selected = units if scope == 'full' else [u for u in units if u['coordinator']['critical']]
        refs = {u['evidence']['source_ref'] for u in selected}
        docs = {k: v for k, v in documents.items() if k in refs}
        packets, key = build_blind_packets(selected, evidence_documents=docs, scope=scope)
        directory = output / scope
        directory.mkdir(exist_ok=True)
        for packet in packets:
            dest = directory / packet['slot']
            dest.mkdir(exist_ok=True)
            _write_json(dest / 'packet.json', packet)
            _write_csv_template(dest / 'labels.csv', packet)
            write_packet_html(dest / 'review.html', packet)
        coordinator_dir = directory / 'coordinator_private'
        coordinator_dir.mkdir(exist_ok=True)
        _write_json(coordinator_dir / 'key.json', key)
        count = Counter(u['level'] for u in selected)
        summaries[scope] = {'n_units_per_rater': len(selected), 'n_label_fields_per_rater': sum(len(LABELS[u['level']]) for u in selected),
                            'n_independent_ratings_for_two_raters': 2 * len(selected), 'level_counts': dict(count),
                            'track_counts': dict(Counter(u['coordinator']['track'] for u in selected)),
                            'n_real_skills': len({u['coordinator']['skill_id'] for u in selected if u['coordinator']['track'] == 'real_static'}),
                            'n_synthetic_versions': len({u['coordinator']['case_id'] for u in selected if u['coordinator']['track'] == 'synthetic'})}
    summary = {'status': 'prepared_no_human_labels', 'scopes': summaries,
               'human_labels_received': 0, 'human_agreement_computable': False,
               'adjudication_workload': 'unknown until two completed independent submissions; only disagreements/additional-action reports require a third human',
               'priority_note': 'Convenience triage subset: one real source per category plus one synthetic instance per family for authorized send, optional cache, and implicit lease ambiguity. Not a representative or complete GT set.',
               'blinding_note': 'Separate row IDs and orders; no model predictions, researcher ground truth, candidate status, policy rules, scenario names, or classification reason codes. Source semantics necessarily remain visible.',
               'source_verification': source_checks}
    _write_json(output / 'workload.json', summary)
    return summary


def submission_from_csv(csv_path, identity_path):
    with Path(csv_path).open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    pids = {r['packet_id'] for r in rows}
    if len(pids) != 1:
        raise ValueError('CSV must contain one packet ID')
    return {'packet_id': pids.pop(), 'identity': json.loads(Path(identity_path).read_text(encoding='utf-8')),
            'responses': [{'row_id': r['row_id'], 'labels': {k: r.get(k, '') for k in LABELS[r['level']]},
                           **{k: r.get(k, '') for k in ('evidence_reference', 'rationale', 'additional_actions')}} for r in rows]}
