#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "runtime.h"
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
typedef unsigned char B;
typedef int (TC *Collector)(void *,int,int *,int *,void *);
typedef const char *(TC *SequenceName)(void *,int);
static B *image;
static Collector original;
static SequenceName label;
static int ready;
static const char prefix[]="pfi_frenzy_";
static unsigned word(B *p,unsigned offset){return *(unsigned *)(p+offset);}
static B *resolve(unsigned h){
    B *table,*entry;
    if(h==0xffffffffu||(table=*(B **)(image+0x566458))==NULL)return NULL;
    entry=table+(h&8191u)*12+4;
    return word(entry,4)==h>>13?*(B **)entry:NULL;
}
static int owned_frenzy(B *actor){
    B *player,*shadow;const char *name;
    player=((B *(__cdecl *)(int))(image+0xac8b))(1);
    if(!player||(int)word(player,0x146c)<=0)return 0;
    name=*(const char **)(player+0x11c);
    if(!name||strcmp(name,"player"))return 0;
    shadow=resolve(word(player,0x1db0));
    if(!shadow||*(uintptr_t *)shadow!=(uintptr_t)(image+0x4b2184))return 0;
    name=*(const char **)(shadow+0x11c);
    return name&&!strcmp(name,"npc_VFrenzyShadow")&&(actor==player||actor==shadow);
}
static int stock_label(const char *name){return name&&!strncmp(name,prefix,sizeof(prefix)-1);}
static int stock_actor(B *actor){
    B *player=((B *(__cdecl *)(int))(image+0xac8b))(1);
    const char *name;
    /* Custom input-driven combos belong only to the confirmed local player.
       Ordinary NPCs, including Killer, retain the complete native AI pool. */
    if(!player||actor!=player)return 1;
    name=*(const char **)(player+0x11c);
    if(!name||strcmp(name,"player"))return 1;
    return owned_frenzy(actor);
}
static int filter(B *actor,int *ids,int *weights,int count){
    int j,n=0,has_stock=0,use_stock;
    if(count<=0||count>2048||!ids||!weights)return count;
    for(j=0;j<count;++j)if(stock_label(label(actor,ids[j]))){has_stock=1;break;}
    /* Old/other models and activities retain their exact native answer. */
    if(!has_stock)return count;
    use_stock=stock_actor(actor);
    for(j=0;j<count;++j)if(stock_label(label(actor,ids[j]))==use_stock){
        ids[n]=ids[j];weights[n]=weights[j];++n;
    }
    /* Preserve weight0 entries: native AI suitability can use stock low attacks. */
    return n;
}
static int FC collect(B *actor,void *unused,int activity,int *ids,int *weights,void *stat){
    int count;(void)unused;
    count=original(actor,activity,ids,weights,stat);
    return filter(actor,ids,weights,count);
}
void pfi_claws_frenzy_server(void){
    B *stub;IMAGE_NT_HEADERS32 *nt;PfiPatch patch;int committed;
    /* Resource isolation has its own native guards, independent of Inventory. */
    if(ready)return;
    image=(B *)GetModuleHandleA("vampire.dll");if(!image)return;
    if(*(unsigned short *)image!=0x5a4d||word(image,0x3c)>0x1000)return;
    nt=(IMAGE_NT_HEADERS32 *)(image+word(image,0x3c));
    if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.TimeDateStamp!=0x41afafae||nt->OptionalHeader.SizeOfImage!=0xab9000)return;
    /* The implementation is below Melee's existing forwarding-thunk hook.
       Both components can own their distinct sites; no ordering/vtable edits. */
    if(memcmp(image+0x8dac0,"\x51\x53\x8b\xd9\x55\x56\x85\xdb\x57",9)||
       memcmp(image+0x8dbe2,"\xc2\x10\x00",3)||
       memcmp(image+0x8fe80,"\x85\xc9\x74\x11\x8b\x91\x6c\x02\x00\x00",10)||
       memcmp(image+0xac8b,"\xe9",1))return;
    stub=VirtualAlloc(NULL,32,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!stub)return;
    memcpy(stub,image+0x8dac0,5);stub[5]=0xe9;
    *(unsigned *)(stub+6)=(unsigned)((uintptr_t)(image+0x8dac5)-(uintptr_t)(stub+10));
    if(!pfi_code_ready(stub,32)){VirtualFree(stub,0,MEM_RELEASE);return;}
    original=(Collector)stub;label=(SequenceName)(image+0x8fe80);
    pfi_jump(&patch,image+0x8dac0,5,collect);committed=pfi_commit(&patch,1);
    if(committed==1)ready=1;
    else if(!committed)VirtualFree(stub,0,MEM_RELEASE);
}
