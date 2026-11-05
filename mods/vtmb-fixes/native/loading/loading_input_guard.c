#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#define CC __attribute__((cdecl))
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
typedef unsigned char B;
typedef uint32_t U;
typedef struct { U version,installed,error; } Status;
__declspec(dllexport) Status loading_input_status={1,0,0};
static B *engine,*client;
static DWORD game_thread,end_tick;
static int active,ended;
static B blocked[256];
typedef struct { int valid; DWORD time; UINT message; WPARAM key; } Origin;
static Origin origin;
static LRESULT (WINAPI *native_dispatch)(const MSG *);
static void (CC *native_key)(int,int);
static void (CC *native_begin)(int);
static void (CC *native_end)(void);
static void (CC *native_down)(void);
static U (TC *native_bits)(void *,int);

static U rd(const B *p,U offset){return *(const U *)(p+offset);}
static int loading(void){
    U host,pending;
    if(active||rd(engine,0xb42318)||engine[0xb42314])return 1;
    host=rd(engine,0xd5e0b0);pending=rd(engine,0xd5e0b4);
    return (host>=1&&host<=3)||(pending>=1&&pending<=3);
}
static void clear_attack(void){memset(client+0x4d2f3c,0,12);}
static int attack_key(int key){
    const char *s;
    if((U)key>=256)return 0;
    s=*(const char **)(engine+0xd607c8+(U)key*4);
    if(!s)return 0;
    while(*s==' '||*s=='\t')s++;
    return !_strnicmp(s,"+attack",7)&&(!s[7]||s[7]==' '||s[7]=='\t'||s[7]==';');
}
static int vk_for(int key){
    if(key>='a'&&key<='z')return key-'a'+'A';
    if((key>='0'&&key<='9')||key==VK_RETURN||key==VK_TAB||key==VK_SPACE||key==VK_ESCAPE)return key;
    switch(key){case 241:return VK_LBUTTON;case 242:return VK_RBUTTON;case 243:return VK_MBUTTON;case 244:return VK_XBUTTON1;case 245:return VK_XBUTTON2;default:return 0;}
}
static int physically_down(int key){int vk=vk_for(key);return vk?!!(GetAsyncKeyState(vk)&0x8000):-1;}
static int real_release(int key){
    if(!origin.valid||GetCurrentThreadId()!=game_thread)return 0;
    if((origin.message==WM_KEYUP||origin.message==WM_SYSKEYUP)&&vk_for(key)==(int)origin.key)return 1;
    return (key==241&&origin.message==WM_LBUTTONUP)||(key==242&&origin.message==WM_RBUTTONUP)||(key==243&&origin.message==WM_MBUTTONUP)||
        (key==244&&origin.message==WM_XBUTTONUP&&HIWORD(origin.key)==XBUTTON1)||(key==245&&origin.message==WM_XBUTTONUP&&HIWORD(origin.key)==XBUTTON2);
}
static void snapshot_held(int finish){
    int key;
    for(key=0;key<256;key++)if(attack_key(key)){
        int physical=physically_down(key);
        if(physical>=0)blocked[key]=(B)physical;
        else if(!finish&&rd(engine,0xd5ff50+(U)key*4))blocked[key]=1;
    }
}
static LRESULT WINAPI dispatch_message(const MSG *msg){
    Origin previous;LRESULT result;
    if(GetCurrentThreadId()!=game_thread)return native_dispatch(msg);
    previous=origin;origin.valid=(msg->message>=WM_MOUSEFIRST&&msg->message<=WM_MOUSELAST)||(msg->message>=WM_KEYFIRST&&msg->message<=WM_KEYLAST)||msg->message==WM_INPUT;
    origin.time=msg->time;origin.message=msg->message;origin.key=msg->wParam;
    /* UI may consume release before Key_Event. It must still re-arm the key. */
    if(origin.valid)for(int key=0;key<256;key++)if(blocked[key]&&real_release(key))blocked[key]=0;
    result=native_dispatch(msg);origin=previous;return result;
}
static void CC key_event(int key,int down){
    if((U)key<256){
        int bound=attack_key(key);
        if(!down){
            if(real_release(key)||physically_down(key)==0)blocked[key]=0;
        }else if(bound){
            int stale=ended&&origin.valid&&GetCurrentThreadId()==game_thread&&(int32_t)(origin.time-end_tick)<=0;
            if(loading()||stale){blocked[key]=1;return;}
            if(blocked[key])return;
        }
    }
    native_key(key,down);
}
static void CC begin_load(int force){
    game_thread=GetCurrentThreadId();active=1;snapshot_held(0);clear_attack();
    native_begin(force);
    if(!rd(engine,0xb42318)&&!engine[0xb42314]&&rd(engine,0xd5e0b0)==4&&rd(engine,0xd5e0b4)==4)active=0;
}
static void CC end_load(void){
    int was_loading=active||rd(engine,0xb42318)||engine[0xb42314];
    if(was_loading){active=1;clear_attack();}
    native_end();
    if(was_loading){clear_attack();snapshot_held(1);end_tick=GetTickCount();ended=1;active=0;}
}
static void CC attack_down(void){if(loading()){clear_attack();return;}native_down();}
static U FC get_bits(void *self,void *unused,int reset){
    U bits;int busy=loading();(void)unused;
    if(busy)clear_attack();bits=native_bits(self,reset);
    if(busy){clear_attack();bits&=~0x800001u;}
    return bits;
}

