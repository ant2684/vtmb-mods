/* Exact delivery DLL tests in a mapped, private native image. No game process. */
#include "native_fixture.h"
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
typedef unsigned char B;
typedef void (TC *Add)(void *,void *);
typedef B *(__cdecl *Create)(B *,const char *,int);
static B *server,*pc,*fists,*sword,*knife,*claws,*table; __attribute__((used)) static B *entry,*actor_for_end;
static B globals[64],header[256],*expected_fx_actor;
static unsigned protect_calls,fail_protect,add_calls,front_calls,create_calls,ensure_calls,proxy_calls,removed,events,fx,activity;
static unsigned select_calls,trait_calls;
static unsigned refresh_calls,pose_calls,current_gender=1;
static unsigned char FC gender_native(B *p,void *unused){(void)unused;check(p==pc,"gender getter receiver");return (unsigned char)current_gender;}
static void FC gender_set(B *group,void *unused,int trait,int value){(void)unused;check(group==server+0x9f0b40&&trait==11&&(value==0||value==1),"native gender stat ABI");current_gender=(unsigned)value;}

static void FC refresh_native(B *p,void *unused,int action,int flags){(void)unused;(void)action;(void)flags;++refresh_calls;p[0x65c]=1;}
static int reenter_add,reenter_create,reenter_ensure,retarget_alias_failure;
static const unsigned sites[]={0x1f88eb,0x1f9193,0x3daf,0x33dde0,0x16c416,0x11fdb,0xd91d,0x1f9a80,0x351090,0x3485fd,0x1f926d,0xcc93,0x1005a,0x227a30,0x196ec3,0xcee53,0x2c2ec0};
static const unsigned sizes[]={7,9,5,5,7,5,5,5,5,6,5,5,5,6,5,8,6};
static unsigned U(B *p,unsigned o){return *(unsigned *)(p+o);}
static void P(B *p,unsigned o,unsigned v){*(unsigned *)(p+o)=v;}
static void *R(unsigned h){if(h==0xffffffffu)return NULL;B *e=table+(h&8191)*12;return U(e,8)==h>>13?*(void **)(e+4):NULL;}
static unsigned H(B *p){for(unsigned i=0;i<17192;i++)if(*(void **)(table+i*12+4)==p)return i|(U(table+i*12,8)<<13);return 0xffffffffu;}
static B *entity(const char *name,unsigned id){B *p=calloc(1,0x2600);check(p!=NULL,"fixture allocation");P(p,0x11c,(unsigned)(uintptr_t)name);P(table,id*12+4,(unsigned)(uintptr_t)p);P(table,id*12+8,7);P(p,0x1db0,0xffffffffu);P(p,0x1538,0xffffffffu);P(p,0x153c,0xffffffffu);P(p,0x149c,0xffffffffu);return p;}

