"""Text/layout inventory; visual page review remains mandatory."""
import json,re,hashlib
from pathlib import Path
from pypdf import PdfReader
P=Path(__file__).resolve().parent
tex=(P/"paper.tex").read_text(encoding="utf-8")
pdf=P/"output/pdf/paper.pdf"
r=PdfReader(pdf)
abstract=re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}",tex,re.S)[1]
words=re.findall(r"\b[\w]+(?:[-'][\w]+)*\b",abstract)
keys=re.findall(r"\\bibitem\{([^}]+)\}",tex)
cited=set(k for v in re.findall(r"\\cite\{([^}]+)\}",tex) for k in v.split(","))
pages=[]
for i,p in enumerate(r.pages,1):
    t=p.extract_text()
    pages.append({"page":i,"words":len(t.split()),"first":t[:95],"last":t[-110:]})
alltext="\n".join(p.extract_text() for p in r.pages)
ref_pages=[i for i,p in enumerate(r.pages,1) if "REFERENCES" in p.extract_text()]
sections={s:next((i for i,p in enumerate(r.pages,1) if s.replace(' ','') in p.extract_text().upper().replace(' ','').replace('\n','')),None)
 for s in ["I. INTRODUCTION","II. RELATED","III. METHODOLOGY","IV. IMPLEMENTATION","V. RESULTS","VI. CONCLUSION","AUTHOR CONTRIBUTIONS","REFERENCES"]}
log=(P/"output/pdf/paper.log").read_text(encoding="utf-8",errors="replace")
report={"pdf_sha256":hashlib.sha256(pdf.read_bytes()).hexdigest(),"pages":len(r.pages),
"body_pages":ref_pages[0]-1 if ref_pages else None,"reference_pages":len(r.pages)-ref_pages[0]+1 if ref_pages else None,
"abstract_words":len(words),"references":len(keys),"uncited":sorted(set(keys)-cited),
"undefined_citations":sorted(cited-set(keys)),"replacement_glyphs":alltext.count("\ufffd"),
"overfull_boxes":re.findall(r"Overfull [^\n]+",log),"undefined_warnings":re.findall(r"LaTeX Warning: [^\n]*undefined[^\n]*",log),
"sections":sections,"page_inventory":pages}
(P/"qa").mkdir(exist_ok=True)
(P/"qa/text_checks.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8",newline="\n")
assert 10 <= report['body_pages'] <= 12
assert report['reference_pages']==1
assert 150 <= report['abstract_words'] <= 200
assert report['references']>=10
assert not report['uncited'] and not report['undefined_citations']
assert not report['overfull_boxes'] and not report['undefined_warnings']
assert not report['replacement_glyphs']
print(json.dumps(report,indent=2))