typedef struct { B *module;U preferred,rva,length,call_offset;const B *signature,*relocations;void *replacement;void **original;B before[24];B *stub;void *forward;DWORD protection; } Hook;
static void jump(B *at,const void *to){at[0]=0xe9;*(U *)(at+1)=(U)((uintptr_t)to-(uintptr_t)(at+5));}
static int expected_bytes(Hook *h,B *expected){
    U delta=(U)((uintptr_t)h->module-h->preferred);
    memcpy(expected,h->signature,h->length);
    for(const B *offset=h->relocations;*offset!=255;offset++){
        U address;
        memcpy(&address,expected+*offset,sizeof(address));
        address+=delta;
        memcpy(expected+*offset,&address,sizeof(address));
    }
    return !memcmp(h->module+h->rva,expected,h->length);
}
#include "loading_guard_signatures.inc"
static int identity(B *module,U timestamp,U size){
    IMAGE_DOS_HEADER *dos=(void *)module;IMAGE_NT_HEADERS32 *nt;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE)return 0;nt=(void *)(module+dos->e_lfanew);
    return nt->Signature==IMAGE_NT_SIGNATURE&&nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&nt->FileHeader.TimeDateStamp==timestamp&&nt->OptionalHeader.SizeOfImage==size;
}
#include "dialogue_mouse_compat.h"
/* Preserve only the reviewed dialogue-mouse handler, never adopt an arbitrary
   E9. Its own native trampoline must still restore the supported six bytes. */
static void *compatible_attack(Hook *h,const B *original){
    B *peer=(B *)GetModuleHandleA("vtmb-dialogue-mouse.vtm"),*site=h->module+h->rva,*target,*trampoline;
    B expected[sizeof(dialogue_mouse_attack_signature)];Hook known={0};MEMORY_BASIC_INFORMATION memory;
    if(!peer||!identity(peer,0x6ae07b5bu,0x1d000u)||site[0]!=0xe9||site[5]!=original[5])return NULL;
    target=site+5+*(int32_t *)(site+1);
    if(target!=peer+0x2320||*(B **)(peer+0x18b20)!=client)return NULL;
    known.module=peer;known.preferred=0x10000000u;known.rva=0x2320;
    known.length=sizeof(dialogue_mouse_attack_signature);known.signature=dialogue_mouse_attack_signature;
    known.relocations=dialogue_mouse_attack_relocations;
    if(!expected_bytes(&known,expected))return NULL;
    trampoline=*(B **)(peer+0x18b44);
    if(!trampoline||!VirtualQuery(trampoline,&memory,sizeof(memory))||memory.State!=MEM_COMMIT||
       (memory.Protect&(PAGE_GUARD|PAGE_NOACCESS))||!(memory.Protect&0xf0)||
       (uintptr_t)trampoline+11>(uintptr_t)memory.BaseAddress+memory.RegionSize)return NULL;
    if(memcmp(trampoline,original,6)||trampoline[6]!=0xe9||trampoline+11+*(int32_t *)(trampoline+7)!=site+6)return NULL;
    return target;
}
static int guard_enabled(void){
    static int enabled=-1;
    static const char suffix[]="\\Bin\\loader\\vtmb-loading-input-guard.ini";
    char path[MAX_PATH],value[24],*slash;
    DWORD length;
    if(enabled>=0)return enabled;
    enabled=0;
    length=GetModuleFileNameA(NULL,path,MAX_PATH);
    if(!length||length>=MAX_PATH)return enabled;
    slash=strrchr(path,'\\');
    if(!slash||(size_t)(slash-path)+sizeof(suffix)>MAX_PATH)return enabled;
    strcpy(slash,suffix);
    GetPrivateProfileStringA("Fixes","LoadingInputGuard","1",value,sizeof(value),path);
    enabled=!strcmp(value,"1");
    return enabled;
}

