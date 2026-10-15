"""Pre-annotation packet amendment: use acquisition metadata, not visible markers."""
import json
from pathlib import Path
from prepare_phase4 import immutable, rows_bytes, json_bytes, sha
from prepare_phase5 import rows, ROOT

def main():
    source=rows(ROOT/'data/phase3/real_prepared.jsonl')
    out=ROOT/'data/phase5/human_review'
    packet=rows(out/'rater_A.jsonl'); strata=rows(out/'selection_manifest.jsonl')
    extra=[]; omitted=[]
    for p in source:
        for file in p['coverage']['truncated_files']:
            lines=p['files'][file].splitlines()
            if not lines: continue
            rid='review_'+sha((p['skill_id']+':acquisition_truncation:'+file).encode())[:18]
            extra.append({'review_id':rid,'skill_id':p['skill_id'],'source_ref':'sources.jsonl',
                          'source_sha256':{f:sha(t.encode()) for f,t in p['files'].items()},
                          'provenance':{'file':file,'line_start':max(1,len(lines)-15),'line_end':len(lines)},
                          'labels':{},'notes':'','status':'pending_independent_human_review'})
            strata.append({'review_id':rid,'stratum':'truncated_by_acquisition_metadata',
                           'skill_id':p['skill_id'],'source_native_id':p['source_native_id']})
        for file in p['coverage']['omitted_files']:
            omitted.append({'skill_id':p['skill_id'],'source_native_id':p['source_native_id'],
                            'omitted_file':file,'status':'not_in_bounded_source_not_reviewable_from_current_packet',
                            'original_provenance':p['provenance']})
    active=packet+extra
    for name in ('rater_A_v2.jsonl','rater_B_v2.jsonl'): immutable(out/name,rows_bytes(active))
    immutable(out/'selection_manifest_v2.jsonl',rows_bytes(strata))
    immutable(out/'omitted_files.jsonl',rows_bytes(omitted))
    info={'prior_items_per_rater':len(packet),'metadata_truncation_additions':len(extra),
          'active_items_per_rater':len(active),'omitted_file_records':len(omitted),
          'reason':'Valid textual cuts need not contain a truncation marker. Acquire metadata is authoritative.',
          'old_packet_preserved':True,'human_labels':0}
    immutable(out/'packet_amendment.json',json_bytes(info)); print(json.dumps(info))

if __name__=='__main__': main()
