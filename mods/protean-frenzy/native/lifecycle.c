#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "runtime.h"
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
#define USED __attribute__((used,noinline))
typedef unsigned char B;
typedef void (TC *ItemFn)(void *,void *);
typedef void (TC *VoidFn)(void *);
typedef const char *(TC *NameFn)(void *,int);
typedef B *(TC *ModelFn)(void *,int);
typedef int (TC *LookupFn)(void *,const char *);
typedef void (TC *SetModelFn)(void *,const char *);
typedef void (TC *EventFn)(void *,void *,int);
typedef B *(TC *CreateFn)(void *,const char *);
typedef void (TC *ActivityFn)(void *,int);
typedef void (__cdecl *FxFn)(void *,int,float,float,float,const char *,int,const char *,int,int);
static B *module;
static ItemFn original_add;
static VoidFn original_ensure;
static void (__stdcall *original_trait_grant)(B *,const char *);
static int ensure_depth;
typedef struct Insert {B *player,*item;struct Insert *previous;} Insert;
static Insert *inserting;
static B *creating_fists;
static B *creating_claws;
__attribute__((used)) static uintptr_t resume_start,done_start,resume_end,done_end,wolf_name;
__attribute__((used)) static uintptr_t resume_tick,tick_native;
__attribute__((used)) static uintptr_t event_native;

