/* Execute both actual finalized helpers with native module/API fixtures. */
#include "../../../infra/common/native_fixture.h"
#define SITE 0x16dfa4u
#define CAP 0x16fe4au
#define PRICE 0xda3cbu
static uint8_t *client,*server,*published_ui,*published_price,*published_cap;
static int missing,vp_calls,fl_calls,alloc_calls,free_calls,vp_at,vp_from,fl_at,fl_from,alloc_at,race;
static const uint8_t original[]={0x8b,0x44,0x24,0x34,0x8a,0x88,0x81,1,0,0,0x84,0xc9,0x0f,0x84,1,7,0,0};
static const uint8_t cap_original[]={0x8a,0x44,0x24,0x13,0x84,0xc0,0x0f,0x85,0xaa,0,0,0};
static const uint8_t price_original[]={0x0f,0x84,0x86,0,0,0};
static HMODULE WINAPI module(LPCSTR name){
 if(!strcmp(name,"client.dll"))return missing&1?NULL:(HMODULE)client;
 if(!strcmp(name,"vampire.dll"))return missing&2?NULL:(HMODULE)server;
 return NULL;
}
static BOOL WINAPI protect(LPVOID p,SIZE_T n,DWORD mode,PDWORD old){
 ++vp_calls;if(vp_calls==vp_at||(vp_from&&vp_calls>=vp_from))return FALSE;
 {BOOL ok=VirtualProtect(p,n,mode,old);
  if(ok&&mode==PAGE_EXECUTE_READWRITE&&((race==1&&p==client+SITE)||(race==2&&p==server+PRICE)||(race==3&&p==client+CAP))){*(uint8_t *)p=0xcc;race=0;}return ok;}
}
static BOOL WINAPI flush(HANDLE h,LPCVOID p,SIZE_T n){
 ++fl_calls;
 if(p==client+CAP&&*(const uint8_t *)p==0xe9)published_cap=destination(client+CAP);
 if(p==client+SITE&&*(const uint8_t *)p==0xe9)published_ui=destination(client+SITE);
 if(p==server+PRICE&&*(const uint8_t *)p==0xe9)published_price=destination(server+PRICE);
 if(fl_calls==fl_at||(fl_from&&fl_calls>=fl_from))return FALSE;
 return FlushInstructionCache(h,p,n);
}
static LPVOID WINAPI alloc(LPVOID p,SIZE_T n,DWORD flags,DWORD mode){++alloc_calls;if(alloc_calls==alloc_at)return NULL;return VirtualAlloc(p,n,flags,mode);}
static BOOL WINAPI release(LPVOID p,SIZE_T n,DWORD flags){++free_calls;return VirtualFree(p,n,flags);}
static DWORD protection(void *p){MEMORY_BASIC_INFORMATION q;check(VirtualQuery(p,&q,sizeof(q))==sizeof(q),"query page");return q.Protect;}
static void safe_helpers(void){
 if(published_cap)check(protection(published_cap)==PAGE_EXECUTE_READ&&published_cap[0]==0x9c,"published capacity helper retained RX");
 if(published_ui)check(protection(published_ui)==PAGE_EXECUTE_READ&&published_ui[0]==0x8b,"published UI helper retained RX");
 if(published_price)check(protection(published_price)==PAGE_EXECUTE_READ&&published_price[0]==0x0f,"published price helper retained RX");
}
static void writable(void){DWORD old;check(VirtualProtect(client+CAP,12,PAGE_EXECUTE_READWRITE,&old),"capacity fixture RW");check(VirtualProtect(client+SITE,18,PAGE_EXECUTE_READWRITE,&old),"client fixture RW");check(VirtualProtect(server+PRICE,6,PAGE_EXECUTE_READWRITE,&old),"server fixture RW");}
static void reset(void){DWORD old;writable();memcpy(client+CAP,cap_original,12);memcpy(client+SITE,original,18);memcpy(server+PRICE,price_original,6);check(VirtualProtect(client+SITE,18,PAGE_EXECUTE_READ,&old),"client fixture RX");check(VirtualProtect(server+PRICE,6,PAGE_EXECUTE_READ,&old),"server fixture RX");check(VirtualProtect(client+CAP,12,PAGE_EXECUTE_READ,&old),"capacity fixture RX");vp_at=vp_from=fl_at=fl_from=alloc_at=race=missing=0;}
static int native_ui(void){return !memcmp(client+SITE,original,18);}
static int native_price(void){return !memcmp(server+PRICE,price_original,6);}
static void both_native(void){check(native_ui()&&native_price()&&!memcmp(client+CAP,cap_original,12),"both native sites restored");}
static HMODULE open_plugin(const char *path){
 HMODULE h=LoadLibraryA(path);check(h!=NULL&&(uintptr_t)h!=0x10000000,"force relocated exact VTM");
 imports(h,"GetModuleHandleA",module);imports(h,"VirtualProtect",protect);imports(h,"FlushInstructionCache",flush);imports(h,"VirtualAlloc",alloc);imports(h,"VirtualFree",release);
 vp_calls=fl_calls=alloc_calls=free_calls=0;published_ui=published_price=published_cap=NULL;return h;
}
static void callback(HMODULE h,const char *name){void (__cdecl *fn)(void)=(void *)GetProcAddress(h,name);check(fn!=NULL,"loader export");fn();}
static void load(HMODULE h){callback(h,"loaded_client");}
static uint8_t *synthetic(int price){
 unsigned size=price?0xab9000:0x6e9000;uint8_t *b=VirtualAlloc(NULL,size,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);IMAGE_DOS_HEADER *d=(void *)b;IMAGE_NT_HEADERS32 *nt;
 const uint8_t owner[]={0x8b,0x16,0x8b,0xce,0xc6,0x44,0x24,0x44,0,0xff,0x92,0xa4,2,0,0,0x50,0x8b,6,0x8b,0xce,0xff,0x90,0x7c,3,0,0};
 const uint8_t stack[]={0x8b,0x13,0x8b,0xcb,0xff,0x92,0xe8,3,0,0,0x84,0xc0,0x0f,0x84,0xae,0,0,0};
 const uint8_t buy[]={0x85,0xc0,0x74,5,0xc6,0x44,0x24,0x10,1,0x8b,7,0x8b,0xcf,0xff,0x90,0xcc,5,0,0,0x84,0xc0,0x0f,0x84,0x86,0,0,0,0x57,0x8b,0xcd,0xe8,0xa7,0xf0,0xf2,0xff};
 const uint8_t cost[]={0x8b,0x44,0x24,0x10,0x8b,0xcf,0x50,0x55,0x56,0xe8,0x46,0x2f,0xf3,0xff,0x8b,0xd8,0x8b,0xce,0x53,0xe8,0xcc,0xfe,0xf2,0xff,0x53,0x8b,0xcd,0xe8,0xef,0,0xf3,0xff};
 check(b!=NULL,"module allocation");d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x80;nt=(void *)(b+0x80);nt->Signature=IMAGE_NT_SIGNATURE;nt->FileHeader.Machine=0x14c;nt->FileHeader.TimeDateStamp=price?0x41afafae:0x41afaf63;nt->OptionalHeader.Magic=0x10b;nt->OptionalHeader.SizeOfImage=size;
 if(price){memcpy(b+0xda3b6,buy,sizeof(buy));memcpy(b+0xda4ec,cost,sizeof(cost));}
 else{memcpy(b+CAP,cap_original,12);b[0x16ebe0]=0xa1;put(b+0x16ebe1,(uint32_t)(uintptr_t)(b+0x49d984));memcpy(b+0x16ebe5,"\x53\x55\x33\xed\x33\xdb\x85\xc0\x7e\x64",10);memcpy(b+SITE,original,18);memcpy(b+0x16df25,owner,sizeof(owner));memcpy(b+0x16f9ef,stack,sizeof(stack));}return b;
}
int main(int argc,char **argv){
 HMODULE h;unsigned i,j;FILE *f;uint8_t *ui_gate,*price_gate,*cap_gate;
 check(argc==5,"plugin/client/server/certificate");check(VirtualAlloc((void *)0x10000000,0x10000,MEM_RESERVE,PAGE_NOACCESS)!=NULL,"reserve preferred plugin address");
 client=!strcmp(argv[2],"--synthetic")?synthetic(0):map_image(argv[2]);server=!strcmp(argv[3],"--synthetic")?synthetic(1):map_image(argv[3]);
 for(i=1;i<=2;i++){
  missing=(int)i;h=open_plugin(argv[1]);callback(h,i==1?"loaded_server":"loaded_client");check(!alloc_calls,"missing either module changes neither site");missing=0;callback(h,i==1?"loaded_client":"loaded_server");check(!native_ui()&&!native_price(),"either module load order installs pair");FreeLibrary(h);both_native();safe_helpers();reset();
 }
 for(i=0;i<2;i++){
  uint8_t *b=i?server:client;unsigned anchors[3]={i?PRICE:SITE,i?0xda3b6:0x16df25,i?0xda4ec:0x16f9ef};IMAGE_NT_HEADERS32 *nt=(void *)(b+((IMAGE_DOS_HEADER *)b)->e_lfanew);
  for(j=0;j<3;j++){uint8_t saved;writable();saved=b[anchors[j]];b[anchors[j]]^=1;h=open_plugin(argv[1]);load(h);check(!alloc_calls,"foreign site/anchor refuses both");FreeLibrary(h);b[anchors[j]]=saved;}
  {DWORD saved=nt->FileHeader.TimeDateStamp;nt->FileHeader.TimeDateStamp^=1;h=open_plugin(argv[1]);load(h);check(!alloc_calls,"module identity refusal");FreeLibrary(h);nt->FileHeader.TimeDateStamp=saved;}
  reset();
 }
 {unsigned extra[2]={CAP,0x16ebe5};for(j=0;j<2;j++){uint8_t saved;writable();saved=client[extra[j]];client[extra[j]]^=1;h=open_plugin(argv[1]);load(h);check(!alloc_calls,"capacity site/cache anchor conflict refuses installation");FreeLibrary(h);client[extra[j]]=saved;}reset();}
 for(i=1;i<=3;i++){race=(int)i;h=open_plugin(argv[1]);load(h);check((i==1?client[SITE]:i==2?server[PRICE]:client[CAP])==0xcc,"race preserves foreign site");check(i==1?native_price():native_ui(),"race does not expose unpaired UI");FreeLibrary(h);safe_helpers();reset();}
 for(i=1;i<=3;i++){alloc_at=(int)i;h=open_plugin(argv[1]);load(h);both_native();FreeLibrary(h);safe_helpers();reset();}
 for(i=1;i<=9;i++){vp_at=(int)i;h=open_plugin(argv[1]);load(h);both_native();check(protection(client+SITE)==PAGE_EXECUTE_READ&&protection(server+PRICE)==PAGE_EXECUTE_READ,"one-shot protect faults restore RX");FreeLibrary(h);safe_helpers();reset();}
 for(i=1;i<=6;i++){fl_at=(int)i;h=open_plugin(argv[1]);load(h);both_native();FreeLibrary(h);safe_helpers();reset();}
 /* Persistent failures may retain a standalone payment hook, never unsafe code
    or a visibility hook whose matching payment hook has been removed. */
 for(i=0;i<2;i++){
  if(i)fl_from=6;else vp_from=9;h=open_plugin(argv[1]);load(h);check(native_ui(),"failed publication rolls UI bytes back");
  if(i)check(!native_price(),"unconfirmed UI cache rollback retains payment");safe_helpers();
  {int n=vp_calls;callback(h,"loaded_server");load(h);check(n==vp_calls,"published failure does not retry installation");}
  vp_from=fl_from=0;FreeLibrary(h);safe_helpers();reset();
 }
 h=open_plugin(argv[1]);load(h);ui_gate=destination(client+SITE);cap_gate=destination(client+CAP);price_gate=destination(server+PRICE);check(protection(cap_gate)==PAGE_EXECUTE_READ,"capacity helper RX before publication");check(protection(ui_gate)==PAGE_EXECUTE_READ&&protection(price_gate)==PAGE_EXECUTE_READ,"both helpers RX before publication");
 for(i=5;i<18;i++)check(client[SITE+i]==0x90,"client bounded padding");check(server[PRICE+5]==0x90,"server bounded padding");
 {int n=vp_calls;load(h);callback(h,"loaded_server");check(n==vp_calls,"both callbacks idempotent");}
 f=fopen(argv[4],"wb");check(f!=NULL,"private exact certificate");fprintf(f,"{\"client_base\":%lu,\"helper_base\":%lu,\"helper_hex\":\"",(unsigned long)(uintptr_t)client,(unsigned long)(uintptr_t)ui_gate);for(i=0;i<52;i++)fprintf(f,"%02x",ui_gate[i]);fprintf(f,"\",\"server_base\":%lu,\"price_helper_base\":%lu,\"price_helper_hex\":\"",(unsigned long)(uintptr_t)server,(unsigned long)(uintptr_t)price_gate);for(i=0;i<16;i++)fprintf(f,"%02x",price_gate[i]);fprintf(f,"\",\"cap_helper_base\":%lu,\"cap_helper_hex\":\"",(unsigned long)(uintptr_t)cap_gate);for(i=0;i<245;i++)fprintf(f,"%02x",cap_gate[i]);fprintf(f,"\"}\n");fclose(f);
 FreeLibrary(h);both_native();safe_helpers();reset();
 h=open_plugin(argv[1]);load(h);vp_from=vp_calls+1;FreeLibrary(h);check(client[SITE]==0xe9&&server[PRICE]==0xe9,"unload UI protect refusal retains coupled payment");safe_helpers();reset();
 h=open_plugin(argv[1]);load(h);fl_from=fl_calls+1;FreeLibrary(h);check(native_ui()&&!native_price(),"unload UI flush refusal retains payment");safe_helpers();reset();
 puts("PASS exact relocated pair: module order/identity, guards, races, API faults, rollback/cache coupling, lifetime and unload");return 0;
}