static void initialize(void){
    Hook hooks[5];B expected[24];U i,done=0;DWORD old,ignored;void **slot;void *dispatch;
    if(loading_input_status.installed||loading_input_status.error||!guard_enabled())return;
    engine=(B *)GetModuleHandleA("engine.dll");client=(B *)GetModuleHandleA("client.dll");
    if(!engine||!client)return;
    if(!identity(engine,ENGINE_TIMESTAMP,ENGINE_SIZE)||!identity(client,CLIENT_TIMESTAMP,CLIENT_SIZE)){loading_input_status.error=1;return;}
    setup_hooks(hooks);slot=(void **)(engine+DISPATCH_IAT);
    dispatch=(void *)GetProcAddress(GetModuleHandleA("user32.dll"),"DispatchMessageA");
    if(!dispatch||*slot!=dispatch){loading_input_status.error=2;return;}
    for(i=0;i<5;i++){
        Hook *h=hooks+i;B *site=h->module+h->rva;
        if(!expected_bytes(h,expected)){
            if(i!=3||!(h->forward=compatible_attack(h,expected))){loading_input_status.error=3;goto fail;}
        }
        memcpy(h->before,site,h->length);if(h->forward)continue;h->stub=VirtualAlloc(NULL,64,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        if(!h->stub){loading_input_status.error=4;goto fail;}
        memcpy(h->stub,site,h->length);
        if(h->call_offset!=0xffffffffu){U at=h->call_offset;B *target=site+at+5+*(int32_t *)(site+at+1);*(int32_t *)(h->stub+at+1)=(int32_t)(target-(h->stub+at+5));}
        jump(h->stub+h->length,site+h->length);
        if(!VirtualProtect(h->stub,64,PAGE_EXECUTE_READ,&ignored)){loading_input_status.error=4;goto fail;}
    }
    native_dispatch=(void *)dispatch;game_thread=GetCurrentThreadId();
    for(i=0;i<5;i++){
        Hook *h=hooks+i;B *site=h->module+h->rva;
        if(memcmp(site,h->before,h->length)||!VirtualProtect(site,h->length,PAGE_EXECUTE_READWRITE,&old)){loading_input_status.error=5;goto fail;}
        h->protection=old;*h->original=h->forward?h->forward:h->stub;jump(site,h->replacement);memset(site+5,0x90,h->length-5);done++;
        if(!VirtualProtect(site,h->length,old,&ignored)){loading_input_status.error=5;goto fail;}
        FlushInstructionCache(GetCurrentProcess(),site,h->length);
    }
    if(*slot!=dispatch||!VirtualProtect(slot,4,PAGE_READWRITE,&old)){loading_input_status.error=6;goto fail;}
    *slot=(void *)dispatch_message;
    if(!VirtualProtect(slot,4,old,&ignored)){
        *slot=dispatch;
        if(!VirtualProtect(slot,4,old,&ignored)){loading_input_status.error=7;return;}
        loading_input_status.error=6;goto fail;
    }
    loading_input_status.installed=1;return;
fail:
    while(done){Hook *h=hooks+--done;B *site=h->module+h->rva;
        if(site[0]==0xe9&&site+5+*(int32_t *)(site+1)==(B *)h->replacement&&VirtualProtect(site,h->length,PAGE_EXECUTE_READWRITE,&old)){
            memcpy(site,h->before,h->length);
            if(!VirtualProtect(site,h->length,h->protection,&ignored)){loading_input_status.error=7;return;}
            FlushInstructionCache(GetCurrentProcess(),site,h->length);
        }else{loading_input_status.error=7;return;}
        *h->original=NULL;
    }
    for(i=0;i<5;i++)if(hooks[i].stub)VirtualFree(hooks[i].stub,0,MEM_RELEASE);
}
__declspec(dllexport) void loaded_engine(void){initialize();}
__declspec(dllexport) void loaded_client(void){initialize();}
__declspec(dllexport) void loaded_gameui(void){initialize();}
__declspec(dllexport) void loaded_vampire(void){initialize();}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID reserved){(void)h;(void)reason;(void)reserved;return TRUE;}