__attribute__((used)) static uintptr_t resume_input,resume_command,skip_command,resume_fx,original_fx;
static unsigned feeding_player=0xffffffffu,feeding_partner=0xffffffffu,feeding_frame;
static B *feeding_player_ptr;
static unsigned morph_epoch,equip_player=0xffffffffu,equip_epoch;
static B *equip_player_ptr;
static int equip_visual;
static unsigned deferred_player=0xffffffffu,deferred_partner,deferred_weapon,deferred_epoch;
static B *deferred_player_ptr,*deferred_weapon_ptr;
static B *world_player,*scene_ptr,*command_ptr;
static unsigned world_wolf,world_frenzy,fx_frame,fx_player=0xffffffffu;
static B *fx_player_ptr;
static unsigned world_handle=0xffffffffu,scene_player=0xffffffffu,scene_actor=0xffffffffu,scene_epoch;
static unsigned scene_duck,scene_pose_duck,command_buttons,command_frame;
static int scene_target,starting_frenzy;
static float world_time,scene_time,scene_origin[3],command_motion;
static const char visual_name[]="__protean_lifecycle_visual_v1";
static const char scene_name[]="__protean_lifecycle_native_v2";
static void equip_tick(B *p);
static void inventory_tick(B *p);
static int inventory_frenzy_seen;
static void reconcile_claws(B *p);
static void finish_scene(B *p);
static void frenzy_tick(B *p);
static int __cdecl allow_command(B *p,int seq);
static unsigned u(B *p,unsigned o){return *(unsigned *)(p+o);}
static int copy_string(char *out,unsigned capacity,const char *in){
    unsigned length;if(!in)return 0;
    for(length=0;length<capacity&&in[length];++length){}
    if(length==capacity)return 0;
    memcpy(out,in,length+1);return 1;
}
static void *resolve(unsigned handle){
    B *table,*entry;if(handle==0xffffffffu)return NULL;
    table=*(B **)(module+0x566458);if(!table)return NULL;
    entry=table+(handle&0x1fffu)*12+4;
    return *(unsigned *)(entry+4)==handle>>13?*(void **)entry:NULL;
}
static unsigned handle_of(void *p){
    B *table=*(B **)(module+0x566458);unsigned j;if(!table||!p)return 0xffffffffu;
    for(j=0;j<8192;++j)if(*(void **)(table+j*12+4)==p)return j|(*(unsigned *)(table+j*12+8)<<13);
    return 0xffffffffu;
}
static int isclass(B *p,const char *n){const char *s=p?*(const char **)(p+0x11c):NULL;return s&&!strcmp(s,n);}
static float now(void){B *g=*(B **)(module+0x70b228);return g?*(float *)(g+12):0.f;}
static int paired(B *p){return resolve(u(p,0x1538))&&(int)u(p,0x153c)>=0;}
static int feeding(B *p){
    const char *name;if(!paired(p)||u(p,0x153c))return 0;
    name=((NameFn)(module+0x8fe80))(p,(int)u(p,0x6f0));
    return name&&!strncmp(name,"feeding_",8);
}
static int contains(const char *s,const char *part){
    char lower[128];unsigned j;if(!s)return 0;
    for(j=0;j<127&&s[j];j++)lower[j]=s[j]>='A'&&s[j]<='Z'?(char)(s[j]+32):s[j];
    lower[j]=0;return strstr(lower,part)!=NULL;
}
static int action_sequence(const char *name){
    return contains(name,"attack")||contains(name,"feeding")||contains(name,"hit_")||contains(name,"flinch")||
        contains(name,"block")||contains(name,"jump")||contains(name,"hop_")||contains(name,"fall")||contains(name,"land")||
        contains(name,"reload")||contains(name,"interact")||contains(name,"walk")||contains(name,"run");
}
static int idle_command(const char *name){
    return !action_sequence(name)&&!contains(name,"morph")&&(contains(name,"idle")||contains(name,"ready")||
        contains(name,"fidget")||contains(name,"crouch")||contains(name,"alert")||contains(name,"howl")||
        contains(name,"look")||contains(name,"sniff")||contains(name,"nails")||contains(name,"stretch")||
        contains(name,"lost")||contains(name,"armscrossed")||contains(name,"disposition")||contains(name,"pray"));
}
static void clear_scene(void){scene_player=scene_actor=0xffffffffu;scene_ptr=NULL;}
static B *valid_actor(B *p){
    B *a=resolve(u(p,0x1db0));
    if(!isclass(a,"npc_VWolfMorph")||u(p,0x168)!=30||u(a,0x168)!=31||
       u(a,0x155c)!=handle_of(p)||u(p,0x155c)!=handle_of(a)||((int)u(p,0x146c)>0&&!starting_frenzy))return NULL;
    return a;
}
static void arm_scene(B *p,int target){
    ++morph_epoch;equip_player=deferred_player=0xffffffffu;equip_player_ptr=NULL;equip_visual=0;
    scene_ptr=p;scene_player=handle_of(p);scene_actor=0xffffffffu;scene_epoch=morph_epoch;
    scene_target=target;scene_duck=u(p,0x2088)&4u;scene_pose_duck=u(p,0x434)&2u;scene_time=now();memcpy(scene_origin,p+0x404,sizeof(scene_origin));
}
static int bind_scene(B *p){
    B *a;if(scene_ptr!=p||resolve(scene_player)!=p||scene_epoch!=morph_epoch)return 0;
    a=valid_actor(p);if(!a)return 0;
    if(scene_actor!=0xffffffffu)return resolve(scene_actor)==a;
    scene_actor=handle_of(a);((void (TC *)(void *,const char *))(module+0xa0420))(a,scene_name);return 1;
}
static void sync_world(B *p,int stable_clock){
    unsigned h=handle_of(p);float t=now();B *table,*a;unsigned j;int removed=0;
    if(!world_player||world_player!=p||world_handle!=h||(stable_clock&&t+.001f<world_time)){
        world_wolf=p[0x1edc];world_frenzy=(int)u(p,0x146c)>0;fx_player=0xffffffffu;fx_player_ptr=NULL;
        clear_scene();++morph_epoch;equip_player=deferred_player=feeding_player=0xffffffffu;
        equip_player_ptr=feeding_player_ptr=NULL;equip_visual=0;command_ptr=NULL;
        world_player=p;world_handle=h;world_time=t;
        inventory_frenzy_seen=(int)u(p,0x146c)>0||isclass(resolve(u(p,0x1db0)),"npc_VFrenzyShadow");
        table=*(B **)(module+0x566458);
        for(j=0;table&&j<8192;j++){
            const char *n;a=*(B **)(table+j*12+4);
            if(!isclass(a,"npc_VWolfMorph")||u(a,0x155c)!=h)continue;
            n=*(const char **)(a+0x26c);if(!n)continue;
            if(!strcmp(n,scene_name)&&a==valid_actor(p)){
                scene_ptr=p;scene_player=h;scene_actor=handle_of(a);scene_epoch=morph_epoch;
                scene_target=u(p,0x1380)==5;finish_scene(p);continue;
            }
            if(strcmp(n,visual_name)&&strcmp(n,scene_name))continue;
            if(u(p,0x1db0)==handle_of(a)){
                if((int)u(p,0x146c)>0)continue;
                *(unsigned *)(p+0x1db0)=0xffffffffu;
            }
            *(unsigned *)(a+0x19c)|=0x20u;((VoidFn)(module+0x24f7b0))(a);removed=1;
        }
        if(removed&&!(int)u(p,0x146c)&&!u(p,0x168)&&!resolve(u(p,0x1db0)))
            *(unsigned *)(p+0x19c)&=~0x20u;
    }
    world_player=p;world_handle=h;if(stable_clock)world_time=t;
}
static void FC refresh_animation(B *p,void *unused,int action,int flags){
    B *g=*(B **)(module+0x70b228);(void)unused;
    if(pfi_transform_active()&&isclass(p,"player")&&!action&&flags==1&&(int)u(p,0x146c)==0&&!resolve(u(p,0x1db0))&&feeding(p)&&
       (u(p,0x1380)==5||(g&&feeding_player_ptr==p&&resolve(feeding_player)==p&&
        feeding_partner==u(p,0x1538)&&feeding_frame==u(g,4))))return;
    ((void (TC *)(void *,int,int))(module+0x181680))(p,action,flags);
}
/* Duck and speed may be held while still. The client also carries a shared
   character/quest-panel state bit (0x04000000), which may remain after hiding UI.
   These are not body actions; actual motion and action buttons keep priority. */
static int can_scene(B *p,B *prepared){
    B *g=*(B **)(module+0x70b228);const char *name;
    if(paired(p)||u(p,0x168)||(int)u(p,0x146c)>0||p[0x200]||(u(p,0x2088)&~(4u|0x20000u|0x4000000u)))return 0;
    if(resolve(u(p,0x1db0))&&resolve(u(p,0x1db0))!=prepared)return 0;
    if(command_ptr==p&&g&&u(g,4)-command_frame<=1u&&((command_buttons&~(4u|0x20000u|0x4000000u))||command_motion>.01f))return 0;
    name=((NameFn)(module+0x8fe80))(p,(int)u(p,0x6f0));return name&&!action_sequence(name);
}
static B *inventory(B *p,const char *name){
    unsigned j;B *item;
    for(j=0;j<224;++j){item=resolve(u(p,0x1624+j*4));if(item&&u(item,0x73c)==j&&isclass(item,name))return item;}
    return NULL;
}
/* Several discipline groups independently grant/remove the same weapon class.
   Once their native transactions settle, keep one equipment pair for the actual
   remaining Protean tier. Do not reapply any discipline/stat effects. */
