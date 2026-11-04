import __main__,sys,math
ROOT='__ROOT__'
tick=0
def log(v):
 f=open(ROOT+'/probe.log','a');f.write(repr(v)+'\n');f.close()
def later(t,call):__main__.ScheduleTask(t,"__import__('p5_probe')."+call)
def command(n):setattr(__main__.ccmd,n,'')
def start():
 sys.stderr=open(ROOT+'/python-errors.log','a',0)
 try:prepare()
 except:log(('ERROR',str(sys.exc_info()[1])))
def prepare():
 p=__main__.FindPlayer();n=__main__.FindEntityByName('Killer')
 log(('INITIAL',p.GetOrigin(),p.health,n.GetOrigin(),n.GetModelName(),dir(n)))
 __main__.G.No_Idle=1
 later(1.,'stage()')
def stage():
 try:
  p=__main__.FindPlayer();n=__main__.FindEntityByName('Killer')
  f=open(ROOT+'/view.txt');yaw=float(f.read());f.close();a=yaw*math.pi/180.
  p.SetOrigin((312.069-110*math.cos(a),2857.54-110*math.sin(a),-109.))
  p.SetAngles((0,yaw,0));n.ScriptUnhide()
  log(('STAGED',p.GetOrigin(),p.health,n.GetOrigin(),yaw))
  later(1.,'begin()')
 except:log(('ERROR',str(sys.exc_info()[1])))
def begin():
 try:
  p=__main__.FindPlayer();n=__main__.FindEntityByName('Killer')
  log(('QUEST_BEFORE',p.GetQuestState('Serial'),__main__.G.Killer_Hostile,__main__.G.Killer_Attacks,n.GetModelName()))
  # This is the hostile dialogue branch's actual condition and native map
  # callback: retain transformation, fade, scene and authored combat Outputs.
  __main__.G.Killer_Hostile=1
  __main__.killerHostileCheck()
  log(('QUEST_AFTER',p.GetQuestState('Serial'),__main__.G.Killer_Hostile,__main__.G.Killer_Attacks,n.GetModelName()))
  log(('AUTHORED_ATTACK_BEGIN',))
  later(.1,'watch()')
 except:log(('ERROR',str(sys.exc_info()[1])))
def watch():
 global tick
 try:
  p=__main__.FindPlayer();n=__main__.FindEntityByName('Killer')
  log(('TICK',tick,p.health,p.GetOrigin(),n.GetOrigin(),n.sequence))
  if tick%2==0 and tick<=32:command('screenshot')
  tick=tick+1
  if tick<=60:later(.25,'watch()')
  else:log(('DONE',));command('quit')
 except:log(('ERROR',str(sys.exc_info()[1])));command('pfi_quit')
