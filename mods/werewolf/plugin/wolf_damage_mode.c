/* UP 11.5: enable the stock damage path only during a live Griffith wolf hit. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>

#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
#define WOLF_CDECL __attribute__((cdecl))
#define WOLF_VTABLE_RVA 0x4cf4d4u
#define DAMAGE_SLOT 0x238u
#define DAMAGE_THUNK_RVA 0x0b271u
#define TRACE_SLOT 0x234u
#define TRACE_THUNK_RVA 0x4e62u
#define NPC_TRACE_THUNK_RVA 0x15b13u
#define ENTITY_TABLE_RVA 0x566458u
#define LEVEL_NAME_RVA 0x1b800u

typedef int (TC *DamageFn)(void *, void *);
typedef void (TC *TraceFn)(void *, void *, const void *, void *);
typedef const char *(WOLF_CDECL *LevelNameFn)(void);
static uint8_t *server_module, *engine_module;
static DamageFn original_damage;
static TraceFn original_trace, native_trace;
static LevelNameFn level_name;
static int installed;
#ifdef WOLF_DIAGNOSTIC
__declspec(dllexport) volatile uint32_t gp_wolf_diagnostics[12];
#endif

static int target_map(const char *name)
{
    return name && (_stricmp(name, "sp_observatory_2") == 0 ||
        _stricmp(name, "sp_observatory_2.bsp") == 0 ||
        _stricmp(name, "maps/sp_observatory_2.bsp") == 0 ||
        _stricmp(name, "maps\\sp_observatory_2.bsp") == 0);
}

static int find_handle(void *entity, uint32_t *handle)
{
    uint8_t *table = *(uint8_t **)(server_module + ENTITY_TABLE_RVA);
    unsigned int i;
    if (!table) return 0;
    for (i = 0; i < 8192; ++i) {
        uint8_t *entry = table + i * 12 + 4;
        if (*(void **)entry == entity) {
            *handle = i | (*(uint32_t *)(entry + 4) << 13);
            return 1;
        }
    }
    return 0;
}

static int same_entity(void *entity, uint32_t handle)
{
    uint8_t *table = *(uint8_t **)(server_module + ENTITY_TABLE_RVA);
    uint8_t *entry;
    if (!table) return 0;
    entry = table + (handle & 0x1fff) * 12 + 4;
    return *(void **)entry == entity &&
        *(uint32_t *)(entry + 4) == handle >> 13;
}

static int wolf_scope(void *self)
{
    uint8_t *entity = (uint8_t *)self;
    const char *name;
    if (!self || !server_module || !level_name ||
        *(void **)self != server_module + WOLF_VTABLE_RVA ||
        !target_map(level_name()) || *(uint32_t *)(entity + 0x200) != 0 ||
        (*(uint32_t *)(entity + 0x19c) & 0x20) ||
        *(uint32_t *)(entity + 0x1fc) == 0) return 0;
    name = *(const char **)(entity + 0x26c);
    return name && strcmp(name, "werewolf") == 0;
}

static void FC wolf_trace(void *self, void *unused, void *packet,
                          const void *direction, void *trace)
{
    uint8_t *entity = (uint8_t *)self;
    uint32_t handle = 0;
    int changed = 0;
    int scoped = packet && wolf_scope(self) && find_handle(self, &handle);
    (void)unused;
#ifdef WOLF_DIAGNOSTIC
    ++gp_wolf_diagnostics[8];
    if (packet) memcpy((void *)&gp_wolf_diagnostics[10], (uint8_t *)packet + 0x44, 4);
#endif
    if (scoped) {
#ifdef WOLF_DIAGNOSTIC
        ++gp_wolf_diagnostics[9];
#endif
        if (*(uint32_t *)(entity + 0x1fc) == 1) {
            *(uint32_t *)(entity + 0x1fc) = 2;
            changed = 1;
        }
        native_trace(self, packet, direction, trace);
    } else original_trace(self, packet, direction, trace);
    if (changed && same_entity(self, handle) &&
        *(void **)self == server_module + WOLF_VTABLE_RVA &&
        *(uint32_t *)(entity + 0x1fc) == 2)
        *(uint32_t *)(entity + 0x1fc) = 1;
}

static int FC wolf_damage(void *self, void *unused, void *packet)
{
    uint8_t *entity = (uint8_t *)self;
    const char *name;
    uint32_t handle = 0;
    int changed = 0, result;
    (void)unused;
#ifdef WOLF_DIAGNOSTIC
    ++gp_wolf_diagnostics[0];
    {
        uintptr_t caller = (uintptr_t)__builtin_return_address(0);
        uintptr_t base = (uintptr_t)server_module;
        gp_wolf_diagnostics[4] = caller >= base && caller < base + 0xab9000 ?
            (uint32_t)(caller - base) : 0xffffffffu;
        if (packet) {
            memcpy((void *)&gp_wolf_diagnostics[5], packet, 4);
            memcpy((void *)&gp_wolf_diagnostics[6], (uint8_t *)packet + 0x30, 4);
            memcpy((void *)&gp_wolf_diagnostics[7], (uint8_t *)packet + 0x38, 4);
        }
    }
#endif
    if (self && packet && server_module && level_name &&
        *(void **)self == server_module + WOLF_VTABLE_RVA &&
        target_map(level_name()) &&
        *(uint32_t *)(entity + 0x200) == 0 &&
        !(*(uint32_t *)(entity + 0x19c) & 0x20) &&
        *(uint32_t *)(entity + 0x1fc) == 1) {
        name = *(const char **)(entity + 0x26c);
        if (name && strcmp(name, "werewolf") == 0 && find_handle(self, &handle)) {
            *(uint32_t *)(entity + 0x1fc) = 2;
            changed = 1;
#ifdef WOLF_DIAGNOSTIC
            ++gp_wolf_diagnostics[1];
#endif
        }
    }
    result = original_damage(self, packet);
#ifdef WOLF_DIAGNOSTIC
    ++gp_wolf_diagnostics[2];
    gp_wolf_diagnostics[3] = (uint32_t)result;
#endif
    /* Native death may remove the object or intentionally disable damage. */
    if (changed && same_entity(self, handle) &&
        *(void **)self == server_module + WOLF_VTABLE_RVA &&
        *(uint32_t *)(entity + 0x1fc) == 2) {
#ifndef WOLF_PERSIST_MODE
        *(uint32_t *)(entity + 0x1fc) = 1;
#endif
    }
    return result;
}

