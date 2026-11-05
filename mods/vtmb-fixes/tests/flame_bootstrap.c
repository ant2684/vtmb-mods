#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static unsigned char *site,*bridge;static void (__cdecl *original)(void *,int);
static unsigned char expected[]={0x53,0x8b,0x5c,0x24,0x08,0x55};
static void __cdecl queued(void *target,int amount){
 FILE *f=fopen(FLAME_TEST_LOG,"a");if(f){fprintf(f,"{\"target\":%u,\"amount\":%d}\n",(unsigned)(uintptr_t)target,amount);fclose(f);}original(target,amount);
}
__declspec(dllexport) void loaded_vampire(void){
 unsigned char *s=(void *)GetModuleHandleA("vampire.dll");if(!s||site)return;
 IMAGE_NT_HEADERS32 *n=(void *)(s+((IMAGE_DOS_HEADER *)s)->e_lfanew);
 if(n->FileHeader.TimeDateStamp!=0x41afafae||n->OptionalHeader.SizeOfImage!=0xab9000||memcmp(s+0x23e4b0,expected,6))return;
 bridge=VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!bridge)return;
 memcpy(bridge,expected,6);bridge[6]=0xe9;*(int32_t *)(bridge+7)=(int32_t)((s+0x23e4b6)-(bridge+11));
 DWORD old,ignore;if(!VirtualProtect(bridge,4096,PAGE_EXECUTE_READ,&old))return;FlushInstructionCache(GetCurrentProcess(),bridge,11);
 original=(void *)bridge;site=s+0x23e4b0;
 if(!VirtualProtect(site,6,PAGE_EXECUTE_READWRITE,&old)){site=NULL;return;}
 site[0]=0xe9;*(int32_t *)(site+1)=(int32_t)((unsigned char *)queued-(site+5));site[5]=0x90;
 FlushInstructionCache(GetCurrentProcess(),site,6);VirtualProtect(site,6,old,&ignore);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD r,LPVOID reserved){(void)h;(void)r;(void)reserved;return TRUE;}
