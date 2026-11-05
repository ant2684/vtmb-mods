/* Exact new input-helper publication, behavior and failure regression. */
#include "native_fixture.h"
static uint8_t *client;static int vp_calls,vp_fail,vp_from,fl_calls,fl_fail,mode,visible=1,has_panel=1,forwarded,closed;
static uint8_t panel[0x500];static int forwarded_key;
static LONG CALLBACK failure(EXCEPTION_POINTERS *p){fprintf(stderr,"EXCEPTION %lx EIP=%lx client=%p address=%lx ESP=%lx\n",p->ExceptionRecord->ExceptionCode,p->ContextRecord->Eip,(void *)client,(unsigned long)p->ExceptionRecord->ExceptionInformation[1],p->ContextRecord->Esp);fflush(stderr);return EXCEPTION_CONTINUE_SEARCH;}
static const char *keys[]={"ConsolePauseFix","SubtitlePauseRadioFix","HistoryStatResetFix","ContainerStackFix","ContainerInputGuard","FlamethrowerDamageNumbers","LoadingInputGuard","CastingAnimationCleanup"};
static DWORD WINAPI profile(LPCSTR section,LPCSTR key,LPCSTR def,LPSTR out,DWORD n,LPCSTR path){unsigned i;(void)section;(void)def;(void)n;(void)path;for(i=0;i<8;i++)if(!strcmp(keys[i],key))break;strcpy(out,i==4?"1":"0");return 1;}
static HMODULE WINAPI module(LPCSTR n){return !strcmp(n,"client.dll")?(HMODULE)client:GetModuleHandleA(n);}
static BOOL WINAPI protect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old){vp_calls++;if(vp_calls==vp_fail||(vp_from&&vp_calls>=vp_from))return FALSE;return VirtualProtect(p,n,flags,old);}
static BOOL WINAPI flush(HANDLE h,LPCVOID p,SIZE_T n){fl_calls++;if(fl_calls==fl_fail)return FALSE;return FlushInstructionCache(h,p,n);}
static void __fastcall native_key(void *self,void *unused,int key){(void)unused;check(self==(void *)0x1234,"key ECX");forwarded++;forwarded_key=key;}
static void *__fastcall query(void *self,void *unused,const char *name){(void)unused;check(self==client+0x4cfe38&&name==(char *)client+0x27b3d0,"query native ABI");panel[0x4d8]=(uint8_t)visible;panel[0x181]=(uint8_t)mode;return has_panel?panel:NULL;}
static void __cdecl native_close(void *button,int down){check(button==client+0x4d2fa4&&down==0,"close native ABI");closed++;}
static void write_jump(uint8_t *p,void *to){DWORD old,tmp;check(VirtualProtect(p,5,PAGE_EXECUTE_READWRITE,&old),"native endpoint writable");jump(p,to);check(VirtualProtect(p,5,old,&tmp),"native endpoint protected");}
static void behavior(void){
 void(__attribute__((thiscall))*key)(void *,int)=(void *)*(uintptr_t *)(client+0x24aa90);void(__cdecl *close_fn)(void)=(void *)(client+0x102150);
 unsigned i;int values[]={0,1,63,64,65,66,91};
 write_jump(client+0x1b4360,native_key);write_jump(client+0xf0ed0,query);write_jump(client+0x101e20,native_close);
 for(i=0;i<7;i++){int before=forwarded;printf("KEY %d\n",values[i]);fflush(stdout);key((void *)0x1234,values[i]);check(forwarded-before==(values[i]!=64&&values[i]!=65),"key suppression/forwarding");if(forwarded!=before)check(forwarded_key==values[i],"key argument retained");}
 for(i=0;i<4;i++){int before=closed;has_panel=i!=0;visible=i!=1;mode=i==3;printf("CLOSE %u\n",i);fflush(stdout);close_fn();check(closed-before==(i!=2),"container/hidden/absent/inventory close behavior");}
}
int main(int argc,char **argv){
 HMODULE h;void(__cdecl *install)(void);uint8_t old[5];uintptr_t vtable;DWORD protection,tmp;int fault,kind;
 check(argc==5,"VTM client fault kind");fault=atoi(argv[3]);kind=atoi(argv[4]);client=map_image(argv[2]);
 AddVectoredExceptionHandler(1,failure);
 memcpy(old,client+0x102150,5);vtable=*(uintptr_t *)(client+0x24aa90);
 VirtualProtect(client+0x102150,5,PAGE_EXECUTE_READ,&protection);VirtualProtect(client+0x24aa90,4,PAGE_READONLY,&protection);
 h=LoadLibraryA(argv[1]);check(h!=NULL,"load finalized unified plugin");
 imports(h,"GetModuleHandleA",module);imports(h,"GetPrivateProfileStringA",profile);imports(h,"VirtualProtect",protect);imports(h,"FlushInstructionCache",flush);
 if(kind==0)vp_fail=fault;if(kind==1)fl_fail=fault;
 if(kind==2){VirtualProtect(client+0x102150,5,PAGE_EXECUTE_READWRITE,&tmp);client[0x102150]=0xcc;VirtualProtect(client+0x102150,5,PAGE_EXECUTE_READ,&tmp);}
 install=(void *)GetProcAddress(h,"loaded_client");check(install!=NULL,"loader callback");install();
 if(fault||kind==2){
  int table_native=*(uintptr_t *)(client+0x24aa90)==vtable;
  int code_native=!memcmp(client+0x102150,old,5);
  if(kind==2){check(table_native&&client[0x102150]==0xcc,"occupied site preserved without partial publication");}
  else check((table_native&&code_native)||(!table_native&&client[0x102150]==0xe9),"OS fault leaves a complete commit or complete rollback");
  FreeLibrary(h);check(*(uintptr_t *)(client+0x24aa90)==vtable,"final native vtable");check(kind==2?client[0x102150]==0xcc:!memcmp(client+0x102150,old,5),"final native/foreign code");
  printf("PASS atomic fault outcome kind=%d fault=%d\n",kind,fault);return 0;
 }
 check(*(uintptr_t *)(client+0x24aa90)!=vtable&&client[0x102150]==0xe9,"both new hooks installed");
 {uint8_t *helper=destination(client+0x102150);MEMORY_BASIC_INFORMATION m;check(VirtualQuery(helper,&m,sizeof(m))==sizeof(m)&&m.State==MEM_COMMIT&&m.Type==MEM_PRIVATE&&m.Protect==PAGE_EXECUTE_READ,"close detour reaches published RX helper");}
 {int count=vp_calls;install();check(vp_calls==count,"idempotent installation");}
 behavior();
 if(kind==3){vp_from=vp_calls+1;FreeLibrary(h);check(client[0x102150]==0xe9,"persistent OS refusal retained published code hook");behavior();puts("PASS helpers callable after VTM unload despite permanent rollback refusal");}
 else{FreeLibrary(h);check(*(uintptr_t *)(client+0x24aa90)==vtable&&!memcmp(client+0x102150,old,5),"owned hooks restored on unload");puts("PASS exact published input helper behavior, ABI and clean unload");}
 return 0;
}
