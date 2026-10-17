"""Verify preservation, record review dispositions and package editable LaTeX."""
import hashlib,json,platform,subprocess,sys,zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from experiment import D,ROOT,read,save,digest

def main():
    old=read('provenance/baseline.json')['files']
    def check(item):
        name,sha=item;p=ROOT/name
        return name if not p.exists() or digest(p.read_bytes())!=sha else None
    with ThreadPoolExecutor(max_workers=8) as pool:changed=[x for x in pool.map(check,old.items()) if x]
    save(D/'provenance/preservation_check.json',{'baseline_files':len(old),'changed_or_missing':changed,'all_preserved':not changed})
    if changed:raise ValueError('OLD_BYTES_CHANGED')
    save(D/'provenance/review_dispositions.json',{
      'multiline_source_identity':{'status':'repaired_after_main_acquisition','old_source':'provenance/pre_evaluation_freeze/adapter.py',
        'old_sha256':digest((D/'provenance/pre_evaluation_freeze/adapter.py').read_bytes()),'new_sha256':digest((D/'adapter.py').read_bytes()),
        'change':'Use AST Call.lineno for effect identity, not enclosing Assign.lineno.',
        'regression':'test_review_regressions.py; observed failing before fix, passing after',
        'main_data_impact':'None in complete post-review offline replay; all evaluated effects are single-line.',
        'acquisition_manifest':'Retains original source hashes. New source is not authorized for additional calls under that frozen manifest.'},
      'catalogue_formula':{'status':'paper_corrected','behavior':'All open catalogues unknown, matching retained implementation.',
        'limitation':'Prompt witness/open wording ambiguous; empty-open cases have no witness so measured labels unaffected.'},
      'deletion_absence_flow':{'status':'retained_known_security_gap','probe':'results/post_review_absence_flow.json',
        'paper':'Visible result subsection, abstract, limitation and future work. No claim of sound confidentiality even for all accepted syntax.',
        'repair_claimed':False},
      'phase5_locator':{'status':'corrected_derived_metric','first':'results/coverage.json','corrected':'results/coverage_corrected.json'},
      'reference_amendment':'amendments_reference.json'})
    z=D/'output/ieee-source.zip';names=['paper.tex','intro_methods.tex','related_work.tex','results_discussion.tex','references.tex','BUILD.md']
    names += [p.relative_to(D).as_posix() for p in sorted((D/'figures').glob('*.pdf'))]
    with zipfile.ZipFile(z,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in names:
            info=zipfile.ZipInfo(name,date_time=(2026,10,17,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,(D/name).read_bytes())
    save(D/'provenance/source_archive.json',{'path':'output/ieee-source.zip','sha256':digest(z.read_bytes()),
      'entries':{n:digest((D/n).read_bytes()) for n in names},'fixed_zip_timestamp':'2026-10-17T00:00:00'})
    print(json.dumps({'old_files_preserved':len(old),'source_archive':str(z),'bytes':z.stat().st_size}))
if __name__=='__main__':main()