static void reconcile_claws(B *p){
    B *claws,*fists,*previous;
    if(u(p,0x1380)<2||(int)u(p,0x146c)>0||resolve(u(p,0x1db0))||u(p,0x168)||
       ensure_depth||inserting||creating_fists==p||creating_claws==p)return;
    claws=inventory(p,"item_w_claws");fists=inventory(p,"item_w_fists");
    if(claws&&!fists)return;
    previous=creating_claws;creating_claws=p;
    if(fists)((void (__stdcall *)(void *,const char *))(module+0x1f9af0))(p,"item_w_fists");
    if(!claws)original_trait_grant(p,"item_w_claws");
    creating_claws=previous;
    claws=inventory(p,"item_w_claws");
    if(!claws){original_ensure(p);return;}
    if(u(p,0x1380)==5&&p[0x1edc]&&equip_player==0xffffffffu&&deferred_player==0xffffffffu){
        equip_player=handle_of(p);equip_player_ptr=p;equip_epoch=morph_epoch;equip_visual=0;
    }
}
static void select_claws(B *p,B *item){
    if(resolve(u(p,0x19a4))!=item)
        ((void (TC *)(void *,const char *,int))(*(uintptr_t **)p)[0x724/4])(p,"item_w_claws",0);
}
static void finish_claws_grant(B *p,B *item){
    int show;
    if(equip_player_ptr!=p||resolve(equip_player)!=p||equip_epoch!=morph_epoch)return;
    show=equip_visual;equip_player=0xffffffffu;equip_player_ptr=NULL;equip_visual=0;
    if(!item||u(p,0x1380)!=5||!p[0x1edc]||(int)u(p,0x146c)>0||resolve(u(p,0x1db0)))return;
    if(paired(p)){
        deferred_player=handle_of(p);deferred_player_ptr=p;deferred_partner=u(p,0x1538);
        deferred_weapon=handle_of(item);deferred_weapon_ptr=item;deferred_epoch=morph_epoch;return;
    }
    select_claws(p,item);
    (void)show;
}
static void equip_tick(B *p){
    B *item;
    if(equip_player!=0xffffffffu&&(equip_player_ptr!=p||resolve(equip_player)!=p||equip_epoch!=morph_epoch)){
        equip_player=0xffffffffu;equip_player_ptr=NULL;equip_visual=0;
    }
    /* Trait callbacks can run before Active_Protean and model refresh settle.
       Consume the morph ticket only here, after the complete native transaction. */
    if(equip_player_ptr==p&&resolve(equip_player)==p){
        if(u(p,0x1380)!=5||!p[0x1edc]){equip_player=0xffffffffu;equip_player_ptr=NULL;equip_visual=0;}
        else if((item=inventory(p,"item_w_claws")))finish_claws_grant(p,item);
    }
    if(deferred_player==0xffffffffu)return;
    item=resolve(deferred_weapon);
    if(deferred_player_ptr!=p||resolve(deferred_player)!=p||deferred_epoch!=morph_epoch||item!=deferred_weapon_ptr||
       u(p,0x1380)!=5||!p[0x1edc]||(int)u(p,0x146c)>0||resolve(u(p,0x1db0))||
       !isclass(item,"item_w_claws")||inventory(p,"item_w_claws")!=item){deferred_player=0xffffffffu;return;}
    if(paired(p)){if(u(p,0x1538)!=deferred_partner)deferred_player=0xffffffffu;return;}
    deferred_player=0xffffffffu;select_claws(p,item);
}
/* Native Frenzy cleanup can recreate Claws but finish with the unarmed weapon
   selected. Restore P5 selection once after that complete owned transition;
   ordinary inventory ticks must not override later manual weapon choices. */
