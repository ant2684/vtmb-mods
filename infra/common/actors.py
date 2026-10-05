"""Read-only native actor evidence on the pinned server; no diagnostic state offsets."""
import struct,time
def actors(p):
 sv=p.modules['vampire.dll'];table=p.u(sv+0x566458);raw=p.read(table,8192*12);out=[]
 def string(a):return p.read(a,256).split(b'\0',1)[0].decode('cp1252','replace') if a else ''
 for i in range(8192):
  _,entity,serial=struct.unpack_from('<III',raw,i*12)
  if not entity:continue
  try:
   cls=string(p.u(entity+0x11c));name=string(p.u(entity+0x26c))
   if cls not in ('player','npc_VWolfMorph','npc_VFrenzyShadow','npc_VHumanCombatant','npc_VWerewolf','npc_VPedestrian') and name!='werewolf':continue
   a={'class':cls,'name':name,'ptr':entity,'handle':i|(serial<<13),'vtable':p.u(entity)-sv,'model':string(p.u(entity+0x388)),
      'origin':list(struct.unpack('<3f',p.read(entity+0x404,12))),'mins':list(struct.unpack('<3f',p.read(entity+0x274,12))),
      'maxs':list(struct.unpack('<3f',p.read(entity+0x280,12))),'ground':p.u(entity+0x384),'solid':p.u(entity+0x2b0),'life':p.read(entity+0x200,1)[0],
      'health':p.u(entity+0x210),'attr_health':p.u(entity+0x11b8),'alive':p.read(entity+0x1481,1)[0],
      'sequence':p.u(entity+0x6f0),'cycle':p.f(entity+0x6f8),'enemy':p.u(entity+0x5ce0),'effects':p.u(entity+0x19c),
      'targetable':p.read(entity+0x1480,1)[0],'spawn_flags':p.u(entity+0x434)}
   if cls.startswith('npc_'):a['think_disabled']=p.read(entity+0x6080,1)[0]
   wh=p.u(entity+0x19a4)
   if wh!=0xffffffff:
    ent=p.u(table+(wh&0x1fff)*12+4)
    if ent and p.u(table+(wh&0x1fff)*12+8)==wh>>13:a['weapon_class']=string(p.u(ent+0x11c))
   if cls=='player':a.update(frenzy=p.u(entity+0x146c),wolf=p.read(entity+0x1edc,1)[0],controller=p.u(entity+0x1db0),protean=p.u(entity+0x1380),weapon_locks={hex(x):p.u(entity+x) for x in [0x1538,0x153c,0x10dc,0x10e0,0x1c64]})
   out.append(a)
  except OSError:pass
 return out
def snapshot(d,label):
 p=d.p;e=p.modules['engine.dll'];sv=p.modules['vampire.dll'];client=p.modules['client.dll']
 r={'label':label,'wall':time.time(),'client_time':p.d(e+0x314890),'paused':p.u(e+0x12b0758),'engine_paused':p.u(e+0x314874),'ai_global_flags':p.u(sv+0x92053c),'actors':actors(p)}
 r['hooks']={hex(x):p.read(sv+x,6).hex() for x in [0x161fc0,0x33ed75,0x16c558,0x33e9be,0x1f9177,0x3510d7,0x1e56e0,0x1e5b30,0x16c5be]}
 r['SetOrigin']=p.u(sv+0x4cf4d4+216*4)-sv;r['SetGround']=p.u(sv+0x4cf4d4+208*4);trace=p.u(sv+0x70b254);r['TraceRay']=p.u(p.u(trace)+16) if trace else 0
 r['filter_index']=p.u(client+0x61992c);r['filter_entry']=p.u(client+0x619928)
 if r['filter_entry']:
  filter=p.u(r['filter_entry']+4)
  if filter:
   method=p.u(p.u(filter)+4);code=p.read(method,8)
   r['filter']={'ptr':filter,'kind':p.u(filter+0x2c),'get_enabled':code.hex()}
   # Historical field names above refer to mat_fullbright ConVar: +2c is
   # integer value; vfunc +4 is IsCommand, not visual filter enable state.
   # A read-only native byte getter, when present: mov al,[ecx+disp8]; ret.
   if code[:2]==b'\x8a\x41' and code[3]==0xc3:r['filter']['enabled']=p.read(filter+code[2],1)[0]
 r['filter_hook']=p.read(client+0x19da73,5).hex()
 return r
