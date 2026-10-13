/* Loaded clean final VTM, real pinned images, mocked external services only. */
#include "../../../infra/common/native_fixture.h"
#include <stdlib.h>
typedef struct { uint32_t words[5]; } Variant;
typedef int (__attribute__((thiscall)) *Input)(void *,const char *,void *,void *,Variant,int);
typedef void (__attribute__((thiscall)) *Activate)(void *,int);
typedef void (__attribute__((thiscall)) *Think)(void *);
typedef struct { int refs; void *type; } Object;
static uint8_t *sv,*en,*py,*wolf,*timer,*init,*other,*table,*clock_data,*group,*groups;
static void *old_input,*old_activate,*old_think,*old_damage,*old_trace;
static int stats[35],state=2,heal_calls,last_heal,starts,forwards,activations,flag_seen,query_calls,deallocations,py_error;
static const char *map="sp_observatory_2";
static Object answer;
static uint8_t saved_input[8],saved_current[8],saved_heal[8],saved_level[8],saved_activate[9],saved_think[8];
static char temp[MAX_PATH],plugin_path[MAX_PATH],ini_path[MAX_PATH];
static HMODULE WINAPI modules(LPCSTR n)
{ if(!strcmp(n,"vampire.dll"))return(HMODULE)sv; if(!strcmp(n,"engine.dll"))return(HMODULE)en;
  if(!strcmp(n,"vampire_python21.dll"))return(HMODULE)py; return NULL; }
static Object *__cdecl add(const char *s){check(!strcmp(s,"__main__"),"only main module");return &answer;}
static Object *__cdecl dictionary(Object *s){check(s==&answer,"borrowed module ABI");return &answer;}
static Object *__cdecl evaluate(const char *s,int mode,Object *g,Object *l)
{check(!strcmp(s,"nativeWolfRegenState()")&&mode==258&&g==&answer&&l==g,"pure synchronous query ABI");
 ++query_calls;if(state==0){py_error=1;return NULL;}answer.refs=1;answer.type=py+0x8e1e8;return &answer;}
static long __cdecl integer(Object *s){check(s==&answer,"int return ABI");return state;}
static void __cdecl clear(void){py_error=0;}
static void *__cdecl error(void){return py_error?(void*)1:NULL;}
static void __cdecl dealloc(Object *s){check(s==&answer&&s->refs==0,"owned result DECREF");++deallocations;}
static FARPROC WINAPI symbol(HMODULE h,LPCSTR name)
{ if(h!=(HMODULE)py)return GetProcAddress(h,name);
  if(!strcmp(name,"_PyThreadState_Current"))return(FARPROC)(py+0xa3850);
  if(!strcmp(name,"PyInt_Type"))return(FARPROC)(py+0x8e1e8);
  if(!strcmp(name,"PyImport_AddModule"))return(void*)add;
  if(!strcmp(name,"PyModule_GetDict"))return(void*)dictionary;
  if(!strcmp(name,"PyRun_String"))return(void*)evaluate;
  if(!strcmp(name,"PyInt_AsLong"))return(void*)integer;
  if(!strcmp(name,"PyErr_Clear"))return(void*)clear;
  if(!strcmp(name,"PyErr_Occurred"))return(void*)error;
  return NULL; }
static const char *__cdecl level(void){return map;}
static int __attribute__((thiscall)) current(void *self,int i)
{check(self==group&&(i==15||i==17),"CURRENT group/index");return stats[i];}
static void __attribute__((thiscall)) heal(void *self,int amount)
{check(self==wolf&&amount>0&&amount<=stats[15],"stock HealthHeal clamp");++heal_calls;last_heal=amount;stats[15]-=amount;}
static int __attribute__((thiscall)) input_forward(void *self,const char *n,void *a,void *c,Variant v,int id)
{ if(self==timer){check(!strcmp(n,"Enable")&&a==init&&c==init&&!id&&!v.words[0],"stock timer Enable ABI");++starts;return 1;}
  check(self==wolf&&!strcmp(n,"Use")&&a==(void*)1&&c==(void*)2&&id==7&&v.words[4]==9,"ordinary input forwards unchanged");
  ++forwards;return 77; }