static void inventory_tick(B *p){
    frenzy_tick(p);
    if((int)u(p,0x146c)>0||isclass(resolve(u(p,0x1db0)),"npc_VFrenzyShadow"))inventory_frenzy_seen=1;
    else if(inventory_frenzy_seen&&!resolve(u(p,0x1db0))&&!u(p,0x168)&&
            !ensure_depth&&!inserting&&creating_fists!=p&&creating_claws!=p){
        inventory_frenzy_seen=0;
        if(u(p,0x1380)==5&&p[0x1edc]){
            equip_player=handle_of(p);equip_player_ptr=p;equip_epoch=morph_epoch;equip_visual=0;
        }
    }
    equip_tick(p);reconcile_claws(p);
}
static void fists_first(B *p,B *fists){
    unsigned j,k,slot,handle;B *item;
    if(!isclass(p,"player")||!isclass(fists,"item_w_fists"))return;
    slot=u(fists,0x73c);handle=handle_of(fists);if(!slot||slot>=32||handle==0xffffffffu)return;
    for(j=0;j<=slot;++j){
        unsigned h=u(p,0x1624+j*4);item=resolve(h);
        if(!item||u(item,0x73c)!=j||(j==slot&&item!=fists))return;
        for(k=0;k<224;++k)if(k!=j&&u(p,0x1624+k*4)==h)return;
    }
    ((ItemFn)(module+0x335780))(p,fists);
}
#include "frenzy_inventory.h"
/* Full Equip retains its native callbacks. Only its duplicate insertion is skipped. */
static void FC add_item(B *p,void *unused,B *item){
    unsigned j,handle;Insert context,*scan;int registered=0;const char *cls=item?*(const char **)(item+0x11c):NULL;(void)unused;
    int legacy=isclass(p,"player")&&cls&&(isclass(item,"item_w_fists")||isclass(item,"item_w_claws")||
       (!strncmp(cls,"item_w_",7)&&(ensure_depth||u(p,0x1380)>=2)));
    int melee=frenzy_inventory_scope(p,item);
    if(legacy||melee){
        handle=handle_of(item);
        if(legacy){if(handle!=0xffffffffu)for(j=0;j<224;++j)if(u(p,0x1624+j*4)==handle){registered=1;break;}}
        else registered=frenzy_inventory_registered(p,item);
        for(scan=inserting;scan;scan=scan->previous)if(scan->player==p&&scan->item==item)registered=1;
    }
    if(!registered){context.player=p;context.item=item;context.previous=inserting;inserting=&context;original_add(p,item);inserting=context.previous;}
    if(isclass(item,"item_w_fists"))fists_first(p,item);
}
/* Guard the full GiveItem transaction, never GiveWeapon: the latter also
   deliberately creates the separate, disposable presentation weapon +1C64. */
static B *__cdecl create_item(B *p,const char *name,int flags){
    B *item,*previous,*result,**creating;int claws=name&&!strcmp(name,"item_w_claws");
    if(!isclass(p,"player")||!name||(!claws&&strcmp(name,"item_w_fists")))
        return ((B *(__cdecl *)(void *,const char *,int))(module+0x21fe50))(p,name,flags);
    creating=claws?&creating_claws:&creating_fists;
    if(*creating==p||(!claws&&creating_claws==p&&u(p,0x1380)>=2))return NULL;
    item=inventory(p,name);
    if(item){if(!claws)fists_first(p,item);return item;}
    previous=*creating;*creating=p;
    result=((B *(__cdecl *)(void *,const char *,int))(module+0x21fe50))(p,name,flags);
    *creating=previous;item=inventory(p,name);
    if(!claws&&item)fists_first(p,item);
    return result;
}
/* Trait +/-item callbacks use a separate grant routine, bypassing GiveItem.
   Its native implementation unconditionally allocates before Equip. Guard
   the complete grant so no existing weapon is reinitialized or destroyed. */
static void __stdcall trait_grant(B *p,const char *name){
    B *item,*previous,**creating;int claws=name&&!strcmp(name,"item_w_claws");
    if(!isclass(p,"player")||!name||(!claws&&strcmp(name,"item_w_fists"))){original_trait_grant(p,name);return;}
    creating=claws?&creating_claws:&creating_fists;
    if(*creating==p||(!claws&&creating_claws==p&&u(p,0x1380)>=2))return;
    item=inventory(p,name);
    if(item){if(!claws)fists_first(p,item);return;}
    previous=*creating;*creating=p;original_trait_grant(p,name);*creating=previous;
    item=inventory(p,name);if(!claws&&item)fists_first(p,item);
}
static void FC ensure_fists(B *p,void *unused){
    B *fists;(void)unused;
    if(!isclass(p,"player")){original_ensure(p);return;}
    if(ensure_depth||creating_fists==p||creating_claws==p)return;
    ++ensure_depth;original_ensure(p);--ensure_depth;
    fists=inventory(p,"item_w_fists");if(fists)fists_first(p,fists);
}
/* The ordinary discipline emitter is stopped when Active_Protean becomes zero.
   Use the stock Protean body burst (also part of tier 5 activation) through
   the native temporary-particle broadcast.
   Its recipient filter is constructed and destroyed by the supported engine. */
USED static void __cdecl return_fx(B *p){
    B filter[64]={0},*body=p,*g=*(B **)(module+0x70b228);
    if(!pfi_transform_active())return;
    B *controller=resolve(u(p,0x1db0));
    if((int)u(p,0x146c)>0&&isclass(controller,"npc_VFrenzyShadow"))body=controller;
    fx_player=handle_of(p);fx_player_ptr=p;fx_frame=g?u(g,4):0;
    ((VoidFn)(module+0x19ce00))(filter);
    ((void (TC *)(void *,const void *))(module+0x19d210))(filter,body+0x404);
    ((void (__cdecl *)(void *,float,void *,int,int,const char *))(module+0x69e80))
        (filter,0.f,body,1,-1,"D_Protean_4BP_Emitter");
    ((void (TC *)(void *,int))(module+0xf5fc0))(filter,0);
}
/* Match native completion: changing to the shared beast body initializes a
   male model. Restore the original gender trait before later model refreshes. */