static HMODULE WINAPI modules(LPCSTR name){
 return !strcmp(name,"vampire.dll")?(HMODULE)server:NULL;
}
static DWORD WINAPI executable(HMODULE h,LPSTR p,DWORD n){(void)h;(void)n;strcpy(p,"C:\\Fixture\\Vampire.exe");return strlen(p);}
static DWORD WINAPI profile(LPCSTR section,LPCSTR key,LPCSTR fallback,LPSTR p,DWORD n,LPCSTR path){
 (void)section;(void)fallback;(void)n;(void)path;p[0]=!strcmp(key,"InventoryFixes")||!strcmp(key,"ProteanTransformFixes")?'1':'0';p[1]=0;return 1;
}
static BOOL WINAPI protect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old){++protect_calls;return protect_calls==fail_protect?FALSE:VirtualProtect(p,n,flags,old);}
/* Isolate this component: the independent model collector intentionally ignores INI switches. Its guards/pools are covered by exact_configuration and exact NPC fixtures. */
static HMODULE open_plugin(const char *path){server[0x8dac0]=0xcc;HMODULE h=LoadLibraryA(path);check(h!=NULL,"load exact candidate");imports(h,"GetModuleHandleA",modules);imports(h,"VirtualProtect",protect);imports(h,"GetModuleFileNameA",executable);imports(h,"GetPrivateProfileStringA",profile);protect_calls=0;return h;}
static void install(HMODULE h){void (__cdecl *f)(void)=(void *)GetProcAddress(h,"loaded_vampire");check(f!=NULL,"only loader API required");f();}
static void FC add_native(B *p,void *unused,B *item){(void)unused;++add_calls;
 if(reenter_add){reenter_add=0;((Add)(server+0x3daf))(p,item);}
 for(unsigned i=0;i<224;i++)if(U(p,0x1624+i*4)==0xffffffffu){P(p,0x1624+i*4,H(item));P(item,0x73c,i);P(item,0x88c,H(p));return;}
 check(0,"fixture inventory full");
}
static void FC front_native(B *p,void *unused,B *item){(void)unused;++front_calls;unsigned slot=U(item,0x73c),h=H(item);
 for(unsigned i=slot;i>0;i--){unsigned other=U(p,0x1624+(i-1)*4);P(p,0x1624+i*4,other);P(R(other),0x73c,i);}P(p,0x1624,h);P(item,0x73c,0);
}
static B *__cdecl create_native(B *p,const char *name,int flags){(void)flags;int is_claws=!strcmp(name,"item_w_claws");check(is_claws||!strcmp(name,"item_w_fists"),"fixture factory scope");++create_calls;
 if(reenter_create){reenter_create=0;check(!((Create)(server+0x11fdb))(p,name,flags),"nested factory is deferred");}
 ((Add)(server+0x3daf))(p,is_claws?claws:fists);return is_claws?claws:fists;
}
static void __stdcall trait_native(B *p,const char *name){++trait_calls;create_native(p,name,0);}
static void __stdcall remove_trait_native(B *p,const char *name){
 for(unsigned i=0;i<224;i++){
  B *item=R(U(p,0x1624+4*i));if(!item||strcmp(*(const char **)(item+0x11c),name))continue;
  unsigned end=(i/32+1)*32;
  for(unsigned j=i;j+1<end;j++){unsigned h=U(p,0x1624+4*(j+1));P(p,0x1624+4*j,h);if(R(h))P(R(h),0x73c,j);}
  P(p,0x1624+4*(end-1),0xffffffffu);P(item,0x73c,0xffffffffu);P(item,0x88c,0xffffffffu);return;
 }
}
static void FC select_native(B *p,void *unused,const char *name,int flags){(void)unused;(void)flags;check(!strcmp(name,"item_w_claws"),"ordinary claws selection");++select_calls;P(p,0x19a4,H(claws));}
static void FC ensure_native(B *p,void *unused){(void)unused;++ensure_calls;
 if(reenter_ensure){reenter_ensure=0;((void (TC *)(void *))(server+0x33dde0))(p);}
 for(unsigned i=0;i<224;i++)if(R(U(p,0x1624+i*4))==fists)return;
 ((Create)(server+0x11fdb))(p,"item_w_fists",0);
}
static void FC set_model(B *p,void *unused,const char *name){(void)unused;P(p,0x2e0,(unsigned)(uintptr_t)name);if(p==pc&&strstr(name,"Animalism_Beastform"))current_gender=1;if(retarget_alias_failure){P(p,0x6f0,46);retarget_alias_failure=0;}}
static B *FC get_model(B *p,void *unused,int index){(void)p;(void)unused;(void)index;return header;}
static const char *FC seq_name(B *p,void *unused,int index){(void)p;(void)unused;if(index==46)return "claws_attack";if(index==45)return "Claws_alert_180_into";if(index==44||index==144)return "wolf_morph";if(index==42||index==142)return "claws_idle";if(index==43||index==143)return "feeding_attacker_tallvictim_back_bite";return "SEQUENCE_NOT_FOUND";}
static int FC seq_lookup(B *p,void *unused,const char *name){(void)unused;int wolf=p[0x1edc]!=0;if(!strcmp(name,"claws_idle"))return wolf?142:42;if(!strcmp(name,"feeding_attacker_tallvictim_back_bite"))return wolf?143:43;return -1;}
static void FC name_native(B *p,void *unused,const char *name){(void)unused;P(p,0x26c,(unsigned)(uintptr_t)name);}
static void FC activity_one(B *p,void *unused,int a){(void)p;(void)unused;check(a==0x1145||a==1,"native morph/idle activity");++activity;}
static void FC activity_three(B *p,void *unused,int a,int b,int c){(void)p;(void)unused;check((a==0x1145&&b==0x1145&&c==99)||(p==pc&&a==1&&b==1&&(c==42||c==142)),"native activity dispatch");++activity;if(p==pc)P(p,0x6f0,c);}
static int FC heaviest(B *p,void *unused,int a,int b){(void)p;(void)unused;(void)b;if(a==1)return p[0x1edc]?142:42;return p==pc?(p[0x1edc]?144:44):99;}
static uintptr_t player_vt[512],proxy_vt[512];
static B *FC proxy_native(B *p,void *unused,const char *name){(void)unused;check(!strcmp(name,"npc_VWolfMorph")||!strcmp(name,"npc_VFrenzyShadow"),"controller type");B *a=entity(name,100+proxy_calls++);P(a,0,(unsigned)(uintptr_t)proxy_vt);P(p,0x1db0,H(a));P(a,0x2e0,U(p,0x2e0));return a;}
static void FC remove_native(B *p,void *unused){(void)unused;++removed;unsigned h=H(p);check(h!=0xffffffffu,"removal owns a live entity");P(table,(h&8191)*12+4,0);}
static void FC event_native(B *self,void *unused,B *p,int event){(void)unused;check(self==server+0x750cb4&&p==pc&&event==2,"event receiver ABI");++events;}
static void __cdecl fx_native(B *p,int type,float a,float b,float c,const char *name,int mode,const char *color,int x,int y){check(p==pc&&type==11&&a==1&&b==1&&c==1&&!strcmp(name,"D_Protean_4BP_Emitter")&&mode==18&&!strcmp(color,"Bip01 pelvis")&&!x&&!y,"particle ABI");++fx;}
__attribute__((used)) static const char *stock_fx_name="D_Protean_4BP_Emitter",*stock_fx_bone="Bip01 pelvis";
__attribute__((naked)) static void run_stock_fx(void){__asm__ volatile(
 "pushl %edi\n\tcall 1f\n\tpopl %edi\n\tret\n\t"
 "1: pushl $0\n\tpushl $0\n\tpushl _stock_fx_bone\n\tpushl $18\n\tpushl _stock_fx_name\n\t"
 "pushl $0x3f800000\n\tpushl $0x3f800000\n\tpushl $0x3f800000\n\tpushl $11\n\tpushl _pc\n\t"
 "movl _pc,%edi\n\tjmp *_entry\n\t");}
static void FC filter_ctor(B *p,void *unused){(void)unused;P(p,0,0x12345678);}
static void FC filter_pas(B *p,void *unused,const void *origin){(void)unused;check(U(p,0)==0x12345678&&origin==(expected_fx_actor?expected_fx_actor:pc)+0x404,"native PAS filter ABI");P(p,4,1);}
static void FC filter_dtor(B *p,void *unused,int deleting){(void)unused;check(U(p,0)==0x12345678&&U(p,4)==1&&!deleting,"native stack filter destructor ABI");P(p,0,0);}
static void __cdecl temp_fx(B *filter,float delay,B *p,int attach,int bone,const char *name){check(U(filter,0)==0x12345678&&U(filter,4)==1&&delay==0.f&&p==(expected_fx_actor?expected_fx_actor:pc)&&attach==1&&bone==-1&&!strcmp(name,"D_Protean_4BP_Emitter"),"independent finite transformation emitter ABI");++fx;}
static void FC pose_native(B *p,void *unused,int a,int b,int c){(void)unused;check(p==pc&&a==0x1145&&b==-1&&c==1,"actual player animation ABI");++pose_calls;P(p,0x6f0,p[0x1edc]?144:44);}
static unsigned scene_cleanup_calls,discipline_calls;
static void __cdecl discipline_native(B *component,int discipline,int level){
 check(*(B **)(component+0xa8)==pc&&discipline==11&&level==5&&U(pc,0x168)==0,"discipline request runs unchanged after scene completion");++discipline_calls;
}

