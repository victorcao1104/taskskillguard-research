"""Family-level exploratory intervals and explicit missing/unknown accounting."""
from collections import defaultdict, Counter
import random
import statistics


def paired_interval(rows,draws=5000,seed=61016):
    groups=defaultdict(list)
    for r in rows:groups[r['family']].append(r['difference'])
    values=[statistics.mean(v) for _,v in sorted(groups.items())]
    if not values:return {'families':0,'conditions':0,'estimate':None,'interval95':None}
    rng=random.Random(seed)
    boot=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(draws))
    return {'families':len(values),'conditions':len(rows),'estimate':statistics.mean(values),
            'interval95':[boot[int(.025*draws)],boot[min(draws-1,int(.975*draws))]],
            'method':'family-balanced paired percentile bootstrap; exploratory, no confirmatory multiplicity claim'}


def label_counts(pairs):
    pairs=list(pairs)
    return {'total':len(pairs),'correct':sum(a==b for a,b in pairs),'missing':sum(b is None for a,b in pairs),
            'gold_unknown':sum(a=='unknown' for a,b in pairs),
            'correct_unknown':sum(a==b=='unknown' for a,b in pairs),
            'unsupported_decision':sum(a=='unknown' and b in ('yes','no') for a,b in pairs),
            'false_unknown':sum(a!='unknown' and b=='unknown' for a,b in pairs),
            'gold_distribution':dict(Counter(a for a,b in pairs)),
            'predicted_distribution':dict(Counter('missing' if b is None else b for a,b in pairs))}
