#include "native_fixture.h"
static uint8_t *server,*client;static int calls,fail_at,off_server,off_client;
static HMODULE WINAPI modules(LPCSTR n){if(!strcmp(n,"vampire.dll"))return(HMODULE)server;if(!strcmp(n,"client.dll"))return(HMODULE)client;return NULL;}
static UINT WINAPI profile(LPCSTR section,LPCSTR key,INT fallback,LPCSTR file){(void)section;(void)fallback;(void)file;return strcmp(key,"Warform Frenzy")? !off_client:!off_server;}
static BOOL WINAPI protect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old){calls++;return calls==fail_at?FALSE:VirtualProtect(p,n,flags,old);}
static HMODULE open_plugin(const char *path){HMODULE h=LoadLibraryA(path);check(h!=NULL,"exact DLL load");imports(h,"GetModuleHandleA",modules);imports(h,"VirtualProtect",protect);imports(h,"GetPrivateProfileIntA",profile);calls=0;return h;}
static void invoke(HMODULE h,const char *n){((void(__cdecl *)(void))GetProcAddress(h,n))();}
static void save(const char *folder,const char *name,void *p,size_t n){char path[MAX_PATH];FILE *f;snprintf(path,sizeof(path),"%s/%s",folder,name);f=fopen(path,"wb");check(f!=NULL,"create captured emitted code");check(fwrite(p,1,n,f)==n,"capture bytes");fclose(f);}
int main(int argc,char **argv){HMODULE h;uint32_t sites[]={0x16c558,0x33e9be,0x1f9177,0x3510d7,0x1e56e0,0x1e5b30,0x33ed75};unsigned sizes[]={6,5,6,6,5,7,1};uint8_t old[7][7],old_client[14],*sc,*cc;unsigned i,j;char metadata[512];
 check(argc==5,"plugin/server/client/output arguments");server=map_image(argv[2]);client=map_image(argv[3]);for(i=0;i<7;i++)memcpy(old[i],server+sites[i],sizes[i]);memcpy(old_client,client+0x19da73,14);
 for(i=1;i<=15;i++){fail_at=(int)i;h=open_plugin(argv[1]);invoke(h,"loaded_vampire");if(i>=3&&(i&1)){check(server[0x33ed75]==0xeb,"restore-protection failure does not discard valid install");}else for(j=0;j<7;j++)check(!memcmp(old[j],server+sites[j],sizes[j]),"server failure rolls back bytes");FreeLibrary(h);for(j=0;j<7;j++)memcpy(server+sites[j],old[j],sizes[j]);}
 for(i=1;i<=3;i++){fail_at=(int)i;h=open_plugin(argv[1]);invoke(h,"loaded_client");if(i!=3)check(!memcmp(old_client,client+0x19da73,14),"client pre-write failures unchanged");FreeLibrary(h);memcpy(client+0x19da73,old_client,14);}
 fail_at=0;off_server=off_client=1;h=open_plugin(argv[1]);invoke(h,"loaded_vampire");invoke(h,"loaded_client");check(!calls,"both component switches");FreeLibrary(h);off_server=off_client=0;
 for(i=0;i<7;i++){server[sites[i]]^=1;h=open_plugin(argv[1]);invoke(h,"loaded_vampire");check(!calls,"each occupied/signature hook rejects atomically");FreeLibrary(h);memcpy(server+sites[i],old[i],sizes[i]);}
 client[0x19da73]=0xe9;h=open_plugin(argv[1]);invoke(h,"loaded_client");check(!calls,"client conflicting hook");FreeLibrary(h);memcpy(client+0x19da73,old_client,14);
 h=open_plugin(argv[1]);invoke(h,"loaded_vampire");invoke(h,"loaded_client");check(server[0x33ed75]==0xeb,"gate enabled");sc=destination(server+sites[0]);cc=destination(client+0x19da73);for(i=0;i<6;i++)check(destination(server+sites[i])==sc+i*0x100+(i>=3?0x100:0),"delivered helper offsets");
 save(argv[4],"server-code.bin",sc,2048);save(argv[4],"client-code.bin",cc,69);snprintf(metadata,sizeof(metadata),"{\"server\":%u,\"client\":%u,\"server_code\":%u,\"client_code\":%u}\n",(unsigned)(uintptr_t)server,(unsigned)(uintptr_t)client,(unsigned)(uintptr_t)sc,(unsigned)(uintptr_t)cc);save(argv[4],"emitted.json",metadata,strlen(metadata));
 i=calls;invoke(h,"loaded_vampire");invoke(h,"loaded_client");check(calls==(int)i,"repeated callbacks do not install again");FreeLibrary(h);puts("PASS exact DLL switches/conflicts/signatures/rollback and emitted final-code capture");return 0;
}
