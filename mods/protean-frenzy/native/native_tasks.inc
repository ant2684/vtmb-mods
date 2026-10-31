/* Native replacements for the former vamputil support. The game may retain
   its stock scripts; this module never calls an interpreter or edits a script. */
typedef void (TC *DispatchFn)(void *,void *,int);
static DispatchFn native_event_dispatch;
static B *activation_player;
typedef struct {
    unsigned player,epoch,generation,tier,model;
    B *pointer;
    float due;
    unsigned command;
} NativeTicket;
static NativeTicket tickets[64];
static unsigned task_generation;
static unsigned frenzy_player=0xffffffffu,frenzy_shadow=0xffffffffu,frenzy_epoch;
static B *frenzy_pointer,*frenzy_shadow_pointer;
static const char *const exit_tasks[]={
    "__main__.ccmd.Alert_Front_outof=\"\"",
    "__main__.ccmd.Alert_90l_outof=\"\"",
    "__main__.ccmd.Alert_90r_outof=\"\"",
    "__main__.ccmd.Alert_180_outof=\"\""
};
static const char *const exit_sequences[]={
    "claws_alert_front_outof","claws_alert_l90_outof",
    "claws_alert_r90_outof","claws_alert_180_outof"
};
static B *native_player(void){
    B *p=((B *(__cdecl *)(int))(module+0xac8b))(1);
    return isclass(p,"player")&&handle_of(p)!=0xffffffffu?p:NULL;
}
typedef void (TC *CorpusFn)(B *,int,int);
static CorpusFn original_corpus;
static B *pending_frenzy_player;
/* The stock callback requests 2 then3. After native initialization, allowing
   the down/up pair would append another Gangrel effect despite capped feats. */
