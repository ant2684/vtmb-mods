/* Load the exact unified candidate against relocated local native images.
   Proves configuration-to-hook ownership, not game/GUI behavior. */
#include "native_fixture.h"
static uint8_t *engine,*client,*server,*ui;
static unsigned mask,profile_calls,allocations;static int invalid=-1;
static const char *keys[]={"ConsolePauseFix","SubtitlePauseRadioFix","HistoryStatResetFix","ContainerStackFix","ContainerInputGuard","FlamethrowerDamageNumbers","CastingAnimationCleanup","HUDIndicatorsFix"};
static DWORD WINAPI profile(LPCSTR section,LPCSTR key,LPCSTR fallback,LPSTR out,DWORD size,LPCSTR path){
 unsigned i;(void)fallback;check(!strcmp(section,"Fixes"),"INI section");check(strstr(path,"\\Bin\\loader\\ant2684-fixes-adjustments.ini")!=NULL,"INI resides beside game EXE");
 for(i=0;i<8;i++)if(!strcmp(key,keys[i]))break;check(i<8&&size>=8,"known bounded key");profile_calls++;
 strcpy(out,(int)i==invalid?"invalid":mask&(1u<<i)?"1":"0");return(DWORD)strlen(out);
}
static HMODULE WINAPI module(LPCSTR n){
 if(!strcmp(n,"engine.dll"))return(HMODULE)engine;if(!strcmp(n,"client.dll"))return(HMODULE)client;
 if(!strcmp(n,"vampire.dll"))return(HMODULE)server;if(!_stricmp(n,"gameui.dll"))return(HMODULE)ui;
 return GetModuleHandleA(n);
}
static LPVOID WINAPI allocate(LPVOID p,SIZE_T n,DWORD type,DWORD protect){allocations++;return VirtualAlloc(p,n,type,protect);}
typedef struct{unsigned group,mod,rva,size;uint8_t before[24];} Site;
static Site sites[]={
 {0,0,0x10dc10,6,{0}},{0,0,0x1a570,5,{0}},{0,3,0x22070,5,{0}},{0,3,0x59d0,9,{0}},
 {1,0,0x1188b0,5,{0}},{1,0,0x2d130,5,{0}},{1,0,0x2b97b,5,{0}},
 {1,2,0x22c50f,5,{0}},{1,2,0x22c807,5,{0}},{1,2,0x22c360,5,{0}},
 {2,2,0x206ad1,8,{0}},{2,2,0xd6dd8,9,{0}},{2,2,0xd6deb,9,{0}},
 {3,1,0x16dfa4,18,{0}},{3,1,0x16fe4a,12,{0}},{3,2,0xda3cb,6,{0}},
 {4,1,0x24aa90,4,{0}},{4,1,0x102150,5,{0}},
 {5,2,0x3e3674,1,{0}},
 {8,0,0xa38a0,6,{0}},{8,0,0x86a80,9,{0}},{8,0,0x86d70,6,{0}},
 {8,1,0x102270,6,{0}},{8,1,0x104460,7,{0}},{8,0,0x173210,4,{0}},
 {7,1,0x79462,5,{0}},{7,1,0x4d07b,5,{0}},{7,1,0x4d18d,5,{0}},
 {7,1,0x51822,5,{0}},{7,1,0x51946,5,{0}},{7,1,0x51a7c,5,{0}},
 {7,1,0x50576,6,{0}},{7,1,0x5079b,6,{0}},{7,1,0x22890c,4,{0}},
 {6,2,0x3275cb,5,{0}}
};
int main(int argc,char **argv){
 HMODULE h;uint8_t *modules[4];unsigned i;DWORD ignored;
 const char *callbacks[]={"loaded_client","loaded_engine","loaded_gameui","loaded_vampire","loaded_server"};
 check(argc==8||argc==9,"VTM engine client server GameUI mask invalid [reverse]");
 mask=(unsigned)strtoul(argv[6],NULL,0);invalid=atoi(argv[7]);
 engine=map_image(argv[2]);client=map_image(argv[3]);server=map_image(argv[4]);ui=map_image(argv[5]);
 modules[0]=engine;modules[1]=client;modules[2]=server;modules[3]=ui;
 *(void **)(engine+0x173210)=(void *)GetProcAddress(LoadLibraryA("user32.dll"),"DispatchMessageA");
 check(*(void **)(engine+0x173210)!=NULL,"real dispatch entry");
 for(i=0;i<sizeof(sites)/sizeof(sites[0]);i++)memcpy(sites[i].before,modules[sites[i].mod]+sites[i].rva,sites[i].size);
 h=LoadLibraryA(argv[1]);check(h!=NULL,"load exact finalized unified VTM");
 imports(h,"GetModuleHandleA",module);imports(h,"GetPrivateProfileStringA",profile);imports(h,"VirtualAlloc",allocate);
 for(i=0;i<5;i++){unsigned at=argc==9?4-i:i;void(__cdecl *fn)(void)=(void *)GetProcAddress(h,callbacks[at]);check(fn!=NULL,"loader callback");fn();}
 check(profile_calls==8,"configuration read exactly once despite callback order");
 for(i=0;i<sizeof(sites)/sizeof(sites[0]);i++){
  Site *s=sites+i;int changed=memcmp(s->before,modules[s->mod]+s->rva,s->size)!=0;
  int expected=!!(mask&(1u<<s->group))&&invalid!=(int)s->group;
  if(changed!=expected){fprintf(stderr,"group %u RVA %x changed=%d expected=%d\n",s->group,s->rva,changed,expected);ExitProcess(1);}
 }
 if(!mask)check(!allocations,"all-off allocates no helpers");
 /* Do not invoke mapped game callbacks after unload. This fixture is a
    per-process installation check, not a general runtime-unload certificate. */
 for(i=0;i<sizeof(sites)/sizeof(sites[0]);i++){Site *s=sites+i;VirtualProtect(modules[s->mod]+s->rva,s->size,PAGE_EXECUTE_READWRITE,&ignored);}
 FreeLibrary(h);printf("PASS mask=%u invalid=%d hooks=%u allocations=%u\n",mask,invalid,(unsigned)(sizeof(sites)/sizeof(sites[0])),allocations);
 return 0;
}
