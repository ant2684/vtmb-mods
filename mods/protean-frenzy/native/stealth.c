#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "runtime.h"
#define TC __attribute__((thiscall))
typedef unsigned char *(TC *DescFn)(void *,int);
typedef int (TC *BoneFn)(void *,const char *);
typedef void (TC *PositionFn)(void *,int,float *,float *);
static unsigned char *module;
__attribute__((used)) static uintptr_t resume_pair,resume_exit;
static float exit_position[3];

static int player_claws(unsigned char *attacker){
    unsigned char *table,*entry,*weapon;uint32_t handle;const char *name;
    name=*(const char **)(attacker+0x11c);
    if(!name||strcmp(name,"player"))return 0;
    handle=*(uint32_t *)(attacker+0x19a4);
    if(handle==0xffffffff)return 0;
    table=*(unsigned char **)(module+0x566458);if(!table)return 0;
    entry=table+(handle&0x1fff)*12;
    if(*(uint32_t *)(entry+8)!=(handle>>13))return 0;
    weapon=*(unsigned char **)(entry+4);if(!weapon)return 0;
    name=*(const char **)(weapon+0x11c);
    return name&&(!strcmp(name,"item_w_claws")||!strcmp(name,"item_w_chang_claw"));
}

/* Both paired clips use one scene anchor. StartGrappleAttack calculates it
   by subtracting the victim's initial animation root, but then supplies the
   victim's old world origin to the second EnterGrappleState call. Give that
   call the same XY anchor as the first. This preserves the victim's initial
   rendered position and authored spacing. Native movement, placeholders,
   collision checks, height handling and completion remain unchanged. */
__attribute__((used,noinline)) static void __cdecl align_pair(unsigned char *attacker,unsigned char *frame){
    if(*(int *)(attacker+0x153c)!=0||*(int *)(attacker+0x1540)!=3||!player_claws(attacker))return;
    *(float *)(frame+0x3c)=*(float *)(frame+0x5c);
    *(float *)(frame+0x40)=*(float *)(frame+0x60);
}

__attribute__((naked)) static void pair_bridge(void){
    __asm__ volatile("pushfl\n\tpushal\n\tleal 36(%esp),%eax\n\tpushl %eax\n\tpushl %edi\n\tcall _align_pair\n\taddl $8,%esp\n\tpopal\n\tpopfl\n\tmovl 0x40(%esp),%eax\n\tmovl 0x2c(%esp),%ecx\n\tjmp *_resume_pair\n\t");
}
/* The player branch of LeaveGrappleState traces to the entity origin, while
   the NPC branch obtains the actual final root position. Use the current
   rendered root XY as the player's trace endpoint too. The native swept-hull
   trace, ground adjustment and placement remain responsible for the result. */
__attribute__((used,noinline)) static const float *__cdecl exit_origin(unsigned char *actor,const float *native_origin){
    unsigned char *desc;const char *activity;size_t length;int bone;float root[3],angles[3];
    if(!player_claws(actor))return native_origin;
    desc=((DescFn)(module+0x8d990))(actor,*(int *)(actor+0x6f0));if(!desc)return native_origin;
    activity=(const char *)(desc+*(int32_t *)(desc+4));length=strlen(activity);
    if(length<=6||strncmp(activity,"ACT_SNEAKATTACK_SUCCESS_ATTACKER_",33)||strcmp(activity+length-6,"_CLAWS"))return native_origin;
    bone=((BoneFn)(module+0x92550))(actor,(const char *)(module+0x5a7998));if(bone<0)return native_origin;
    root[0]=native_origin[0];root[1]=native_origin[1];root[2]=native_origin[2];
    ((PositionFn)(module+0x926e0))(actor,bone,root,angles);
    if(!__builtin_isfinite(root[0])||!__builtin_isfinite(root[1]))return native_origin;
    exit_position[0]=root[0];exit_position[1]=root[1];exit_position[2]=native_origin[2];
    return exit_position;
}
__attribute__((naked)) static void exit_bridge(void){
    __asm__ volatile("pushfl\n\tpushal\n\tpushl %eax\n\tpushl %esi\n\tcall _exit_origin\n\taddl $8,%esp\n\tmovl %eax,28(%esp)\n\tpopal\n\tpopfl\n\tpushl $0\n\tpushl $1\n\tpushl %edi\n\tpushl %ebx\n\tpushl %eax\n\tjmp *_resume_exit\n\t");
}
void pfi_stealth_server(void){
    const unsigned char expected[]={0x8b,0x44,0x24,0x40,0x8b,0x4c,0x24,0x2c};
    const unsigned char exit_expected[]={0x6a,0x00,0x6a,0x01,0x57,0x53,0x50};
    const unsigned char desc_expected[]={0x53,0x55,0x8b,0xe9,0x56,0x85,0xed,0x57};
    const unsigned char bone_expected[]={0x85,0xc9,0x74,0x11,0x8b,0x91,0x6c,0x02};
    const unsigned char position_expected[]={0x83,0xec,0x30,0x56,0x8b,0xf1,0x85,0xf6};
    IMAGE_NT_HEADERS32 *nt;DWORD old,ignored;unsigned char *at;
    if(module)return;module=(unsigned char *)GetModuleHandleA("vampire.dll");if(!module)return;
    nt=(IMAGE_NT_HEADERS32 *)(module+((IMAGE_DOS_HEADER *)module)->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||
       nt->OptionalHeader.SizeOfImage!=0xab9000||nt->FileHeader.TimeDateStamp!=0x41afafae||
       memcmp(module+0x329298,expected,sizeof(expected))||memcmp(module+0x329c24,exit_expected,sizeof(exit_expected))||
       memcmp(module+0x8d990,desc_expected,8)||memcmp(module+0x92550,bone_expected,8)||memcmp(module+0x926e0,position_expected,8))return;
    resume_pair=(uintptr_t)(module+0x3292a0);resume_exit=(uintptr_t)(module+0x329c2b);
    PfiPatch patches[2];
    pfi_jump(patches,module+0x329298,8,pair_bridge);
    pfi_jump(patches+1,module+0x329c24,7,exit_bridge);
    pfi_commit(patches,2);
}
