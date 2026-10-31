/* Owned test only: start an engine Python timeline, then remove our hook.
   Never part of a gameplay payload. No input injection or observation hooks. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
static unsigned char *server,*stub,saved[8];
static int started;
static void FC frame(unsigned char *p,void *unused){
    HMODULE py;int (__cdecl *run)(const char *);DWORD old,tmp;(void)unused;
    ((void(TC *)(void *))stub)(p);
    if(started||!p||!*(unsigned *)(p+0x2e0)||!*(void **)(server+0x70b228))return;
    if(!*(const char **)(p+0x11c)||strcmp(*(const char **)(p+0x11c),"player")||
       *(float *)(*(unsigned char **)(server+0x70b228)+12)<3.f)return;
    py=GetModuleHandleA("vampire_python21.dll");if(!py)return;
    run=(void *)GetProcAddress(py,"PyRun_SimpleString");if(!run)return;
    started=1;
    if(server[0x16be10]!=0xe9||server+0x16be15+*(int *)(server+0x16be11)!=(unsigned char *)frame)return;
    if(!VirtualProtect(server+0x16be10,8,PAGE_EXECUTE_READWRITE,&old))return;
    memcpy(server+0x16be10,saved,8);
    VirtualProtect(server+0x16be10,8,old,&tmp);FlushInstructionCache(GetCurrentProcess(),server+0x16be10,8);
    VirtualFree(stub,0,MEM_RELEASE);stub=NULL;
    /* Owned fixture: drive only the native interface KButton, without opening
       the modal UI. The production module is unchanged; no process injection. */
    unsigned char *client=(void *)GetModuleHandleA("client.dll");
    if(!client||memcmp(client+0x101e20,"\x8a\x44\x24\x08\x56\x57\x83\xcf\xff\x33\xf6\x84\xc0\x75\x22\x8b",16)||
       memcmp(client+0x104676,"\xf6\x05",2)||
       *(unsigned *)(client+0x104678)!=(unsigned)(uintptr_t)(client+0x4d33d8))return;
    if(!*(unsigned *)(client+0x4d33d0)&&!*(unsigned *)(client+0x4d33d4))
        ((void (__cdecl *)(void *,int))(client+0x101e20))(client+0x4d33d0,1);
    run("import sys\nsys.stderr=open('p5_owned_python_errors.txt','w',0)\nimport p5_probe\np5_probe.start()");
}
__declspec(dllexport) void loaded_vampire(void){
    unsigned char *site;DWORD old,tmp;
    if(server)return;server=(void *)GetModuleHandleA("vampire.dll");if(!server)return;
    site=server+0x16be10;
    if(memcmp(site,"\x83\xec\x20\xa1",4)||*(unsigned *)(site+4)!=(unsigned)(uintptr_t)(server+0x70b228))return;
    memcpy(saved,site,8);stub=VirtualAlloc(NULL,0x1000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!stub)return;
    memcpy(stub,saved,8);stub[8]=0xe9;*(unsigned *)(stub+9)=(unsigned)((uintptr_t)(site+8)-(uintptr_t)(stub+13));
    if(!VirtualProtect(stub,0x1000,PAGE_EXECUTE_READ,&tmp))return;
    if(!VirtualProtect(site,8,PAGE_EXECUTE_READWRITE,&old))return;
    site[0]=0xe9;*(unsigned *)(site+1)=(unsigned)((uintptr_t)frame-(uintptr_t)(site+5));memset(site+5,0x90,3);
    VirtualProtect(site,8,old,&tmp);FlushInstructionCache(GetCurrentProcess(),site,8);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD r,LPVOID p){(void)h;(void)r;(void)p;return TRUE;}
