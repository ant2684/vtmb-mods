#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#if defined(__GNUC__)
#define VTM_THISCALL __attribute__((thiscall))
#define VTM_FASTCALL __attribute__((fastcall))
#define VTM_CDECL __attribute__((cdecl))
#else
#define VTM_THISCALL __thiscall
#define VTM_FASTCALL __fastcall
#define VTM_CDECL __cdecl
#endif

/* Pinned to the 32-bit Steam vampire.dll used by Unofficial Patch 11.5. */
enum {
    RVA_ENTITY_TABLE = 0x566458,
    RVA_WEREWOLF_VTABLE = 0x4cf4d4,
    RVA_FRENZY_SHADOW_VTABLE = 0x4b2184,
    RVA_SYNC_HOOK = 0x16c5be,
    RVA_SYNC_RETURN = 0x16c5c4,
    RVA_RAY_INIT = 0x6dec0,
    RVA_NAV_FILTER_CTOR = 0x2e30d0,
    RVA_NAV_FILTER_VTABLE = 0x49d8c0,
    RVA_SIMPLE_FILTER_VTABLE = 0x482fe4,
    RVA_ENGINE_TRACE_GLOBAL = 0x70b254,
    RVA_ENGINE_GET_LEVEL_NAME = 0x1b800,
    GROUND_ENTITY_HANDLE_OFFSET = 0x384,
    GET_ORIGIN_SLOT = 0x364 / 4
};

typedef struct { float x, y, z; } Vec3;

typedef Vec3 *(VTM_THISCALL *GetVectorFn)(void *);
typedef unsigned char (VTM_THISCALL *ShouldHitEntityFn)(void *, void *, int);
typedef void (VTM_THISCALL *TraceRayFn)(void *, const void *, unsigned int, void *, void *);
typedef void (VTM_THISCALL *SetGroundFn)(void *, void *);
typedef const char *(VTM_CDECL *GetLevelNameFn)(void);




static uint8_t *server_module,*engine_module,*sync_stub;
static uint8_t original_sync[6];
static int installed,trace_abi_verified,trace_hook_depth,trace_hook_ready,ground_hook_ready;
static void *cached_werewolf;
static unsigned int cached_werewolf_index=0xffffffffu;
static uint32_t cached_werewolf_serial;
static void *observed_player,*observed_shadow,*observed_werewolf;
static int observed_player_handle=-1,observed_shadow_handle=-1,observed_werewolf_handle=-1;
static TraceRayFn original_trace_ray;
static SetGroundFn original_wolf_set_ground;
typedef struct {void **vtable;void *pass_entity;int collision_group;void *original_filter;} WolfTraceFilter;


static IMAGE_NT_HEADERS32 *pe_headers(uint8_t *module)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)module;
    IMAGE_NT_HEADERS32 *nt;
    if (!module || dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 || dos->e_lfanew > 0x1000)
        return NULL;
    nt = (IMAGE_NT_HEADERS32 *)(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC)
        return NULL;
    return nt;
}

static int write_memory(void *address, const void *bytes, unsigned int count)
{
    DWORD old_protection, ignored;
    if (!VirtualProtect(address, count, PAGE_EXECUTE_READWRITE, &old_protection)) return 0;
    memcpy(address, bytes, count);
    FlushInstructionCache(GetCurrentProcess(), address, count);
    VirtualProtect(address, count, old_protection, &ignored);
    return 1;
}

static void *resolve_handle(int handle)
{
    uint8_t *table;
    uint32_t index, serial;
    uint8_t *entry;
    if (!server_module || handle == -1) return NULL;
    table = *(uint8_t **)(server_module + RVA_ENTITY_TABLE);
    if (!table) return NULL;
    index = (uint32_t)handle & 0x1fff;
    serial = (uint32_t)handle >> 13;
    entry = table + index * 12 + 4;
    if (*(uint32_t *)(entry + 4) != serial) return NULL;
    return *(void **)entry;
}

static void *active_player_shadow(void *player)
{
    void *entity;
    int handle;
    if (!player || *(int *)((uint8_t *)player + 0x146c) <= 0) return NULL;
    handle = *(int *)((uint8_t *)player + 0x1db0);
    entity = resolve_handle(handle);
    if (!entity || *(void **)entity != server_module + RVA_FRENZY_SHADOW_VTABLE) return NULL;
    return entity;
}

