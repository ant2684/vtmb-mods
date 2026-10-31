#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "runtime.h"

int pfi_options[PFI_COUNT];
int pfi_inventory_ready;
static int configured;
static const char *const keys[PFI_COUNT]={
 "WarformFrenzy","FilterLoadFix","InventoryFixes","ProteanTransformFixes",
 "ClawsComboBuffer","ClawsStealthPosition","MeleeFrenzy","GriffithFrenzyCollision"
};

void pfi_configure(void){
 char path[MAX_PATH],value[24],*slash;unsigned j;DWORD length;
 if(configured)return;
 configured=1;
 length=GetModuleFileNameA(NULL,path,MAX_PATH);
 if(!length||length>=MAX_PATH)return;
 slash=strrchr(path,'\\');
 if(!slash||(size_t)(slash-path)+sizeof("\\Bin\\loader\\protean-frenzy-improved.ini")>MAX_PATH)return;
 strcpy(slash,"\\Bin\\loader\\protean-frenzy-improved.ini");
 for(j=0;j<PFI_COUNT;++j){
  GetPrivateProfileStringA("Fixes",keys[j],"1",value,sizeof(value),path);
  /* Invalid explicit values disable the affected function. */
  pfi_options[j]=!strcmp(value,"1");
 }
 if(!pfi_options[PFI_INVENTORY]){
  pfi_options[PFI_TRANSFORM]=0;pfi_options[PFI_MELEE]=0;
 }
}

/* Readiness follows the atomically installed native lifecycle hooks. */
int pfi_transform_active(void){return pfi_options[PFI_TRANSFORM]&&pfi_inventory_ready;}

__declspec(dllexport) void loaded_vampire(void){
 static int attempted;if(attempted)return;attempted=1;pfi_configure();
 if(pfi_options[PFI_WARFORM])pfi_core_server();
 if(pfi_options[PFI_INVENTORY])pfi_lifecycle_server();
 /* Matching models contain both pools even with all optional fixes off. */
 pfi_claws_frenzy_server();
 if(pfi_options[PFI_MELEE]&&pfi_inventory_ready)pfi_melee_server();
 if(pfi_options[PFI_BUFFER])pfi_flow_server();
 if(pfi_options[PFI_STEALTH])pfi_stealth_server();
 if(pfi_options[PFI_GRIFFITH])pfi_griffith_server();
}
__declspec(dllexport) void loaded_client(void){
 static int attempted;if(attempted)return;attempted=1;pfi_configure();
 if(pfi_options[PFI_FILTER])pfi_core_client();
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID reserved){(void)h;(void)reason;(void)reserved;return TRUE;}
