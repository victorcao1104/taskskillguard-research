"""Persist phasewise normal-Skill execution checks without model calls."""
import json
from audit_pipeline import original
from gr14.data import FAMILIES,make_case
from gr14.campaign import STUDY
from gr14.provider import immutable

results={phase:{family:original(make_case(family,'benign'),phase) for family in FAMILIES} for phase in ('validation','final','stress')}
summary={phase:{'worlds':sum(x['worlds'] for x in families.values()),'all_safe_complete':all(x['all_safe_complete'] for x in families.values())} for phase,families in results.items()}
immutable(STUDY/'reports/benign_all_phases.json',{'label':'Post-acquisition additive audit of actual original execution; no reconstructed program substituted','summary':summary,'results':results})
print(json.dumps(summary,indent=2))
