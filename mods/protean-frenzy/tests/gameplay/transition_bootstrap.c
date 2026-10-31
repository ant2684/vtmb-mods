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
static unsigned char *previous_player;
static float previous_time;
static void FC frame(unsigned char *p,void *unused){
    HMODULE py;int (__cdecl *run)(const char *);DWORD old,tmp;(void)unused;
    ((void(TC *)(void *))stub)(p);
    if(!p||!*(unsigned *)(p+0x2e0)||!*(void **)(server+0x70b228))return;
    if(!*(const char **)(p+0x11c)||strcmp(*(const char **)(p+0x11c),"player")||
       *(float *)(*(unsigned char **)(server+0x70b228)+12)<3.f)return;
    py=GetModuleHandleA("vampire_python21.dll");if(!py)return;
    run=(void *)GetProcAddress(py,"PyRun_SimpleString");if(!run)return;
    float current_time=*(float *)(*(unsigned char **)(server+0x70b228)+12);
    if(started){
        int changed=p!=previous_player||current_time+.01f<previous_time;
        previous_player=p;previous_time=current_time;
        if(!changed)return;
        ++started;
        if(started==2){run("__import__('p5_probe').loaded_callback()");return;}
    }else{
        started=1;previous_player=p;previous_time=current_time;
        run("import sys\nsys.stderr=open('p5_owned_python_errors.txt','w',0)\nimport p5_probe\np5_probe.start()");return;
    }
    if(server[0x16be10]!=0xe9||server+0x16be15+*(int *)(server+0x16be11)!=(unsigned char *)frame)return;
    if(!VirtualProtect(server+0x16be10,8,PAGE_EXECUTE_READWRITE,&old))return;
    memcpy(server+0x16be10,saved,8);
    VirtualProtect(server+0x16be10,8,old,&tmp);FlushInstructionCache(GetCurrentProcess(),server+0x16be10,8);
    VirtualFree(stub,0,MEM_RELEASE);stub=NULL;
    run("__import__('p5_probe').mapped_callback()");
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