static unsigned native_gender(B *p){
    return ((unsigned char (TC *)(void *))(module+0x336920))(p);
}
static void restore_gender(B *p,unsigned gender){
    B *group=module+0x9f0b40;B **groups=*(B ***)(p+0x13c0);unsigned count=u(p,0x13bc),j;
    if(groups&&count<1024)for(j=0;j<count;j++)if(groups[j]&&u(groups[j],0x10)==0){group=groups[j];break;}
    ((void (TC *)(void *,int,int))(module+0x2008e0))(group,11,(int)gender);
    *(unsigned *)(p+0x13cc)=gender;
}
USED static int __cdecl morph(B *p,int enter){
    static const unsigned offsets[]={0x6f0,0x650,0x73c,0x76c,0x79c,0x7cc};
    B *header,*prepared=NULL;char oldseq[6][128],path[260];const char *name;int sequence,interrupted=0;unsigned j;
    float cycle,rate;unsigned gender=native_gender(p);
    if(!pfi_transform_active()||!isclass(p,"player")||(int)u(p,0x146c)>0)return 0;
    sync_world(p,0);
    if(enter<0){prepared=resolve(u(p,0x1db0));if(!isclass(prepared,"npc_VWolfMorph"))return 0;enter=0;}
    else if(resolve(u(p,0x1db0))&&!(scene_ptr==p&&resolve(scene_player)==p))return 0;
    if(scene_ptr==p&&scene_player==handle_of(p)){
        /* A load can reuse player address/serial after destroying the old actor.
           Only an actually owned live scene counts as an interrupted morph. */
        if(bind_scene(p)){finish_scene(p);prepared=NULL;interrupted=1;}
        else clear_scene();
    }
    if(!interrupted&&can_scene(p,prepared)){arm_scene(p,enter);return 0;}
    header=((ModelFn)(module+0x952d0))(p,-1);if(!header)return 0;
    if(enter){
        name=(const char *)(header+12);
        if(!strncmp(name,"models/",7)){if(!copy_string(path,sizeof(path),name))return 0;}
        else {memcpy(path,"models/",7);if(!copy_string(path+7,sizeof(path)-7,name))return 0;}
        if(!_stricmp(path,(const char *)(module+0x586950)))return 0;
        memcpy(p+0x23d4,path,strlen(path)+1);
    }
    for(j=0;j<6;++j){
        unsigned index=u(p,offsets[j]);oldseq[j][0]=0;
        if(j>=2&&!u(p,offsets[j]-8))continue;
        if(index>=8192)continue;
        name=((NameFn)(module+0x8fe80))(p,(int)index);
        if(name&&strcmp(name,"SEQUENCE_NOT_FOUND")&&!copy_string(oldseq[j],sizeof(oldseq[j]),name))return 0;
    }
    cycle=*(float *)(p+0x6f8);rate=*(float *)(p+0x6f4);
    if(!copy_string(path,sizeof(path),enter?(const char *)(module+0x586950):(const char *)(p+0x23d4)))return 0;
    if(strncmp(path,"models/",7))return 0;
    if(prepared)*(unsigned *)(p+0x1db0)=0xffffffffu;
    ++morph_epoch;equip_player=deferred_player=0xffffffffu;equip_player_ptr=NULL;equip_visual=0;
    if(feeding(p)){
        B *g=*(B **)(module+0x70b228);
        feeding_player=handle_of(p);feeding_player_ptr=p;feeding_partner=u(p,0x1538);feeding_frame=g?u(g,4):0;
    }
    if(prepared)((VoidFn)(module+0x24f7b0))(prepared);
    p[0x1edc]=(B)enter;
    /* SetModel retains its model-name pointer: it must never point at this stack. */
    ((SetModelFn)(*(uintptr_t **)p)[0x1a4/4])(p,enter?(const char *)(module+0x586950):(const char *)(p+0x23d4));
    if(enter)restore_gender(p,gender);
    /* All indices are model-relative, including the four native event layers.
       Keep their cycles/event cursors: resetting them can lose/repeat the bite. */
    for(j=0;j<6;++j)if(oldseq[j][0]){
        sequence=((LookupFn)(module+0xe057))(p,oldseq[j]);
        if(sequence>=0)*(int *)(p+offsets[j])=sequence;
    }
    *(float *)(p+0x6f8)=cycle;*(float *)(p+0x6f4)=rate;
    *(float *)(p+0x1c68)=*(float *)(*(B **)(module+0x70b228)+12);
    ((EventFn)(module+0x227a30))(module+0x750cb4,p,2);
    if(!enter)return_fx(p);
    if(enter){equip_player=handle_of(p);equip_player_ptr=p;equip_epoch=morph_epoch;equip_visual=0;}
    return 1;
}