static IMAGE_NT_HEADERS32 *headers(uint8_t *module)
{
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    if (!module) return NULL;
    dos = (IMAGE_DOS_HEADER *)module;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 || dos->e_lfanew > 0x1000)
        return NULL;
    nt = (IMAGE_NT_HEADERS32 *)(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC)
        return NULL;
    return nt;
}

static int exchange_slot(unsigned int offset, void *expected, void *replacement)
{
    void **slot = (void **)(server_module + WOLF_VTABLE_RVA + offset);
    DWORD old, ignored;
    void *previous;
    if (!VirtualProtect(slot, sizeof(*slot), PAGE_READWRITE, &old)) return 0;
    previous = InterlockedCompareExchangePointer(slot, replacement, expected);
    if (!VirtualProtect(slot, sizeof(*slot), old, &ignored)) {
        if (previous == expected)
            InterlockedCompareExchangePointer(slot, expected, replacement);
        VirtualProtect(slot, sizeof(*slot), old, &ignored);
        return 0;
    }
    return previous == expected;
}

__declspec(dllexport) void loaded_vampire(void)
{
    static const uint8_t expected_thunk[] = {0xe9,0x4a,0x1a,0x3c,0x00};
    static const uint8_t expected_method[] = {0x83,0xec,0x4c,0x53,0x55,0x8b,0xe9,0x56};
    static const uint8_t expected_mode[] = {0xc7,0x86,0xfc,0x01,0x00,0x00,0x01,0x00,0x00,0x00};
    static const uint8_t expected_trace[] = {0xe9,0x89,0x7d,0x3c,0x00};
    static const uint8_t expected_native_trace[] = {0xe9,0x68,0x0c,0x25,0x00};
    IMAGE_NT_HEADERS32 *server, *engine;
    void *expected;
    if (installed) return;
    server_module = (uint8_t *)GetModuleHandleA("vampire.dll");
    engine_module = (uint8_t *)GetModuleHandleA("engine.dll");
    server = headers(server_module);
    engine = headers(engine_module);
    if (!server || server->FileHeader.TimeDateStamp != 0x41afafae ||
        server->OptionalHeader.SizeOfImage != 0xab9000 ||
        !engine || engine->FileHeader.TimeDateStamp != 0x41afaf48 ||
        engine->OptionalHeader.SizeOfImage != 0x13bb000 ||
        engine_module[LEVEL_NAME_RVA] != 0x8b ||
        engine_module[LEVEL_NAME_RVA + 1] != 0x15 ||
        engine_module[LEVEL_NAME_RVA + 6] != 0x56 ||
        memcmp(server_module + DAMAGE_THUNK_RVA, expected_thunk, sizeof(expected_thunk)) ||
        memcmp(server_module + TRACE_THUNK_RVA, expected_trace, sizeof(expected_trace)) ||
        memcmp(server_module + NPC_TRACE_THUNK_RVA, expected_native_trace, sizeof(expected_native_trace)) ||
        memcmp(server_module + 0x3cccc0, expected_method, sizeof(expected_method)) ||
        memcmp(server_module + 0x3cafb5, expected_mode, sizeof(expected_mode))) return;
    expected = server_module + DAMAGE_THUNK_RVA;
    if (*(void **)(server_module + WOLF_VTABLE_RVA + DAMAGE_SLOT) != expected) return;
    if (*(void **)(server_module + WOLF_VTABLE_RVA + TRACE_SLOT) != server_module + TRACE_THUNK_RVA) return;
    original_damage = (DamageFn)expected;
    original_trace = (TraceFn)(server_module + TRACE_THUNK_RVA);
    native_trace = (TraceFn)(server_module + NPC_TRACE_THUNK_RVA);
    level_name = (LevelNameFn)(engine_module + LEVEL_NAME_RVA);
    if (!exchange_slot(DAMAGE_SLOT, expected, (void *)wolf_damage)) return;
    if (!exchange_slot(TRACE_SLOT, (void *)original_trace, (void *)wolf_trace)) {
        exchange_slot(DAMAGE_SLOT, (void *)wolf_damage, (void *)original_damage);
        return;
    }
    installed = 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)instance;
    if (reason == DLL_PROCESS_DETACH && !reserved && installed &&
        (uint8_t *)GetModuleHandleA("vampire.dll") == server_module) {
        exchange_slot(TRACE_SLOT, (void *)wolf_trace, (void *)original_trace);
        exchange_slot(DAMAGE_SLOT, (void *)wolf_damage, (void *)original_damage);
    }
    return TRUE;
}