static void __attribute__((thiscall)) activation(void *self,int flag)
{check(self==init||self==other,"stock Activate self");++activations;flag_seen=flag;}
static void __attribute__((thiscall)) thought(void *self)
{check(self==other,"only unrelated auto replays stock outputs");++forwards;}
static void now(float t){memcpy(clock_data+12,&t,4);}
static void actor(uint8_t *p,unsigned i,const char *name,const char *kind,unsigned vt)
{put(table+i*12+4,(uint32_t)(uintptr_t)p);put(table+i*12+8,1);put(p,(uint32_t)(uintptr_t)(sv+vt));
 put(p+0x26c,(uint32_t)(uintptr_t)name);put(p+0x11c,(uint32_t)(uintptr_t)kind);}
static void activate(int flag){((Activate)*(void**)(sv+0x465694+0x208))(init,flag);}
static void think(void){((Think)*(void**)(sv+0x465694+0x218))(init);}
static void command(const char *n,void *caller)
{Variant v={{0,0,0,0,9}};((Input)*(void**)(sv+0x4cf4d4+0x1d8))(wolf,n,(void*)1,caller,v,7);}
static void legacy(void){command("WolfRegenReset",timer);command("WolfRegenStart",timer);command("WolfRegenStop",timer);}
static HMODULE open_plugin(const char *config)
{
 HMODULE h; void(__cdecl *load)(void);FILE *f;
 if(config){f=fopen(ini_path,"wb");check(f!=NULL,"owned INI");fputs(config,f);fclose(f);}
 else if(GetFileAttributesA(ini_path)!=INVALID_FILE_ATTRIBUTES)check(DeleteFileA(ini_path),"owned INI remove");
 memcpy(sv+0xabc90,saved_input,8);memcpy(sv+0x2012d0,saved_current,8);memcpy(sv+0x33c340,saved_heal,8);
 memcpy(sv+0x130d40,saved_activate,9);memcpy(sv+0x130db0,saved_think,8);memcpy(en+0x1b800,saved_level,8);
 h=LoadLibraryA(plugin_path);check(h!=NULL,"clean VTM load");imports(h,"GetModuleHandleA",modules);imports(h,"GetProcAddress",symbol);
 load=(void*)GetProcAddress(h,"loaded_vampire");check(load!=NULL,"only required export");load();
 check(*(void**)(sv+0x4cf4d4+0x238)!=old_damage&&*(void**)(sv+0x4cf4d4+0x234)!=old_trace,"damage remains independent");
 jump(sv+0xabc90,input_forward);jump(sv+0x2012d0,current);jump(sv+0x33c340,heal);jump(en+0x1b800,level);
 jump(sv+0x130d40,activation);jump(sv+0x130db0,thought);
 state=2;map="sp_observatory_2";py_error=0;put(wolf+0x200,0);put(wolf+0x19c,0);put(wolf+0xff0,0);
 put(init+0x204,0);put(table+8,1);put(table+20,1);put(table+32,1);
 heal_calls=last_heal=starts=forwards=activations=query_calls=deallocations=0;
 stats[15]=100;stats[17]=900;now(10);return h;
}
static void close_plugin(HMODULE h)
{check(FreeLibrary(h),"unload");check(*(void**)(sv+0x4cf4d4+0x1d8)==old_input&&
 *(void**)(sv+0x465694+0x208)==old_activate&&*(void**)(sv+0x465694+0x218)==old_think&&
 *(void**)(sv+0x4cf4d4+0x238)==old_damage&&*(void**)(sv+0x4cf4d4+0x234)==old_trace,"all five owned slots restored");}
