/* Qualified game-thread restoration. No replay of serialized output chains. */
#define AUTO_VTABLE 0x465694u
#define AUTO_ACTIVATE 0x208u
#define AUTO_THINK 0x218u
typedef void (TC *WolfAutoActivate)(void *, int);
typedef void (TC *WolfAutoThink)(void *);
typedef struct WolfPyObject { int refs; void *type; } WolfPyObject;
typedef WolfPyObject *(WOLF_CDECL *WolfPyAdd)(const char *);
typedef WolfPyObject *(WOLF_CDECL *WolfPyDict)(WolfPyObject *);
typedef WolfPyObject *(WOLF_CDECL *WolfPyEval)(const char *, int, WolfPyObject *, WolfPyObject *);
typedef long (WOLF_CDECL *WolfPyInt)(WolfPyObject *);
typedef void (WOLF_CDECL *WolfPyClear)(void);
typedef void *(WOLF_CDECL *WolfPyError)(void);
static WolfAutoActivate stock_auto_activate;
static WolfAutoThink stock_auto_think;
static int lifecycle_registered, lifecycle_failed, lifecycle_committed;
static void *lifecycle_owner, *lifecycle_timer;
static uint32_t lifecycle_serial, lifecycle_timer_serial;
static uint64_t lifecycle_epoch;
static DWORD lifecycle_thread;
static double lifecycle_last, lifecycle_wait;

