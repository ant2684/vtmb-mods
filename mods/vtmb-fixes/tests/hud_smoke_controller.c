/* Owned test controller only; never included in the game payload. Requests
   run before the native command-buffer drain on the engine main thread,
   including while paused. No Windows input or video mode changes. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static unsigned char *engine,*bridge;
static unsigned seen;
static int damage(int kind){
 unsigned char *s=(void *)GetModuleHandleA("vampire.dll"),*table,*player,info[76];
 typedef void *(__attribute__((thiscall)) *Ctor)(void *,void *,void *,float,int,int,int,int);
 typedef int (__attribute__((thiscall)) *Damage)(void *,void *);
 if(!s||memcmp(s+0x1c26d0,"\x8b\x44\x24\x1c\x8b\x54\x24\x10",8)||memcmp(s+0xa1250,"\x83\xec\x4c\x53\x8b\xd9",6))return -1;
 table=*(unsigned char **)(s+0x566458);if(!table)return -2;player=*(unsigned char **)(table+16);
 if(!player||!*(const char **)(player+0x11c)||strcmp(*(const char **)(player+0x11c),"player"))return -3;
 memset(info,0,sizeof(info));((Ctor)(s+0x1c26d0))(info,player,player,30.f,kind,0,0,-1);
 return ((Damage)(s+0xa1250))(player,info);
}
static void poll(void){
 char raw[4096],*code;DWORD n;HANDLE f;unsigned seq;HMODULE py;int (__cdecl *run)(const char *);FILE *reply;int result;
 f=CreateFileA(HUD_REQUEST,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,0,NULL);
 if(f==INVALID_HANDLE_VALUE)return;
 if(!ReadFile(f,raw,sizeof(raw)-1,&n,NULL)){CloseHandle(f);return;}CloseHandle(f);raw[n]=0;
 seq=(unsigned)strtoul(raw,&code,10);if(*code=='\r')++code;
 if(!seq||seq==seen||*code!='\n')return;++code;
 if(!strncmp(code,"VB_CONSOLE\n",11)){
  seen=seq;result=-4;
  if(!memcmp(engine+0x2dcc0,"\x8b\x54\x24\x04\x83\xc9\xff",7)){
   ((void(__cdecl *)(const char *))(engine+0x2dcc0))(code+11);result=0;
  }
 }
 else if(!strncmp(code,"HUD_BURN",8)){seen=seq;result=damage(8);}
 else if(!strncmp(code,"HUD_NORMAL",10)){seen=seq;result=damage(0);}
 else{
  py=GetModuleHandleA("vampire_python21.dll");if(!py)return;
  run=(void *)GetProcAddress(py,"PyRun_SimpleString");if(!run)return;
  seen=seq;result=run(code);
 }
 reply=fopen(HUD_RESPONSE,"a");if(reply){fprintf(reply,"{\"sequence\":%u,\"pid\":%lu,\"result\":%d}\n",seq,(unsigned long)GetCurrentProcessId(),result);fclose(reply);}
}
static void __cdecl execute(void){poll();((void(__cdecl *)(void))bridge)();}
__declspec(dllexport) void loaded_engine(void){
 unsigned char *at;DWORD old,ignored;
 if(engine)return;engine=(void *)GetModuleHandleA("engine.dll");if(!engine)return;
 at=engine+0x2df10;if(memcmp(at,"\x81\xec\x00\x04\x00\x00",6))return;
 bridge=VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!bridge)return;
 memcpy(bridge,at,6);bridge[6]=0xe9;*(int32_t *)(bridge+7)=(int32_t)((at+6)-(bridge+11));
 if(!VirtualProtect(bridge,4096,PAGE_EXECUTE_READ,&ignored))return;
 if(!VirtualProtect(at,6,PAGE_EXECUTE_READWRITE,&old))return;
 at[0]=0xe9;*(int32_t *)(at+1)=(int32_t)((unsigned char *)execute-(at+5));at[5]=0x90;
 FlushInstructionCache(GetCurrentProcess(),at,6);VirtualProtect(at,6,old,&ignored);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID reserved){(void)h;(void)reason;(void)reserved;return TRUE;}