static int entity_handle(void *entity)
{
    uint8_t *table;
    unsigned int i;
    if (!server_module || !entity) return -1;
    table = *(uint8_t **)(server_module + RVA_ENTITY_TABLE);
    if (!table) return -1;
    for (i = 0; i < 8192; ++i) {
        uint8_t *entry = table + i * 12 + 4;
        if (*(void **)entry == entity)
            return (int)(i | (*(uint32_t *)(entry + 4) << 13));
    }
    return -1;
}

static int is_named_werewolf(void *entity)
{
    const char *name;
    if (!entity || *(void **)entity != server_module + RVA_WEREWOLF_VTABLE) return 0;
    /* Python GetName reads the same CBaseEntity field at +0x26c. */
    name = *(const char **)((uint8_t *)entity + 0x26c);
    return name && strcmp(name, "werewolf") == 0;
}

static void *find_werewolf(void)
{
    uint8_t *table;
    unsigned int i;
    uint8_t *entry;
    table = *(uint8_t **)(server_module + RVA_ENTITY_TABLE);
    if (!table) return NULL;
    if (cached_werewolf && cached_werewolf_index < 8192) {
        entry = table + cached_werewolf_index * 12 + 4;
        if (*(void **)entry == cached_werewolf &&
            *(uint32_t *)(entry + 4) == cached_werewolf_serial &&
            is_named_werewolf(cached_werewolf))
            return cached_werewolf;
    }
    cached_werewolf = NULL;
    cached_werewolf_index = 0xffffffffu;
    cached_werewolf_serial = 0;
    for (i = 0; i < 8192; ++i) {
        void *entity;
        entry = table + i * 12 + 4;
        entity = *(void **)entry;
        if (is_named_werewolf(entity)) {
            cached_werewolf = entity;
            cached_werewolf_index = i;
            cached_werewolf_serial = *(uint32_t *)(entry + 4);
            return entity;
        }
    }
    return NULL;
}

static Vec3 *entity_origin(void *entity)
{
    void **vtable = *(void ***)entity;
    return ((GetVectorFn)vtable[GET_ORIGIN_SLOT])(entity);
}


static int target_map_active(void) {
    const char *level;
    if(!engine_module)return 0;
    level=((GetLevelNameFn)(engine_module+RVA_ENGINE_GET_LEVEL_NAME))();
    return level && (_stricmp(level,"sp_observatory_2")==0 ||
        _stricmp(level,"sp_observatory_2.bsp")==0 ||
        _stricmp(level,"maps/sp_observatory_2.bsp")==0 ||
        _stricmp(level,"maps\\sp_observatory_2.bsp")==0);
}
static int observed_scope_live(void) {
    return observed_player && observed_shadow && observed_werewolf && target_map_active() &&
        resolve_handle(observed_player_handle)==observed_player &&
        resolve_handle(observed_shadow_handle)==observed_shadow &&
        resolve_handle(observed_werewolf_handle)==observed_werewolf &&
        active_player_shadow(observed_player)==observed_shadow;
}


static unsigned char VTM_FASTCALL wolf_should_hit_entity(
    WolfTraceFilter *filter, void *unused_edx, void *candidate, int contents_mask)
{
    void **original_methods = *(void ***)filter->original_filter;
    (void)unused_edx;
    if (candidate == observed_player) return 0;
    if (candidate == observed_shadow) return 1;
    return ((ShouldHitEntityFn)original_methods[0])(
        filter->original_filter, candidate, contents_mask);
}


