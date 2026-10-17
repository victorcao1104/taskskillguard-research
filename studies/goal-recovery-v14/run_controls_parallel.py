"""Resource scheduling only; unchanged frozen control computation, disjoint families."""
from concurrent.futures import ProcessPoolExecutor
import gr14.campaign as campaign

def one(family):
    campaign.FAMILIES=(family,)
    campaign.controls()
    return family

if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=3) as pool:
        for family in pool.map(one,campaign.FAMILIES):print('Completed '+family,flush=True)
