#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

/* A separate x86 process exercises Windows PE loading and DLL startup. It
   never loads the game or executes a callback against a fake game module. */
int main(int argc, char **argv) {
    HMODULE module;
    void *blocked;
    if(argc!=3)return 2;
    blocked=VirtualAlloc((void *)0x10000000,0x100000,MEM_RESERVE,PAGE_NOACCESS);
    if(!blocked){fprintf(stderr,"Cannot occupy preferred image base: %lu\n",GetLastError());return 1;}
    module=LoadLibraryA(argv[1]);
    if(!module){fprintf(stderr,"LoadLibrary failed: %lu\n",GetLastError());return 1;}
    if(!GetProcAddress(module,argv[2])){fprintf(stderr,"Export missing: %lu\n",GetLastError());FreeLibrary(module);return 1;}
    if(!FreeLibrary(module)){fprintf(stderr,"FreeLibrary failed: %lu\n",GetLastError());return 1;}
    VirtualFree(blocked,0,MEM_RELEASE);
    puts("PASS native x86 Windows clean-PE relocated load, export and unload");return 0;
}
