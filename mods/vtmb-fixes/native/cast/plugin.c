#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
typedef unsigned char B;
typedef uint32_t U;
typedef void (TC *ClearFn)(void *);
typedef void (TC *SetIntFn)(void *,int);
static B *server;
static B before[5],after[5];
static DWORD saved_protection;
static int changed;
__declspec(dllexport) U casting_cleanup_status;
enum { SITE=0x3275cb, CLEAR=0x1f9690, LIST=0x13dc };
static const B anchor[]={0x8d,0x8e,0x60,0x14,0,0,0xe8,0x9b,0xa3,0xcd,0xff,
 0x8d,0x8e,0xdc,0x13,0,0,0xe8,0x60,0x32,0xce,0xff,0x39,0x9e,0xc0,0x13,0,0};
static const B clear_bytes[]={0x83,0x39,0,0x74,6,0xc7,1,0,0,0,0,0xc3};
static U rd(const void *p,unsigned off){return *(const U *)((const B *)p+off);}
static int cast_group(const B *list){
 U count=rd(list,0),total=rd(server,0x74df7c),i;
 B **table=*(B ***)(server+0x74df80);
 if(count>32||total>4096||!table)return 0;
 for(i=0;i<count;i++){
  U id=rd(list,4+i*4);const char *name;
  if(id>=total||!table[id])continue;
  name=*(const char **)(table[id]+8);
  if(name&&(!_stricmp(name,"discipline (cast)")||!_stricmp(name,"discipline (cast_alt)")))return 1;
 }
 return 0;
}
static int cast_activities(void){
 int last=*(int *)(server+0x751a54),i;
 int *activities=(int *)(server+0x5bf918);
 if(last<2||last>19||activities[0]!=222||activities[1]!=188)return 0;
 for(i=2;i<=last;i++)if(activities[i]>=3890&&activities[i]<=3892)return 1;
 return 0;
}
/* This call belongs exclusively to the combat-character destructor, after
   inventory cleanup and before the count-only trait-list clear. Normal Cast
   expiry and discipline activation are never intercepted. */
static void FC clear_on_destroy(void *list,void *unused){
 B *actor=(B *)list-LIST,*cv,*parent;const char *cls,*name;int value;
 (void)unused;
 cls=*(const char **)(actor+0x11c);
 if(cls&&!strcmp(cls,"player")){
  cv=*(B **)(server+0x7520a4);
  if(cv&&(parent=*(B **)(cv+4))!=NULL){
   name=*(const char **)(cv+0x10);value=*(int *)(parent+0x2c);
   if(name&&!strcmp(name,"vdebug_wpn_anims_cycle")&&(value==1||value==2)&&
      (cast_group((const B *)list)||cast_activities()))
    ((SetIntFn)(*(void ***)(cv))[0x10/4])(cv,0);
  }
 }
 ((ClearFn)(server+CLEAR))(list);
}
static int supported(B *m){
 IMAGE_DOS_HEADER *dos=(void *)m;IMAGE_NT_HEADERS32 *nt;
 if(!m||dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<0||dos->e_lfanew>0x1000)return 0;
 nt=(void *)(m+dos->e_lfanew);
 return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&
  nt->FileHeader.TimeDateStamp==0x41afafae&&nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC&&
  nt->OptionalHeader.SizeOfImage==0xab9000&&
  !memcmp(m+0x3275ba,anchor,sizeof(anchor))&&!memcmp(m+CLEAR,clear_bytes,sizeof(clear_bytes));
}
static int restore(void){
 DWORD temporary,ignored;int retry;
 if(!changed)return 1;
 if(memcmp(server+SITE,after,5)&&memcmp(server+SITE,before,5))return 0;
 if(!VirtualProtect(server+SITE,5,PAGE_EXECUTE_READWRITE,&temporary))return 0;
 if(memcmp(server+SITE,after,5)&&memcmp(server+SITE,before,5)){
  VirtualProtect(server+SITE,5,saved_protection,&ignored);return 0;
 }
 memcpy(server+SITE,before,5);
 if(!FlushInstructionCache(GetCurrentProcess(),server+SITE,5))return 0;
 for(retry=0;retry<3;retry++)if(VirtualProtect(server+SITE,5,saved_protection,&ignored)){changed=0;return 1;}
 return 0;
}
__declspec(dllexport) void loaded_vampire(void){
 B *m;DWORD ignored;int retry;
 if(changed)return;
 m=(B *)GetModuleHandleA("vampire.dll");if(!supported(m))return;
 server=m;memcpy(before,m+SITE,5);memcpy(after,before,5);
 *(U *)(after+1)=(U)(uintptr_t)clear_on_destroy-(U)(uintptr_t)(m+SITE+5);
 if(!VirtualProtect(m+SITE,5,PAGE_EXECUTE_READWRITE,&saved_protection))return;
 if(memcmp(m+SITE,before,5)){
  VirtualProtect(m+SITE,5,saved_protection,&ignored);return;
 }
 memcpy(m+SITE,after,5);changed=1;
 if(FlushInstructionCache(GetCurrentProcess(),m+SITE,5)&&
    VirtualProtect(m+SITE,5,saved_protection,&ignored)){casting_cleanup_status=1;return;}
 for(retry=0;retry<3&&changed;retry++)restore();
 casting_cleanup_status=changed?3:2;
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved){
 (void)instance;
 if(reason==DLL_PROCESS_DETACH&&!reserved&&changed){
  restore();casting_cleanup_status=0;
 }
 return TRUE;
}
