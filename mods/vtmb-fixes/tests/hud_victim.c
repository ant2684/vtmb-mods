#include "native_fixture.h"
#define FC __attribute__((fastcall))
#define TC __attribute__((thiscall))
static uint8_t *image;
static int calls,fail_at,paint_calls;
static HMODULE WINAPI module(const char *name){return !_stricmp(name,"client.dll")?(HMODULE)image:NULL;}
static BOOL WINAPI pin(DWORD flags,const char *address,HMODULE *out){(void)flags;(void)address;*out=(HMODULE)image;return TRUE;}
static BOOL WINAPI protect(void *at,SIZE_T n,DWORD flags,DWORD *old){if(++calls==fail_at)return FALSE;return VirtualProtect(at,n,flags,old);}
static DWORD WINAPI setting(const char *s,const char *key,const char *f,char *out,DWORD n,const char *p){(void)s;(void)f;(void)n;(void)p;out[0]=!strcmp(key,"HUDIndicatorsFix")?'1':'0';out[1]=0;return 1;}
static void patch(unsigned rva,void *target){DWORD old,ignored;check(VirtualProtect(image+rva,5,PAGE_EXECUTE_READWRITE,&old),"fixture patch");jump(image+rva,target);VirtualProtect(image+rva,5,old,&ignored);}
static void FC paint(void *self,void *unused){(void)self;(void)unused;++paint_calls;}
static int __attribute__((naked)) predicate(void *entry __attribute__((unused)),void *player __attribute__((unused))){
 __asm__ volatile("push %ebp\n mov 12(%esp),%ebp\n call *8(%esp)\n pop %ebp\n and $255,%eax\n ret");
}
int main(int argc,char **argv){
 HMODULE plugin;void (__cdecl *load)(void);uint32_t *status;uint8_t player[0x1500]={0},before[sizeof(player)],hud[0x1c0]={0},saved[3][6];
 unsigned i;const unsigned rva[3]={0x50576,0x5079b,0x22890c},size[3]={6,6,4};void *entry,*wrapper;
 check(argc==4,"arguments");image=map_image(argv[2]);plugin=LoadLibraryA(argv[1]);check(plugin!=NULL,"exact clean module loads");
 imports(plugin,"GetModuleHandleA",module);imports(plugin,"GetModuleHandleExA",pin);imports(plugin,"VirtualProtect",protect);imports(plugin,"GetPrivateProfileStringA",setting);
 load=(void *)GetProcAddress(plugin,"loaded_client");status=(void *)GetProcAddress(plugin,"victim_bar_status");check(load&&status,"exports");
 if(!strcmp(argv[3],"conflict"))image[rva[1]]=0x90;
 if(!strcmp(argv[3],"rollback"))fail_at=14;
 for(i=0;i<3;i++)memcpy(saved[i],image+rva[i],size[i]);load();
 if(strcmp(argv[3],"normal")){
  check(!status[0]&&status[1],"refusal status");for(i=0;i<3;i++)check(!memcmp(saved[i],image+rva[i],size[i]),"all hooks refused or restored");
 }else{
  check(status[0]==1&&!status[1],"installed");load();check(!status[1],"idempotent");
  entry=image+rva[0]+5+*(int32_t *)(image+rva[0]+1);wrapper=*(void **)(image+rva[2]);
  check(image[rva[0]+5]==0x90&&image[rva[1]+5]==0x90,"six-byte instruction replaced exactly");
  *(void **)(image+0x4a0d50)=player;put(player+0x14cc,6);put(image+0x3ede94,6);*(float *)(player+0x14d0)=1.f;
  check(predicate(entry,player)==1,"dialogue positive duration enables HUD interpolation");
  player[0x14d4]=1;*(float *)(player+0x14d0)=0.f;check(predicate(entry,player)==1,"ordinary native flag preserved");
  player[0x14d4]=0;check(predicate(entry,player)==0,"prefeed and interrupted/end inactive");
  *(float *)(player+0x14d0)=-1.f;check(predicate(entry,player)==0,"negative duration inactive");
  put(player+0x14d0,0x7f800000);check(predicate(entry,player)==0,"nonfinite duration inactive");
  *(float *)(player+0x14d0)=1.f;memcpy(before,player,sizeof(player));patch(0x50560,paint);
  put(hud+0x1ac,15);put(hud+0x1a8,40);((void(TC *)(void *))wrapper)(hud);
  check(paint_calls==1&&*(uint32_t *)(hud+0x1ac)==6&&*(uint32_t *)(hud+0x1a8)==100,"preview six of six corrects stale15 maximum");
  put(player+0x14cc,10);put(image+0x3ede94,5);((void(TC *)(void *))wrapper)(hud);check(*(uint32_t *)(hud+0x1a8)==50,"different maximum and partial amount");
  put(player+0x14cc,0);((void(TC *)(void *))wrapper)(hud);check(paint_calls==2,"unknown maximum waits for coherent data");
  put(player+0x14cc,6);put(image+0x3ede94,6);check(!memcmp(before,player,sizeof(player)),"player state and flags unchanged");
 }
 printf("PASS victim bar %s\n",argv[3]);return 0;
}