static void FC scripted_corpus(B *actor,void *unused,int discipline,int level){
    B *p;int wanted;(void)unused;
    if(discipline==4&&(level==2||level==3)&&pfi_inventory_ready&&
       (p=native_player())!=NULL&&resolve(u(p,0x1db0))==actor&&
       isclass(actor,"npc_VFrenzyShadow")&&*(uintptr_t *)actor==(uintptr_t)(module+0x4b2184)&&
       ((int)u(p,0x146c)>0||pending_frenzy_player==p)){
        wanted=u(p,0x11a4)==3?3:2;
        if((int)u(actor,0x1364)>=wanted)return;
    }
    original_corpus(actor,discipline,level);
}
static void frenzy_prepare(B *p,int pending){
    B *shadow;unsigned ph=handle_of(p),sh;int wanted;
    if(!isclass(p,"player")||(!pending&&(int)u(p,0x146c)<=0)||
       !isclass(shadow=resolve(u(p,0x1db0)),"npc_VFrenzyShadow")||
       *(uintptr_t *)shadow!=(uintptr_t)(module+0x4b2184)){
        frenzy_player=frenzy_shadow=0xffffffffu;return;
    }
    sh=handle_of(shadow);
    if(ph==0xffffffffu||sh==0xffffffffu)return;
    if(frenzy_player==ph&&frenzy_pointer==p&&frenzy_shadow==sh&&
       frenzy_shadow_pointer==shadow&&frenzy_epoch==morph_epoch)return;
    wanted=u(p,0x11a4)==3?3:2; /* Reflected effective clan; Gangrel == 3. */
    if((int)u(shadow,0x1364)<wanted)
        scripted_corpus(shadow,NULL,4,wanted);
    if((int)u(shadow,0x1364)>=wanted){
        frenzy_player=ph;frenzy_pointer=p;frenzy_shadow=sh;
        frenzy_shadow_pointer=shadow;frenzy_epoch=morph_epoch;
    }
}
static void frenzy_tick(B *p){frenzy_prepare(p,0);}
static void FC event_dispatch(B *manager,void *unused,B *p,int event){
    B *previous=activation_player,*previous_frenzy=pending_frenzy_player;(void)unused;
    if(event==0&&isclass(p,"player"))pending_frenzy_player=p;
    if(pfi_transform_active()&&isclass(p,"player")&&event==15){
        /* Native OnActivateProtean notification, independent of map Outputs. */
        sync_world(p,0);++task_generation;activation_player=p;
    }
    native_event_dispatch(manager,p,event);
    if(event==0)frenzy_prepare(p,1);
    activation_player=previous;pending_frenzy_player=previous_frenzy;
}
static int exit_task(const char *code){
    unsigned j;if(!code)return -1;
    for(j=0;j<4;++j)if(!strcmp(code,exit_tasks[j]))return (int)j;
    return -1;
}
/* Only the exact former support callback is retired on old saves. */
static int legacy_exit_task(const char *code){
    const char prefix[]="__import__('vamputil')._proteanIdleExit(";
    const char *s;if(!code||strncmp(code,prefix,sizeof(prefix)-1))return 0;
    s=code+sizeof(prefix)-1;if(*s<'0'||*s>'9')return 0;
    do{++s;}while(*s>='0'&&*s<='9');
    return s[0]==')'&&!s[1];
}
USED static int __cdecl capture_task(const char *code,float delay){
    B *p;int command;unsigned j;
    if(!pfi_transform_active()||!code||(p=native_player())==NULL)return 1;
    if(activation_player==p&&(u(p,0x1380)==5||p[0x1edc])&&
       ((delay==0.f&&!strcmp(code,"__main__.ccmd.holster=\"\""))||
        (delay==2.f&&!strcmp(code,"__main__.ccmd.setClaws=\"\""))))return 0;
    command=exit_task(code);
    if(command<0)return 1;
    for(j=0;j<64;++j)if(!tickets[j].pointer||tickets[j].due<now()||
        tickets[j].epoch!=morph_epoch||tickets[j].generation!=task_generation||resolve(tickets[j].player)!=tickets[j].pointer){
        tickets[j].player=handle_of(p);tickets[j].pointer=p;tickets[j].epoch=morph_epoch;tickets[j].generation=task_generation;
        tickets[j].tier=u(p,0x1380);tickets[j].model=u(p,0x2e0);
        tickets[j].due=now()+delay;tickets[j].command=(unsigned)command;break;
    }
    /* An overflowing cosmetic queue fails closed without allocating game state. */
    return 0;
}
USED static int __cdecl allow_queued_task(const char *code){
    B *p;
    if(!pfi_transform_active())return 1;
    /* New exact exits are native tickets. These are unowned serialized exits
       from before a load or before installation, with no valid native epoch. */
    if(exit_task(code)>=0||legacy_exit_task(code))return 0;
    p=native_player();
    if(p&&(u(p,0x1380)==5||p[0x1edc])&&code&&
       !strcmp(code,"__main__.ccmd.setClaws=\"\""))return 0;
    return 1;
}
static void native_tasks_tick(B *p){
    unsigned j;int sequence;
    for(j=0;j<64;++j){
        NativeTicket ticket=tickets[j];
        if(!ticket.pointer)continue;
        if(ticket.epoch!=morph_epoch||ticket.generation!=task_generation||resolve(ticket.player)!=ticket.pointer||
           ticket.pointer!=p||ticket.tier!=u(p,0x1380)||ticket.model!=u(p,0x2e0)){
            tickets[j].pointer=NULL;continue;
        }
        if(now()<ticket.due)continue;
        tickets[j].pointer=NULL;
        sequence=((LookupFn)(module+0xe057))(p,exit_sequences[ticket.command]);
        if(sequence<0||!allow_command(p,sequence))continue;
        *(int *)(p+0x6f0)=sequence;
        ((VoidFn)(module+0x117b1))(p);
        *(float *)(p+0x6f8)=0.f;
    }
}
__attribute__((naked)) static void schedule_bridge(void){
    __asm__ volatile(
      "pushfl\n\tpushal\n\tmovl %esp,%ebx\n\tsubl $528,%esp\n\tandl $-16,%esp\n\tfxsave (%esp)\n\t"
      "pushl 40(%ebx)\n\tpushl 52(%ebx)\n\tcall _capture_task\n\taddl $8,%esp\n\t"
      "fxrstor (%esp)\n\tmovl %ebx,%esp\n\ttestl %eax,%eax\n\tjz 1f\n\tpopal\n\tpopfl\n\t"
      "movl 16(%esp),%eax\n\tpushl %eax\n\tjmp *_schedule_resume\n\t"
      "1: popal\n\tpopfl\n\tjmp *_schedule_skip\n\t");
}
__attribute__((naked)) static void queued_bridge(void){
    __asm__ volatile(
      "pushfl\n\tpushal\n\tmovl %esp,%ebx\n\tsubl $528,%esp\n\tandl $-16,%esp\n\tfxsave (%esp)\n\t"
      "pushl 28(%ebx)\n\tcall _allow_queued_task\n\taddl $4,%esp\n\t"
      "fxrstor (%esp)\n\tmovl %ebx,%esp\n\ttestl %eax,%eax\n\tjz 1f\n\tpopal\n\tpopfl\n\t"
      "pushl %eax\n\tmovl %ebx,%ecx\n\tcall *_queued_native\n\tjmp *_queued_resume\n\t"
      "1: popal\n\tpopfl\n\tjmp *_queued_skip\n\t");
}
__attribute__((used)) static uintptr_t schedule_resume,schedule_skip,queued_native,queued_resume,queued_skip;
static int native_tasks_dependencies(void){
    if(memcmp(module+0x2c2ec0,"\x53\x55\x56\x57\x8b\xf9\x33\xc0",8)||
       memcmp(module+0x2c31f7,"\x5f\x5e\x5d\x5b\xc2\x08\x00",7)||
       memcmp(module+0x31c1d3,"\xa4\x11\x00\x00",4))return 0;
    if(!pfi_options[PFI_TRANSFORM])return 1;
    if(memcmp(module+0x117b1,"\xe9\x9a\xf1\x07\x00",5))return 0;
    schedule_resume=(uintptr_t)(module+0x196ec8);schedule_skip=(uintptr_t)(module+0x196ef6);
    queued_native=(uintptr_t)(module+0x53e4);queued_resume=(uintptr_t)(module+0xcee5b);
    queued_skip=(uintptr_t)(module+0xcef07);
    return 1;
}
