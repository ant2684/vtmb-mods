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

static const char *activity_names[256];static int activity_count;
static int activity_id(const char *name){
 if(!name||!*name)return -1;
 for(int j=0;j<activity_count;j++)if(!strcmp(activity_names[j],name))return 100+j;
 check(activity_count<256,"activity table bounds");activity_names[activity_count]=_strdup(name);check(activity_names[activity_count]!=NULL,"activity name allocation");return 100+activity_count++;
}
static uint8_t *read_model(const char *path){
 load_model(path);
 for(int j=0;j<readi(model,272);j++){
  uint8_t *q=model+readi(model,276)+764*j;
  int offset=readi(q,4);put(q+12,activity_id(offset?(const char*)(q+offset):""));
 }
 return model;
}
static const char *sequence_label(uint8_t *m,int id){
 uint8_t *q=m+readi(m,276)+764*id;return (const char*)(q+readi(q,0));
}
static void compare(uint8_t *actor,uint8_t *baseline,uint8_t *candidate,const uint8_t *before,const uint8_t *hook){
 int ids[2048],weights[2048],actual[2048],actual_weights[2048];
 int(TC *collector)(void*,int,int*,int*,int)=(void*)(server+0x8dac0);
 int compared=0,custom_only=0;
 for(int a=0;a<activity_count;a++){
  model=baseline;memcpy(server+0x8dac0,before,5);
  int count=collector(actor,100+a,ids,weights,-1);
  uint8_t *expected_model=baseline;
  /* Custom-only player activities (for example ACT_SNEAK_CLAWS) were already
     present in the released resource. They have no original stock pool. Verify
     exact native forwarding on that existing resource, not invented vanilla
     candidates. Supported stock activities must still match the original. */
  if(count==0){
   model=candidate;count=collector(actor,100+a,ids,weights,-1);
   expected_model=candidate;if(count>0)++custom_only;
  }
  model=candidate;memcpy(server+0x8dac0,hook,5);
  int found=collector(actor,100+a,actual,actual_weights,-1);
  if(found!=count){fprintf(stderr,"activity=%s native_count=%d fixed_count=%d\n",activity_names[a],count,found);for(int j=0;j<found;j++)fprintf(stderr," candidate=%s\n",sequence_label(candidate,actual[j]));}
  check(found==count,"NPC native candidate count across all activities");
  for(int j=0;j<count;j++){
   const char *wanted=sequence_label(expected_model,ids[j]);
   const char *got=sequence_label(candidate,actual[j]);
   if(!strncmp(got,"pfi_frenzy_",11))got+=11;
   if(strcmp(wanted,got)||weights[j]!=actual_weights[j]){
    fprintf(stderr,"activity=%s index=%d wanted=%s/%d got=%s/%d\n",activity_names[a],j,wanted,weights[j],got,actual_weights[j]);
    check(0,"NPC exact native names/order/weights");
   }
  }
  if(count>0)++compared;
 }
 printf("PASS actor=%s populated_activities=%d custom_only_forwarded=%d: exact native names/order/weights\n",*(const char**)(actor+0x11c),compared,custom_only);
}
int main(int argc,char **argv){
 check(argc==8,"plugin/server/combined-male/stock-male/combined-female/stock-female/fists arguments");
 server=map_image(argv[2]);pc=calloc(1,0x7000);shadow=calloc(1,0x7000);other=calloc(1,0x7000);table=calloc(8192,12);
 check(pc&&shadow&&other&&table,"fixture allocation");
 *(const char**)(pc+0x11c)="player";*(uint8_t**)(pc+0xa8)=pc;
 *(const char**)(shadow+0x11c)="npc_VFrenzyShadow";*(uintptr_t*)shadow=(uintptr_t)(server+0x4b2184);
 *(const char**)(other+0x11c)="npc_VVampire";
 *(uint8_t**)(server+0x566458)=table;*(uint8_t**)(table+2*12+4)=shadow;put(table+2*12+8,7);put(pc+0x1db0,7u<<13|2u);
 *(unsigned**)(server+0x9f3680)=&depth;*(uint8_t**)(server+0x9f3620)=log_records;
 jump(server+0x13d8b,get_model);jump(server+0xb4f6,descriptor);jump(server+0xac8b,player);jump(server+0xeb29,activities);
 uint8_t before[5],hook[5];memcpy(before,server+0x8dac0,5);
 HMODULE dll=LoadLibraryA(argv[1]);check(dll!=NULL,"load finalized plugin");
 imports(dll,"GetModuleHandleA",modules);imports(dll,"GetModuleFileNameA",executable);imports(dll,"GetPrivateProfileStringA",profile);
 void(__cdecl *start)(void)=(void*)GetProcAddress(dll,"loaded_vampire");check(start!=NULL,"loader export");start();
 memcpy(hook,server+0x8dac0,5);check(memcmp(before,hook,5)!=0,"independent collector hook installed");
 for(int sex=0;sex<2;sex++){
  uint8_t *candidate=read_model(argv[3+2*sex]);uint8_t *baseline=read_model(argv[4+2*sex]);
  *(const char**)(other+0x11c)="npc_VVampire";compare(other,baseline,candidate,before,hook);
  put(pc+0x146c,10);*(const char**)(other+0x11c)="npc_VHumanCombatant";compare(other,baseline,candidate,before,hook);
  compare(shadow,baseline,candidate,before,hook);put(pc+0x146c,0);
  free(baseline);free(candidate);
 }
 uint8_t *fists=read_model(argv[7]);*(const char**)(other+0x11c)="npc_VHumanCombatant";
 compare(other,fists,fists,before,hook);free(fists);
 memcpy(server+0x8dac0,before,5);FreeLibrary(dll);
 puts("PASS native NPC behavior pools: both Claws models/all activities, unrelated NPC during local Frenzy, owned Shadow, unchanged non-Claws model");
 return 0;
}