static void VTM_FASTCALL actual_trace_ray(void *engine_trace,void *unused_edx,
    const void *ray,unsigned int mask,void *filter,void *result) {
    void *caller=__builtin_return_address(0),*pass=NULL;
    void *filter_vtable=filter?*(void **)filter:NULL;
    int kind=0,correct=0;
    WolfTraceFilter corrected_filter;void *corrected_methods[2];
    (void)unused_edx;
    if(filter_vtable==server_module+RVA_NAV_FILTER_VTABLE){pass=*(void **)((uint8_t *)filter+0x10);kind=2;}
    else if(filter_vtable==server_module+RVA_SIMPLE_FILTER_VTABLE){pass=*(void **)((uint8_t *)filter+4);kind=1;}
    if(!trace_hook_depth && observed_werewolf && pass==observed_werewolf &&
        caller>=(void *)server_module && caller<(void *)(server_module+0x500000) && observed_scope_live()) {
        Vec3 *sp=entity_origin(observed_shadow),*wp=entity_origin(observed_werewolf);
        float xy=sqrtf((sp->x-wp->x)*(sp->x-wp->x)+(sp->y-wp->y)*(sp->y-wp->y));
        unsigned int site=(unsigned int)((uint8_t *)caller-server_module);
        correct=xy<160.0f && (mask==0x0202400b || mask==0x0200400b) &&
            active_player_shadow(observed_player)==observed_shadow &&
            (site==0x3cbb59 || site==0x3cbc52 || site==0x3cbd33 || site==0x26eb39 ||
             site==0x2a9aef || site==0x26ad67 || site==0x2e3630 || site==0x2e38a7);
    }
    if(correct && filter_vtable && ((void **)filter_vtable)[1]) {
        corrected_methods[0]=(void *)wolf_should_hit_entity;
        corrected_methods[1]=((void **)filter_vtable)[1];
        corrected_filter.vtable=corrected_methods;corrected_filter.pass_entity=pass;
        corrected_filter.collision_group=*(int *)((uint8_t *)filter+(kind==2?0x14:8));
        corrected_filter.original_filter=filter;filter=&corrected_filter;
    }
    ++trace_hook_depth;
    original_trace_ray(engine_trace,ray,mask,filter,result);
    --trace_hook_depth;
}
static void VTM_FASTCALL correct_wolf_set_ground(void *self,void *unused_edx,void *new_ground) {
    void *caller=__builtin_return_address(0);(void)unused_edx;
    if(self==observed_werewolf && new_ground==observed_player && observed_scope_live() &&
        (uint8_t *)caller==server_module+0x26e849) {
        original_wolf_set_ground(self,NULL);return;
    }
    original_wolf_set_ground(self,new_ground);
}
static void reset_runtime_state(void) {
    observed_player=observed_shadow=observed_werewolf=NULL;
    observed_player_handle=observed_shadow_handle=observed_werewolf_handle=-1;
}
static void install_actual_trace_hook(void) {
    void *engine_trace;void **vtable;void *wrapper=(void *)actual_trace_ray;
    if(trace_hook_ready || !trace_abi_verified)return;
    engine_trace=*(void **)(server_module+RVA_ENGINE_TRACE_GLOBAL);
    vtable=engine_trace?*(void ***)engine_trace:NULL;
    if(!vtable || !vtable[4])return;
    original_trace_ray=(TraceRayFn)vtable[4];
    if((void *)original_trace_ray==wrapper)return;
    if(!write_memory(vtable+4,&wrapper,sizeof(wrapper)))return;
    trace_hook_ready=1;
}
static void install_ground_hook(void) {
    void **vtable;void *wrapper=(void *)correct_wolf_set_ground;
    if(ground_hook_ready || !observed_werewolf)return;
    vtable=*(void ***)observed_werewolf;
    if(vtable!=(void **)(server_module+RVA_WEREWOLF_VTABLE) || vtable[208]!=server_module+0x158e8) {
        ground_hook_ready=-1;return;
    }
    original_wolf_set_ground=(SetGroundFn)vtable[208];
    if(!write_memory(vtable+208,&wrapper,sizeof(wrapper)))return;
    ground_hook_ready=1;
}
static void VTM_CDECL frenzy_sync_tick(void *player,void *sync_source) {
    void *shadow,*werewolf;(void)sync_source;
    if(!target_map_active()){reset_runtime_state();return;}
    shadow=active_player_shadow(player);
    if(!shadow){reset_runtime_state();return;}
    werewolf=find_werewolf();
    if(!werewolf){reset_runtime_state();return;}
    if(observed_player!=player || resolve_handle(observed_player_handle)!=player)
        observed_player_handle=entity_handle(player);
    observed_shadow_handle=*(int *)((uint8_t *)player+0x1db0);
    observed_werewolf_handle=(int)(cached_werewolf_index|(cached_werewolf_serial<<13));
    if(observed_player_handle==-1 || resolve_handle(observed_shadow_handle)!=shadow ||
        resolve_handle(observed_werewolf_handle)!=werewolf){reset_runtime_state();return;}
    observed_player=player;observed_shadow=shadow;observed_werewolf=werewolf;
    install_actual_trace_hook();install_ground_hook();
}