static void FC cleanup_native(B *p,void *unused,int pose,int position){
 (void)unused;check(p==pc&&pose==1&&position==1,"native cleanup ABI");B *a=R(U(p,0x1db0));
 check(a&&!strcmp(*(const char **)(a+0x11c),"npc_VWolfMorph")&&U(a,0x155c)==H(p),"cleanup exact scene ownership");
 ++scene_cleanup_calls;P(p,0x6f0,U(a,0x6f0));P(p,0x1db0,0xffffffffu);remove_native(a,NULL);
}
static void FC start_scene_native(B *p,void *unused,const char *name){
 (void)unused;B *a=proxy_native(p,NULL,name);P(a,0x168,31);P(a,0x155c,H(p));P(p,0x155c,H(a));P(p,0x168,30);P(p,0x16c,2);p[0x1edc]=1;
 P(a,0x6f0,144);P(a,0x2e0,(unsigned)(uintptr_t)(server+0x586950));strcpy((char *)p+0x23d4,"models/character/pc/male/gangrel/armor_0/Gangrel_Male_Armor_0.mdl");
}
static void FC tick_native(B *p,void *unused){(void)unused;check(p==pc,"native frame receiver");}
__attribute__((naked)) static void run_start(B *p __attribute__((unused))){__asm__ volatile("pushl %ebp\n\tpushl %ebx\n\tpushl %esi\n\tpushl %edi\n\tmovl 20(%esp),%edi\n\tcall *_entry\n\tpopl %edi\n\tpopl %esi\n\tpopl %ebx\n\tpopl %ebp\n\tret\n\t");}
__attribute__((naked)) static void run_end(B *p __attribute__((unused))){__asm__ volatile("pushl %ebp\n\tpushl %ebx\n\tpushl %esi\n\tpushl %edi\n\tmovl 20(%esp),%edi\n\tmovl _actor_for_end,%eax\n\tmovl $2,%ebx\n\tcall *_entry\n\tpopl %edi\n\tpopl %esi\n\tpopl %ebx\n\tpopl %ebp\n\tret\n\t");}
__attribute__((naked)) static void run_tick(B *p __attribute__((unused))){__asm__ volatile("pushl %ebp\n\tpushl %ebx\n\tpushl %esi\n\tpushl %edi\n\tmovl 20(%esp),%ebp\n\tcall *_entry\n\tpopl %edi\n\tpopl %esi\n\tpopl %ebx\n\tpopl %ebp\n\tret\n\t");}

__attribute__((naked)) static void run_command(B *p __attribute__((unused)),int seq __attribute__((unused))){__asm__ volatile("pushl %ebp\n\tpushl %ebx\n\tpushl %esi\n\tpushl %edi\n\tmovl 20(%esp),%esi\n\tmovl 24(%esp),%eax\n\tcall *_entry\n\tpopl %edi\n\tpopl %esi\n\tpopl %ebx\n\tpopl %ebp\n\tret\n\t");}

__attribute__((used,aligned(16))) static B fx_outer[512],fx_before[512],fx_after[512];
__attribute__((used)) static unsigned gp_after[7],flags_before,flags_after,sp_before,sp_after;
__attribute__((used,aligned(16))) static unsigned simd_words[4]={0x11223344,0x55667788,0x99aabbcc,0xddeeff00};
__attribute__((naked)) static void probe_registers(void){__asm__ volatile(
 "pushfl\n\tpushal\n\tfxsave _fx_outer\n\tfninit\n\tfld1\n\tfldpi\n\t"
 "movdqa _simd_words,%xmm0\n\tmovdqa _simd_words,%xmm7\n\t"
 "movl $0x11223344,%eax\n\tmovl $0x22334455,%ecx\n\tmovl $0x33445566,%edx\n\tmovl $0x44556677,%ebx\n\t"
 "movl $0x55667788,%ebp\n\tmovl $0x66778899,%esi\n\tmovl _pc,%edi\n\t"
 "pushl $0x246\n\tpopfl\n\tpushfl\n\tpopl _flags_before\n\tmovl %esp,_sp_before\n\tfxsave _fx_before\n\t"
 "call *_entry\n\tfxsave _fx_after\n\tmovl %esp,_sp_after\n\tpushfl\n\tpopl _flags_after\n\t"
 "movl %eax,_gp_after\n\tmovl %ecx,_gp_after+4\n\tmovl %edx,_gp_after+8\n\tmovl %ebx,_gp_after+12\n\t"
 "movl %ebp,_gp_after+16\n\tmovl %esi,_gp_after+20\n\tmovl %edi,_gp_after+24\n\t"
 "fxrstor _fx_outer\n\tpopal\n\tpopfl\n\tret\n\t");}
static void check_registers(void){
 unsigned expected[]={0x11223344,0x22334455,0x33445566,0x44556677,0x55667788,0x66778899,(unsigned)(uintptr_t)pc};
 check(!memcmp(gp_after,expected,sizeof(expected))&&sp_after==sp_before&&flags_after==flags_before,"bridge preserves GPRs, stack and flags");
 check(!memcmp(fx_before,fx_after,24)&&!memcmp(fx_before+24,fx_after+24,8)&&!memcmp(fx_before+32,fx_after+32,128)&&!memcmp(fx_before+160,fx_after+160,128),"bridge preserves x87, MXCSR and SSE registers");
}

