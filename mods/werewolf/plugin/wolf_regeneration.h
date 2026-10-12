/* Functional game-thread inputs. No datamap allocation, threads or diagnostics. */
#include <errno.h>
#include <limits.h>
#include <math.h>
#include <stdlib.h>

#define INPUT_SLOT 0x1d8u
#define INPUT_THUNK 0x13b47u
typedef struct { uint32_t words[5]; } WolfVariant;
typedef int (TC *WolfInputFn)(void *, const char *, void *, void *, WolfVariant, int);
typedef int (TC *WolfCurrentFn)(void *, int);
typedef void (TC *WolfHealFn)(void *, int);
static HINSTANCE wolf_instance;
static WolfInputFn stock_input;
static int regen_registered, regen_hp = 5;
static DWORD regen_page_protection;
static int regen_protection_pending;
static double regen_interval = 1.0;
static void *regen_owner;
static uint32_t regen_serial;
static int regen_active, regen_stopped, regen_visible;
static double regen_next, regen_last;

static char *regen_trim(char *s)
{
    char *end;
    while (*s == ' ' || *s == '\t' || *s == '\r') ++s;
    end = s + strlen(s);
    while (end > s && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '\r')) --end;
    *end = 0;
    return s;
}

static void regen_settings(void)
{
    char path[MAX_PATH], content[4097], *slash, *line, *next;
    DWORD length, size, got;
    HANDLE file;
    int section = 0, seen_hp = 0, seen_interval = 0, good = 1;
    length = GetModuleFileNameA(wolf_instance, path, sizeof(path));
    if (!length || length >= sizeof(path)) { regen_hp = 0; return; }
    slash = strrchr(path, '\\');
    if (!slash || (size_t)(slash - path) + sizeof("\\griffith-wolf-native-damage.ini") > sizeof(path)) {
        regen_hp = 0; return;
    }
    strcpy(slash + 1, "griffith-wolf-native-damage.ini");
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                       NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        DWORD error = GetLastError();
        if (error != ERROR_FILE_NOT_FOUND && error != ERROR_PATH_NOT_FOUND) regen_hp = 0;
        return;
    }
    size = GetFileSize(file, NULL);
    if (size > 4096 || !ReadFile(file, content, size, &got, NULL) || got != size) good = 0;
    CloseHandle(file);
    if (!good || memchr(content, 0, size)) { regen_hp = 0; return; }
    content[size] = 0;
    line = content;
    if (size >= 3 && (uint8_t)content[0] == 0xef && (uint8_t)content[1] == 0xbb &&
        (uint8_t)content[2] == 0xbf) line += 3;
    for (; line; line = next) {
        char *key, *value, *equals, *end;
        next = strchr(line, '\n');
        if (next) *next++ = 0;
        key = regen_trim(line);
        if (!*key || *key == ';' || *key == '#') continue;
        if (*key == '[') {
            section = !_stricmp(key, "[Regeneration]");
            if (!strchr(key, ']')) good = 0;
            continue;
        }
        equals = strchr(key, '=');
        if (!equals) { good = 0; continue; }
        if (!section) continue;
        *equals = 0; value = regen_trim(equals + 1); key = regen_trim(key);
        errno = 0;
        if (!_stricmp(key, "HPPerTick")) {
            long number = strtol(value, &end, 10);
            if (seen_hp++ || !*value || *end || errno || number < 0 || number > INT_MAX) good = 0;
            else regen_hp = (int)number;
        } else if (!_stricmp(key, "TickIntervalSeconds")) {
            double number = strtod(value, &end);
            if (seen_interval++ || !*value || *end || errno || !isfinite(number) || number < 0.1) good = 0;
            else regen_interval = number;
        }
    }
    if (!good) regen_hp = 0;
}

static int regen_identity(void *self, uint32_t *serial)
{
    uint8_t *p = self;
    const char *name;
    if (!p || !target_map(level_name()) || *(void **)p != server_module + WOLF_VTABLE_RVA) return 0;
    name = *(const char **)(p + 0x26c);
    return name && !strcmp(name, "werewolf") && find_handle(self, serial);
}

static void *regen_group(void *self)
{
    uint8_t *p = self, **groups = *(uint8_t ***)(p + 0x13c0);
    int count = *(int *)(p + 0x13bc), i;
    if (!groups || count <= 0 || count > 32) return NULL;
    for (i = 0; i < count; ++i)
        if (groups[i] && *(int *)(groups[i] + 0x10) == 0 && *(int *)(groups[i] + 4) == 35)
            return groups[i];
    return NULL;
}

