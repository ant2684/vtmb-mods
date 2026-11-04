#include "native_fixture.h"
#include <stdlib.h>
#include "../native/claws_frenzy.c"
#include "../native/patch.c"
int pfi_inventory_ready=1;
static B *pc,*shadow,*other,*table;
static const char *labels[]={"claws_custom_1","pfi_frenzy_claws_attack_med","claws_custom_2","pfi_frenzy_claws_attack_low","pfi_frenzy_claws_attack_jump"};
static int calls,mode;
static void *expected_actor;
static B *__cdecl player(int n){if(n!=1)fprintf(stderr,"player index=%d\n",n);check(n==1,"local player lookup");return pc;}
static const char *TC name(void *actor,int n){check(actor==expected_actor,"label actor preserved");return labels[n];}
static int TC native(void *actor,int activity,int *ids,int *weights,void *stat){
    ++calls;check(actor==expected_actor&&activity==123&&stat==(void *)0x12345,"original collector args");
    if(mode<0)return mode;
    for(int j=0;j<5;++j){ids[j]=j;weights[j]=j==3?0:j==4?5:1;}
    return mode?1:5;
}
static void run(B *actor,int stock){
    int ids[8]={-1},weights[8]={-1};uintptr_t before,after;
    expected_actor=actor;int prev=calls;
    __asm__ volatile("movl %%esp,%0":"=r"(before));
    volatile Collector entry=(Collector)(void *)collect;
    int n=entry(actor,123,ids,weights,(void *)0x12345);
    __asm__ volatile("movl %%esp,%0":"=r"(after));
    check(before==after,"thiscall stack unchanged");check(calls==prev+1,"native collector called once");
    if(mode<0){check(n==mode,"negative native result forwarded");return;}
    if(mode){check(n==1&&ids[0]==0&&weights[0]==1,"legacy/non Claws activity unchanged");return;}
    if(stock)check(n==3&&ids[0]==1&&ids[1]==3&&ids[2]==4&&weights[0]==1&&weights[1]==0&&weights[2]==5,"stock order and weight0 retained");
    else check(n==2&&ids[0]==0&&ids[1]==2&&weights[0]==1&&weights[1]==1,"ordinary custom candidates unchanged");
}
int main(void){
    image=VirtualAlloc(NULL,0xb00000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    table=calloc(8192,12);pc=calloc(1,0x7000);shadow=calloc(1,0x7000);other=calloc(1,0x7000);
    check(image&&table&&pc&&shadow&&other,"fixture allocation");
    *(B **)(image+0x566458)=table;jump(image+0xac8b,player);
    *(const char **)(pc+0x11c)="player";*(const char **)(shadow+0x11c)="npc_VFrenzyShadow";
    *(uintptr_t *)shadow=(uintptr_t)(image+0x4b2184);put(pc+0x1db0,7u<<13|2u);
    *(B **)(table+2*12+4)=shadow;put(table+2*12+8,7);
    original=native;label=name;
    *(const char **)(other+0x11c)="npc_VVampire";
    run(pc,0);run(other,1);run(shadow,1);put(pc+0x146c,10);run(pc,1);run(shadow,1);run(other,1);
    put(table+2*12+8,8);run(pc,0);run(shadow,1);put(table+2*12+8,7);
    *(uintptr_t *)shadow=0;run(pc,0);*(uintptr_t *)shadow=(uintptr_t)(image+0x4b2184);
    *(const char **)(shadow+0x11c)="npc_VWolfMorph";run(pc,0);*(const char **)(shadow+0x11c)="npc_VFrenzyShadow";
    mode=1;run(shadow,0);mode=-1;run(shadow,0);mode=0;
    put(pc+0x146c,0);run(pc,0);put(pc+0x146c,10);run(pc,1);
    *(const char **)(other+0x11c)="npc_VHumanCombatant";run(other,1);
    B *saved_pc=pc;pc=NULL;run(other,1);pc=saved_pc;
    *(const char **)(pc+0x11c)="npc_VVampire";run(pc,1);*(const char **)(pc+0x11c)="player";
    check(filter(pc,NULL,NULL,0)==0&&filter(pc,NULL,NULL,-1)==-1&&filter(pc,NULL,NULL,2049)==2049,"bounds forwarded safely");
    puts("PASS stock/player candidate isolation, zero weights, order, local owner/serial/class, negative forwarding and x86 ABI");
    return 0;
}
