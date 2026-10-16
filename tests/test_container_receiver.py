import copy
import unittest
from infra.core import Failure
from mods.container.tests.audit import receiver_audit

KNIFE='item_w_knife';RING='item_g_ring_silver'
def snapshot(cls,p,d,owner,kind=4,enabled=True,money=1000):
    owners={n:{'inventory':[],'money':money if n=='player' else 0} for n in ['player','Trip','haven_refrigerator']}
    for n,q in [('player',p),(owner,d)]:
        if q:owners[n]['inventory']=[{'class':cls,'count':q,'slot':1}]
    row={'side':'player','slot':1,'count':p,'selected':1,'entity':123,'panel':{'visible':1}}
    return {'owners':owners,'ui':{'rows':[row],'action_kind':kind,'action':{'enabled':enabled}},'receiver_filter_bytes':'e9'+'00'*4+'90'*7,'vendor_policy':{'records':[{'name':'Trip','classes':[]}]}}

def fixture():
    e={'states':{},'actions':[]};states=e['states']
    for prefix,cls,owner,kind,p in [('give',KNIFE,'haven_refrigerator',2,2),('sell',RING,'Trip',4,1)]:
        for label,a,b,enabled in [('full-selected',p,10,False),('full-rejected',p,10,False),('space-freed',p+1,9,True),('space-available',p+1,9,True),('refilled',p,10,False)]:states[prefix+'-'+label]=snapshot(cls,a,b,owner,kind,enabled)
    money=1000
    for label,p,d,buy in [('sell-fill-'+str(k),10-k,k,False) for k in range(10)]+[('sell-space-freed',1,10,True),('sell-refilled',2,9,False)]:
        delta=1 if buy else -1;price=40 if buy else 4;kind=3 if buy else 4;side='donor' if buy else 'player'
        before=snapshot(RING,p,d,'Trip',kind,True,money);row=before['ui']['rows'][0];row.update(side=side,count=d if buy else p)
        money-=delta*price
        after=snapshot(RING,p+delta,d-delta,'Trip',4,d-delta<10,money);states[label]=after
        e['actions'].append({'label':label,'class':RING,'before':before,'quote':{'direction':'buy' if buy else 'sell','price':price,'selected':copy.deepcopy(row),'selected_global':123,'ammo_flag':0,'text_hex':('Value: $'+str(price)).encode().hex()}})
    return e

class ReceiverAuditTests(unittest.TestCase):
    def test_native_receiver_edges_and_finite_stock(self):receiver_audit(fixture())
    def test_full_receiver_enabled_rejected(self):
        for prefix in ['give','sell']:
            e=fixture();e['states'][prefix+'-full-selected']['ui']['action']['enabled']=True
            with self.assertRaises(Failure):receiver_audit(e)
    def test_receiver_count_and_wallet_changes_rejected(self):
        for wallet in [False,True]:
            e=fixture();v=e['states']['sell-full-rejected']['owners']['player']
            if wallet:v['money']+=1
            else:v['inventory'][0]['count']+=1
            with self.assertRaises(Failure):receiver_audit(e)
    def test_capacity_must_recover(self):
        for prefix in ['give','sell']:
            e=fixture();e['states'][prefix+'-space-available']['ui']['action']['enabled']=False
            with self.assertRaises(Failure):receiver_audit(e)
    def test_wrong_finite_trade_wallet_rejected(self):
        e=fixture();e['states']['sell-space-freed']['owners']['player']['money']+=1
        with self.assertRaises(Failure):receiver_audit(e)
