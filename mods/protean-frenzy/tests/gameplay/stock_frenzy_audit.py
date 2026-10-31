"""Specific future regression: native close-range fallback, not a forced AI schedule."""
import ast

def audit_stock_frenzy(log,rows):
    events=[ast.literal_eval(s) for s in log.splitlines()]
    front=[e for e in events if e[0]=='NATIVE_TARGET_VIEW']
    assert len(front)==2 and all(e[1]>100 and abs(e[2])<70 for e in front),'Targets must start ahead of actual view'
    names={a.get('sequence_name','') for r in rows for a in r['actors'] if a['cls']=='npc_VFrenzyShadow'}
    assert 'pfi_frenzy_claws_attack_low' in names,'Native close-range attack never observed'
    assert not any(n.startswith(('claws_chain_','claws_diagonal_')) for n in names),'Custom player combo selected by Frenzy AI'
    # Do not ban stock dodge activities: the contract preserves native AI choices.
    return ['Stock Frenzy regression: actual low attack, no player-combo leakage, both targets ahead of real view']
