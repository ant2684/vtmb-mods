"""Unique workflows: non-None gender reset/full pool and None/explicit reset."""
import sys,json,time
from drive import Driver
from gameplay import start,clan,gender,sheet,base,purchase,save,select_history,reject,values

def allocation(s):
 out=[]
 for g in s['players'][0]['groups'][:3]:
  v=g['values'][:]
  if g['type']==0:v[11]=v[34]=0
  out.append(v)
 return out

def initial(d):
 start(d);clan(d,0);gender(d,False);sheet(d)
 neutral=d.snap(True);save(d,'neutral_none',neutral);return neutral

def assert_reset(d,neutral,label):
 after=d.snap(True);save(d,label,after)
 assert after['players'][0]['history']==-1 and allocation(after)==allocation(neutral),'Gender did not fully reset allocation/History'
 assert after['players'][0]['groups'][0]['effective'][1]==1,'Prior History bonus remains'
 assert values(d)[34]>0,'New creation purchases are unfunded'
 return after

def full_pool(d):
 steps=[(0,(506,309)),(0,(551,309)),(0,(1766,309)),(1,(460,589)),(1,(506,589)),(1,(551,589)),(1,(1090,589)),(1,(1135,589)),(1,(1720,589)),(2,(506,880))]
 for n,(kind,xy) in enumerate(steps):purchase(d,kind,xy,'fresh_pool_'+str(n))
 for n,(kind,xy) in enumerate([(0,(506,363)),(0,(1135,309)),(0,(1766,363)),(1,(460,643)),(1,(1090,643)),(1,(1720,643)),(2,(1135,880))]):reject(d,xy,'exhausted_'+str(n))
 funded=d.snap(True);base(d);sheet(d);returned=d.snap(True)
 assert allocation(returned)==allocation(funded) and values(d)[34]==funded['players'][0]['groups'][0]['values'][34]
 save(d,'full_pool_returned',returned)
 return returned

def regression(d,mode):
 d.click_delay=.2;neutral=initial(d)
 if mode in ['verify','observe']:
  # Actual bonus History, not the empty None path.
  select_history(d,10);sheet(d);s=d.snap(True);save(d,'selected_history',s)
  assert s['players'][0]['history']==78 and s['players'][0]['groups'][0]['effective'][1]==2
  purchase(d,0,(551,309),'invested_with_history')
  gender(d,True);sheet(d);after=d.snap(True);save(d,'after_gender',after)
  print(json.dumps({'raw_strength':values(d)[1],'effective_strength':after['players'][0]['groups'][0]['effective'][1],'history':after['players'][0]['history'],'fully_reset':allocation(after)==allocation(neutral)}),flush=True)
  if mode=='observe':
   # Demonstrate the reported duplicated pool through two native purchases:
   # the surviving old physical point plus a fresh full two-point category.
   assert values(d)[1]==2
   purchase(d,0,(551,309),'refreshed_pool_strength')
   purchase(d,0,(506,363),'refreshed_pool_dexterity')
   save(d,'duplicated_pool',d.snap(True));print('Reproduced old investment plus full refreshed physical pool',flush=True);return
  assert_reset(d,neutral,'reset_after_history_gender')
  funded=full_pool(d)
  d.click(2118,1189);d.click(2120,1387);deadline=time.time()+90
  while time.time()<deadline:
   accepted=d.snap()
   if accepted['players'] and accepted['players'][0]['groups'][0]['values'][34]==0:break
   time.sleep(.25)
  else:raise RuntimeError('Native Accept completion not observed')
  save(d,'after_accept',accepted);assert allocation(accepted)==allocation(funded),'Accept changed newly allocated stats'
  workflows=['non-None History plus purchase then gender clears investment and bonus','full fresh pool: 3 attributes, 6 abilities, 1 discipline','all seven exhausted categories reject extra purchases','Base/Sheet keeps new allocation','Accept keeps new allocation and clears creation funding']
 else:
  for kind,xy in [(0,(506,309)),(1,(460,589)),(2,(506,880))]:purchase(d,kind,xy,'none_investment_'+str(kind))
  gender(d,True);sheet(d);assert_reset(d,neutral,'none_to_female_reset')
  purchase(d,0,(506,309),'new_female_purchase')
  gender(d,False);sheet(d);assert_reset(d,neutral,'female_to_male_reset')
  select_history(d,10);sheet(d);first=d.snap(True);save(d,'explicit_history_first',first)
  assert values(d)[1]==1 and first['players'][0]['groups'][0]['effective'][1]==2
  purchase(d,0,(551,309),'before_explicit_none')
  select_history(d,0);sheet(d);none=d.snap(True);save(d,'explicit_none',none)
  assert none['players'][0]['history']==0 and allocation(none)==allocation(neutral)
  select_history(d,10);sheet(d);repeat=d.snap(True);assert allocation(repeat)==allocation(first) and repeat['players'][0]['groups'][0]['effective'][1]==2
  purchase(d,0,(551,309),'before_same_history')
  select_history(d,10);sheet(d);same=d.snap(True);save(d,'same_history',same)
  assert allocation(same)==allocation(first) and same['players'][0]['groups'][0]['effective'][1]==2
  workflows=['None with attribute/ability/discipline purchases then gender clears all','new female purchase succeeds','reverse gender change resets too','explicit None resets allocation','repeated and same History bonus occurs once']
 launch=json.loads((d.session/'launch.json').read_text(encoding='utf-8-sig'))
 result={'result':'PASS','hash':launch['PluginHash'],'workflows':workflows}
 (d.session/'scenario-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':regression(Driver(sys.argv[1]),sys.argv[2])
