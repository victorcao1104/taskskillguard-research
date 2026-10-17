"""Strong source-free compiler from postconditions to bounded constraint search.

No case ID, family name, original source or prepared replacement is an input.
It retains explicit checked reuse and state handling rather than blind replay.
"""

EFFECTS="""if not exists('/output/selection'):
    write('/output/selection',result)
receipt_value=receipt('report')
if receipt_value=='unknown':
    receipt_value=status('report')
if receipt_value!='success' and receipt_value!='sent':
    send('report','team',result)
if exists('/tmp/cache'):
    delete('/tmp/cache')
"""


def compile_program(task,*,reuse=True):
    goal=task['goal'];parts=['result=None']
    parts+= ["if exists('/output/selection'):","    artifact_value=read('/output/selection')","    if valid(artifact_value):","        result=artifact_value"]
    if reuse:
        parts += ["if result is None:","    for cache_name in saved_names():","        cache_value=saved(cache_name)","        if valid(cache_value):","            result=cache_value","            break"]
    parts += ["if result is None:","    options=read('/input/options')","    options=sorted(options,key=lambda row:(row['cost'],row['id']))",
              f"    for size in range({goal['min_count']},{goal['max_count']+1}):",
              "        for selection in combinations(options,size):"]
    for field,bounds in goal.get('sum_bounds',{}).items():
        for bound,value in bounds.items():
            cmp='<' if bound=='min' else '>'
            parts += [f"            if sum([row[{field!r}] for row in selection]) {cmp} {value!r}:","                continue"]
    if goal['order_by']:
        fields=goal['order_by'];parts += [f"            selection=sorted(selection,key=lambda row:[row[field] for field in {fields!r}])"]
    parts += ["            proposal=[row['id'] for row in selection]","            if valid(proposal):","                result=proposal","                break",
              "        if result is not None:","            break"]
    return {'compute':'\n'.join(parts)+'\n','effects':"if result is not None:\n"+'\n'.join('    '+line for line in EFFECTS.splitlines())+'\n'}
