/* Executes the exact clean VTM against private relocated original PE images.
   Native callbacks below are controlled ABI fixtures, not gameplay evidence. */
#include "native_fixture.h"
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
typedef unsigned char B;
typedef unsigned U;
static B *engine,*client,*peer,*stubs[5];
static int chained;
static DWORD clock_tick=1000;
static short physical[256];
static unsigned allocations,protect_count,protect_failure,key_down_calls,key_up_calls,attack_calls;
static int abort_begin;
static int consume_release;
static U original_bits=0x800001;
static unsigned rd(B *p,U offset){return *(unsigned *)(p+offset);}
static void wr(B *p,U offset,U value){put(p+offset,value);}
static DWORD WINAPI tick(void){return clock_tick;}
static SHORT WINAPI async_key(int key){return physical[key&255];}
static void __cdecl fake_key(int key,int down){
 if(down){key_down_calls++;wr(engine,0xd5ff50+(U)key*4,1);}
 else{key_up_calls++;wr(engine,0xd5ff50+(U)key*4,0);}
}
static void __cdecl fake_begin(int force){(void)force;if(!abort_begin){wr(engine,0xb42318,1);engine[0xb42314]=1;}}
static void __cdecl fake_end(void){wr(engine,0xb42318,0);engine[0xb42314]=0;wr(engine,0xd5e0b0,4);wr(engine,0xd5e0b4,4);}
static void __cdecl fake_down(void){attack_calls++;wr(client,0x4d2f44,3);}
static U FC fake_bits(void *self,void *unused,int reset){(void)unused;check(self==(void *)0x1234&&(reset==0||reset==1),"thiscall bits arguments");return original_bits;}
static LRESULT WINAPI fake_dispatch(const MSG *msg){
 void (__cdecl *key)(int,int)=(void *)(engine+0xa38a0);
 if(consume_release&&(msg->message==WM_LBUTTONUP||msg->message==WM_KEYUP))return 0x12345678;
 if(msg->message==WM_LBUTTONDOWN||msg->message==WM_LBUTTONUP)key(241,msg->message==WM_LBUTTONDOWN);
 if(msg->message==WM_KEYDOWN||msg->message==WM_KEYUP)key((int)msg->wParam,msg->message==WM_KEYDOWN);
 if(msg->message==WM_MOUSEMOVE&&(msg->wParam&MK_LBUTTON))key(241,1);
 return 0x12345678;
}
static HMODULE WINAPI modules(LPCSTR name){if(!strcmp(name,"engine.dll"))return(HMODULE)engine;if(!strcmp(name,"client.dll"))return(HMODULE)client;if(!strcmp(name,"vtmb-dialogue-mouse.vtm"))return(HMODULE)peer;return GetModuleHandleA(name);}
static FARPROC WINAPI procedure(HMODULE h,LPCSTR name){if((uintptr_t)name>65535&&!strcmp(name,"DispatchMessageA"))return(FARPROC)fake_dispatch;return GetProcAddress(h,name);}
static LPVOID WINAPI allocate(LPVOID at,SIZE_T size,DWORD type,DWORD flags){void *p=VirtualAlloc(at,size,type,flags);check(size==64&&allocations<5,"only five trampoline allocations");stubs[allocations++]=p;return p;}
static BOOL WINAPI protect(LPVOID p,SIZE_T size,DWORD flags,PDWORD old){protect_count++;if(protect_count==protect_failure)return FALSE;return VirtualProtect(p,size,flags,old);}
static void send(UINT message,DWORD stamp,WPARAM key){MSG msg={0};msg.message=message;msg.time=stamp;msg.wParam=key;check(((LRESULT(WINAPI *)(const MSG *))*(void **)(engine+0x173210))(&msg)==0x12345678,"DispatchMessage return/ABI");}
int main(int argc,char **argv){
 HMODULE plugin;void (__cdecl *install)(void),(__cdecl *begin)(int),(__cdecl *end)(void),(__cdecl *down)(void);U (TC *bits)(void *,int);U *status;
 U rvas[]={0xa38a0,0x86a80,0x86d70,0x102270,0x104460};B saved[5][24];B *module[5];
 check(argc==5||argc==6,"fixture arguments: VTM engine client fault [dialogue mouse]");
 engine=map_image(argv[2]);client=map_image(argv[3]);wr(engine,0xd5e0b0,4);wr(engine,0xd5e0b4,4);wr(engine,0xb42318,0);engine[0xb42314]=0;
 memset(engine+0xd607c8,0,256*4);wr(engine,0xd607c8+241*4,(U)(uintptr_t)"+attack");wr(engine,0xd607c8+13*4,(U)(uintptr_t)"+attack");
 wr(engine,0xd607c8+'e'*4,(U)(uintptr_t)"+use");memset(engine+0xd5ff50,0,256*4);
 *(void **)(engine+0x173210)=(void *)fake_dispatch;
 module[0]=module[1]=module[2]=engine;module[3]=module[4]=client;
 if(argc==6){
  DWORD old,ignored;B *site=client+0x102270;B *tr=VirtualAlloc(NULL,64,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);check(tr!=NULL,"peer native trampoline");
  peer=map_image(argv[5]);wr(peer,0x18b20,(U)(uintptr_t)client);wr(peer,0x18b44,(U)(uintptr_t)tr);
  memcpy(tr,site,6);jump(tr+6,site+6);check(VirtualProtect(tr,64,PAGE_EXECUTE_READ,&old),"peer trampoline RX");
  jump(site,peer+0x2320);chained=1;
  if(!strcmp(argv[4],"dialogue-code"))peer[0x2320]^=1;
  if(!strcmp(argv[4],"dialogue-owner"))wr(peer,0x18b20,(U)(uintptr_t)(client+1));
  if(!strcmp(argv[4],"dialogue-target"))jump(site,peer+0x2321);
  if(!strcmp(argv[4],"dialogue-trampoline"))wr(peer,0x18b44,0);
  if(!strcmp(argv[4],"dialogue-version"))((IMAGE_NT_HEADERS32 *)(peer+((IMAGE_DOS_HEADER *)peer)->e_lfanew))->FileHeader.TimeDateStamp^=1;
  if(!strcmp(argv[4],"dialogue-return")){check(VirtualProtect(tr,64,PAGE_READWRITE,&old),"peer corrupt fixture writable");tr[7]^=1;check(VirtualProtect(tr,64,PAGE_EXECUTE_READ,&ignored),"peer corrupt fixture RX");}
 }
 /* Keep applied relocations but make the directory unusable in memory. */
 if(!strcmp(argv[4],"dialogue")){
  B *images[]={engine,client,peer};
  for(U i=0;i<3;i++){
   IMAGE_NT_HEADERS32 *nt=(void *)(images[i]+((IMAGE_DOS_HEADER *)images[i])->e_lfanew);
   nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC].VirtualAddress=nt->OptionalHeader.SizeOfImage;
   nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC].Size=8;
  }
 }
 for(U i=0;i<5;i++)memcpy(saved[i],module[i]+rvas[i],24);
 if(!strcmp(argv[4],"signature"))engine[0xa38a0]^=1;
 if(!strcmp(argv[4],"iat"))*(void **)(engine+0x173210)=(void *)0x11223344;
 if(argv[4][0]>='0'&&argv[4][0]<='9')protect_failure=(unsigned)atoi(argv[4]);
 plugin=LoadLibraryA(argv[1]);check(plugin!=NULL,"load exact clean VTM");
 imports(plugin,"GetModuleHandleA",modules);imports(plugin,"GetProcAddress",procedure);imports(plugin,"VirtualAlloc",allocate);imports(plugin,"VirtualProtect",protect);imports(plugin,"GetTickCount",tick);imports(plugin,"GetAsyncKeyState",async_key);
 status=(void *)GetProcAddress(plugin,"loading_input_status");install=(void *)GetProcAddress(plugin,"loaded_engine");check(status&&install,"production exports");install();
 if(!strcmp(argv[4],"disabled")){
  check(!status[1]&&!status[2]&&!allocations,"disabled guard remains inactive");
  for(U i=0;i<5;i++)check(!memcmp(saved[i],module[i]+rvas[i],24),"disabled guard preserves native code");
  check(*(void **)(engine+0x173210)==(void *)fake_dispatch,"disabled guard preserves dispatch");
  puts("PASS standalone guard disabled");return 0;
 }
 if(strcmp(argv[4],"ok")&&strcmp(argv[4],"dialogue")){
  check(!status[1]&&status[2],"conflict/fault fails closed");
  for(U i=0;i<5;i++)if(strcmp(argv[4],"signature")||i)check(!memcmp(saved[i],module[i]+rvas[i],24),"no partial detours after failure");
  check(*(void **)(engine+0x173210)==(!strcmp(argv[4],"iat")?(void *)0x11223344:(void *)fake_dispatch),"failed install preserves dispatch ownership");
  puts("PASS exact guard fail-closed/rollback");return 0;
 }
 check(status[1]==1&&!status[2]&&allocations==(chained?4u:5u),"all five guarded hooks and IAT installed, peer helper borrowed only");install();check(allocations==(chained?4u:5u),"loader callbacks idempotent");
 {void *targets[]={fake_key,fake_begin,fake_end,fake_down,fake_bits};DWORD old,ignored;for(U i=0;i<5;i++){B *entry=chained&&i==3?peer+0x2320:stubs[i-(chained&&i>3)];check(VirtualProtect(entry,64,PAGE_EXECUTE_READWRITE,&old),"fixture trampoline writable");jump(entry,targets[i]);check(VirtualProtect(entry,64,old,&ignored),"fixture trampoline RX restored");}}
 begin=(void *)(engine+0x86a80);end=(void *)(engine+0x86d70);down=(void *)(client+0x102270);bits=(void *)(client+0x104460);
 send(WM_LBUTTONDOWN,1001,0);send(WM_LBUTTONUP,1002,0);check(key_down_calls==1&&key_up_calls==1,"normal pre-load click passes");
 wr(client,0x4d2f3c,241);wr(client,0x4d2f44,3);physical[VK_LBUTTON]=(short)0x8000;begin(0);check(!rd(client,0x4d2f3c)&&!rd(client,0x4d2f44),"entry clears held/press latch");
 send(WM_LBUTTONDOWN,1100,0);check(key_down_calls==1,"click during loading suppressed");
 down();check(!attack_calls&&!rd(client,0x4d2f44),"queued +attack during load suppressed");
 check(bits((void *)0x1234,0)==0&&bits((void *)0x1234,1)==0,"both button sampling modes mask attack and release");
 /* ClearIO's synthetic release must not re-arm a still held physical button. */
 ((void (__cdecl *)(int,int))(engine+0xa38a0))(241,0);
 clock_tick=2000;end();check(!rd(client,0x4d2f44),"end clears residual latch");
 send(WM_LBUTTONDOWN,1900,0);check(key_down_calls==1,"stale OS click delivered after end suppressed");
 send(WM_MOUSEMOVE,1901,MK_LBUTTON);check(key_down_calls==1,"stale mouse mask resample suppressed");
 send(WM_LBUTTONDOWN,2100,0);check(key_down_calls==1,"hold crossing load requires release");
 send(WM_LBUTTONUP,2101,0);physical[VK_LBUTTON]=0;send(WM_LBUTTONDOWN,2102,0);check(key_down_calls==2,"first fresh press after real release passes");
 send(WM_LBUTTONUP,2103,0);down();check(attack_calls==1&&bits((void *)0x1234,1)==0x800001,"normal attack and non-load bits remain native");
 /* Fully released loading click cannot poison the first new physical click. */
 begin(0);physical[VK_LBUTTON]=0;send(WM_LBUTTONDOWN,2200,0);send(WM_LBUTTONUP,2201,0);clock_tick=3000;end();send(WM_LBUTTONDOWN,3001,0);check(key_down_calls==3,"released click permits first new post-load press");send(WM_LBUTTONUP,3002,0);
 /* Stale down/up pair is rejected, subsequent new pair works immediately. */
 send(WM_LBUTTONDOWN,2990,0);send(WM_LBUTTONUP,2991,0);send(WM_LBUTTONDOWN,3003,0);check(key_down_calls==4,"stale pair cannot mask next fresh press");send(WM_LBUTTONUP,3004,0);
 /* A secondary binding uses the same gate; ordinary use is unaffected. */
 begin(0);send(WM_KEYDOWN,3100,13);check(key_down_calls==4,"Enter attack during loading suppressed");send(WM_KEYUP,3101,13);((void (__cdecl *)(int,int))(engine+0xa38a0))('e',1);check(key_down_calls==5,"unrelated use binding preserved");clock_tick=4000;end();send(WM_KEYDOWN,3999,13);check(key_down_calls==5,"queued keyboard attack rejected");send(WM_KEYUP,4001,13);send(WM_KEYDOWN,4002,13);check(key_down_calls==6,"fresh rebound attack passes");
 /* Signed timestamp comparison survives the 32-bit Windows tick rollover. */
 begin(0);clock_tick=8;end();send(WM_LBUTTONDOWN,0xfffffff0u,0);check(key_down_calls==6,"wraparound stale input suppressed");send(WM_LBUTTONUP,0xfffffff1u,0);send(WM_LBUTTONDOWN,9,0);check(key_down_calls==7,"wraparound fresh input allowed");
 abort_begin=1;begin(0);send(WM_LBUTTONUP,10,0);send(WM_LBUTTONDOWN,11,0);check(key_down_calls==8,"aborted plaque entry does not stick input gate");
 abort_begin=0;physical[VK_LBUTTON]=(short)0x8000;begin(0);clock_tick=100;end();consume_release=1;send(WM_LBUTTONUP,101,0);consume_release=0;physical[VK_LBUTTON]=0;send(WM_LBUTTONDOWN,102,0);check(key_down_calls==9,"UI-consumed release re-arms first new press");
 puts("PASS exact clean guard: queue provenance, loading samples, holds/releases, fresh presses, rebinding, rollover, abort, ABI, idempotence");return 0;
}