static void hooks_unchanged(B old[17][10]){for(unsigned j=0;j<17;j++)check(!memcmp(server+sites[j],old[j],sizes[j]),"failed install left all hooks unchanged");}
static void setup(void){
 table=calloc(8192,12);check(table!=NULL,"entity table");P(server,0x566458,(unsigned)(uintptr_t)table);P(server,0x70b228,(unsigned)(uintptr_t)globals);*(float *)(globals+12)=100.f;
 pc=entity("player",1);fists=entity("item_w_fists",2);sword=entity("item_w_katana",3);knife=entity("item_w_knife",4);claws=entity("item_w_claws",5);P(pc,0,(unsigned)(uintptr_t)player_vt);
 for(unsigned i=0;i<224;i++)P(pc,0x1624+4*i,0xffffffffu);P(pc,0x6f0,42);P(pc,0x650,42);*(float *)(pc+0x6f4)=1.f;*(float *)(pc+0x6f8)=.35f;
 strcpy((char *)header+12,"character/pc/male/gangrel/armor_0/Gangrel_Male_Armor_0.mdl");
 player_vt[0x4d8/4]=(uintptr_t)activity_one;player_vt[0x4dc/4]=(uintptr_t)activity_three;player_vt[0x724/4]=(uintptr_t)select_native;player_vt[0x1a4/4]=(uintptr_t)set_model;proxy_vt[0x1a4/4]=(uintptr_t)set_model;proxy_vt[0x4d8/4]=(uintptr_t)activity_one;proxy_vt[0x4dc/4]=(uintptr_t)activity_three;
 server[0x1f9a85]=0x5e;jump(server+0x1f9a86,trait_native);jump(server+0x336920,gender_native);jump(server+0x2008e0,gender_set);jump(server+0xd8830,discipline_native);jump(server+0x1618e0,cleanup_native);jump(server+0x181680,refresh_native);jump(server+0x334e70,add_native);jump(server+0x335780,front_native);jump(server+0x21fe50,create_native);server[0x33dde5]=0x5e;jump(server+0x33dde6,ensure_native);
 jump(server+0x19ce00,filter_ctor);jump(server+0x19d210,filter_pas);jump(server+0xf5fc0,filter_dtor);jump(server+0x69e80,temp_fx);jump(server+0x1644f0,pose_native);jump(server+0x1f9af0,remove_trait_native);jump(server+0xa0420,name_native);jump(server+0x952d0,get_model);jump(server+0x8fe80,seq_name);jump(server+0xe057,seq_lookup);jump(server+0x161a70,proxy_native);jump(server+0x24f7b0,remove_native);jump(server+0x227a30,event_native);jump(server+0x50d90,fx_native);jump(server+0x125c1,heaviest);jump(server+0x430e,tick_native);
 server[0x1f8a26]=0xc3;server[0x1f8fa3]=0xc3;server[0x1f88f2]=0xe8;P(server,0x1f88f3,(unsigned)((B *)start_scene_native-(server+0x1f88f7)));server[0x1f88f7]=0xc3;memcpy(server+0x351095,"\x5e\xc2\x04\x00",4);server[0x348603]=server[0x348612]=server[0x1f9272]=0xc3;server[0x1f919c]=0xc3;server[0x16c41d]=0xc3;
}
static void place(B *item,unsigned slot){P(pc,0x1624+slot*4,H(item));P(item,0x73c,slot);P(item,0x88c,H(pc));}
static void frenzy_inventory_cases(void){
 static const char *names[]={"item_w_knife","item_w_tire_iron","item_w_baton","item_w_baseball_bat","item_w_severed_arm","item_w_torch","item_w_sledgehammer","item_w_fireaxe","item_w_bush_hook","item_w_katana","item_w_avamp_blade","item_w_chang_blade","item_w_occultblade","item_w_chang_claw"};
 B *shadow=entity("npc_VFrenzyShadow",7000),*other=entity("npc_VHumanCombatant",7001),*item=entity("item_w_katana",7002);
 P(pc,0x1380,0);P(pc,0x1db0,H(shadow));
 for(unsigned profile=0;profile<14;++profile)for(unsigned who=0;who<2;++who){
  B *actor=who?shadow:pc;for(unsigned j=0;j<224;++j)P(actor,0x1624+4*j,0xffffffffu);
  P(item,0x11c,(unsigned)(uintptr_t)names[profile]);P(item,0x73c,3);P(item,0x88c,H(actor));P(actor,0x1624+12,H(item));
  unsigned before=add_calls;((Add)(server+0x3daf))(actor,item);
  check(add_calls==before&&U(item,0x73c)==3&&U(actor,0x1624)==0xffffffffu,"all14 player/owned Shadow registrations stay unique");
 }
 P(item,0x11c,(unsigned)(uintptr_t)"item_w_katana");
 for(unsigned j=0;j<224;++j){P(pc,0x1624+4*j,0xffffffffu);P(shadow,0x1624+4*j,0xffffffffu);P(other,0x1624+4*j,0xffffffffu);}
 P(item,0x88c,0xffffffffu);P(item,0x73c,0xffffffffu);
 unsigned before=add_calls;reenter_add=1;((Add)(server+0x3daf))(shadow,item);
 check(add_calls==before+1&&U(shadow,0x1624)==H(item),"new Shadow weapon inserts once despite nested callback");
 P(pc,0x1db0,H(shadow)+0x2000);before=add_calls;((Add)(server+0x3daf))(shadow,item);
 check(add_calls==before+1,"stale owner controller does not enable Shadow guard");P(pc,0x1db0,H(shadow));
 P(item,0x88c,H(other));P(item,0x73c,3);P(other,0x1624+12,H(item));before=add_calls;((Add)(server+0x3daf))(other,item);
 check(add_calls==before+1,"ordinary NPC insertion remains native");
 P(item,0x88c,H(shadow));P(item,0x73c,5);P(shadow,0x1624+20,0xffffffffu);before=add_calls;((Add)(server+0x3daf))(shadow,item);
 check(add_calls==before+1,"mismatched item slot does not suppress native registration");
 P(item,0x11c,(unsigned)(uintptr_t)"item_w_claws");before=add_calls;((Add)(server+0x3daf))(shadow,item);
 check(add_calls==before+1,"ordinary Shadow claws behavior is unchanged");
 P(pc,0x1db0,0xffffffffu);
 puts("PASS unified inventory: 14 profiles/player/owned FrenzyShadow, nested first insert, stale controller, unrelated NPC, mismatched slot, stock claws");
}
int main(int argc,char **argv){
 check(argc==3,"plugin and supported native DLL arguments");B old[17][10];HMODULE h;
 /* OS fault coverage is in exact_configuration, with original RX protections. */
 fail_protect=0;
 for(unsigned i=0;i<17;i++){
  server=map_image(argv[2]);server[sites[i]]^=1;for(unsigned j=0;j<17;j++)memcpy(old[j],server+sites[j],sizes[j]);h=open_plugin(argv[1]);install(h);check(!protect_calls,"occupied hook refused before mutation");hooks_unchanged(old);FreeLibrary(h);VirtualFree(server,0,MEM_RELEASE);
 }
 const unsigned dependencies[]={0x334e70,0x335780,0x33589d,0x33dde0,0x21fe50,0x161a70,0x952d0,0x8fe80,0xe057,0x227a30,0x50d90,0x24f7b0,0x125c1,0x430e,0x181680,0x1f9a80,0xb7fe0,0xa0420,0x1f9af0,0x1644f0,0x19ce00,0x19d210,0xf5fc0,0x69e80,0x1618e0,0xd8830,0x336920,0x2008e0,0x2c2ec6,0x2c31f7,0x31c1d3,0x117b1};
 for(unsigned i=0;i<sizeof(dependencies)/sizeof(dependencies[0]);i++){
  server=map_image(argv[2]);server[dependencies[i]]^=1;for(unsigned j=0;j<17;j++)memcpy(old[j],server+sites[j],sizes[j]);h=open_plugin(argv[1]);install(h);check(!protect_calls,"dependency mismatch refused before mutation");hooks_unchanged(old);FreeLibrary(h);VirtualFree(server,0,MEM_RELEASE);
 }
 server=map_image(argv[2]);
 /* Reproduce the actual shared RX code page: end and trait hooks share it. */
 DWORD image_old,image_tmp;check(VirtualProtect(server+0x1f9000,0x1000,PAGE_EXECUTE_READ,&image_old),"fixture RX code page");
 h=open_plugin(argv[1]);install(h);
 MEMORY_BASIC_INFORMATION page_info;check(VirtualQuery(server+0x1f9000,&page_info,sizeof(page_info))!=0&&page_info.Protect==PAGE_EXECUTE_READ,"shared page original protection restored");
 check(VirtualProtect(server+0x1f9000,0x1000,image_old,&image_tmp),"fixture writable helpers");
 for(unsigned i=0;i<17;i++)check(server[sites[i]]==0xe9,"all seventeen Lifecycle hooks installed");unsigned count=protect_calls;install(h);check(count==protect_calls,"repeated loader callback");
 check(server[0xb0b4]==0xe9&&U(server,0xb0b5)==0x323067,"presentation weapon factory untouched");setup();
 entry=server+0x16c416;run_tick(pc);
 check(U(pc,0x168)==0,"native lifecycle ready with no Python module or handshake");
 place(sword,0);place(knife,1);place(fists,2);P(pc,0x19a4,H(sword));for(unsigned i=0;i<100;i++)((Add)(server+0x3daf))(pc,fists);
 check(!add_calls&&front_calls==1&&U(pc,0x1624)==H(fists)&&U(pc,0x1628)==H(sword)&&U(pc,0x162c)==H(knife)&&U(pc,0x19a4)==H(sword),"repeat insert/order/active weapon");
 for(unsigned i=0;i<224;i++)P(pc,0x1624+4*i,0xffffffffu);reenter_add=1;((Add)(server+0x3daf))(pc,fists);check(add_calls==1&&U(pc,0x1624)==H(fists),"same-handle nested insertion guarded");
 for(unsigned i=0;i<224;i++)P(pc,0x1624+4*i,0xffffffffu);reenter_create=1;((Create)(server+0x11fdb))(pc,"item_w_fists",0);check(create_calls==1,"nested full factory guarded");
 for(unsigned i=0;i<100;i++)check(((Create)(server+0x11fdb))(pc,"item_w_fists",0)==fists,"registered fists reused");check(create_calls==1,"no repeated entity allocation");
 for(unsigned i=0;i<224;i++)P(pc,0x1624+4*i,0xffffffffu);reenter_ensure=1;((void(TC *)(void *))(server+0x33dde0))(pc);check(ensure_calls==1&&create_calls==2,"nested ensure guarded without losing fists");
 entry=server+0x1f88eb;P(pc,0x2088,1);probe_registers();check_registers();check(pc[0x1edc]==1&&U(pc,0x168)==0&&U(pc,0x1db0)==0xffffffffu&&!proxy_calls,"held action has priority and form immediate");
 P(pc,0x2088,1);actor_for_end=proxy_native(pc,NULL,(char *)server+0x5a6be0);entry=server+0x1f9193;run_end(pc);check(!pc[0x1edc]&&U(pc,0x168)==0&&U(pc,0x1db0)==0xffffffffu&&fx==1,"immediate return with cosmetic proxy detached");
 entry=server+0x16c416;P(pc,0x2088,1);run_tick(pc);check(!(U(pc,0x19c)&0x20),"any input interrupts presentation");P(pc,0x2088,0);
 B *victim=entity("npc_VHumanCombatant",20);P(pc,0x1538,H(victim));P(pc,0x153c,0);P(pc,0x6f0,43);P(pc,0x650,43);P(pc,0x734,1);P(pc,0x73c,43);P(pc,0x760,0x3eaaaaab);unsigned before_proxy=proxy_calls,before_events=events;float before_cycle=*(float *)(pc+0x6f8);
 entry=server+0x1f88eb;run_start(pc);check(pc[0x1edc]&&U(pc,0x6f0)==143&&U(pc,0x650)==143&&U(pc,0x73c)==143&&U(pc,0x760)==0x3eaaaaab&&*(float *)(pc+0x6f8)==before_cycle,"feeding sequence indices remapped with event cursor and progress retained");
 P(pc,0x1380,5);pc[0x65c]=0;((void(TC *)(void *,int,int))(server+0xd91d))(pc,0,1);check(!refresh_calls&&!pc[0x65c],"model refresh does not finish bite");
 check(U(pc,0x1538)==H(victim)&&U(pc,0x153c)==0&&proxy_calls==before_proxy&&events==before_events+1,"feeding partner untouched and no morph animation");
 actor_for_end=proxy_native(pc,NULL,(char *)server+0x5a6be0);before_proxy=proxy_calls;entry=server+0x1f9193;run_end(pc);check(!pc[0x1edc]&&U(pc,0x6f0)==43&&U(pc,0x1538)==H(victim)&&proxy_calls==before_proxy,"expiry during feeding preserves pair and skips presentation");
 P(pc,0x1380,0);P(globals,4,U(globals,4)+1);((void(TC *)(void *,int,int))(server+0xd91d))(pc,0,1);check(refresh_calls==1,"stale frame ticket cannot suppress a later refresh");

 P(pc,0x1380,5);P(pc,0x1538,H(victim));P(pc,0x153c,0);P(pc,0x2088,1);entry=server+0x1f88eb;run_start(pc);
 ((void(__stdcall *)(B *,const char *))(server+0x1f9a80))(pc,"item_w_claws");entry=server+0x16c416;run_tick(pc);check(trait_calls==1&&!select_calls,"claws grant while feeding defers only selection");
 for(unsigned j=0;j<100;j++)((void(__stdcall *)(B *,const char *))(server+0x1f9a80))(pc,"item_w_claws");check(trait_calls==1,"repeated trait grant never allocates a second claws entity");
 P(pc,0x1538,0xffffffffu);P(pc,0x153c,0xffffffffu);entry=server+0x16c416;run_tick(pc);check(select_calls==1&&U(pc,0x19a4)==H(claws),"native selection once on exact feeding completion");run_tick(pc);check(select_calls==1,"deferred selection never repeats");
 P(pc,0x1538,H(victim));P(pc,0x153c,0);entry=server+0x1f88eb;run_start(pc);((void(__stdcall *)(B *,const char *))(server+0x1f9a80))(pc,"item_w_claws");entry=server+0x16c416;run_tick(pc);
 P(table,1*12+8,8);P(pc,0x1538,0xffffffffu);P(pc,0x153c,0xffffffffu);entry=server+0x16c416;run_tick(pc);check(select_calls==1,"serial replacement invalidates pending selection");P(table,1*12+8,7);run_tick(pc);check(select_calls==1,"invalidated selection cannot return on pointer reuse");
 P(pc,0x1538,H(victim));P(pc,0x153c,0);P(pc,0x1380,5);entry=server+0x1f88eb;run_start(pc);((void(__stdcall *)(B *,const char *))(server+0x1f9a80))(pc,"item_w_claws");entry=server+0x16c416;run_tick(pc);
 actor_for_end=proxy_native(pc,NULL,(char *)server+0x5a6be0);entry=server+0x1f9193;run_end(pc);P(pc,0x1380,0);P(pc,0x1538,0xffffffffu);P(pc,0x153c,0xffffffffu);entry=server+0x16c416;run_tick(pc);check(select_calls==1,"cancellation invalidates pending selection");

 P(pc,0x1538,0xffffffffu);P(pc,0x153c,0xffffffffu);P(pc,0x168,0);P(pc,0x1db0,0xffffffffu);P(pc,0x6f0,42);P(pc,0x2088,0);P(pc,0x1380,5);pc[0x1edc]=0;
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);
 B *scene=R(U(pc,0x1db0));check(scene&&U(pc,0x168)==30&&U(scene,0x168)==31&&U(pc,0x6f0)==42,"idle delegates original human/beast scene without replacing primary pose");
 check(!strcmp(*(const char **)(scene+0x26c),"__protean_lifecycle_native_v2"),"scene gets serialized ownership marker");
 current_gender=0;unsigned fx_before=fx;entry=server+0x1f926d;probe_registers();check_registers();check(fx==fx_before+1,"return particle bridge uses stack ABI and preserves complete machine state");
 B quiet[96]={0};unsigned quiet_clean=scene_cleanup_calls;float stable_time=*(float *)(globals+12);
 *(float *)(globals+12)-=.08f;((void(TC *)(B *,B *))(server+0x351090))(pc,quiet);
 check(U(pc,0x168)==30&&scene_cleanup_calls==quiet_clean,"per-command prediction clock jitter is not mistaken for a load");
 *(float *)(globals+12)=stable_time+.1f;entry=server+0x16c416;run_tick(pc);check(U(pc,0x168)==30,"stable frame keeps original scene after command clock jitter");
 B cmd[96]={0};P(cmd,0x30,1);unsigned clean_before=scene_cleanup_calls;
 ((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 check(scene_cleanup_calls==clean_before+1&&U(pc,0x168)==0&&U(pc,0x1db0)==0xffffffffu&&pc[0x1edc]&&U(pc,0x6f0)==142&&U(cmd,0x30)==1,"raw attack completes owned scene before native input and preserves same command");check(current_gender==0&&U(pc,0x13cc)==0,"shared beast initialization preserves original female gender metadata");
 ((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);check(scene_cleanup_calls==clean_before+1,"input completion is idempotent");
 P(cmd,0x30,0);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 P(pc,0x6f0,42);pc[0x1edc]=0;entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);scene=R(U(pc,0x1db0));check(scene!=NULL,"second idle scene");
 P(cmd,0x20,0x43c80000);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 check(U(pc,0x168)==0&&pc[0x1edc]&&U(cmd,0x20)==0x43c80000,"forward axis completes scene before suppression");
 P(cmd,0x20,0);P(cmd,0x30,0);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);P(pc,0x6f0,42);pc[0x1edc]=0;
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);
 B *component=entity("component",70);P(component,0xa8,(unsigned)(uintptr_t)pc);
 ((void(__cdecl *)(B *,int,int))(server+0x1005a))(component,11,5);check(discipline_calls==1&&U(pc,0x168)==0,"discipline hotkey completes current scene before native validity checks");
 P(cmd,0x20,0);P(cmd,0x30,0);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);P(pc,0x6f0,42);pc[0x1edc]=0;
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;P(pc,0x146c,1);clean_before=scene_cleanup_calls;
 B *shadow=((B *(TC *)(B *,const char *))(server+0xcc93))(pc,"npc_VFrenzyShadow");
 check(shadow&&U(pc,0x1db0)==H(shadow)&&scene_cleanup_calls==clean_before+1&&U(shadow,0x2e0)==(unsigned)(uintptr_t)(server+0x586950),"complete our scene before native Frenzy acquires the final beast model");
 P(cmd,0x20,0);P(pc,0x146c,1);B *frenzy=entity("npc_VFrenzyShadow",30);P(pc,0x1db0,H(frenzy));P(pc,0x168,30);clean_before=scene_cleanup_calls;
 ((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);check(U(pc,0x1db0)==H(frenzy)&&scene_cleanup_calls==clean_before,"unrelated genuine Frenzy controller is never finished");
 P(pc,0x168,0);P(pc,0x1380,5);pc[0x1edc]=1;entry=server+0x16c416;run_tick(pc);
 expected_fx_actor=frenzy;P(globals,4,U(globals,4)+1);P(pc,0x1380,0);pc[0x1edc]=0;fx_before=fx;((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 check(fx==fx_before+1&&U(pc,0x1db0)==H(frenzy)&&U(pc,0x146c)==1,"Core reverse during true Frenzy emits on the visible Shadow without touching ownership");
 run_tick(pc);check(fx==fx_before+1,"true Frenzy return effect does not repeat on later frames");expected_fx_actor=NULL;

 /* Additional boundary cases execute the same frozen delivery bytes. */
 P(pc,0x146c,0);P(pc,0x168,0);P(pc,0x1db0,0xffffffffu);P(pc,0x6f0,42);P(pc,0x1380,5);pc[0x1edc]=0;
 P(pc,0x2088,4);P(pc,0x434,2);memset(cmd,0,sizeof(cmd));P(cmd,0x30,4);
 ((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);clean_before=scene_cleanup_calls;
 ((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);check(U(pc,0x168)==30,"held duck preserves native scene");
 P(cmd,0x30,0);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);check(U(pc,0x168)==30,"toggle-duck button release preserves stationary crouch scene");
 entry=server+0x3485fd;run_command(pc,45);check(U(pc,0x168)==30&&U(pc,0x6f0)==42,"background alert command cannot replace own scene");
 run_command(pc,46);check(U(pc,0x168)==0&&U(pc,0x6f0)==46&&scene_cleanup_calls==clean_before+1,"scripted attack completes scene then keeps original sequence command");
 run_command(pc,45);check(U(pc,0x6f0)==45,"outside scene native idle command remains allowed");
 P(pc,0x6f0,42);pc[0x1edc]=0;P(pc,0x2088,4);P(cmd,0x30,4);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);
 P(cmd,0x30,0);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);P(cmd,0x30,4);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 check(U(pc,0x168)==0,"new crouch press immediately interrupts scene");
 P(pc,0x2088,0);P(pc,0x434,0);P(cmd,0x30,0);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);P(pc,0x6f0,42);pc[0x1edc]=0;
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);scene=R(U(pc,0x1db0));check(scene&&U(pc,0x168)==30,"serialized scene fixture setup");
 *(float *)(globals+12)-=10.f;clean_before=scene_cleanup_calls;run_tick(pc);
 check(U(pc,0x168)==0&&U(pc,0x1db0)==0xffffffffu&&pc[0x1edc]&&scene_cleanup_calls==clean_before+1,"loaded v2 marker completes target without replay");
 B *legacy=proxy_native(pc,NULL,"npc_VWolfMorph");P(legacy,0x26c,(unsigned)(uintptr_t)"__protean_lifecycle_visual_v1");P(legacy,0x155c,H(pc));P(pc,0x19c,U(pc,0x19c)|0x20);
 *(float *)(globals+12)-=10.f;unsigned removed_before=removed;run_tick(pc);
 check(removed==removed_before+1&&U(pc,0x1db0)==0xffffffffu&&!(U(pc,0x19c)&0x20),"loaded legacy marker restores player visibility without replay");
 P(pc,0x146c,0xffffffffu);P(pc,0x1380,5);pc[0x1edc]=1;run_tick(pc);fx_before=fx;P(pc,0x1380,0);pc[0x1edc]=0;run_tick(pc);
 check(fx==fx_before,"negative Frenzy counter does not create a false Core return effect");

 /* Walking is a speed modifier, not actual locomotion, even when toggled. */
 P(pc,0x146c,0);P(pc,0x168,0);P(pc,0x1db0,0xffffffffu);P(pc,0x6f0,42);P(pc,0x1380,5);pc[0x1edc]=0;
 memset(cmd,0,sizeof(cmd));P(cmd,0x30,0x20000u);P(pc,0x2088,0x20000u);
 ((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);
 check(U(pc,0x168)==30,"stationary speed modifier permits original morph scene");
 clean_before=scene_cleanup_calls;((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 check(U(pc,0x168)==30&&scene_cleanup_calls==clean_before,"held speed does not interrupt the scene");
 P(cmd,0x30,0);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);P(cmd,0x30,0x20000u);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 check(U(pc,0x168)==30,"speed-mode toggle alone does not interrupt the scene");
 P(cmd,0x20,0x43c80000);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 check(U(pc,0x168)==0&&pc[0x1edc]&&U(cmd,0x30)==0x20000u&&U(cmd,0x20)==0x43c80000,"actual walk motion finishes scene before preserving the same command");
 P(cmd,0x20,0);P(pc,0x6f0,42);pc[0x1edc]=0;((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);P(cmd,0x30,0x20001u);
 ((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);check(U(pc,0x168)==0&&U(cmd,0x30)==0x20001u,"attack still interrupts with speed mode held");

 /* Interface state is not a body action, including a latched hidden panel. */
 P(pc,0x146c,0);P(pc,0x168,0);P(pc,0x1db0,0xffffffffu);P(pc,0x6f0,42);P(pc,0x1380,5);pc[0x1edc]=0;
 memset(cmd,0,sizeof(cmd));P(cmd,0x30,0x4000000u);P(pc,0x2088,0x4000000u);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);check(U(pc,0x168)==30,"latched character/quest interface state permits native morph");
 ((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);check(U(pc,0x168)==30,"interface state does not interrupt native morph");
 P(cmd,0x30,0x4000001u);((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);check(U(pc,0x168)==0&&U(cmd,0x30)==0x4000001u,"attack keeps priority with interface state");
 /* A load may reuse player address/serial while the old scene has disappeared. */
 P(cmd,0x30,0x4000000u);P(pc,0x2088,0x4000000u);P(pc,0x6f0,42);pc[0x1edc]=0;((void(TC *)(B *,B *))(server+0x351090))(pc,cmd);
 entry=server+0x1f88eb;run_start(pc);entry=server+0x16c416;run_tick(pc);B *old_scene=R(U(pc,0x1db0));check(old_scene&&U(pc,0x168)==30,"unfinished scene before simulated reload");
 remove_native(old_scene,NULL);P(pc,0x1db0,0xffffffffu);P(pc,0x155c,0xffffffffu);P(pc,0x168,0);P(pc,0x16c,0);P(pc,0x6f0,42);pc[0x1edc]=0;*(float *)(globals+12)+=5.f;
 entry=server+0x1f88eb;run_start(pc);check(U(pc,0x168)==30&&R(U(pc,0x1db0)),"stale scene ticket after forward-time load does not suppress new idle scene");
 /* Ending Frenzy may remove/recreate Claws AFTER native weapon restoration.
    Presence alone does not prove that the surviving P5 selected its weapon. */
 setup();select_calls=0;place(claws,0);place(sword,1);P(pc,0x19a4,H(sword));P(pc,0x1380,5);pc[0x1edc]=1;
 B *finish_shadow=entity("npc_VFrenzyShadow",7100);P(pc,0x1db0,H(finish_shadow));P(pc,0x146c,1);
 entry=server+0x16c416;run_tick(pc);check(!select_calls,"active Frenzy retains controller weapon selection");
 P(pc,0x146c,0);P(pc,0x1db0,0xffffffffu);run_tick(pc);
 check(select_calls==1&&U(pc,0x19a4)==H(claws),"remaining P5 selects its registered Claws after complete Frenzy cleanup");
 run_tick(pc);check(select_calls==1,"Frenzy-end selection is one-shot, not per-frame weapon enforcement");
 P(pc,0x19a4,H(sword));run_tick(pc);check(select_calls==1&&U(pc,0x19a4)==H(sword),"later manual selection is not overridden");
 P(pc,0x146c,1);P(pc,0x1db0,H(finish_shadow));run_tick(pc);P(pc,0x146c,0);P(pc,0x1db0,0xffffffffu);P(pc,0x1380,2);run_tick(pc);
 check(select_calls==1&&U(pc,0x19a4)==H(sword),"lower Protean tiers retain their selected melee weapon");
 P(pc,0x1380,5);P(pc,0x146c,1);P(pc,0x1db0,H(finish_shadow));run_tick(pc);
 B *finish_partner=entity("npc_VHumanCombatant",7101);P(pc,0x1538,H(finish_partner));P(pc,0x153c,0);P(pc,0x146c,0);P(pc,0x1db0,0xffffffffu);run_tick(pc);
 check(select_calls==1&&U(pc,0x1538)==H(finish_partner),"Frenzy-end restoration preserves an existing feeding pair");
 P(pc,0x1538,0xffffffffu);P(pc,0x153c,0xffffffffu);run_tick(pc);check(select_calls==2&&U(pc,0x19a4)==H(claws),"Frenzy-end Claws selection occurs once after feeding release");
 frenzy_inventory_cases();
 puts("PASS exact candidate: 17 hook conflicts, 32 dependency conflicts; repeated/nested inventory, shared RX page, ABI preservation, feeding event continuity, original scene delegation and same-command input interruption, stationary speed/interface state, stale loaded-scene ticket with motion/attack priority; integrated configuration and OS faults checked separately.");
 return 0;
}
