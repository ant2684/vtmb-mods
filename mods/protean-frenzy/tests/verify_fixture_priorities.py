"""Native-hunger fixtures must not reintroduce signed ranking overflow."""
import ast
from pathlib import Path
p=Path(__file__).resolve().parent/'gameplay/game_probe.py'
tree=ast.parse(p.read_text(encoding='utf-8'))
values=[]
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name.startswith('native_hunger'):
        for call in ast.walk(node):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='SetRelationship':
                assert len(call.args)==1 and isinstance(call.args[0],ast.Constant)
                value=call.args[0].value
                assert value in ['player D_NU 10','player D_HT 10'],(node.name,value)
                values.append(value)
assert sorted(values)==['player D_HT 10','player D_NU 10','player D_NU 10'],values
print('PASS all three native-hunger fixture relationship priorities are10')
