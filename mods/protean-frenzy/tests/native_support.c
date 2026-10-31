/* Supplementary source-compiled regression for native callback ownership.
   Exact-DLL ABI/install regressions and live scenarios are separate gates. */
#include "native_fixture.h"
#include "../native/lifecycle.c"
#include "../native/patch.c"
int pfi_options[PFI_COUNT];
int pfi_inventory_ready=1;
int pfi_transform_active(void){return pfi_options[PFI_TRANSFORM]&&pfi_inventory_ready;}
static B *pc,*shadow,*table;
static B globals[64];
static unsigned corpus_calls,reset_calls,dispatch_calls;
static int expected_corpus,expected_discipline=4;
static B *expected_actor;
static B * __cdecl get_player(int index){check(index==1,"local player index");return pc;}
static void FC corpus(B *actor,void *unused,int discipline,int level){
    (void)unused;check(actor==expected_actor&&discipline==expected_discipline&&level==expected_corpus,"native setter original receiver/enum/tier");
    ++corpus_calls;if(discipline==4)*(unsigned *)(actor+0x1364)=(unsigned)level;
}
static int FC lookup(B *actor,void *unused,const char *name){
    (void)unused;check(actor==pc,"native sequence lookup receiver");
    for(unsigned j=0;j<4;++j)if(!strcmp(name,exit_sequences[j]))return 100+(int)j;
    check(0,"only mapped native alert exits");return -1;
}
static void FC reset(B *actor,void *unused){(void)unused;check(actor==pc,"native cycle reset receiver");++reset_calls;}
static void FC dispatch(B *manager,void *unused,B *actor,int event){
    (void)manager;(void)unused;check(actor==pc,"event player forwarding");++dispatch_calls;
    if(event==15){
        check(!capture_task("__main__.ccmd.holster=\"\"",0.f),"owned P5 holster task cancelled before Python object creation");
        check(!capture_task("__main__.ccmd.setClaws=\"\"",2.f),"owned P5 delayed claws task cancelled");
    }
}
static void set(B *p,unsigned offset,unsigned value){*(unsigned *)(p+offset)=value;}
static B *entity(const char *name,unsigned index){
    B *p=calloc(1,0x7000);check(p!=NULL,"entity allocation");
    *(const char **)(p+0x11c)=name;
    *(B **)(table+index*12+4)=p;set(table,index*12+8,7);
    set(p,0x1db0,0xffffffffu);set(p,0x1538,0xffffffffu);set(p,0x153c,0xffffffffu);
    return p;
}
static void reset_tickets(void){
    memset(tickets,0,sizeof(tickets));reset_calls=0;
    set(pc,0x1380,5);set(pc,0x2e0,123);set(pc,0x6f0,42);
    set(pc,0x146c,0);set(pc,0x1db0,0xffffffffu);set(pc,0x168,0);
    world_player=pc;world_handle=handle_of(pc);world_time=10.f;
    *(float *)(globals+12)=10.f;scene_ptr=NULL;++morph_epoch;
}
int main(void){
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    module=VirtualAlloc(NULL,0xb00000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    table=calloc(8192,12);check(module&&table,"private native image allocation");
    *(B **)(module+0x566458)=table;*(B **)(module+0x70b228)=globals;
    pc=entity("player",1);shadow=entity("npc_VFrenzyShadow",2);expected_actor=shadow;
    *(B **)shadow=module+0x4b2184;
    jump(module+0xac8b,get_player);jump(module+0x2c2ec0,corpus);
    jump(module+0xe057,lookup);jump(module+0x117b1,reset);
    pfi_options[PFI_INVENTORY]=pfi_options[PFI_TRANSFORM]=1;
    native_event_dispatch=(void *)dispatch;original_corpus=(void *)corpus;

    set(pc,0x146c,10);set(pc,0x1db0,handle_of(shadow));set(pc,0x11a4,3);
    expected_corpus=3;frenzy_tick(pc);
    check(corpus_calls==1&&u(shadow,0x1364)==3,"missing callback repaired through native Corpus");
    for(unsigned j=0;j<100;++j)frenzy_tick(pc);
    check(corpus_calls==1,"repeated ticks cannot reapply bonuses");
    scripted_corpus(shadow,NULL,4,2);scripted_corpus(shadow,NULL,4,3);
    scripted_corpus(shadow,NULL,4,2);scripted_corpus(shadow,NULL,4,3);
    check(corpus_calls==1,"duplicate stock 2->3 callbacks cannot append Frenzy effect groups");
    ++morph_epoch;frenzy_tick(pc);
    check(corpus_calls==1,"already applied stock callback is not repeated");
    set(pc,0x146c,0);frenzy_tick(pc);set(shadow,0x1364,0);
    set(pc,0x11a4,2);expected_corpus=2;
    event_dispatch(NULL,NULL,pc,0);
    check(corpus_calls==2&&u(shadow,0x1364)==2,"pending true Frenzy event initializes before counter publication");
    set(pc,0x146c,10);frenzy_tick(pc);check(corpus_calls==2,"event plus first tick is one initialization");
    *(const char **)(shadow+0x11c)="npc_VHumanCombatant";set(shadow,0x1364,0);++morph_epoch;
    frenzy_tick(pc);check(corpus_calls==2,"unrelated NPC is not initialized");
    *(const char **)(shadow+0x11c)="npc_VFrenzyShadow";
    set(pc,0x1db0,handle_of(shadow)+(1u<<13));frenzy_tick(pc);
    check(corpus_calls==2,"stale controller serial cannot receive effects");

    /* Narrow interception: unrelated native calls retain the exact original ABI. */
    set(pc,0x1db0,handle_of(shadow));set(pc,0x146c,10);set(shadow,0x1364,3);
    unsigned forwarded=corpus_calls;
    expected_discipline=7;expected_corpus=2;scripted_corpus(shadow,NULL,7,2);
    check(corpus_calls==++forwarded&&u(shadow,0x1364)==3,"other disciplines are forwarded, not treated as Corpus");
    B *other=entity("npc_VHumanCombatant",3);expected_actor=other;expected_discipline=4;
    scripted_corpus(other,NULL,4,2);check(corpus_calls==++forwarded,"unowned actors forward to the original setter");
    expected_actor=shadow;expected_corpus=0;scripted_corpus(shadow,NULL,4,0);
    check(corpus_calls==++forwarded&&u(shadow,0x1364)==0,"effect removal remains original during Frenzy");
    pfi_inventory_ready=0;set(shadow,0x1364,3);expected_corpus=2;
    scripted_corpus(shadow,NULL,4,2);check(corpus_calls==++forwarded,"disabled readiness forwards the setter");
    pfi_inventory_ready=1;set(pc,0x146c,0);expected_corpus=3;
    scripted_corpus(shadow,NULL,4,3);check(corpus_calls==++forwarded,"outside true Frenzy the setter remains original");

    reset_tickets();
    check(capture_task("__main__.ccmd.holster=\"\"",0.f),"ordinary queued holster remains original");
    unsigned morph_before=morph_epoch;event_dispatch(NULL,NULL,pc,15);check(!activation_player,"nested activation scope restored");
    check(morph_epoch==morph_before,"activation ticket generation cannot invalidate the owned morph scene");
    check(capture_task("custom_task()",3.f),"unrelated scripts remain original");
    check(allow_queued_task("__main__.ccmd.Alert_Front_outof=\"\";custom_task()"),"similar compound script is not swallowed");
    check(!allow_queued_task("__import__('vamputil')._proteanIdleExit(17)"),"serialized retired helper cannot call missing Python function");
    check(allow_queued_task("__import__('vamputil')._proteanIdleExit(x)"),"only exact retired callback syntax is recognized");
    pfi_options[PFI_TRANSFORM]=0;
    check(capture_task(exit_tasks[0],3.f)&&allow_queued_task(exit_tasks[0]),"disabled option forwards schedule and execution");
    pfi_options[PFI_TRANSFORM]=1;
    for(unsigned c=0;c<4;++c){
        reset_tickets();check(!capture_task(exit_tasks[c],3.f),"four stock schedules become native tickets");
        *(float *)(globals+12)=12.9f;native_tasks_tick(pc);check(!reset_calls,"native timer does not fire early");
        *(float *)(globals+12)=13.1f;native_tasks_tick(pc);
        check(reset_calls==1&&u(pc,0x6f0)==100+c,"native valid exit uses model-local lookup and original cycle reset");
        native_tasks_tick(pc);check(reset_calls==1,"ticket consumed once");
    }
    for(unsigned invalid=0;invalid<5;++invalid){
        reset_tickets();capture_task(exit_tasks[0],3.f);
        if(invalid==0)++morph_epoch;
        if(invalid==1)set(pc,0x1380,2);
        if(invalid==2)set(pc,0x2e0,456);
        if(invalid==3)set(table,20,8);
        if(invalid==4){*(float *)(globals+12)=1.f;sync_world(pc,1);}
        *(float *)(globals+12)=14.f;native_tasks_tick(pc);
        check(!reset_calls,"epoch/tier/model/serial/world rollback invalidates delayed exit");
        if(invalid==3)set(table,20,7);
    }
    reset_tickets();capture_task(exit_tasks[0],.25f);
    *(float *)(globals+12)=10.3f;native_tasks_tick(pc);check(reset_calls==1,"other delays on the same exact task retain their timing");
    check(allow_command(pc,45),"legitimate direct idle command outside morph remains native");
    puts("PASS native readiness, pending/loaded/repeated Frenzy ownership, native Corpus tiers, all four timed exits, invalidation, disabled forwarding, legacy tasks and direct idle scope");
    return 0;
}
