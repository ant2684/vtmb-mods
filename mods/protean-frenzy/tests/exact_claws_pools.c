/* Exact delivered DLL + native collector + real delivered model descriptors.
   Only activity-name/model/descriptor getters and local-player lookup are
   fixture answers. No game process; no copy of the production filter here. */
#include "native_fixture.h"
#include <stdlib.h>
#define TC __attribute__((thiscall))
static uint8_t *server,*pc,*shadow,*other,*table,*model;
static unsigned inventory,blocked,depth;
static uint8_t log_records[1024];
static int calls;
static int readi(uint8_t *p,unsigned n){return *(int *)(p+n);}
static uint8_t *TC get_model(void *actor,int index){
    check(actor==pc||actor==shadow||actor==other,"model actor");return index==-1?model:NULL;
}
static uint8_t *TC descriptor(void *actor,int sequence){
    check(actor==pc||actor==shadow||actor==other,"descriptor actor");
    check(sequence>=0&&sequence<readi(model,272),"descriptor bounds");
    return model+readi(model,276)+764*sequence;
}
static uint8_t *__cdecl player(int index){check(index==1,"local player index");return pc;}
static void __cdecl activities(void *header){check(header==model,"resolved model");++calls;}
static HMODULE WINAPI modules(LPCSTR name){return !strcmp(name,"vampire.dll")?(HMODULE)server:NULL;}
static DWORD WINAPI executable(HMODULE h,LPSTR p,DWORD capacity){
    const char *name="C:\\PFI pool fixture\\Vampire.exe";(void)h;check(capacity>strlen(name),"exe capacity");strcpy(p,name);return strlen(name);
}
static DWORD WINAPI profile(LPCSTR section,LPCSTR key,LPCSTR fallback,LPSTR p,DWORD capacity,LPCSTR path){
    const char *value=!strcmp(key,"InventoryFixes")&&inventory?"1":"0";(void)fallback;
    check(!strcmp(section,"Fixes")&&strstr(path,"protean-frenzy-improved.ini")&&capacity>1,"INI ABI");strcpy(p,value);return 1;
}
static void run(uint8_t *actor,int want_stock){
    int ids[128]={0},weights[128]={0};uintptr_t before,after;int previous=calls;
    int (TC *collector)(void*,int,int*,int*,int)=(void*)(server+0x8dac0);
    __asm__ volatile("movl %%esp,%0":"=r"(before));
    int n=collector(actor,123,ids,weights,-1);
    __asm__ volatile("movl %%esp,%0":"=r"(after));
    check(before==after&&depth==0&&calls==previous+1,"native collector once and balanced ABI/scope");
    check(n==(want_stock?6:7),"isolated real-model count");
    int zeros=0;
    for(int j=0;j<n;++j){
        uint8_t *q=descriptor(actor,ids[j]);const char *name=(const char*)(q+readi(q,0));
        int stock=!strncmp(name,"pfi_frenzy_",11);
        check(stock==want_stock,"no stock/custom leakage in exact DLL");
        check(weights[j]==readi(q,16),"native weights preserved");
        if(!strcmp(name,"pfi_frenzy_claws_attack_low")){check(weights[j]==0,"stock low weight0");++zeros;}
    }
    check(!want_stock||zeros==1,"complete stock pool retains zero-weight low attack");
}
static void load_model(const char *path){
    FILE*f=fopen(path,"rb");long bytes;check(f!=NULL,"open model");fseek(f,0,SEEK_END);bytes=ftell(f);rewind(f);
    model=malloc(bytes);check(model&&fread(model,1,bytes,f)==(size_t)bytes,"read model");fclose(f);
    check(!memcmp(model,"IDST",4)&&readi(model,4)==2531&&readi(model,140)==bytes,"model identity/header");
    for(int j=0;j<readi(model,272);++j){
        uint8_t*q=descriptor(pc,j);int offset=readi(q,4);const char*activity=offset?(const char*)(q+offset):"";
        put(q+12,!strcmp(activity,"ACT_MELEE_ATTACK_CLAWS")?123:0xffffffffu);
    }
}
int main(int argc,char **argv){
    check(argc==5,"plugin/server/male/female arguments");
    for(int sex=0;sex<2;++sex)for(int setting=0;setting<3;++setting){
        inventory=setting!=0;blocked=setting==2;calls=depth=0;
        server=map_image(argv[2]);pc=calloc(1,0x7000);shadow=calloc(1,0x7000);other=calloc(1,0x7000);table=calloc(8192,12);
        check(pc&&shadow&&other&&table,"fixture state");load_model(argv[3+sex]);
        *(const char**)(pc+0x11c)="player";*(uint8_t**)(pc+0xa8)=pc;
        *(const char**)(shadow+0x11c)="npc_VFrenzyShadow";*(uintptr_t*)shadow=(uintptr_t)(server+0x4b2184);
        *(const char**)(other+0x11c)="npc_VHumanCombatant";
        *(uint8_t**)(server+0x566458)=table;*(uint8_t**)(table+2*12+4)=shadow;put(table+2*12+8,7);put(pc+0x1db0,7u<<13|2u);
        *(unsigned**)(server+0x9f3680)=&depth;*(uint8_t**)(server+0x9f3620)=log_records;
        jump(server+0x13d8b,get_model);jump(server+0xb4f6,descriptor);jump(server+0xac8b,player);jump(server+0xeb29,activities);
        if(blocked)server[0x3daf]=0xcc; /* Inventory hook conflict must not disable model isolation. */
        uint8_t saved[5];memcpy(saved,server+0x8dac0,5);
        HMODULE dll=LoadLibraryA(argv[1]);check(dll!=NULL,"load exact finalized DLL");
        imports(dll,"GetModuleHandleA",modules);imports(dll,"GetModuleFileNameA",executable);imports(dll,"GetPrivateProfileStringA",profile);
        void(__cdecl*start)(void)=(void*)GetProcAddress(dll,"loaded_vampire");check(start!=NULL,"native loader export");start();
        check(memcmp(saved,server+0x8dac0,5)!=0,"pool hook installed with Inventory off/on/failed");
        run(pc,0);put(pc+0x146c,10);run(pc,1);run(shadow,1);run(other,0);
        put(table+2*12+8,8);run(pc,0);put(table+2*12+8,7);put(pc+0x146c,0);run(pc,0);
        start();run(pc,0);
        printf("PASS exact model sex=%d Inventory=%u conflict=%u ordinary7/Frenzy6, zero weights, ownership, ABI\n",sex,inventory,blocked);
        /* Process-private hook helpers may be left until this short fixture exits;
           restore its native site before unloading their owner. */
        memcpy(server+0x8dac0,saved,5);FreeLibrary(dll);VirtualFree(server,0,MEM_RELEASE);
        free(model);free(pc);free(shadow);free(other);free(table);
    }
    puts("PASS 6 exact-DLL/model pool cases including InventoryFixes=0 and lifecycle install failure");return 0;
}
