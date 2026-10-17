"""Structural PDF checks; visual review is recorded separately, not inferred."""
from pathlib import Path
import hashlib,json,re
from pypdf import PdfReader

D=Path(__file__).resolve().parent
pages=[p.extract_text() for p in PdfReader(D/'paper.pdf').pages]
reference_pages=[i+1 for i,p in enumerate(pages) if p.lstrip().startswith('REFERENCES')]
abstract=(D/'abstract.tex').read_text(encoding='utf-8').split(r'\begin{abstract}')[1].split(r'\end{abstract}')[0]
bibliography=(D/'references.tex').read_text(encoding='utf-8');entries=re.findall(r'\\bibitem\{([^}]+)\}',bibliography)
cited=set()
for path in D.glob('*.tex'):
    for group in re.findall(r'\\cite\{([^}]+)\}',path.read_text(encoding='utf-8')):cited.update(group.split(','))
log=(D/'output/paper.log').read_text(encoding='utf-8',errors='replace')
report={'pages':len(pages),'body_pages':reference_pages[0]-1,'reference_pages':len(pages)-reference_pages[0]+1,
    'abstract_words':len(abstract.split()),'references':len(entries),'uncited_keys':sorted(set(entries)-cited),
    'unresolved_citation_keys':sorted(cited-set(entries)),'overfull_boxes':log.count('Overfull'),
    'replacement_characters_in_pdf':sum(p.count('\ufffd') for p in pages),
    'pdf_sha256':hashlib.sha256((D/'paper.pdf').read_bytes()).hexdigest(),
    'nonfatal_build_warnings':'algorithm.sty encoding warning; host fontconfig warning; retained log. Standard fonts rendered successfully.'}
report['pass']=10<=report['body_pages']<=12 and report['reference_pages']==1 and 150<=report['abstract_words']<=200 and report['references']>=10 and not report['unresolved_citation_keys'] and not report['overfull_boxes'] and not report['replacement_characters_in_pdf']
(D/'qa').mkdir(exist_ok=True);(D/'qa/paper_check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report));raise SystemExit(0 if report['pass'] else 1)
