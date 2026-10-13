/* Exercise the loaded final VTM; scratch INI lives in an exclusively owned temp dir. */
#include "../../../infra/common/native_fixture.h"
#include <stdlib.h>
typedef struct { uint32_t words[5]; } Variant;
typedef int (__attribute__((thiscall)) *Input)(void *, const char *, void *, void *, Variant, int);
static uint8_t *server, *engine, *entity, *table, *clock_data, *group, *groups, *reset_sender;
static int stats[35], heal_calls, last_heal, forwarded, protect_calls, fail_at, deny_restore;
static const char *map = "sp_observatory_2";
static uint8_t saved_current[8], saved_heal[8], saved_input[8], saved_level[7];
static char plugin_path[MAX_PATH], ini_path[MAX_PATH], temp_dir[MAX_PATH];
static void *original_input, *original_damage, *original_trace;
static HMODULE WINAPI modules(LPCSTR name)
{
    if (!strcmp(name, "vampire.dll")) return (HMODULE)server;
    if (!strcmp(name, "engine.dll")) return (HMODULE)engine;
    return NULL;
}
static BOOL WINAPI protect(LPVOID at, SIZE_T n, DWORD flags, PDWORD old)
{
    ++protect_calls;
    if (protect_calls == fail_at) return FALSE;
    if (deny_restore && at == server + 0x4cf4d4 + 0x1d8 && flags != PAGE_READWRITE) return FALSE;
    return VirtualProtect(at, n, flags, old);
}
static const char *__cdecl level(void) { return map; }
static int __attribute__((thiscall)) current(void *self, int index)
{
    check(self == group && (index == 15 || index == 17), "CURRENT accessor/self/index");
    return stats[index];
}
static void __attribute__((thiscall)) heal(void *self, int amount)
{
    check(self == entity && amount > 0 && amount <= stats[15], "HealthHeal absolute clamp");
    ++heal_calls; last_heal = amount; stats[15] -= amount;
}
static int __attribute__((thiscall)) forward(void *self, const char *name, void *activator,
                                             void *caller, Variant value, int id)
{
    check(self == entity && !strcmp(name, "Use") && activator == (void *)0x1234 &&
          caller == (void *)0x5678 && id == 71, "forwarded input ABI/self/arguments");
    check(value.words[0] == 0xabc && value.words[4] == 4, "20-byte by-value variant ABI");
    ++forwarded; return 77;
}
static int input(const char *name)
{
    Variant v = {{0xabc,2,3,4,4}};
    return ((Input)*(void **)(server + 0x4cf4d4 + 0x1d8))(entity, name, (void *)0x1234, (void *)0x5678, v, 71);
}
static void reset_input(void)
{
    Variant v = {{0,0,0,0,0}};
    ((Input)*(void **)(server + 0x4cf4d4 + 0x1d8))(entity, "WolfRegenReset", NULL, reset_sender, v, 0);
}
static void now(float t) { memcpy(clock_data + 0xc, &t, 4); }
static void configure(const char *text)
{
    if (text) {
        FILE *f = fopen(ini_path, "wb"); check(f != NULL, "owned test INI open");
        check(fwrite(text, 1, strlen(text), f) == strlen(text), "owned INI bytes");
        fclose(f);
    } else if (GetFileAttributesA(ini_path) != INVALID_FILE_ATTRIBUTES)
        check(DeleteFileA(ini_path), "remove only owned test INI");
}
static HMODULE open_plugin(const char *config)
{
    HMODULE plugin;
    void (__cdecl *load)(void);
    configure(config);
    memcpy(server + 0x2012d0, saved_current, 8);
    memcpy(server + 0x33c340, saved_heal, 8);
    memcpy(server + 0xabc90, saved_input, 8);
    memcpy(engine + 0x1b800, saved_level, 7);
    plugin = LoadLibraryA(plugin_path); check(plugin != NULL, "clean final VTM loads");
    imports(plugin, "GetModuleHandleA", modules);
    imports(plugin, "VirtualProtect", protect);
    protect_calls = 0;
    load = (void *)GetProcAddress(plugin, "loaded_vampire"); check(load != NULL, "required export");
    load();
    check(*(void **)(server + 0x4cf4d4 + 0x238) != original_damage &&
          *(void **)(server + 0x4cf4d4 + 0x234) != original_trace, "damage fix remains installed");
    jump(engine + 0x1b800, level);
    jump(server + 0x2012d0, current);
    jump(server + 0x33c340, heal);
    jump(server + 0xabc90, forward);
    heal_calls = last_heal = forwarded = 0;
    memset(stats, 0, sizeof(stats)); stats[15] = 100; stats[17] = 900;
    put(entity + 0x200, 0); put(entity + 0x19c, 0); put(entity + 0xff0, 0);
    now(10); map = "sp_observatory_2";
    return plugin;
}
static void close_plugin(HMODULE plugin)
{
    check(FreeLibrary(plugin), "final VTM unloads");
    check(*(void **)(server + 0x4cf4d4 + 0x1d8) == original_input &&
          *(void **)(server + 0x4cf4d4 + 0x238) == original_damage &&
          *(void **)(server + 0x4cf4d4 + 0x234) == original_trace, "all owned slots restored");
}
int main(int argc, char **argv)
{
    HMODULE plugin;
    char root[MAX_PATH];
    unsigned i;
    const char *bad[] = {
        "HPPerTick=-1", "HPPerTick=1.5", "HPPerTick=99999999999999999999",
        "TickIntervalSeconds=nan", "TickIntervalSeconds=inf", "TickIntervalSeconds=0",
        "TickIntervalSeconds=0.01", "HPPerTick=5junk", "TickIntervalSeconds=1junk"
    };
    check(argc == 4, "VTM/server/engine arguments");
    check(GetTempPathA(sizeof(root), root) != 0, "temp root");
    snprintf(temp_dir, sizeof(temp_dir), "%swolf_regen_%lu_%lu", root, GetCurrentProcessId(), GetTickCount());
    check(CreateDirectoryA(temp_dir, NULL), "exclusive temp directory");
    snprintf(plugin_path, sizeof(plugin_path), "%s\\regen.vtm", temp_dir);
    snprintf(ini_path, sizeof(ini_path), "%s\\griffith-wolf-native-damage.ini", temp_dir);
    check(CopyFileA(argv[1], plugin_path, TRUE), "exact VTM scratch copy");
    server = map_image(argv[2]); engine = map_image(argv[3]);
    entity = calloc(1, 0x6800); table = calloc(8192, 12); clock_data = calloc(1, 64);
    group = calloc(1, 64); groups = calloc(1, 4);
    reset_sender = calloc(1, 0x400);
    check(entity && table && clock_data && group && groups, "fixture objects");
    put(server + 0x566458, (uint32_t)(uintptr_t)table);
    put(table + 4, (uint32_t)(uintptr_t)entity); put(table + 8, 1);
    put(table + 16, (uint32_t)(uintptr_t)reset_sender); put(table + 20, 3);
    put(reset_sender + 0x11c, (uint32_t)(uintptr_t)"logic_relay");
    put(reset_sender + 0x26c, (uint32_t)(uintptr_t)"gp_wolf_regen_reset");
    put(entity, (uint32_t)(uintptr_t)(server + 0x4cf4d4));
    put(entity + 0x26c, (uint32_t)(uintptr_t)"werewolf"); put(entity + 0x1fc, 1);
    put(entity + 0x13bc, 1); put(entity + 0x13c0, (uint32_t)(uintptr_t)groups);
    put(groups, (uint32_t)(uintptr_t)group); put(group + 4, 35);
    put(server + 0x70b228, (uint32_t)(uintptr_t)clock_data);
    original_input = *(void **)(server + 0x4cf4d4 + 0x1d8);
    original_damage = *(void **)(server + 0x4cf4d4 + 0x238);
    original_trace = *(void **)(server + 0x4cf4d4 + 0x234);
    memcpy(saved_current, server + 0x2012d0, 8); memcpy(saved_heal, server + 0x33c340, 8);
    memcpy(saved_input, server + 0xabc90, 8); memcpy(saved_level, engine + 0x1b800, 7);
    plugin = open_plugin(NULL);
    check(input("Use") == 77 && forwarded == 1, "non-regeneration input forwarded exactly once");
    input("WolfRegenStart"); now(10.99f); input("WolfRegenTick"); check(!heal_calls, "full first interval");
    now(11); input("WolfRegenTick"); check(heal_calls == 1 && last_heal == 5, "default5HP/1second");
    input("WolfRegenTick"); check(heal_calls == 1, "no duplicate or paused-time payout");
    stats[15] = 3; now(12); input("WolfRegenTick"); check(last_heal == 3 && stats[15] == 0, "last partial tick/max clamp");
    now(13); input("WolfRegenTick"); check(heal_calls == 2, "full health no call");
    stats[15] = 50; stats[17] = 1200; now(25); input("WolfRegenTick"); check(heal_calls == 3, "long stall pays one only/current max");
    put(entity + 0xff0, 0x11e); now(26); input("WolfRegenTick"); check(heal_calls == 3, "crush blocks BEFORE queued stop");
    put(entity + 0xff0, 0); input("WolfRegenStart"); now(27); input("WolfRegenTick"); check(heal_calls == 3, "crush disarm is sticky");
    now(30); reset_input(); input("WolfRegenStart"); now(30.99f); input("WolfRegenTick");
    check(heal_calls == 3, "same handle later-time load waits a full interval");
    now(31); input("WolfRegenTick"); check(heal_calls == 4, "explicit live load reset/same handle/later clock");
    input("WolfRegenStop"); now(12); input("WolfRegenTick"); check(heal_calls == 4, "queued tick after stop ignored");
    put(table + 8, 2); input("WolfRegenStart"); now(13); input("WolfRegenTick"); check(heal_calls == 5, "new serial fresh state");
    put(entity + 0x200, 1); now(14); input("WolfRegenTick"); check(heal_calls == 5, "dead cannot heal");
    put(entity + 0x200, 0); stats[15] = stats[17]; now(15); input("WolfRegenTick"); now(16); input("WolfRegenTick"); check(heal_calls == 5, "zeroHP cannot resurrect");
    stats[15] = 50; map = "other_map"; now(17); input("Use"); check(forwarded == 2 && heal_calls == 5, "other map forwarded");
    close_plugin(plugin);
    plugin = open_plugin(NULL); input("WolfRegenStart");
    now(10.5f); input("WolfRegenStart"); now(11); input("WolfRegenTick");
    check(heal_calls == 1, "repeated Start does not postpone deadline");
    now(10.99f); input("WolfRegenTick"); now(12); input("WolfRegenTick");
    check(heal_calls == 2, "simulation clock rewind does not disarm live healing");
    input("WolfRegenStop"); input("WolfRegenStart"); now(13); input("WolfRegenTick");
    check(heal_calls == 2, "late queued Start and Tick cannot remove stop");
    put(entity + 0xff0, 0x11e); reset_input(); input("WolfRegenStart"); now(14); input("WolfRegenTick");
    check(heal_calls == 2, "load reset cannot remove active crush stop");
    put(entity + 0xff0, 0); put(entity + 0x200, 1); reset_input(); input("WolfRegenStart"); now(15); input("WolfRegenTick");
    check(heal_calls == 2, "load reset cannot revive dead actor");
    close_plugin(plugin);
    {
        const unsigned fps[] = {20, 30, 60, 144, 240};
        unsigned f, frame;
        for (f = 0; f < sizeof(fps)/sizeof(fps[0]); ++f) {
            plugin = open_plugin(NULL); input("WolfRegenStart");
            for (frame = 1; frame <= fps[f] * 10; ++frame) {
                now(10.0f + (float)frame / fps[f]); input("WolfRegenTick");
            }
            check(heal_calls == 10 && stats[15] == 50, "exact50HP/10game-seconds across frame rates");
            close_plugin(plugin);
        }
    }
    for (i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i) {
        char config[256]; snprintf(config, sizeof(config), "[Regeneration]\n%s\n", bad[i]);
        plugin = open_plugin(config); input("WolfRegenStart"); now(12); input("WolfRegenTick");
        check(!heal_calls, "malformed INI disables regeneration only"); close_plugin(plugin);
    }
    plugin = open_plugin("[Regeneration]\nHPPerTick=0\nTickIntervalSeconds=1\n");
    input("WolfRegenStart"); now(12); input("WolfRegenTick"); check(!heal_calls, "explicit off"); close_plugin(plugin);
    plugin = open_plugin("[Regeneration]\nHPPerTick=2\nTickIntervalSeconds=0.5\n");
    input("WolfRegenStart"); now(10.5f); input("WolfRegenTick"); check(last_heal == 2, "user settings"); close_plugin(plugin);
    /* Failure in the additional input slot must not remove old working damage hooks. */
    fail_at = 5; plugin = open_plugin(NULL);
    check(*(void **)(server + 0x4cf4d4 + 0x1d8) == original_input, "registration refusal keeps original input");
    close_plugin(plugin); fail_at = 0;
    fail_at = 6; plugin = open_plugin(NULL);
    check(*(void **)(server + 0x4cf4d4 + 0x1d8) == original_input, "transient restore failure rolls slot back");
    close_plugin(plugin); fail_at = 0;
    deny_restore = 1; plugin = open_plugin(NULL);
    check(*(void **)(server + 0x4cf4d4 + 0x1d8) == original_input, "persistent restore refusal keeps no VTM pointer");
    deny_restore = 0; close_plugin(plugin);
    plugin = open_plugin(NULL);
    *(void **)(server + 0x4cf4d4 + 0x1d8) = server + 0xabc90;
    check(FreeLibrary(plugin), "foreign-owner unload");
    check(*(void **)(server + 0x4cf4d4 + 0x1d8) == server + 0xabc90, "foreign input slot not overwritten on unload");
    *(void **)(server + 0x4cf4d4 + 0x1d8) = original_input;
    configure(NULL); check(DeleteFileA(plugin_path), "remove only owned scratch VTM");
    check(RemoveDirectoryA(temp_dir), "remove empty owned scratch directory");
    puts("PASS exact VTM regeneration: input ABI, native service/clamp, clock, crush, serial, INI, independent rollback");
    return 0;
}
