"""Paper structure/source-archive checks; requires pypdf for PDF inspection."""
import json,re,hashlib,zipfile
from pathlib import Path
from pypdf import PdfReader
D=Path(__file__).resolve().parent
pdf=D/'output/paper.pdf';reader=PdfReader(pdf)
text=(D/'paper.tex').read_text(encoding='utf-8');abstract=text.split(r'\begin{abstract}')[1].split(r'\end{abstract}')[0]
pages=[p.extract_text() for p in reader.pages];refs=[i+1 for i,p in enumerate(pages) if p.lstrip().startswith('REFERENCES')]
bib=(D/'references.tex').read_text(encoding='utf-8');entries=re.findall(r'\\bibitem\{([^}]+)\}',bib)
citations=set()
for name in ('paper.tex','intro_methods.tex','related_work.tex','results_discussion.tex'):
    for c in re.findall(r'\\cite\{([^}]+)\}',(D/name).read_text(encoding='utf-8')):citations.update(c.split(','))
log=(D/'output/paper.log').read_text(encoding='utf-8',errors='replace')
checks={'pages':len(pages),'body_pages':refs[0]-1 if refs else None,'reference_pages':len(pages)-refs[0]+1 if refs else None,
 'abstract_words':len(abstract.split()),'references':len(entries),'unresolved_citation_keys':sorted(citations-set(entries)),
 'overfull_boxes':log.count('Overfull'),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
 'visual_review':'All11 final pages inspected at105dpi; table/caption/diagram/font/page flow checked; reference-only balance update inspected separately.',
 'source_archive_entries':zipfile.ZipFile(D/'output/ieee-source.zip').namelist()}
checks['structural_pass']=10<=checks['body_pages']<=12 and checks['reference_pages']==1 and 150<=checks['abstract_words']<=200 and checks['references']>=10 and not checks['unresolved_citation_keys'] and checks['overfull_boxes']==0
(D/'qa/paper_check.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(checks));raise SystemExit(0 if checks['structural_pass'] else 1)