static void native_idle(B *p){
    uintptr_t *vt=*(uintptr_t **)p;int seq;
    ((ActivityFn)vt[0x4d8/4])(p,1);
    seq=((int (TC *)(void *,int,int))(module+0x125c1))(p,1,-1);
    if(seq>=0)((void (TC *)(void *,int,int,int))vt[0x4dc/4])(p,1,1,seq);
}
static void finish_scene(B *p){
    B *a;int target=scene_target;unsigned gender=native_gender(p);
    if(!bind_scene(p))return;
    a=resolve(scene_actor);
    /* Native cleanup copies only this validated scene's pose and removes its
       controller. Never use it once a feeding pair or real Frenzy owns control. */
    if(paired(p))return;
    ((void (TC *)(void *,int,int))(module+0x1618e0))(p,1,1);
    *(unsigned *)(p+0x168)=0;*(unsigned *)(p+0x16c)=0;
    *(unsigned *)(p+0x155c)=0xffffffffu;*(unsigned *)(p+0x1ebc)=0xffffffffu;
    p[0x1edc]=(B)target;
    ((SetModelFn)(*(uintptr_t **)p)[0x1a4/4])(p,target?(const char *)(module+0x586950):(const char *)(p+0x23d4));
    if(target)restore_gender(p,gender);
    *(float *)(p+0x1c68)=now();
    memset(p+0x734,0,4*48);clear_scene();
    if(target&&u(p,0x1380)==5){equip_player=handle_of(p);equip_player_ptr=p;equip_epoch=morph_epoch;equip_visual=0;equip_tick(p);}
    native_idle(p);(void)a;
}
static B *FC controller_create(B *p,void *unused,const char *name){
    (void)unused;
    if(isclass(p,"player")&&name&&!strcmp(name,"npc_VFrenzyShadow")&&scene_ptr==p&&resolve(scene_player)==p){
        starting_frenzy=1;
        if(bind_scene(p))finish_scene(p);
        starting_frenzy=0;
    }
    return ((CreateFn)(module+0x161a70))(p,name);
}
static void __cdecl discipline_request(B *component,int discipline,int level){
    B *p=component?*(B **)(component+0xa8):NULL;
    if(isclass(p,"player")&&bind_scene(p))finish_scene(p);
    ((void (__cdecl *)(B *,int,int))(module+0xd8830))(component,discipline,level);
}
static void observe_form_fx(B *p){
    /* Core restores both bodies directly when Protean ends during true Frenzy,
       bypassing the ordinary return FX call. Emit once on that observed change. */
    if(world_wolf&&!p[0x1edc]&&u(p,0x1380)<5&&(world_frenzy||(int)u(p,0x146c)>0)){
        B *g=*(B **)(module+0x70b228);
        if(!(fx_player_ptr==p&&resolve(fx_player)==p&&g&&fx_frame==u(g,4)))return_fx(p);
    }
    world_wolf=p[0x1edc];world_frenzy=(int)u(p,0x146c)>0;
}
#include "native_tasks.inc"
USED static void __cdecl scene_tick(B *p){
    if(!pfi_transform_active()){
        unsigned h=handle_of(p);float t=now();
        if(world_player!=p||world_handle!=h||t+.001f<world_time){
            ++morph_epoch;equip_player=deferred_player=0xffffffffu;equip_player_ptr=NULL;
            inventory_frenzy_seen=(int)u(p,0x146c)>0||isclass(resolve(u(p,0x1db0)),"npc_VFrenzyShadow");
        }
        world_player=p;world_handle=h;world_time=t;
        inventory_tick(p);return;
    }
    sync_world(p,1);
    native_tasks_tick(p);
    if(scene_ptr==p&&resolve(scene_player)==p){
        if(bind_scene(p)){
            if((u(p,0x434)&2u)!=scene_pose_duck||p[0x200]||now()-scene_time>3.f)finish_scene(p);
        }else if(!resolve(u(p,0x1db0))&&!u(p,0x168)){
            int target=scene_target;clear_scene();
            if(target&&u(p,0x1380)==5&&p[0x1edc]){equip_player=handle_of(p);equip_player_ptr=p;equip_epoch=morph_epoch;equip_visual=0;}
        }
    }
    observe_form_fx(p);
    inventory_tick(p);
}
USED static void __cdecl raw_input(B *p,B *cmd){
    B *g;float x,y,z;if(!isclass(p,"player")||!cmd)return;
    if(!pfi_transform_active())return;
    sync_world(p,0);observe_form_fx(p);g=*(B **)(module+0x70b228);
    command_ptr=p;command_buttons=u(cmd,0x30);command_frame=g?u(g,4):0;
    x=*(float *)(cmd+0x20);y=*(float *)(cmd+0x24);z=*(float *)(cmd+0x28);command_motion=x*x+y*y+z*z;
    if(bind_scene(p)){
        int pressed_duck=(command_buttons&4u)&&!(scene_duck&4u);
        scene_duck=command_buttons&4u;
        if((command_buttons&~(4u|0x20000u|0x4000000u))||pressed_duck||command_motion>.01f||cmd[0x2c]||u(cmd,0x34))finish_scene(p);
    }
}
USED static int __cdecl allow_command(B *p,int seq){
    const char *name;
    if(!isclass(p,"player"))return 1;
    if(!bind_scene(p))return 1;
    name=((NameFn)(module+0x8fe80))(p,seq);
    if(idle_command(name))return 0;
    finish_scene(p);return 1;
}
__attribute__((naked)) static void tick_bridge(void){
    __asm__ volatile(
      "movl %ebp,%ecx\n\tcall *_tick_native\n\t"
      "pushfl\n\tpushal\n\tmovl %esp,%ebx\n\tsubl $528,%esp\n\tandl $-16,%esp\n\tfxsave (%esp)\n\t"
      "pushl %ebp\n\tcall _scene_tick\n\taddl $4,%esp\n\tfxrstor (%esp)\n\tmovl %ebx,%esp\n\tpopal\n\tpopfl\n\tjmp *_resume_tick\n\t");
}
__attribute__((naked)) static void input_bridge(void){
    __asm__ volatile(
      "pushfl\n\tpushal\n\tmovl %esp,%ebx\n\tsubl $528,%esp\n\tandl $-16,%esp\n\tfxsave (%esp)\n\t"
      "pushl 40(%ebx)\n\tpushl 24(%ebx)\n\tcall _raw_input\n\taddl $8,%esp\n\tfxrstor (%esp)\n\tmovl %ebx,%esp\n\tpopal\n\tpopfl\n\t"
      "pushl %esi\n\tmovl 8(%esp),%esi\n\tjmp *_resume_input\n\t");
}
__attribute__((naked)) static void command_bridge(void){
    __asm__ volatile(
      "pushfl\n\tpushal\n\tmovl %esp,%ebx\n\tsubl $528,%esp\n\tandl $-16,%esp\n\tfxsave (%esp)\n\t"
      "pushl %eax\n\tpushl %esi\n\tcall _allow_command\n\taddl $8,%esp\n\tfxrstor (%esp)\n\tmovl %ebx,%esp\n\ttestl %eax,%eax\n\tjz 1f\n\t"
      "popal\n\tpopfl\n\tmovl %eax,0x6f0(%esi)\n\tjmp *_resume_command\n\t"
      "1: popal\n\tpopfl\n\tjmp *_skip_command\n\t");
}
__attribute__((naked)) static void fx_bridge(void){
    __asm__ volatile(
      "pushfl\n\tpushal\n\tmovl %esp,%ebx\n\tsubl $528,%esp\n\tandl $-16,%esp\n\tfxsave (%esp)\n\t"
      "call _pfi_transform_active\n\ttestl %eax,%eax\n\tjz 1f\n\t"
      "pushl %edi\n\tcall _return_fx\n\taddl $4,%esp\n\tfxrstor (%esp)\n\tmovl %ebx,%esp\n\tpopal\n\tpopfl\n\tjmp *_resume_fx\n\t"
      "1: fxrstor (%esp)\n\tmovl %ebx,%esp\n\tpopal\n\tpopfl\n\tcall *_original_fx\n\tjmp *_resume_fx\n\t");
}
__attribute__((naked)) static void start_bridge(void){
    __asm__ volatile(
      "pushfl\n\tpushal\n\tmovl %esp,%ebx\n\tsubl $528,%esp\n\tandl $-16,%esp\n\tfxsave (%esp)\n\t"
      "pushl $1\n\tpushl %edi\n\tcall _morph\n\taddl $8,%esp\n\tfxrstor (%esp)\n\tmovl %ebx,%esp\n\ttestl %eax,%eax\n\tjz 1f\n\t"
      "popal\n\tpopfl\n\tjmp *_done_start\n\t"
      "1: popal\n\tpopfl\n\tpushl _wolf_name\n\tmovl %edi,%ecx\n\tjmp *_resume_start\n\t");
}
__attribute__((naked)) static void end_bridge(void){
    __asm__ volatile(
      "pushfl\n\tpushal\n\tmovl %esp,%ebx\n\tsubl $528,%esp\n\tandl $-16,%esp\n\tfxsave (%esp)\n\t"
      "pushl $-1\n\tpushl %edi\n\tcall _morph\n\taddl $8,%esp\n\tfxrstor (%esp)\n\tmovl %ebx,%esp\n\ttestl %eax,%eax\n\tjz 1f\n\t"
      "popal\n\tpopfl\n\tjmp *_done_end\n\t"
      "1: popal\n\tpopfl\n\tpushl %ebx\n\tpushl %edi\n\tmovl %eax,%esi\n\tcall *_event_native\n\tjmp *_resume_end\n\t");
}
typedef struct {unsigned rva,size;B bytes[10];void *target;} Hook;
static Hook hooks[]={
    {0x1f88eb,7,{0x68,0xe0,0x6b,0x5a,0x10,0x8b,0xcf},start_bridge},
    {0x1f9193,9,{0x53,0x57,0x8b,0xf0,0xe8,0xc6,0x6b,0xe1,0xff},end_bridge},
    {0x3daf,5,{0xe9,0xbc,0x10,0x33,0x00},add_item},
    {0x33dde0,5,{0x56,0x8b,0xf1,0x85,0xf6},ensure_fists},
    {0x16c416,7,{0x8b,0xcd,0xe8,0xf1,0x7e,0xe9,0xff},tick_bridge},
    {0x11fdb,5,{0xe9,0x70,0xde,0x20,0x00},create_item},
    {0xd91d,5,{0xe9,0x5e,0x3d,0x17,0x00},refresh_animation},
    {0x1f9a80,5,{0x56,0x8b,0x74,0x24,0x08},trait_grant},
    {0x351090,5,{0x56,0x8b,0x74,0x24,0x08},input_bridge},
    {0x3485fd,6,{0x89,0x86,0xf0,0x06,0x00,0x00},command_bridge},
    {0x1f926d,5,{0xe8,0xbf,0xa6,0xe0,0xff},fx_bridge},
    {0xcc93,5,{0xe9,0xd8,0x4d,0x15,0x0},controller_create},
    {0x1005a,5,{0xe9,0xd1,0x87,0xc,0x0},discipline_request},
    {0x227a30,6,{0x53,0x8b,0xd9,0x56,0x33,0xf6},event_dispatch},
    {0x196ec3,5,{0x8b,0x44,0x24,0x10,0x50},schedule_bridge},
    {0xcee53,8,{0x50,0x8b,0xcb,0xe8,0x89,0x65,0xf3,0xff},queued_bridge},
    {0x2c2ec0,6,{0x53,0x55,0x56,0x57,0x8b,0xf9},scripted_corpus}
};
enum {HOOK_COUNT=sizeof(hooks)/sizeof(hooks[0])};
static int hook_selected(unsigned index){
    return index==2||index==3||index==4||index==5||index==7||index==13||index==16||pfi_options[PFI_TRANSFORM];
}
#include "native_guards.h"
static int dependencies_match(void){
    unsigned j,k;
    for(j=0;j<sizeof(guards)/sizeof(guards[0]);++j){
        const struct Guard *g=guards+j;
        if(!pfi_options[PFI_TRANSFORM]&&g->rva!=0x334e70&&g->rva!=0x335780&&
           g->rva!=0x33589d&&g->rva!=0x33dde0&&g->rva!=0x21fe50&&
           g->rva!=0x1f9a80&&g->rva!=0x1f9af0&&g->rva!=0x430e)continue;
        for(k=0;k<g->size;++k){
            if(g->mask[k]=='r'){
                unsigned expected;memcpy(&expected,g->bytes+k,4);
                if(u(module,g->rva+k)!=expected+(unsigned)(uintptr_t)module-0x10000000u)return 0;
                k+=3;
            }else if(module[g->rva+k]!=(B)g->bytes[k])return 0;
        }
    }
    if(!native_tasks_dependencies())return 0;
    if(!pfi_options[PFI_TRANSFORM])return 1;
    return !strcmp((const char *)(module+0x5a6be0),"npc_VWolfMorph")&&
           !strcmp((const char *)(module+0x5a6bc0),"D_ProteanTransform_Emitter")&&
           !strcmp((const char *)(module+0x586950),"models/character/monster/Animalism_Beastform/Animalism_Beastform.mdl");
}
void pfi_lifecycle_server(void){
    IMAGE_NT_HEADERS32 *nt;unsigned j;B patches[HOOK_COUNT][10],*trampoline;DWORD old[HOOK_COUNT],ignored;
    if(module)return;
    module=(B *)GetModuleHandleA("vampire.dll");if(!module)return;
    if(*(unsigned short *)module!=0x5a4d||u(module,0x3c)>0x1000)return;
    nt=(IMAGE_NT_HEADERS32 *)(module+*(unsigned *)(module+0x3c));
    if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||nt->OptionalHeader.Magic!=0x10b||nt->FileHeader.TimeDateStamp!=0x41afafae||nt->OptionalHeader.SizeOfImage!=0xab9000||!dependencies_match())return;
    for(j=0;j<HOOK_COUNT;++j){
        if(!hook_selected(j))continue;
        if(j==0){*(unsigned *)(hooks[j].bytes+1)=(unsigned)(uintptr_t)(module+0x5a6be0);}
        if(memcmp(module+hooks[j].rva,hooks[j].bytes,hooks[j].size))return;
    }
    trampoline=VirtualAlloc(NULL,0x1000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!trampoline)return;
    memcpy(trampoline,hooks[3].bytes,5);trampoline[5]=0xe9;*(unsigned *)(trampoline+6)=(unsigned)((uintptr_t)(module+0x33dde5)-(uintptr_t)(trampoline+10));
    memcpy(trampoline+32,hooks[7].bytes,5);trampoline[37]=0xe9;*(unsigned *)(trampoline+38)=(unsigned)((uintptr_t)(module+0x1f9a85)-(uintptr_t)(trampoline+42));
    {
        memcpy(trampoline+64,hooks[13].bytes,6);trampoline[70]=0xe9;
        *(unsigned *)(trampoline+71)=(unsigned)((uintptr_t)(module+0x227a36)-(uintptr_t)(trampoline+75));
        native_event_dispatch=(void *)(trampoline+64);
        memcpy(trampoline+96,hooks[16].bytes,6);trampoline[102]=0xe9;
        *(unsigned *)(trampoline+103)=(unsigned)((uintptr_t)(module+0x2c2ec6)-(uintptr_t)(trampoline+107));
        original_corpus=(void *)(trampoline+96);
    }
    if(!pfi_code_ready(trampoline,0x1000)){VirtualFree(trampoline,0,MEM_RELEASE);return;}
    original_ensure=(VoidFn)trampoline;original_add=(ItemFn)(module+0x334e70);
    original_trait_grant=(void *) (trampoline+32);
    wolf_name=(uintptr_t)(module+0x5a6be0);
    resume_start=(uintptr_t)(module+0x1f88f2);done_start=(uintptr_t)(module+0x1f8a26);
    resume_end=(uintptr_t)(module+0x1f919c);done_end=(uintptr_t)(module+0x1f8fa3);
    event_native=(uintptr_t)(module+0xfd62);
    resume_input=(uintptr_t)(module+0x351095);resume_command=(uintptr_t)(module+0x348603);
    skip_command=(uintptr_t)(module+0x348612);resume_fx=(uintptr_t)(module+0x1f9272);
    original_fx=(uintptr_t)(module+0x3931);
    resume_tick=(uintptr_t)(module+0x16c41d);tick_native=(uintptr_t)(module+0x430e);
    PfiPatch batch[HOOK_COUNT];unsigned count=0;int committed;
    for(j=0;j<HOOK_COUNT;++j)if(hook_selected(j))
        pfi_jump(batch+count++,module+hooks[j].rva,hooks[j].size,hooks[j].target);
    committed=pfi_commit(batch,count);
    if(committed==1)pfi_inventory_ready=1;
    else if(!committed)VirtualFree(trampoline,0,MEM_RELEASE);
}