int main(int argc,char **argv)
{
 HMODULE h; char root[MAX_PATH];unsigned i,f;const unsigned fps[]={20,60,144,240};
 const char *bad[]={"HPPerTick=-1","HPPerTick=1.5","TickIntervalSeconds=nan","TickIntervalSeconds=0.01"};
 check(argc==5,"VTM/server/engine/Python arguments");GetTempPathA(sizeof(root),root);
 snprintf(temp,sizeof(temp),"%swolf_lifecycle_%lu_%lu",root,GetCurrentProcessId(),GetTickCount());check(CreateDirectoryA(temp,NULL),"exclusive fixture dir");
 snprintf(plugin_path,sizeof(plugin_path),"%s\\candidate.vtm",temp);snprintf(ini_path,sizeof(ini_path),"%s\\griffith-wolf-native-damage.ini",temp);
 check(CopyFileA(argv[1],plugin_path,TRUE),"exact tested binary copy");sv=map_image(argv[2]);en=map_image(argv[3]);py=map_image(argv[4]);
 wolf=calloc(1,0x6800);timer=calloc(1,0x500);init=calloc(1,0x500);other=calloc(1,0x500);table=calloc(8192,12);clock_data=calloc(1,64);group=calloc(1,64);groups=calloc(1,4);
 check(wolf&&timer&&init&&other&&table&&clock_data&&group&&groups,"fixture allocation");
 actor(wolf,0,"werewolf","npc_VWerewolf",0x4cf4d4);actor(timer,1,"gp_wolf_regen_timer","logic_timer",0x465fb4);
 actor(init,2,"gp_wolf_regen_init","logic_auto",0x465694);actor(other,3,"other_auto","logic_auto",0x465694);
 put(wolf+0x1fc,1);put(wolf+0x13bc,1);put(wolf+0x13c0,(uint32_t)(uintptr_t)groups);put(groups,(uint32_t)(uintptr_t)group);put(group+4,35);
 put(sv+0x566458,(uint32_t)(uintptr_t)table);put(sv+0x70b228,(uint32_t)(uintptr_t)clock_data);
 put(py+0xa3850,1);put(py+0x8e1e8+8,(uint32_t)(uintptr_t)dealloc);
 old_input=*(void**)(sv+0x4cf4d4+0x1d8);old_activate=*(void**)(sv+0x465694+0x208);old_think=*(void**)(sv+0x465694+0x218);
 old_damage=*(void**)(sv+0x4cf4d4+0x238);old_trace=*(void**)(sv+0x4cf4d4+0x234);
 memcpy(saved_input,sv+0xabc90,8);memcpy(saved_current,sv+0x2012d0,8);memcpy(saved_heal,sv+0x33c340,8);memcpy(saved_level,en+0x1b800,8);
 memcpy(saved_activate,sv+0x130d40,9);memcpy(saved_think,sv+0x130db0,8);
 h=open_plugin(NULL);map="not_ready";activate(0x123400);check(activations==1&&flag_seen==0x123400,"Activate once/exact argument before map ready");
 map="sp_observatory_2";think();check(starts==1,"disabled timer restored independently");
 legacy();now(10.99f);command("WolfRegenTick",timer);check(!heal_calls,"first full interval despite old inputs");
 now(11);command("WolfRegenTick",timer);command("WolfRegenTick",timer);check(heal_calls==1&&last_heal==5,"default tick/no double payout");
 command("Use",(void*)2);check(forwards==1,"ordinary wolf input");
 ((Think)*(void**)(sv+0x465694+0x218))(other);check(forwards==2,"unrelated auto outputs unchanged");
 now(30);activate(0);legacy();command("WolfRegenTick",timer);check(heal_calls==1,"new load disarms old ticks/same handle/later clock");
 think();legacy();now(30.99f);command("WolfRegenTick",timer);check(heal_calls==1,"stale Reset/Start/Stop cannot change new deadline");
 now(31);command("WolfRegenTick",timer);check(heal_calls==2&&starts==2,"same handle reload heals automatically once");
 now(32);command("WolfRegenTick",other);check(heal_calls==2,"foreign timer rejected");
 stats[15]=3;command("WolfRegenTick",timer);check(last_heal==3&&!stats[15],"partial heal/current max cap");
 now(33);command("WolfRegenTick",timer);check(heal_calls==3,"full HP unchanged");
 stats[15]=50;now(50);command("WolfRegenTick",timer);check(heal_calls==4,"stall pays one tick only");
 put(wolf+0xff0,0x11e);now(51);command("WolfRegenTick",timer);put(wolf+0xff0,0);legacy();now(52);command("WolfRegenTick",timer);
 check(heal_calls==4,"crush stop sticky before queued commands");close_plugin(h);
 h=open_plugin(NULL);think();check(starts==1,"fresh Spawn Think initializes without Activate");
 put(wolf+0x200,1);now(11);command("WolfRegenTick",timer);put(wolf+0x200,0);legacy();now(12);command("WolfRegenTick",timer);check(!heal_calls,"dead cannot revive");close_plugin(h);
 h=open_plugin(NULL);state=0;activate(0);think();now(14.9f);think();state=2;think();now(15.89f);command("WolfRegenTick",timer);check(!heal_calls,"first interval starts at ready commit");now(15.9f);command("WolfRegenTick",timer);check(heal_calls==1,"delayed readiness succeeds");close_plugin(h);
 h=open_plugin(NULL);state=0;activate(0);think();now(15);think();state=2;think();now(16);command("WolfRegenTick",timer);check(!starts&&!heal_calls,"timeout fails closed");close_plugin(h);
 h=open_plugin(NULL);state=1;think();now(90);think();state=2;think();now(91);command("WolfRegenTick",timer);check(heal_calls==1,"intro wait is not readiness timeout");close_plugin(h);
 for(i=3;i<=4;++i){h=open_plugin(NULL);state=i;activate(0);think();legacy();now(12);command("WolfRegenTick",timer);check(!starts&&!heal_calls,"completed/invalid fail closed");close_plugin(h);}
 h=open_plugin(NULL);put(table+44,(uint32_t)(uintptr_t)other);put(other+0x26c,(uint32_t)(uintptr_t)"gp_wolf_regen_init");think();check(!starts,"duplicate init refused");put(other+0x26c,(uint32_t)(uintptr_t)"other_auto");close_plugin(h);
 h=open_plugin(NULL);put(init+0x204,1);think();check(!starts,"remove-after-fire init refused without replay");close_plugin(h);
 for(f=0;f<sizeof(fps)/sizeof(fps[0]);++f){h=open_plugin(NULL);think();for(i=1;i<=fps[f]*10;++i){now(10+(float)i/fps[f]);command("WolfRegenTick",timer);}check(heal_calls==10&&stats[15]==50,"phase preserved across FPS");close_plugin(h);}
 for(i=0;i<sizeof(bad)/sizeof(bad[0]);++i){char text[256];snprintf(text,sizeof(text),"[Regeneration]\n%s\n",bad[i]);h=open_plugin(text);think();now(12);command("WolfRegenTick",timer);check(!heal_calls,"bad INI disables regen only");close_plugin(h);}
 h=open_plugin("[Regeneration]\nHPPerTick=50\nTickIntervalSeconds=1\n");think();now(11);command("WolfRegenTick",timer);check(last_heal==50,"user50HP setting");close_plugin(h);
 h=open_plugin("[Regeneration]\nHPPerTick=0\n");think();now(11);command("WolfRegenTick",timer);check(!heal_calls,"zero disables");close_plugin(h);
 *(void**)(sv+0x465694+0x208)=sv+0x130d40;h=open_plugin(NULL);check(*(void**)(sv+0x4cf4d4+0x1d8)==old_input,"auto conflict rolls input registration back");check(FreeLibrary(h),"conflicted plugin unload");*(void**)(sv+0x465694+0x208)=old_activate;
 if(GetFileAttributesA(ini_path)!=INVALID_FILE_ATTRIBUTES)check(DeleteFileA(ini_path),"owned INI cleanup");check(DeleteFileA(plugin_path),"owned VTM cleanup");check(RemoveDirectoryA(temp),"empty owned fixture dir cleanup");
 puts("PASS exact clean VTM lifecycle/regen: ABI, current health, reload/legacy events, readiness, independent timer, FPS, settings, conflict/unload");return 0;
}
