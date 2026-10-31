/* Compile the timeline with the actual embedded Python 2.1, without a game. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){
    FILE *f;long n;char *text,folder[MAX_PATH],*filename;HMODULE py;void *result;
    void (__cdecl *init)(void),(__cdecl *error)(void),(__cdecl *finish)(void);
    void *(__cdecl *compile)(const char *,const char *,int);
    if(argc!=3)return 2;
    if(!GetFullPathNameA(argv[1],MAX_PATH,folder,&filename)||!filename)return 8;*filename=0;SetDllDirectoryA(folder);
    py=LoadLibraryA(argv[1]);if(!py){fprintf(stderr,"LoadLibrary: %lu\n",GetLastError());return 3;}
    init=(void *)GetProcAddress(py,"Py_Initialize");compile=(void *)GetProcAddress(py,"Py_CompileString");
    error=(void *)GetProcAddress(py,"PyErr_Print");finish=(void *)GetProcAddress(py,"Py_Finalize");
    if(!init||!compile||!error||!finish)return 4;
    f=fopen(argv[2],"rb");if(!f)return 5;fseek(f,0,SEEK_END);n=ftell(f);rewind(f);
    text=calloc((size_t)n+1,1);if(!text)return 6;
    if(fread(text,1,(size_t)n,f)!=(size_t)n)return 7;fclose(f);
    /* Py_CompileString bypasses the importer's universal-newline file reader. */
    long write=0;for(long read=0;read<n;++read){if(text[read]=='\r'&&read+1<n&&text[read+1]=='\n')continue;text[write++]=text[read];}text[write]=0;
    init();result=compile(text,argv[2],257);if(!result)error();finish();free(text);
    if(!result)return 1;puts("PASS: actual Python 2.1 compiled game timeline; no game launched");return 0;
}
