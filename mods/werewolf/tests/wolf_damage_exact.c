/* Exercise the actual delivered candidate through Windows PE loading. */
#include "../../../infra/common/native_fixture.h"
typedef int (__attribute__((thiscall)) *DamageFn)(void *, void *);
typedef void (__attribute__((thiscall)) *TraceFn)(void *, void *, const void *, void *);
static uint8_t *server, *engine, *entity, *table;
static const char *current_map = "sp_observatory_2";
static void *wanted_packet;
static int protection_calls, fail_at, hits, seen_mode;
static int trace_hits, stock_trace_hits;
static HMODULE WINAPI modules(LPCSTR name)
{
    if (!strcmp(name, "vampire.dll")) return (HMODULE)server;
    if (!strcmp(name, "engine.dll")) return (HMODULE)engine;
    return NULL;
}
static BOOL WINAPI protect(LPVOID at, SIZE_T n, DWORD flags, PDWORD old)
{
    ++protection_calls;
    if (protection_calls == fail_at) return FALSE;
    return VirtualProtect(at, n, flags, old);
}
static const char *__cdecl level(void) { return current_map; }
static int __attribute__((thiscall)) receive(void *self, void *packet)
{
    check(self == entity && packet == wanted_packet, "exact thiscall packet and self");
    ++hits;
    seen_mode = *(int *)(entity + 0x1fc);
    return 321;
}
static void __attribute__((thiscall)) trace_native(void *self, void *packet, const void *direction, void *trace)
{
    check(self == entity && packet == wanted_packet && direction == (void *)0x1234 && trace == (void *)0x5678,
          "TraceAttack exact three-argument thiscall");
    check(*(int *)(entity + 0x1fc) == 2, "native TraceAttack sees normal damage mode");
    ++trace_hits;
}
static void __attribute__((thiscall)) trace_stock(void *self, void *packet, const void *direction, void *trace)
{
    check(self == entity && packet == wanted_packet && direction == (void *)0x1234 && trace == (void *)0x5678,
          "out-of-scope original TraceAttack arguments");
    ++stock_trace_hits;
}
static HMODULE open_plugin(const char *path)
{
    HMODULE plugin = LoadLibraryA(path);
    check(plugin != NULL, "actual candidate loads");
    imports(plugin, "GetModuleHandleA", modules);
    imports(plugin, "VirtualProtect", protect);
    protection_calls = 0;
    return plugin;
}
static void load(HMODULE plugin)
{
    void (__cdecl *start)(void) = (void *)GetProcAddress(plugin, "loaded_vampire");
    check(start != NULL, "loader export exists");
    start();
}
int main(int argc, char **argv)
{
    HMODULE plugin;
    uint8_t original_method[8], original_level[7], packet[76], wolf_trace_code[8], npc_trace_code[8];
    void **slot, **trace_slot;
    void *original, *original_trace;
    unsigned int i;
    int after_mode;
    uint8_t *anchors[5];
    check(argc == 4 || argc == 5, "plugin/server/engine/optional-mode arguments");
    after_mode = argc == 5 ? atoi(argv[4]) : 1;
    server = map_image(argv[2]); engine = map_image(argv[3]);
    slot = (void **)(server + 0x4cf4d4 + 0x238); original = *slot;
    trace_slot = (void **)(server + 0x4cf4d4 + 0x234); original_trace = *trace_slot;
    anchors[0] = server + 0xb271; anchors[1] = server + 0x3cccc0;
    anchors[2] = server + 0x3cafb5;
    anchors[3] = server + 0x4e62; anchors[4] = server + 0x15b13;
    for (i = 0; i < 5; ++i) {
        uint8_t saved = *anchors[i]; *anchors[i] ^= 0xff;
        plugin = open_plugin(argv[1]); load(plugin);
        check(*slot == original && *trace_slot == original_trace && !protection_calls, "mismatched native signature rejected");
        check(FreeLibrary(plugin), "rejected candidate unloads"); *anchors[i] = saved;
    }
    *slot = server + 0x2beda0;
    plugin = open_plugin(argv[1]); load(plugin);
    check(*slot == server + 0x2beda0 && !protection_calls, "conflicting vtable preserved");
    FreeLibrary(plugin); *slot = original;
    for (fail_at = 1; fail_at <= 4; ++fail_at) {
        plugin = open_plugin(argv[1]); load(plugin);
        check(*slot == original && *trace_slot == original_trace, "protection failure rolls both slots back");
        FreeLibrary(plugin);
    }
    fail_at = 0;
    plugin = open_plugin(argv[1]); load(plugin);
    check(*slot != original && (uint8_t *)*slot > (uint8_t *)plugin, "actual binary owns wrapper");
    check(*trace_slot != original_trace, "actual binary owns TraceAttack wrapper");
    memcpy(original_method, server + 0x3cccc0, 8);
    memcpy(original_level, engine + 0x1b800, 7);
    memcpy(wolf_trace_code, server + 0x3ccbf0, 8);
    memcpy(npc_trace_code, server + 0x266780, 8);
    jump(server + 0x3cccc0, receive); jump(engine + 0x1b800, level);
    jump(server + 0x3ccbf0, trace_stock); jump(server + 0x266780, trace_native);
    entity = calloc(1, 0x6700); table = calloc(8192, 12);
    check(entity && table, "test object memory");
    put(server + 0x566458, (uint32_t)(uintptr_t)table);
    put(table + 4, (uint32_t)(uintptr_t)entity); put(table + 8, 1);
    put(entity, (uint32_t)(uintptr_t)(server + 0x4cf4d4));
    put(entity + 0x26c, (uint32_t)(uintptr_t)"werewolf");
    put(entity + 0x1fc, 1); memset(packet, 0xa5, sizeof(packet)); wanted_packet = packet;
    ((TraceFn)*trace_slot)(entity, packet, (void *)0x1234, (void *)0x5678);
    check(trace_hits == 1 && stock_trace_hits == 0 && *(int *)(entity + 0x1fc) == 1,
          "scoped TraceAttack uses base path and restores damage mode");
    check(((DamageFn)*slot)(entity, packet) == 321, "original return preserved");
    check(hits == 1 && seen_mode == 2 && *(int *)(entity + 0x1fc) == after_mode, "expected standard damage mode lifetime");
    for (i = 0; i < sizeof(packet); ++i) check(packet[i] == 0xa5, "raw packet unchanged");
    current_map = "la_crackhouse_1";
    put(entity + 0x1fc, 1);
    ((TraceFn)*trace_slot)(entity, packet, (void *)0x1234, (void *)0x5678);
    check(trace_hits == 1 && stock_trace_hits == 1, "other map uses original wolf TraceAttack");
    check(((DamageFn)*slot)(entity, packet) == 321 && hits == 2 && seen_mode == 1, "other map unchanged");
    current_map = "sp_observatory_2"; put(entity + 0x19c, 0x20);
    check(((DamageFn)*slot)(entity, packet) == 321 && hits == 3 && seen_mode == 1, "hidden phase unchanged");
    check(FreeLibrary(plugin), "actual candidate unloads");
    check(*slot == original, "original vtable restored on unload");
    check(*trace_slot == original_trace, "original TraceAttack restored on unload");
    memcpy(server + 0x3cccc0, original_method, 8);
    memcpy(engine + 0x1b800, original_level, 7);
    memcpy(server + 0x3ccbf0, wolf_trace_code, 8);
    memcpy(server + 0x266780, npc_trace_code, 8);
    free(entity); free(table); VirtualFree(server, 0, MEM_RELEASE); VirtualFree(engine, 0, MEM_RELEASE);
    puts("PASS exact clean VTM: signature/conflict/protection guards, x86 ABI, scoped hit, unchanged packet, unload rollback");
    return 0;
}
