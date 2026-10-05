#include "native_fixture.h"
typedef void(__thiscall *TraceFn)(void *,const void *,unsigned,void *,void *);
typedef void(__thiscall *GroundFn)(void *,void *);
typedef unsigned char(__thiscall *HitFn)(void *,void *,int);
typedef int(__thiscall *TypeFn)(void *);
typedef struct{float x,y,z;}Vec;
static uint8_t *server,*engine,*player,*shadow,*wolf,*table;static void *trace_vt[5],*trace_obj[1];
static int calls,fail_at,hit_calls,type_calls,trace_calls,corrected,recurse;static void *ground;
static const char *map="sp_observatory_2";static void *input_filter;static TraceFn nested;
static HMODULE WINAPI modules(LPCSTR n){if(!strcmp(n,"vampire.dll"))return(HMODULE)server;if(!strcmp(n,"engine.dll"))return(HMODULE)engine;return NULL;}
static BOOL WINAPI protect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old){calls++;return calls==fail_at?FALSE:VirtualProtect(p,n,flags,old);}
static const char *__cdecl level(void){return map;}
static Vec *__thiscall origin(void *self){return (void *)((uint8_t *)self+0x800);}
static unsigned char __thiscall hit(void *self,void *candidate,int mask){check(self==input_filter,"native filter ECX");check(mask==0x0202400b||mask==0x0200400b||mask==7,"native filter mask");hit_calls++;return candidate==player?1:candidate==shadow?0:1;}
static int __thiscall type(void *self){(void)self;type_calls++;return 2;}
static void __thiscall ground_fn(void *self,void *value){check(self==wolf||self==player,"ground ECX");ground=value;}
static void __thiscall trace_fn(void *self,const void *ray,unsigned mask,void *filter,void *result){void **vt=*(void ***)filter;unsigned char a,b,c;
 check(self==trace_obj&&ray==(void *)0x1234&&result==(void *)0x5678,"TraceRay ABI");trace_calls++;corrected=filter!=input_filter;
 a=((HitFn)vt[0])(filter,player,(int)mask);b=((HitFn)vt[0])(filter,shadow,(int)mask);c=((HitFn)vt[0])(filter,table,(int)mask);check(((TypeFn)vt[1])(filter)==2,"trace type delegated");
 check(a==(corrected?0:1)&&b==(corrected?1:0)&&c==1,"scoped collision behavior");
 if(recurse){int before=hit_calls;recurse=0;nested(trace_obj,ray,mask,input_filter,result);check(hit_calls-before==3,"recursion forwards unchanged");}
}
static void emit_trace(uint32_t site,TraceFn fn){uint8_t *p=server+site-21;unsigned i;for(i=0;i<4;i++){memcpy(p,"\xff\x74\x24\x10",4);p+=4;}p[0]=0xe8;put(p+1,(uint32_t)(uintptr_t)fn-(uint32_t)(uintptr_t)(p+5));memcpy(p+5,"\xc2\x10\0",3);}
static void emit_ground(uint32_t site,GroundFn fn){uint8_t *p=server+site-9;memcpy(p,"\xff\x74\x24\x04\xe8",5);put(p+5,(uint32_t)(uintptr_t)fn-(uint32_t)(uintptr_t)(p+9));memcpy(p+9,"\xc2\x04\0",3);}
static HMODULE open_plugin(const char *path){HMODULE h=LoadLibraryA(path);check(h!=NULL,"exact DLL load");imports(h,"GetModuleHandleA",modules);imports(h,"VirtualProtect",protect);calls=0;return h;}
static void load(HMODULE h){((void(__cdecl *)(void))GetProcAddress(h,"loaded_vampire"))();}
static void call_trace(uint32_t site,unsigned mask,uint8_t *filter,int expect){hit_calls=type_calls=trace_calls=0;input_filter=filter;((TraceFn)(server+site-21))(trace_obj,(void *)0x1234,mask,filter,(void *)0x5678);check(corrected==expect,"trace guard");check(hit_calls==(expect?1:3)&&type_calls==1&&trace_calls==1,"no diagnostic filter calls");}
int main(int argc,char **argv){HMODULE h;uint8_t sync[6],ray[6],nav[6],eng[7],filter[24];void(__cdecl *tick)(void *,void *);TraceFn tf;GroundFn gf;unsigned i;uint32_t sites[]={0x3cbb59,0x3cbc52,0x3cbd33,0x26eb39,0x2a9aef,0x26ad67,0x2e3630,0x2e38a7};void *set_origin;
 check(argc==4,"plugin/server/engine arguments");server=map_image(argv[2]);engine=map_image(argv[3]);memcpy(sync,server+0x16c5be,6);memcpy(ray,server+0x6dec0,6);memcpy(nav,server+0x2e30d0,6);memcpy(eng,engine+0x1b800,7);
 for(i=0;i<4;i++){uint8_t *p=i==0?server+0x16c5be:i==1?server+0x6dec0:i==2?server+0x2e30d0:engine+0x1b800;uint8_t old=*p;*p=0xe9;h=open_plugin(argv[1]);load(h);check(!calls,"signature/conflicting hook rejects");FreeLibrary(h);*p=old;}
 fail_at=1;h=open_plugin(argv[1]);load(h);check(!memcmp(server+0x16c5be,sync,6),"sync install error preserves original bytes");FreeLibrary(h);fail_at=0;
 h=open_plugin(argv[1]);load(h);tick=(void *)*(uint32_t *)(destination(server+0x16c5be)+5);check((uint8_t *)tick>(uint8_t *)h,"tick belongs to delivered image");jump(engine+0x1b800,level);
 player=calloc(1,0x3000);shadow=calloc(1,0x3000);wolf=calloc(1,0x3000);table=calloc(8192,12);check(player&&shadow&&wolf&&table,"objects");put(server+0x566458,(uint32_t)(uintptr_t)table);
 put(table+16,(uint32_t)(uintptr_t)player);put(table+20,7);put(table+28,(uint32_t)(uintptr_t)shadow);put(table+32,7);put(table+40,(uint32_t)(uintptr_t)wolf);put(table+44,7);
 put(player+0x146c,1);put(player+0x1db0,(7<<13)|2);put(shadow,(uint32_t)(uintptr_t)(server+0x4b2184));put(wolf,(uint32_t)(uintptr_t)(server+0x4cf4d4));put(wolf+0x26c,(uint32_t)(uintptr_t)"werewolf");
 ((void **)(server+0x4b2184))[0x364/4]=origin;((void **)(server+0x4cf4d4))[0x364/4]=origin;set_origin=((void **)(server+0x4cf4d4))[216];check(((void **)(server+0x4cf4d4))[208]==server+0x158e8,"stock ground site");jump(server+0x158e8,ground_fn);
 trace_obj[0]=trace_vt;trace_vt[4]=trace_fn;put(server+0x70b254,(uint32_t)(uintptr_t)trace_obj);((void **)(server+0x482fe4))[0]=hit;((void **)(server+0x482fe4))[1]=type;((void **)(server+0x49d8c0))[0]=hit;((void **)(server+0x49d8c0))[1]=type;
 tick(player,NULL);check(((void **)(server+0x4cf4d4))[216]==set_origin,"stock SetOrigin never hooked");tf=trace_vt[4];gf=((void **)(server+0x4cf4d4))[208];check(tf!=trace_fn&&gf!=(void *)ground_fn,"only required TraceRay and SetGround installed");
 for(i=0;i<8;i++)emit_trace(sites[i],tf);emit_trace(0x26eb00,tf);emit_ground(0x26e849,gf);emit_ground(0x26e800,gf);nested=(TraceFn)(server+0x3cbb59-21);
 memset(filter,0,sizeof(filter));put(filter,(uint32_t)(uintptr_t)(server+0x482fe4));put(filter+4,(uint32_t)(uintptr_t)wolf);put(filter+8,11);for(i=0;i<8;i++)call_trace(sites[i],0x0202400b,filter,1);call_trace(sites[0],0x0200400b,filter,1);call_trace(sites[0],7,filter,0);call_trace(0x26eb00,0x0202400b,filter,0);
 *(Vec *)(wolf+0x800)=(Vec){161,0,0};call_trace(sites[0],0x0202400b,filter,0);*(Vec *)(wolf+0x800)=(Vec){159,0,0};call_trace(sites[0],0x0202400b,filter,1);
 put(filter,(uint32_t)(uintptr_t)(server+0x49d8c0));put(filter+0x10,(uint32_t)(uintptr_t)wolf);put(filter+0x14,11);call_trace(sites[0],0x0202400b,filter,1);
 ((GroundFn)(server+0x26e849-9))(wolf,player);check(ground==NULL,"no original-player support");((GroundFn)(server+0x26e849-9))(wolf,shadow);check(ground==shadow,"shadow interaction preserved");((GroundFn)(server+0x26e800-9))(wolf,player);check(ground==player,"unrelated ground caller forwarded");
 recurse=1;input_filter=filter;hit_calls=type_calls=trace_calls=0;nested(trace_obj,(void *)0x1234,0x0202400b,filter,(void *)0x5678);check(hit_calls==4&&trace_calls==2&&type_calls==2,"nested trace ABI and forwarding");
 put(table+32,8);call_trace(sites[0],0x0202400b,filter,0);((GroundFn)(server+0x26e849-9))(wolf,player);check(ground==player,"stale handle forwarded");tick(player,NULL);put(table+32,7);call_trace(sites[0],0x0202400b,filter,0);tick(player,NULL);
 put(player+0x146c,0);tick(player,NULL);call_trace(sites[0],0x0202400b,filter,0);put(player+0x146c,1);tick(player,NULL);map="sm_pawnshop_1";tick(player,NULL);call_trace(sites[0],0x0202400b,filter,0);map="sp_observatory_2";call_trace(sites[0],0x0202400b,filter,0);tick(player,NULL);call_trace(sites[0],0x0202400b,filter,1);
 check(((void **)(server+0x4cf4d4))[216]==set_origin,"SetOrigin unchanged after all workflows");check(!memcmp(server+0x6dec0,ray,6)&&!memcmp(server+0x2e30d0,nav,6),"ABI anchors never become hooks");FreeLibrary(h);puts("PASS exact DLL TraceRay/SetGround ABI, all callsites, masks, distance, owner/map/handle lifecycle, no extra sampling or SetOrigin");return 0;
}
