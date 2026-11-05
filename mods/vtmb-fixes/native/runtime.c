#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string.h>

static int configured, options[8];
static const char *keys[]={"ConsolePauseFix","SubtitlePauseRadioFix","HistoryStatResetFix","ContainerStackFix","ContainerInputGuard","FlamethrowerDamageNumbers","CastingAnimationCleanup","HUDIndicatorsFix"};
static void configure(void){
 char path[MAX_PATH],value[24],*slash;DWORD n;unsigned i;
 if(configured)return;configured=1;
 n=GetModuleFileNameA(NULL,path,MAX_PATH);if(!n||n>=MAX_PATH)return;
 slash=strrchr(path,'\\');if(!slash||(size_t)(slash-path)+sizeof("\\Bin\\loader\\ant2684-fixes-adjustments.ini")>MAX_PATH)return;
 strcpy(slash,"\\Bin\\loader\\ant2684-fixes-adjustments.ini");
 for(i=0;i<8;i++){GetPrivateProfileStringA("Fixes",keys[i],"1",value,sizeof(value),path);options[i]=!strcmp(value,"1");}
}
#define DECL(m,n) void vf_##m##_##n(void)
DECL(console,loaded_gameui);
DECL(subtitle,loaded_engine);DECL(subtitle,loaded_vampire);
DECL(history,loaded_client);DECL(history,loaded_vampire);
DECL(container,loaded_client);DECL(container,loaded_server);
DECL(input,loaded_client);DECL(flame,loaded_vampire);
DECL(cast,loaded_vampire);
DECL(hud_side,loaded_client);DECL(hud_victim,loaded_client);
BOOL WINAPI vf_container_DllMain(HINSTANCE,DWORD,LPVOID);
BOOL WINAPI vf_input_DllMain(HINSTANCE,DWORD,LPVOID);
BOOL WINAPI vf_flame_DllMain(HINSTANCE,DWORD,LPVOID);
BOOL WINAPI vf_cast_DllMain(HINSTANCE,DWORD,LPVOID);

__declspec(dllexport) void loaded_engine(void){configure();if(options[1])vf_subtitle_loaded_engine();}
__declspec(dllexport) void loaded_gameui(void){configure();if(options[0])vf_console_loaded_gameui();}
__declspec(dllexport) void loaded_client(void){
 configure();if(options[2])vf_history_loaded_client();if(options[3])vf_container_loaded_client();
 if(options[4])vf_input_loaded_client();
 if(options[7]){vf_hud_side_loaded_client();vf_hud_victim_loaded_client();}
}
__declspec(dllexport) void loaded_vampire(void){
 configure();if(options[1])vf_subtitle_loaded_vampire();if(options[2])vf_history_loaded_vampire();
 if(options[3])vf_container_loaded_server();if(options[5])vf_flame_loaded_vampire();
 if(options[6])vf_cast_loaded_vampire();
}
__declspec(dllexport) void loaded_server(void){loaded_vampire();}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID reserved){
 if(reason==DLL_PROCESS_DETACH&&!reserved){
  if(options[4])vf_input_DllMain(h,reason,reserved);
  if(options[6])vf_cast_DllMain(h,reason,reserved);
  if(options[5])vf_flame_DllMain(h,reason,reserved);
  if(options[3])vf_container_DllMain(h,reason,reserved);
 }
 return TRUE;
}
