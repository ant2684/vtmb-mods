/* Execute the exact delivery's loader callbacks against private native images. */
#include "native_fixture.h"
static uint8_t *server,*client,*engine;
static const char *keys[]={"WarformFrenzy","FilterLoadFix","InventoryFixes","ProteanTransformFixes","ClawsComboBuffer","ClawsStealthPosition","MeleeFrenzy","GriffithFrenzyCollision"};
static unsigned selected,protect_calls,flush_calls,fail_protect,fail_flush,alloc_count;
static void *allocations[64];static int invalid_key=-1;
static HMODULE WINAPI modules(LPCSTR name){
 if(!strcmp(name,"vampire.dll"))return (HMODULE)server;
 if(!strcmp(name,"client.dll"))return (HMODULE)client;
 if(!strcmp(name,"engine.dll"))return (HMODULE)engine;
 return NULL;
}
static DWORD WINAPI executable(HMODULE h,LPSTR buffer,DWORD size){
 const char *path="C:\\PFI fixture\\Vampire.exe";(void)h;
 check(size>strlen(path),"path capacity");strcpy(buffer,path);return strlen(path);
}
static DWORD WINAPI profile(LPCSTR section,LPCSTR key,LPCSTR fallback,LPSTR buffer,DWORD size,LPCSTR path){
 check(!strcmp(section,"Fixes")&&strstr(path,"protean-frenzy-improved.ini"),"only current INI interface");
 unsigned i;for(i=0;i<8&&strcmp(keys[i],key);++i){}check(i<8,"documented key only");
 const char *value=(int)i==invalid_key?"invalid":(selected&(1u<<i))?"1":"0";
 (void)fallback;check(size>strlen(value),"INI value capacity");strcpy(buffer,value);return strlen(value);
}
static BOOL WINAPI protect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old){
 ++protect_calls;if(protect_calls==fail_protect)return FALSE;
 return VirtualProtect(p,n,flags,old);
}
static BOOL WINAPI flush(HANDLE process,LPCVOID p,SIZE_T size){
 ++flush_calls;if(flush_calls==fail_flush)return FALSE;
 return FlushInstructionCache(process,p,size);
}
static LPVOID WINAPI allocate(LPVOID address,SIZE_T size,DWORD type,DWORD protection){
 void *p=VirtualAlloc(address,size,type,protection);
 if(p){check(alloc_count<64,"bounded helper count");allocations[alloc_count++]=p;}return p;
}
static BOOL WINAPI release(LPVOID address,SIZE_T size,DWORD type){
 unsigned i;for(i=0;i<alloc_count;++i)if(allocations[i]==address)allocations[i]=NULL;
 return VirtualFree(address,size,type);
}
typedef struct {uint8_t *image;unsigned rva,size;uint8_t bytes[24];DWORD protection;} Site;
static Site sites[80];static unsigned count;
static void add(uint8_t *image,unsigned rva,unsigned size){
 Site *s=sites+count++;s->image=image;s->rva=rva;s->size=size;memcpy(s->bytes,image+rva,size);
 MEMORY_BASIC_INFORMATION info;check(VirtualQuery(image+rva,&info,sizeof(info))!=0,"native page protection");s->protection=info.Protect;
}
static unsigned core[]={0x16c558,0x33e9be,0x1f9177,0x3510d7,0x1e56e0,0x1e5b30,0x33ed75};
static unsigned inventory[]={0x3daf,0x33dde0,0x16c416,0x11fdb,0x1f9a80,0x227a30,0x2c2ec0};
static unsigned transform[]={0x1f88eb,0x1f9193,0xd91d,0x351090,0x3485fd,0x1f926d,0xcc93,0x1005a,0x196ec3,0xcee53};
static unsigned melee[]={0x161fc0,0x162038,0x375c80,0x8dc40,0x12503,0x376f20,0xf03d,0xc036,0x8dd30,0x32b0,0xd4e0,0x2725d0,0xd0b2,0x3e9e00,0x343020,0x33f6d0,0x329a70,0x94b70,0x12512,0xb230,0x6fbe};
static unsigned melee_sizes[]={9,17,7,5,5,8,5,5,5,5,5,7,5,5,5,10,9,6,5,5,5};
static unsigned stealth[]={0x329298,0x329c24};
static HMODULE open(const char *path){
 HMODULE h=LoadLibraryA(path);check(h!=NULL,"load unified exact candidate");
 imports(h,"GetModuleHandleA",modules);imports(h,"GetModuleFileNameA",executable);
 imports(h,"GetPrivateProfileStringA",profile);imports(h,"VirtualProtect",protect);
 imports(h,"FlushInstructionCache",flush);imports(h,"VirtualAlloc",allocate);imports(h,"VirtualFree",release);
 protect_calls=flush_calls=alloc_count=0;return h;
}
static void invoke(HMODULE h,const char *name){void(__cdecl *f)(void)=(void *)GetProcAddress(h,name);check(f!=NULL,"required loader export");f();}
static Site *find(uint8_t *image,unsigned rva){for(unsigned i=0;i<count;++i)if(sites[i].image==image&&sites[i].rva==rva)return sites+i;check(0,"recorded site");return NULL;}
static int changed(uint8_t *image,unsigned rva){Site *s=find(image,rva);return memcmp(image+rva,s->bytes,s->size)!=0;}
static void group(unsigned *rvas,unsigned n,int expected){for(unsigned i=0;i<n;++i){if(changed(server,rvas[i])!=expected)fprintf(stderr,"mask=%u rva=%x expected=%d actual=%d\n",selected,rvas[i],expected,changed(server,rvas[i]));check(changed(server,rvas[i])==expected,"exact selected hook group");}}
static void protections(void){for(unsigned i=0;i<count;++i){MEMORY_BASIC_INFORMATION info;check(VirtualQuery(sites[i].image+sites[i].rva,&info,sizeof(info))!=0,"query restored page");check(info.Protect==sites[i].protection,"ORIGINAL page protection restored");}}
static void reset(HMODULE h){
 for(unsigned i=0;i<count;++i){DWORD old;check(VirtualProtect(sites[i].image+sites[i].rva,sites[i].size,PAGE_EXECUTE_READWRITE,&old),"fixture restore writable");memcpy(sites[i].image+sites[i].rva,sites[i].bytes,sites[i].size);check(VirtualProtect(sites[i].image+sites[i].rva,sites[i].size,sites[i].protection,&old),"fixture restore original protection");}
 /* Native code is restored before helper/image storage is released. */
 for(unsigned i=0;i<alloc_count;++i)if(allocations[i])VirtualFree(allocations[i],0,MEM_RELEASE);
 FreeLibrary(h);
}
static void expect(unsigned mask){
 int inv=(mask&4)!=0,trans=inv&&(mask&8),mel=inv&&(mask&64);
 group(core,sizeof(core)/sizeof(*core),(mask&1)!=0);
 group(inventory,sizeof(inventory)/sizeof(*inventory),inv);
 check(changed(server,0x8dac0),"model pool isolation independent of every optional setting");
 group(transform,sizeof(transform)/sizeof(*transform),trans);
 group(melee,sizeof(melee)/sizeof(*melee),mel);
 group(stealth,2,(mask&32)!=0);
 check(changed(server,0x254250)==((mask&16)!=0),"buffer flag");
 check(changed(server,0x16c5be)==((mask&128)!=0),"Griffith flag");
 check(changed(client,0x19da73)==((mask&2)!=0),"filter flag");
 check(server[0x1618e0]==0x53,"original controller body retained");
}
int main(int argc,char **argv){
 check(argc==5,"plugin/server/client/engine arguments");server=map_image(argv[2]);client=map_image(argv[3]);engine=map_image(argv[4]);
 unsigned i;for(i=0;i<7;++i)add(server,core[i],i==6?1:i==5?7:i==1||i==4?5:6);
 for(i=0;i<7;++i)add(server,inventory[i],i==2?7:i>=5?6:5);
 for(i=0;i<10;++i)add(server,transform[i],i==0?7:i==1?9:i==4?6:i==9?8:5);
 for(i=0;i<21;++i)add(server,melee[i],melee_sizes[i]);
 add(server,0x254250,5);add(server,stealth[0],8);add(server,stealth[1],7);add(server,0x16c5be,6);add(client,0x19da73,5);
 add(server,0x8dac0,5);
 /* All original hook pages are real RX pages, not a permissive RWX fixture. */
 for(i=0;i<count;++i){DWORD old;check(VirtualProtect(sites[i].image+sites[i].rva,sites[i].size,PAGE_EXECUTE_READ,&old),"RX fixture");sites[i].protection=PAGE_EXECUTE_READ;}
 for(selected=0;selected<256;++selected){HMODULE h=open(argv[1]);invoke(h,"loaded_vampire");invoke(h,"loaded_client");expect(selected);protections();unsigned calls=protect_calls;invoke(h,"loaded_vampire");invoke(h,"loaded_client");check(calls==protect_calls,"idempotent loader callbacks");reset(h);}
 /* Invalid explicit values disable only that component and its dependencies. */
 for(invalid_key=0;invalid_key<8;++invalid_key){selected=255;HMODULE h=open(argv[1]);invoke(h,"loaded_vampire");invoke(h,"loaded_client");expect(selected&~(1u<<invalid_key));protections();reset(h);}invalid_key=-1;
 unsigned profiles[]={1,2,4,12,16,32,68,128};unsigned faults=0;
 for(unsigned p=0;p<8;++p){
  selected=profiles[p];HMODULE h=open(argv[1]);invoke(h,"loaded_vampire");invoke(h,"loaded_client");unsigned np=protect_calls,nf=flush_calls;reset(h);
  for(unsigned kind=0;kind<2;++kind)for(unsigned fault=1;fault<=(kind?nf:np);++fault){
   fail_protect=kind?0:fault;fail_flush=kind?fault:0;
   h=open(argv[1]);invoke(h,"loaded_vampire");invoke(h,"loaded_client");protections();
   /* Each independently installed group must be all-original or all-new. */
   unsigned *groups[]={core,inventory,transform,melee,stealth};unsigned lengths[]={7,7,10,21,2};
   for(unsigned g=0;g<5;++g){int first=changed(server,groups[g][0]);for(i=1;i<lengths[g];++i)check(changed(server,groups[g][i])==first,"atomic group under OS failure");}
   reset(h);++faults;
  }
  fail_protect=fail_flush=0;
 }
 printf("PASS 256 configuration matrices, 8 malformed values, %u exact OS-fault cases, RX protection and idempotence\n",faults);
 return 0;
}
