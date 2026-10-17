"""Two independent implementations of declarative output properties.

No function here constructs a selection or supplies a computation pipeline.
The fast predicate is available to programs; truth() is the final evaluator.
"""


def valid_selection(candidate, rows, goal):
    if not isinstance(candidate,list) or any(type(x) is not str for x in candidate):return False
    if len(set(candidate))!=len(candidate):return False
    lookup={r['id']:r for r in rows}
    if any(x not in lookup for x in candidate):return False
    selected=[lookup[x] for x in candidate]
    if not goal.get('min_count',0)<=len(selected)<=goal.get('max_count',len(rows)):return False
    for field,bounds in goal.get('sum_bounds',{}).items():
        total=sum(r[field] for r in selected)
        if 'min' in bounds and total<bounds['min']:return False
        if 'max' in bounds and total>bounds['max']:return False
    for field,needed in goal.get('cover',{}).items():
        have=set()
        for r in selected:
            v=r[field];have.update(v if isinstance(v,list) else [v])
        if not set(needed)<=have:return False
    for field in goal.get('unique',[]):
        if len({r[field] for r in selected})!=len(selected):return False
    ids=set(candidate)
    if goal.get('closed_dependencies') and any(not set(r.get('requires',[]))<=ids for r in selected):return False
    if goal.get('no_conflicts') and any(set(r.get('conflicts',[]))&ids for r in selected):return False
    if goal.get('order_by'):
        keys=goal['order_by']
        if selected!=sorted(selected,key=lambda r:tuple(r[k] for k in keys)):return False
    return True


def truth(candidate, rows, goal):
    """Independent loop-based checker returning violations, never a solution."""
    errors=[]
    if type(candidate) is not list:return {'valid':False,'violations':['OUTPUT_NOT_LIST']}
    selected=[];seen=[]
    for identifier in candidate:
        if type(identifier) is not str:return {'valid':False,'violations':['INVALID_IDENTIFIER_TYPE']}
        if identifier in seen:errors.append('DUPLICATE_IDENTIFIER')
        seen.append(identifier);matches=[row for row in rows if row['id']==identifier]
        if len(matches)!=1:errors.append('UNKNOWN_IDENTIFIER')
        else:selected.append(matches[0])
    if errors:return {'valid':False,'violations':sorted(set(errors))}
    if len(selected)<goal.get('min_count',0):errors.append('TOO_FEW')
    if len(selected)>goal.get('max_count',len(rows)):errors.append('TOO_MANY')
    for field,bounds in goal.get('sum_bounds',{}).items():
        total=0
        for row in selected:total+=row[field]
        if 'min' in bounds and total<bounds['min']:errors.append('SUM_BELOW:'+field)
        if 'max' in bounds and total>bounds['max']:errors.append('SUM_ABOVE:'+field)
    for field,requirements in goal.get('cover',{}).items():
        for value in requirements:
            found=False
            for row in selected:
                item=row[field]
                if (isinstance(item,list) and value in item) or item==value:found=True
            if not found:errors.append('MISSING_COVER:'+field+':'+str(value))
    for field in goal.get('unique',[]):
        for i in range(len(selected)):
            for j in range(i):
                if selected[i][field]==selected[j][field]:errors.append('NOT_UNIQUE:'+field)
    if goal.get('closed_dependencies'):
        for row in selected:
            for dependency in row.get('requires',[]):
                if dependency not in candidate:errors.append('MISSING_DEPENDENCY')
    if goal.get('no_conflicts'):
        for row in selected:
            for other in selected:
                if other['id'] in row.get('conflicts',[]):errors.append('INCOMPATIBLE_PAIR')
    if goal.get('order_by'):
        for i in range(1,len(selected)):
            previous=tuple(selected[i-1][f] for f in goal['order_by'])
            current=tuple(selected[i][f] for f in goal['order_by'])
            if current<previous:errors.append('WRONG_ORDER')
    return {'valid':not errors,'violations':sorted(set(errors))}
