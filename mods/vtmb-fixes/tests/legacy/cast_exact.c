/* Execute the finalized VTM in this standalone process, never in the game. */
#include "native_fixture.h"
#define SITE 0x3275cbu
#define CLEAR 0x1f9690u
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
static uint8_t *server,*actor,*list;
static uint8_t cv[64],groups[3][24];
static void *vtable[8],*catalog[3];
static int calls,saw_count,protect_calls,flush_calls,fail_protect,fail_flush,missing;
static uint8_t original[5];
static HMODULE WINAPI modules(LPCSTR name){return !missing&&!strcmp(name,"vampire.dll")?(HMODULE)server:NULL;}
static BOOL WINAPI protect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old){
 ++protect_calls;if(protect_calls==fail_protect)return FALSE;
 return VirtualProtect(p,n,flags,old);
}
static BOOL WINAPI flush(HANDLE p,LPCVOID at,SIZE_T n){
 ++flush_calls;if(flush_calls==fail_flush)return FALSE;
 return FlushInstructionCache(p,at,n);
}
static void FC set_value(void *self,void *unused,int value){
 (void)unused;check(self==cv&&value==0,"native ConVar integer-setter ABI");
 saw_count=*(int *)list;put(cv+0x2c,value);++calls;
}
static void page(DWORD protection){DWORD old;check(VirtualProtect(server+SITE,16,protection,&old),"fixture page protection");}
static void baseline(void){
 page(PAGE_EXECUTE_READWRITE);memcpy(server+SITE,original,5);server[SITE+5]=0x39;page(PAGE_EXECUTE_READ);
 fail_protect=fail_flush=0;protect_calls=flush_calls=0;
}
static HMODULE open_plugin(const char *path){
 HMODULE h=LoadLibraryA(path);check(h!=NULL,"finalized relocated plugin loads");
 imports(h,"GetModuleHandleA",modules);imports(h,"VirtualProtect",protect);imports(h,"FlushInstructionCache",flush);
 return h;
}
static void load(HMODULE h){
 void (*fn)(void)=(void *)GetProcAddress(h,"loaded_vampire");check(fn!=NULL,"loader callback");fn();
}
static unsigned status(HMODULE h){unsigned *p=(void *)GetProcAddress(h,"casting_cleanup_status");check(p!=NULL,"status export");return *p;}
static void setup(const char *cls,int id,int flag){
 memset(actor,0,0x2400);put(actor+0x11c,(uint32_t)(uintptr_t)cls);
 if(id>=0){put(list,1);put(list+4,id);}
 put(cv+0x2c,flag);put(server+0x751a54,1);
 memset(server+0x5bf918,0,80);put(server+0x5bf918,222);put(server+0x5bf91c,188);
 calls=0;saw_count=-1;put(server+0x7520a4,(uint32_t)(uintptr_t)cv);
 put(cv+0x10,(uint32_t)(uintptr_t)"vdebug_wpn_anims_cycle");
}
static void destroy(void){
 /* Return immediately after the patched real call site. Only the fixture's
    caller continuation changes; the production VTM remains byte-for-byte. */
 void (TC *fn)(void *)=(void *)(server+SITE);
 page(PAGE_EXECUTE_READWRITE);server[SITE+5]=0xc3;page(PAGE_EXECUTE_READ);
 fn(list);check(*(uint32_t *)list==0,"original native list clear still executes");
}
int main(int argc,char **argv){
 HMODULE h;unsigned i;DWORD saved;MEMORY_BASIC_INFORMATION mbi;
 check(argc==3,"plugin and original native DLL arguments");
 server=map_image(argv[2]);memcpy(original,server+SITE,5);
 actor=calloc(1,0x2400);check(actor!=NULL,"fixture actor");list=actor+0x13dc;
 vtable[4]=(void *)set_value;put(cv,(uint32_t)(uintptr_t)vtable);put(cv+4,(uint32_t)(uintptr_t)cv);
 for(i=0;i<3;i++)catalog[i]=groups[i];
 put(groups[0]+8,(uint32_t)(uintptr_t)"unrelated");
 put(groups[1]+8,(uint32_t)(uintptr_t)"discipline (cast)");
 put(groups[2]+8,(uint32_t)(uintptr_t)"discipline (cast_alt)");
 put(server+0x74df7c,3);put(server+0x74df80,(uint32_t)(uintptr_t)catalog);
 baseline();missing=1;h=open_plugin(argv[1]);load(h);check(status(h)==0&&!memcmp(server+SITE,original,5),"missing image refuses");FreeLibrary(h);missing=0;
 saved=((IMAGE_NT_HEADERS32 *)(server+((IMAGE_DOS_HEADER *)server)->e_lfanew))->FileHeader.TimeDateStamp;
 ((IMAGE_NT_HEADERS32 *)(server+((IMAGE_DOS_HEADER *)server)->e_lfanew))->FileHeader.TimeDateStamp^=1;
 h=open_plugin(argv[1]);load(h);check(status(h)==0,"unsupported image refuses");FreeLibrary(h);
 ((IMAGE_NT_HEADERS32 *)(server+((IMAGE_DOS_HEADER *)server)->e_lfanew))->FileHeader.TimeDateStamp=saved;
 page(PAGE_EXECUTE_READWRITE);server[SITE]=0xe9;page(PAGE_EXECUTE_READ);
 h=open_plugin(argv[1]);load(h);check(status(h)==0&&server[SITE]==0xe9,"occupied call site preserved");FreeLibrary(h);baseline();
 h=open_plugin(argv[1]);load(h);check(status(h)==1&&server[SITE]==0xe8&&memcmp(server+SITE,original,5),"owned call replacement installed");
 i=*(uint32_t *)(server+SITE+1);load(h);check(i==*(uint32_t *)(server+SITE+1),"idempotent installation");
 setup("player",1,1);check(*(int *)(cv+0x2c)==1&&!calls,"active cast is not ended by installation");
 destroy();check(*(int *)(cv+0x2c)==0&&calls==1&&saw_count==1,"reload destroys cast owner then resets flag before clear");
 setup("player",2,2);destroy();check(*(int *)(cv+0x2c)==0&&calls==1,"alternate/resisted cast mode cleared on destruction");
 setup("npc_VHumanCombatant",1,1);destroy();check(*(int *)(cv+0x2c)==1&&!calls,"NPC cleanup cannot stop player casting");
 setup("player",0,1);destroy();check(*(int *)(cv+0x2c)==1&&!calls,"unrelated debug activity state preserved");
 setup("player",1,7);destroy();check(*(int *)(cv+0x2c)==7&&!calls,"unrelated debug mode preserved");
 setup("player",-1,1);put(server+0x751a54,6);put(server+0x5bf920,3890);destroy();check(*(int *)(cv+0x2c)==0&&calls==1,"orphaned known casting list repaired at next teardown");
 setup("player",1,1);destroy();check(*(int *)(cv+0x2c)==0,"early cast before delayed Python stage also cleared");
 setup("player",1,0);destroy();check(!calls,"idle zero needs no setter call");
 setup("player",1,1);put(server+0x7520a4,0);destroy();check(!calls,"missing ConVar is harmless");
 setup("player",1,1);put(cv+0x10,(uint32_t)(uintptr_t)"different_convar");destroy();check(!calls,"ConVar identity guard");
 FreeLibrary(h);check(!memcmp(server+SITE,original,5),"owned call restored on unload");
 for(i=0;i<3;i++){
  baseline();if(i<2)fail_protect=i+1;else fail_flush=1;
  h=open_plugin(argv[1]);load(h);
  check(status(h)!=1&&!memcmp(server+SITE,original,5),"failed install leaves original native call");
  check(VirtualQuery(server+SITE,&mbi,sizeof(mbi))&&mbi.Protect==PAGE_EXECUTE_READ,"failure restores page protection");
  fail_protect=fail_flush=0;FreeLibrary(h);
 }
 puts("PASS: loader guards, native call ABI, casting ownership, teardown reset, unload and install rollback");
 free(actor);VirtualFree(server,0,MEM_RELEASE);return 0;
}
