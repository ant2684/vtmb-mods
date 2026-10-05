"""Shared native-input/check helpers for distinct regression scenarios."""
import sys,time,json,re,hashlib

from pathlib import Path

from drive import Driver,W,u,C

def start(d):
 rect=W.RECT();u.GetWindowRect(d.hwnd,C.byref(rect));assert (rect.left,rect.top,rect.right,rect.bottom)==(0,0,2560,1440),'Preserve current video mode; adapt input coordinates first'
 deadline=time.time()+45
 # Fresh -console launch: wait for its startup panel, not merely a window.
 while not d.console():
  if time.time()>deadline:d.record('startup_timeout',True);raise RuntimeError('Startup console was not ready')
  time.sleep(.2)
 time.sleep(3);d.p.refresh();d.record('startup_ready');d.click(1444,123)
 deadline=time.time()+10
 while d.console():
  if time.time()>deadline:d.record('console_close_timeout',True);raise RuntimeError('Startup console did not close')
  time.sleep(.5);d.click(1444,123)
 d.record('menu_ready')
 d.click(1280,615)
 deadline=time.time()+60
 while not d.snap()['players']:
  if time.time()>deadline:d.record('creation_timeout',True);raise RuntimeError('Character creation did not load')
  d.p.refresh()
  time.sleep(.3)
 time.sleep(1);d.key(0x32);time.sleep(1)

def values(d):return d.snap()['players'][0]['groups'][0]['values']

def base(d):d.click(180,166)

def sheet(d):d.click(517,167)

def clan(d,index):
 base(d);d.click(1215,356);d.click(200,393+index*22)

def gender(d,female):
 base(d);d.click(1215,541);d.click(200,580 if female else 603)

def select_history(d,index):
 base(d);d.click(1215,729);d.click(200,768+22*index)

def stable(s):
 rows=[]
 for g in s['players'][0]['groups'][:3]:
  vals=g['values'][:];eff=g['effective'][:];secondary=g['secondary'][:]
  # Native reset copies the pre-reset funding into its baseline slot. The
  # current funding is checked separately; this service baseline is not a stat.
  if g['type']==0:vals[34]=eff[34]=secondary[34]=0
  rows.append((vals,eff,secondary,g['costs']))
 return rows

def save(d,label,s):
 (d.session/(label+'.json')).write_text(json.dumps(s,indent=2))

def purchase(d,kind,coordinates,label):
 before=d.snap(True);groups=before['players'][0]['groups'];a=groups[0]['values'][34]
 x,y=coordinates;d.click(x,y,.2);after=d.snap(True);changes=[]
 for gi in range(3):
  for i,(old,new) in enumerate(zip(groups[gi]['values'],after['players'][0]['groups'][gi]['values'])):
   if old!=new and not(gi==0 and i==34):changes.append((gi,i,old,new))
 save(d,label+'_before',before);save(d,label+'_after',after)
 assert len(changes)==1 and changes[0][0]==kind and changes[0][3]==changes[0][2]+1,(label,changes)
 gi,i,old,new=changes[0];cost=groups[gi]['costs'][str(i)]
 assert after['players'][0]['groups'][0]['values'][34]==a-cost,(label,cost,a,after['players'][0]['groups'][0]['values'][34])
 return after,changes[0],cost

def reject(d,coordinates,label):
 before=d.snap(True);d.click(*coordinates,.2);after=d.snap(True)
 save(d,label+'_before',before);save(d,label+'_after',after)
 assert stable(before)==stable(after) and before['players'][0]['groups'][0]['values'][34]==after['players'][0]['groups'][0]['values'][34],(label,'out-of-budget purchase changed stats')