static int FC wolf_regen_input(void *self, void *unused, const char *name,
                               void *activator, void *caller, WolfVariant value, int output_id)
{
    uint32_t serial = 0;
    int start = name && !_stricmp(name, "WolfRegenStart");
    int stop = name && !_stricmp(name, "WolfRegenStop");
    int tick = name && !_stricmp(name, "WolfRegenTick");
    uint8_t *clock, *p = self;
    double now;
    void *group;
    int damage, maximum, amount;
    (void)unused;
    if (!(start || stop || tick) || !regen_identity(self, &serial))
        return stock_input(self, name, activator, caller, value, output_id);
    if (!regen_hp) return 1;
    clock = *(uint8_t **)(server_module + 0x70b228);
    if (!clock) return 1;
    now = *(float *)(clock + 0xc);
    if (!isfinite(now) || now < 0) return 1;
    if (regen_owner != self || regen_serial != serial || now < regen_last) {
        regen_owner = self; regen_serial = serial;
        regen_active = regen_stopped = regen_visible = 0;
        regen_next = now + regen_interval;
    }
    regen_last = now;
    /* This activity is installed before OnBeginCrushAnimation is fired.
       It closes the window before queued map/Python stop outputs arrive. */
    if (*(int *)(p + 0xff0) == 0x11e) stop = 1;
    if (stop) { regen_active = regen_visible = 0; regen_stopped = 1; return 1; }
    if (start) {
        if (regen_stopped) return 1;
        regen_active = 1; regen_visible = wolf_scope(self);
        regen_next = now + regen_interval;
        return 1;
    }
    if (!regen_active || regen_stopped) return 1;
    if (!wolf_scope(self)) { regen_visible = 0; return 1; }
    if (!regen_visible) { regen_visible = 1; regen_next = now + regen_interval; }
    if (now + 0.00001 < regen_next) return 1;
    /* Keep the phase, but pay only one tick after a stall; never catch up. */
    regen_next += (floor((now + 0.00001 - regen_next) / regen_interval) + 1.0) * regen_interval;
    if (!isfinite(regen_next)) { regen_active = 0; return 1; }
    group = regen_group(self);
    if (!group) return 1;
    damage = ((WolfCurrentFn)(server_module + 0x2012d0))(group, 15);
    maximum = ((WolfCurrentFn)(server_module + 0x2012d0))(group, 17);
    if (maximum <= 0 || damage <= 0 || damage >= maximum || !same_entity(self, serial)) return 1;
    amount = regen_hp < damage ? regen_hp : damage;
    ((WolfHealFn)(server_module + 0x33c340))(self, amount);
    return 1;
}

static void regen_install(void)
{
    static const uint8_t input_thunk[] = {0xe9,0x44,0x81,0x09,0x00};
    static const uint8_t input_body[] = {0x83,0xec,0x24,0x53,0x8b,0xd9,0x55,0x56};
    static const uint8_t heal[] = {0x57,0x8b,0xf9,0x85,0xff,0x74,0x11,0x8b};
    static const uint8_t current[] = {0x56,0x57,0x8b,0x7c,0x24,0x0c,0x8b,0xf1};
    static const uint8_t crush[] = {0x81,0xbe,0xf0,0x0f,0x00,0x00,0x1e,0x01,0x00,0x00};
    if (memcmp(server_module + INPUT_THUNK, input_thunk, sizeof(input_thunk)) ||
        memcmp(server_module + 0xabc90, input_body, sizeof(input_body)) ||
        memcmp(server_module + 0x33c340, heal, sizeof(heal)) ||
        memcmp(server_module + 0x2012d0, current, sizeof(current)) ||
        memcmp(server_module + 0x3cda6e, crush, sizeof(crush))) return;
    void **slot = (void **)(server_module + WOLF_VTABLE_RVA + INPUT_SLOT);
    DWORD ignored;
    void *previous;
    stock_input = (WolfInputFn)(server_module + INPUT_THUNK);
    if (*slot != (void *)stock_input) return;
    regen_settings();
    if (!VirtualProtect(slot, sizeof(*slot), PAGE_READWRITE, &regen_page_protection)) return;
    previous = InterlockedCompareExchangePointer(slot, (void *)wolf_regen_input, (void *)stock_input);
    if (!VirtualProtect(slot, sizeof(*slot), regen_page_protection, &ignored)) {
        regen_protection_pending = 1;
        if (previous == (void *)stock_input)
            InterlockedCompareExchangePointer(slot, (void *)stock_input, (void *)wolf_regen_input);
        if (VirtualProtect(slot, sizeof(*slot), regen_page_protection, &ignored)) regen_protection_pending = 0;
        return;
    }
    regen_registered = previous == (void *)stock_input;
}

static void regen_unload(void)
{
    regen_active = 0;
    if (regen_registered) exchange_slot(INPUT_SLOT, (void *)wolf_regen_input, (void *)stock_input);
    if (regen_protection_pending) {
        DWORD ignored;
        VirtualProtect(server_module + WOLF_VTABLE_RVA + INPUT_SLOT,
                       sizeof(void *), regen_page_protection, &ignored);
    }
}
