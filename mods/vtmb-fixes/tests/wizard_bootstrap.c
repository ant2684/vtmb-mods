/* Owned test setup only: select the original native manual-creation action.
   No stat writes, no replacement renderer, no production delivery changes. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define TC __attribute__((thiscall))
typedef unsigned char B;
static B *client;static HHOOK hook;static UINT_PTR timer;static int selected;
static DWORD last_log;
static void record(const char *event,int index,int result){
 FILE *f=fopen(WIZARD_TEST_LOG,"a");if(!f)return;
 fprintf(f,"{\"event\":\"%s\",\"active\":%u,\"visible\":%u,\"index\":%d,\"result\":%d}\n",event,client?client[0x5fb201]:0,client?client[0x5fb1fe]:0,index,result);fclose(f);
}
static LRESULT CALLBACK observe(int code,WPARAM w,LPARAM l){
 HHOOK own=hook;
 if(code>=0&&client&&!selected){
  if(GetTickCount()-last_log>1000){record("waiting",-1,0);last_log=GetTickCount();}
  if(client[0x5fb201]&&client[0x5fb1fe]){
   void *ui=((void *(TC *)(void *,const char *))(client+0xf0ed0))(client+0x4cfe38,"VCharWizardUI");
   if(ui){
    selected=1;
    int index=((int(TC *)(void *,int))(client+0x175f40))(ui,1);
    int result=((int(TC *)(void *,int))(client+0x175f00))(ui,index);
    record("manual_action",index,result);
    if(timer){KillTimer(NULL,timer);timer=0;}
    if(hook){UnhookWindowsHookEx(hook);hook=NULL;}
   }
  }
 }
 return CallNextHookEx(own,code,w,l);
}
__declspec(dllexport) void loaded_client(void){
 IMAGE_NT_HEADERS32 *nt;HMODULE self;B expected[]={0xa0,0,0,0,0,0x84,0xc0};
 if(client)return;client=(B *)GetModuleHandleA("client.dll");if(!client)return;
 nt=(void *)(client+((IMAGE_DOS_HEADER *)client)->e_lfanew);
 *(uint32_t *)(expected+1)=(uint32_t)(uintptr_t)(client+0x5fb1fe);
 if(nt->FileHeader.TimeDateStamp!=0x41afaf63||nt->OptionalHeader.SizeOfImage!=0x6e9000||
    memcmp(client+0x175f00,expected,sizeof(expected))||
    memcmp(client+0x175f40,"\x53\x56\x8b\xf1\x57",5)||
    memcmp(client+0xf0ed0,"\x53\x56\x8b\x5c\x24\x0c\x57\x8b\xf9",9)){record("unsupported",-1,0);return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCSTR)observe,&self))return;
 hook=SetWindowsHookExA(WH_GETMESSAGE,observe,self,GetCurrentThreadId());
 timer=SetTimer(NULL,0,50,NULL);record(hook&&timer?"installed":"setup_failed",-1,0);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID reserved){
 (void)h;if(reason==DLL_PROCESS_DETACH&&!reserved){if(timer)KillTimer(NULL,timer);if(hook)UnhookWindowsHookEx(hook);}return TRUE;
}