static int build_sync_stub(void)
{
    uint8_t code[32];
    uint8_t patch[6];
    unsigned int at = 0;
    int32_t displacement;
    sync_stub = (uint8_t *)VirtualAlloc(NULL, 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    if (!sync_stub) return 0;
    code[at++] = 0x9c; code[at++] = 0x60;       /* pushfd, pushad */
    code[at++] = 0x53; code[at++] = 0x55;       /* controller, player */
    code[at++] = 0xb8;                          /* mov eax, helper */
    *(uint32_t *)(code + at) = (uint32_t)(uintptr_t)frenzy_sync_tick; at += 4;
    code[at++] = 0xff; code[at++] = 0xd0;       /* call eax */
    code[at++] = 0x83; code[at++] = 0xc4; code[at++] = 0x08;
    code[at++] = 0x61; code[at++] = 0x9d;       /* popad, popfd */
    memcpy(code + at, original_sync, 6); at += 6;
    code[at++] = 0xe9;
    displacement = (int32_t)((server_module + RVA_SYNC_RETURN) - (sync_stub + at + 4));
    memcpy(code + at, &displacement, 4); at += 4;
    memcpy(sync_stub, code, at);
    FlushInstructionCache(GetCurrentProcess(), sync_stub, at);
    patch[0] = 0xe9;
    displacement = (int32_t)(sync_stub - (server_module + RVA_SYNC_HOOK + 5));
    memcpy(patch + 1, &displacement, 4);
    patch[5] = 0x90;
    if (!write_memory(server_module + RVA_SYNC_HOOK, patch, sizeof(patch))) {
        VirtualFree(sync_stub, 0, MEM_RELEASE);
        sync_stub = NULL;
        return 0;
    }
    return 1;
}

__declspec(dllexport) void loaded_vampire(void)
{
    static const uint8_t expected_sync[] = {0x8b,0x83,0xf0,0x06,0x00,0x00};
    static const uint8_t expected_ray_init[] = {0x8b,0x44,0x24,0x08,0x56,0x57};
    static const uint8_t expected_nav_ctor[] = {0x53,0x8b,0x5c,0x24,0x08,0x56};
    IMAGE_NT_HEADERS32 *nt;
    IMAGE_NT_HEADERS32 *engine_nt;
    if (installed) return;
    server_module = (uint8_t *)GetModuleHandleA("vampire.dll");
    nt = pe_headers(server_module);
    if (!nt || nt->FileHeader.TimeDateStamp != 0x41afafae ||
        nt->OptionalHeader.SizeOfImage != 0x0ab9000) {
        
        return;
    }
    engine_module = (uint8_t *)GetModuleHandleA("engine.dll");
    engine_nt = pe_headers(engine_module);
    if (!engine_nt || engine_nt->FileHeader.TimeDateStamp != 0x41afaf48 ||
        engine_nt->OptionalHeader.SizeOfImage != 0x13bb000 ||
        engine_module[RVA_ENGINE_GET_LEVEL_NAME] != 0x8b ||
        engine_module[RVA_ENGINE_GET_LEVEL_NAME + 1] != 0x15 ||
        engine_module[RVA_ENGINE_GET_LEVEL_NAME + 6] != 0x56) {
        
        return;
    }
    if (memcmp(server_module + RVA_SYNC_HOOK, expected_sync, sizeof(expected_sync)) != 0) {
        
        return;
    }
    trace_abi_verified =
        memcmp(server_module + RVA_RAY_INIT, expected_ray_init, sizeof(expected_ray_init)) == 0 &&
        memcmp(server_module + RVA_NAV_FILTER_CTOR, expected_nav_ctor, sizeof(expected_nav_ctor)) == 0;
    if (!trace_abi_verified) return;
    memcpy(original_sync, server_module + RVA_SYNC_HOOK, sizeof(original_sync));
    if (!build_sync_stub()) {
        
        return;
    }
    installed = 1;
    
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)instance; (void)reason; (void)reserved;
    return TRUE;
}
