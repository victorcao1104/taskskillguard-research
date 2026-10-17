import itertools
import random
from gr14.goals import valid_selection, truth


def rows():
    return [dict(id='a', cost=2, quality=5, tags=['x'], owner='u', rank=3, requires=[], conflicts=[]),
            dict(id='b', cost=3, quality=6, tags=['y'], owner='v', rank=1, requires=[], conflicts=[]),
            dict(id='c', cost=1, quality=7, tags=['y'], owner='w', rank=2, requires=['a'], conflicts=[])]


def test_nonunique_goals_are_not_a_pipeline():
    goal={'min_count':2,'max_count':2,'cover':{'tags':['x','y']},'sum_bounds':{'cost':{'max':5}}}
    assert valid_selection(['a','b'],rows(),goal)
    assert valid_selection(['a','c'],rows(),goal)
    assert not valid_selection(['b','c'],rows(),goal)
    assert truth(['a','b'],rows(),goal)['valid']


def test_order_duplicates_and_dependencies():
    goal={'min_count':1,'max_count':3,'closed_dependencies':True,'order_by':['rank','id']}
    assert not valid_selection(['c'],rows(),goal)
    assert not valid_selection(['a','c'],rows(),goal)
    assert valid_selection(['c','a'],rows(),goal)
    for invalid in (None,{},['missing'],['a','a'],[True]):
        assert not valid_selection(invalid,rows(),goal)
        assert not truth(invalid,rows(),goal)['valid']


def test_checker_differential_and_boundary_values():
    rng=random.Random(81)
    for _ in range(30):
        data=rows()
        for r in data:r['cost']=rng.randrange(0,6)
        goals=[{'min_count':0,'max_count':2,'sum_bounds':{'cost':{'min':2,'max':5}}},
               {'min_count':1,'unique':['owner'],'closed_dependencies':True},
               {'min_count':2,'cover':{'tags':['x','y']},'order_by':['rank','id']}]
        for n in range(4):
            for ids in itertools.permutations([r['id'] for r in data],n):
                for g in goals:assert valid_selection(list(ids),data,g)==truth(list(ids),data,g)['valid']


def test_pairwise_conflicts_are_symmetric():
    data=rows();data[0]['conflicts']=['b']
    assert not valid_selection(['b','a'],data,{'no_conflicts':True})
    assert not truth(['a','b'],data,{'no_conflicts':True})['valid']