static int lifecycle_identity(void *self, uint32_t *handle)
{
    uint8_t *p = self;
    const char *name, *kind;
    /* Activate runs before LevelName is ready on a saved-map load. Defer map
       qualification until Think; never infer loading from pointer or clock. */
    if (!p || *(void **)p != server_module + AUTO_VTABLE || !find_handle(self, handle)) return 0;
    name = *(const char **)(p + 0x26c); kind = *(const char **)(p + 0x11c);
    return name && kind && !strcmp(name, "gp_wolf_regen_init") && !strcmp(kind, "logic_auto");
}
static double lifecycle_clock(void)
{
    uint8_t *clock = *(uint8_t **)(server_module + 0x70b228);
    double now = clock ? *(float *)(clock + 0xc) : -1;
    return isfinite(now) && now >= 0 ? now : -1;
}
static void lifecycle_schedule(void *self, double now)
{
    /* Exact stock CLogicAuto Spawn/Activate schedule field, qualified live. */
    *(float *)((uint8_t *)self + 0x17c) = (float)(now + 0.1);
}
static void lifecycle_begin(void *self, uint32_t handle)
{
    ++lifecycle_epoch;
    lifecycle_owner = self; lifecycle_serial = handle; lifecycle_timer = NULL;
    lifecycle_thread = GetCurrentThreadId();
    lifecycle_failed = lifecycle_committed = 0;
    lifecycle_last = lifecycle_wait = -1;
    regen_owner = NULL; regen_serial = 0;
    regen_active = regen_visible = regen_stopped = 0;
}
static void lifecycle_stop(void)
{
    regen_active = regen_visible = 0; regen_stopped = 1; lifecycle_failed = 1;
}
static int regen_state_read(void)
{
    HMODULE py = GetModuleHandleA("vampire_python21.dll");
    IMAGE_NT_HEADERS32 *nt = headers((uint8_t *)py);
    WolfPyAdd add; WolfPyDict dict; WolfPyEval eval; WolfPyInt number;
    WolfPyClear clear; WolfPyError error;
    WolfPyObject *module, *globals, *answer;
    void **thread; void *int_type;
    long state;
    if (GetCurrentThreadId() != lifecycle_thread || !nt ||
        nt->FileHeader.TimeDateStamp != 0x4164cbcc || nt->OptionalHeader.SizeOfImage != 0xae000) return 0;
    thread = (void **)GetProcAddress(py, "_PyThreadState_Current");
    add = (void *)GetProcAddress(py, "PyImport_AddModule");
    dict = (void *)GetProcAddress(py, "PyModule_GetDict");
    eval = (void *)GetProcAddress(py, "PyRun_String");
    number = (void *)GetProcAddress(py, "PyInt_AsLong");
    clear = (void *)GetProcAddress(py, "PyErr_Clear");
    error = (void *)GetProcAddress(py, "PyErr_Occurred");
    int_type = (void *)GetProcAddress(py, "PyInt_Type");
    if (!thread || !*thread || !add || !dict || !eval || !number || !clear || !error || !int_type || error()) return 0;
    module = add("__main__"); globals = module ? dict(module) : NULL;
    answer = globals ? eval("nativeWolfRegenState()", 258, globals, globals) : NULL;
    if (!answer) { clear(); return 0; }
    state = answer->type == int_type ? number(answer) : 4;
    /* Python2.1's Py_DECREF ABI; no native callable is registered in Python. */
    if (!--answer->refs)
        ((void (WOLF_CDECL *)(WolfPyObject *))*(void **)((uint8_t *)answer->type + 8))(answer);
    if (error()) { clear(); return 4; }
    return state >= 0 && state <= 4 ? (int)state : 4;
}
static void *lifecycle_find(const char *wanted, const char *kind, uint32_t vtable, uint32_t *serial)
{
    uint8_t *table = *(uint8_t **)(server_module + ENTITY_TABLE_RVA);
    void *found = NULL;
    unsigned i;
    if (!table) return NULL;
    for (i = 0; i < 8192; ++i) {
        uint8_t *p = *(uint8_t **)(table + i * 12 + 4);
        const char *name, *class_name;
        if (!p) continue;
        name = *(const char **)(p + 0x26c);
        if (!name || strcmp(name, wanted)) continue;
        class_name = *(const char **)(p + 0x11c);
        if (found || !class_name || strcmp(class_name, kind) || *(void **)p != server_module + vtable) return NULL;
        found = p; *serial = i | (*(uint32_t *)(table + i * 12 + 8) << 13);
    }
    return found;
}
static int regen_tick_allowed(void *caller)
{
    return lifecycle_registered && lifecycle_committed && !lifecycle_failed &&
        caller == lifecycle_timer && same_entity(caller, lifecycle_timer_serial) &&
        same_entity(lifecycle_owner, lifecycle_serial) && target_map(level_name());
}
static void FC lifecycle_activate(void *self, void *unused, int flag)
{
    uint32_t handle = 0;
    int scoped = lifecycle_identity(self, &handle);
    double now;
    (void)unused;
    if (scoped) lifecycle_begin(self, handle);
    stock_auto_activate(self, flag);
    if (scoped && same_entity(self, handle) && (now = lifecycle_clock()) >= 0)
        lifecycle_schedule(self, now);
}
static void FC lifecycle_think(void *self, void *unused)
{
    uint32_t handle, wolf_handle = 0, timer_handle = 0, init_handle = 0;
    uint64_t epoch;
    void *wolf, *timer, *init;
    int state;
    double now;
    WolfVariant empty = {{0,0,0,0,0}};
    (void)unused;
    if (!lifecycle_identity(self, &handle) || !target_map(level_name())) {
        stock_auto_think(self); return;
    }
    /* Fresh-map Spawn schedules Think without calling Activate in this game. */
    if (self != lifecycle_owner || handle != lifecycle_serial) lifecycle_begin(self, handle);
    if (lifecycle_failed || lifecycle_committed || !regen_hp) return;
    now = lifecycle_clock(); if (now < 0) { lifecycle_stop(); return; }
    if (lifecycle_last >= 0 && now < lifecycle_last) now = lifecycle_last;
    lifecycle_last = now;
    if (lifecycle_wait < 0) lifecycle_wait = now;
    epoch = lifecycle_epoch; state = regen_state_read();
    if (epoch != lifecycle_epoch || !same_entity(self, handle)) return;
    if (!state) {
        if (now - lifecycle_wait >= 5) { lifecycle_stop(); return; }
        lifecycle_schedule(self, now); return;
    }
    if (state == 3 || state == 4) { lifecycle_stop(); return; }
    if (state == 1) { lifecycle_wait = now; lifecycle_schedule(self, now); return; }
    init = lifecycle_find("gp_wolf_regen_init", "logic_auto", AUTO_VTABLE, &init_handle);
    wolf = lifecycle_find("werewolf", "npc_VWerewolf", WOLF_VTABLE_RVA, &wolf_handle);
    timer = lifecycle_find("gp_wolf_regen_timer", "logic_timer", 0x465fb4, &timer_handle);
    if (init != self || init_handle != handle || !wolf || !timer ||
        (*(uint32_t *)((uint8_t *)self + 0x204) & 1)) { lifecycle_stop(); return; }
    if (*(uint32_t *)((uint8_t *)wolf + 0x200) || *(int *)((uint8_t *)wolf + 0xff0) == 0x11e) {
        lifecycle_stop(); return;
    }
    if (!wolf_scope(wolf)) { lifecycle_wait = now; lifecycle_schedule(self, now); return; }
    if (!same_entity(wolf, wolf_handle) || !same_entity(timer, timer_handle)) { lifecycle_stop(); return; }
    regen_owner = wolf; regen_serial = wolf_handle;
    regen_last = now; regen_next = now + regen_interval;
    regen_visible = regen_active = 1; regen_stopped = 0;
    lifecycle_timer = timer; lifecycle_timer_serial = timer_handle; lifecycle_committed = 1;
    /* Stock timer AcceptInput -> Enable; preserve the exact 20-byte variant ABI. */
    ((WolfInputFn)(server_module + INPUT_THUNK))(timer, "Enable", self, self, empty, 0);
    if (epoch != lifecycle_epoch || !same_entity(timer, timer_handle) || !same_entity(wolf, wolf_handle)) lifecycle_stop();
}
static int lifecycle_exchange(unsigned slot, void *expected, void *replacement)
{
    void **at = (void **)(server_module + AUTO_VTABLE + slot);
    DWORD old, ignored;
    void *previous;
    if (!VirtualProtect(at, sizeof(*at), PAGE_READWRITE, &old)) return 0;
    previous = InterlockedCompareExchangePointer(at, replacement, expected);
    if (!VirtualProtect(at, sizeof(*at), old, &ignored)) {
        if (previous == expected) InterlockedCompareExchangePointer(at, expected, replacement);
        VirtualProtect(at, sizeof(*at), old, &ignored); return 0;
    }
    return previous == expected;
}
static int lifecycle_install(void)
{
    static const uint8_t activate[] = {0x53,0x8b,0x5c,0x24,0x08,0x56,0x53,0x8b,0xf1};
    static const uint8_t think[] = {0x56,0x8b,0xf1,0x6a,0x00,0x56,0x6a,0x00};
    stock_auto_activate = (void *)(server_module + 0xc437);
    stock_auto_think = (void *)(server_module + 0x8cb0);
    if (memcmp(server_module + 0x130d40, activate, sizeof(activate)) ||
        memcmp(server_module + 0x130db0, think, sizeof(think)) ||
        *(void **)(server_module + AUTO_VTABLE + AUTO_ACTIVATE) != (void *)stock_auto_activate ||
        *(void **)(server_module + AUTO_VTABLE + AUTO_THINK) != (void *)stock_auto_think) return 0;
    if (!lifecycle_exchange(AUTO_ACTIVATE, (void *)stock_auto_activate, (void *)lifecycle_activate)) return 0;
    if (!lifecycle_exchange(AUTO_THINK, (void *)stock_auto_think, (void *)lifecycle_think)) {
        lifecycle_exchange(AUTO_ACTIVATE, (void *)lifecycle_activate, (void *)stock_auto_activate); return 0;
    }
    lifecycle_registered = 1; return 1;
}
static void lifecycle_unload(void)
{
    if (!lifecycle_registered) return;
    lifecycle_stop();
    lifecycle_exchange(AUTO_THINK, (void *)lifecycle_think, (void *)stock_auto_think);
    lifecycle_exchange(AUTO_ACTIVATE, (void *)lifecycle_activate, (void *)stock_auto_activate);
    lifecycle_registered = 0;
}
