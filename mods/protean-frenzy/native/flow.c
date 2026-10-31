#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "runtime.h"

#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
#define CC __attribute__((cdecl))
typedef const char *(TC *NameFn)(void *,int);
typedef void *(TC *OwnerFn)(void *);
typedef unsigned char *(TC *DescFn)(void *,int);
typedef void (TC *ContinueFn)(void *);
static unsigned char *module;
static ContinueFn original_continue;
static void *seen_player,*seen_weapon;
static int seen_sequence=-1,pending;
static float previous_cycle;

static char lower(char c){return c>='A'&&c<='Z'?(char)(c+32):c;}
static int equal(const char *a,const char *b){
    while(*a&&*b&&lower(*a)==lower(*b)){++a;++b;}
    return *a==0&&*b==0;
}
static const char *name_of(void *actor,int seq){
    if(!actor||seq<0||seq>8191)return "";
    return ((NameFn)(module+0x8fe80))(actor,seq);
}

typedef struct {const char *name;float duration;} ComboWindow;
static const ComboWindow combo_windows[]={
#include "combo_windows.inc"
};
static float stage_duration(const char *name){
    unsigned int i;
    for(i=0;i<sizeof(combo_windows)/sizeof(combo_windows[0]);++i)
        if(equal(name,combo_windows[i].name))return combo_windows[i].duration;
    return 0.f;
}

static void FC continue_attack(void *weapon,void *unused){
    unsigned char *component=((OwnerFn)(module+0x14fab))(weapon),*pc,*desc;
    int sequence,fresh,same;float cycle,start,end,lead,duration,rate;
    const char *name;
    (void)unused;
    pc=component?*(unsigned char **)(component+0xa8):NULL;
    if(!pc){pending=0;seen_player=NULL;original_continue(weapon);return;}
    sequence=*(int *)(pc+0x6f0);cycle=*(float *)(pc+0x6f8);
    same=pc==seen_player&&weapon==seen_weapon&&sequence==seen_sequence&&cycle>=previous_cycle;
    if(!same)pending=0;
    seen_player=pc;seen_weapon=weapon;seen_sequence=sequence;previous_cycle=cycle;
    name=name_of(pc,sequence);
    duration=stage_duration(name);
    if(!(duration>0.f)){pending=0;original_continue(weapon);return;}
    rate=*(float *)(pc+0x6f4);
    if(!(rate>0.f&&rate<16.f))rate=1.f;
    /* One150ms input lead for all active continuations; normalize by each
       clip's duration and actual playback multiplier, never by a fixed cycle. */
    lead=.150f*rate/duration;
    desc=((DescFn)(module+0x8d990))(pc,sequence);
    if(!desc){pending=0;original_continue(weapon);return;}
    start=*(float *)(desc+752);end=*(float *)(desc+756);fresh=(*(unsigned int *)(pc+0x208c)&1)!=0;
    /* Buffer a separate click before the authored window. Ignore the initial
       press on the first observed tick. Native transition timing is kept. */
    if(same&&fresh&&cycle<start&&cycle>=start-lead&&cycle>.10f)pending=1;
    if(cycle>end)pending=0;
    if(pending&&cycle>=start&&cycle<=end){
        unsigned int was=*(unsigned int *)(pc+0x208c);
        *(unsigned int *)(pc+0x208c)=was|1;
        original_continue(weapon);
        if(!(was&1))*(unsigned int *)(pc+0x208c)&=~1u;
        if(*(int *)(pc+0x6f0)!=sequence)pending=0;
        return;
    }
    original_continue(weapon);
}

static void jump(unsigned char *p,const void *to){
    p[0]=0xe9;*(uint32_t *)(p+1)=(uint32_t)((uintptr_t)to-(uintptr_t)(p+5));
}
static int matches(unsigned int rva,const unsigned char *bytes,size_t length){
    return memcmp(module+rva,bytes,length)==0;
}

void pfi_flow_server(void){
    static const unsigned char continuation[]={0x53,0x56,0x57,0x8b,0xd9};
    static const unsigned char owner[]={0xe9,0x40,0xd2,0x23,0x00};
    static const unsigned char descriptor[]={0x53,0x55,0x8b,0xe9,0x56,0x85,0xed,0x57};
    static const unsigned char names[]={0x85,0xc9,0x74,0x11,0x8b,0x91,0x6c,0x02,0x00,0x00};
    unsigned char *trampoline;DWORD previous,ignored;IMAGE_NT_HEADERS32 *nt;
    if(module)return;
    module=(unsigned char *)GetModuleHandleA("vampire.dll");
    if(!module)return;
    nt=(IMAGE_NT_HEADERS32 *)(module+((IMAGE_DOS_HEADER *)module)->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||
       nt->OptionalHeader.SizeOfImage!=0xab9000||nt->FileHeader.TimeDateStamp!=0x41afafae||
       !matches(0x254250,continuation,sizeof(continuation))||
       !matches(0x14fab,owner,sizeof(owner))||!matches(0x8d990,descriptor,sizeof(descriptor))||
       !matches(0x8fe80,names,sizeof(names)))return;
    trampoline=(unsigned char *)VirtualAlloc(NULL,16,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!trampoline)return;
    memcpy(trampoline,continuation,5);jump(trampoline+5,module+0x254255);
    if(!pfi_code_ready(trampoline,16)){VirtualFree(trampoline,0,MEM_RELEASE);return;}
    original_continue=(ContinueFn)trampoline;
    PfiPatch patch;pfi_jump(&patch,module+0x254250,5,continue_attack);
    int committed=pfi_commit(&patch,1);
    if(!committed)VirtualFree(trampoline,0,MEM_RELEASE);
}
