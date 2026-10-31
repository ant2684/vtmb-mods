#include "native_fixture.h"
static uint8_t *server,*client;static int calls,fail_at,off_server,off_client;
static HMODULE WINAPI modules(LPCSTR n){if(!strcmp(n,"vampire.dll"))return(HMODULE)server;if(!strcmp(n,"client.dll"))return(HMODULE)client;return NULL;}

static DWORD WINAPI executable(HMODULE h,LPSTR buffer,DWORD size){(void)h;(void)size;strcpy(buffer,"C:\\Fixture\\Vampire.exe");return strlen(buffer);}
static DWORD WINAPI new_profile(LPCSTR section,LPCSTR key,LPCSTR fallback,LPSTR buffer,DWORD size,LPCSTR path){
 (void)section;(void)fallback;(void)size;(void)path;buffer[0]=(!strcmp(key,"WarformFrenzy")&&!off_server)||(!strcmp(key,"FilterLoadFix")&&!off_client)?'1':'0';buffer[1]=0;return 1;
}

static BOOL WINAPI protect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old){calls++;return calls==fail_at?FALSE:VirtualProtect(p,n,flags,old);}
static HMODULE open_plugin(const char *path){HMODULE h=LoadLibraryA(path);check(h!=NULL,"exact DLL load");imports(h,"GetModuleHandleA",modules);imports(h,"VirtualProtect",protect);imports(h,"GetPrivateProfileStringA",new_profile);imports(h,"GetModuleFileNameA",executable);calls=0;return h;}
static void invoke(HMODULE h,const char *n){((void(__cdecl *)(void))GetProcAddress(h,n))();}
static void save(const char *folder,const char *name,void *p,size_t n){char path[MAX_PATH];FILE *f;snprintf(path,sizeof(path),"%s/%s",folder,name);f=fopen(path,"wb");check(f!=NULL,"create captured emitted code");check(fwrite(p,1,n,f)==n,"capture bytes");fclose(f);}
int main(int argc,char **argv){HMODULE h;uint32_t sites[]={0x16c558,0x33e9be,0x1f9177,0x3510d7,0x1e56e0,0x1e5b30,0x33ed75};unsigned sizes[]={6,5,6,6,5,7,1};uint8_t old[7][7],old_client[14],*sc,*cc;unsigned i,j;char metadata[512];
 check(argc==5,"plugin/server/client/output arguments");server=map_image(argv[2]);client=map_image(argv[3]);for(i=0;i<7;i++)memcpy(old[i],server+sites[i],sizes[i]);memcpy(old_client,client+0x19da73,14);
 /* OS failures are covered by exact_configuration with strict protection checks. */
 fail_at=0;off_server=off_client=1;h=open_plugin(argv[1]);invoke(h,"loaded_vampire");invoke(h,"loaded_client");check(!calls,"both component switches");FreeLibrary(h);off_server=off_client=0;
 for(i=0;i<7;i++){server[sites[i]]^=1;h=open_plugin(argv[1]);invoke(h,"loaded_vampire");check(!calls,"each occupied/signature hook rejects atomically");FreeLibrary(h);memcpy(server+sites[i],old[i],sizes[i]);}
 client[0x19da73]=0xe9;h=open_plugin(argv[1]);invoke(h,"loaded_client");check(!calls,"client conflicting hook");FreeLibrary(h);memcpy(client+0x19da73,old_client,14);
 h=open_plugin(argv[1]);invoke(h,"loaded_vampire");invoke(h,"loaded_client");check(server[0x33ed75]==0xeb,"gate enabled");sc=destination(server+sites[0]);cc=destination(client+0x19da73);for(i=0;i<6;i++)check(destination(server+sites[i])==sc+i*0x100+(i>=3?0x100:0),"delivered helper offsets");
 save(argv[4],"server-code.bin",sc,2048);save(argv[4],"client-code.bin",cc,69);snprintf(metadata,sizeof(metadata),"{\"server\":%u,\"client\":%u,\"server_code\":%u,\"client_code\":%u}\n",(unsigned)(uintptr_t)server,(unsigned)(uintptr_t)client,(unsigned)(uintptr_t)sc,(unsigned)(uintptr_t)cc);save(argv[4],"emitted.json",metadata,strlen(metadata));
 i=calls;invoke(h,"loaded_vampire");invoke(h,"loaded_client");check(calls==(int)i,"repeated callbacks do not install again");FreeLibrary(h);puts("PASS exact DLL switches/conflicts/signatures/rollback and emitted final-code capture");return 0;
}
