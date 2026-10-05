/* All four hook sites are validated before any code write. A failed install
   rolls back in reverse order and retains callable helper memory if OS rollback
   cannot be certified. Rechecks after VirtualProtect detect intervening owners. */
typedef struct {
    uint8_t *site; uint8_t original[5], patch[5]; DWORD protection;
    int changed, protected_once;
} CallHook;
static CallHook hooks[4];
static int installation_failed;
static int restore_hook(CallHook *h)
{
    DWORD old, ignored; int ok = 1;
    if (!h->changed) return 1;
    if (memcmp(h->site, h->patch, 5) && memcmp(h->site, h->original, 5)) return 0;
    if (!VirtualProtect(h->site, 5, PAGE_EXECUTE_READWRITE, &old)) return 0;
    if (memcmp(h->site, h->patch, 5) && memcmp(h->site, h->original, 5)) {
        VirtualProtect(h->site, 5, h->protection, &ignored); return 0;
    }
    memcpy(h->site, h->original, 5);
    if (!FlushInstructionCache(GetCurrentProcess(), h->site, 5)) ok = 0;
    if (!VirtualProtect(h->site, 5, h->protection, &ignored)) ok = 0;
    if (ok) h->changed = 0;
    return ok;
}
static int install_hook(CallHook *h)
{
    DWORD ignored;
    if (memcmp(h->site, h->original, 5)) return 0;
    if (!VirtualProtect(h->site, 5, PAGE_EXECUTE_READWRITE, &h->protection)) return 0;
    h->protected_once = 1;
    if (memcmp(h->site, h->original, 5)) {
        if (!VirtualProtect(h->site, 5, h->protection, &ignored)) installation_failed = 1;
        return 0;
    }
    memcpy(h->site, h->patch, 5); h->changed = 1;
    if (!FlushInstructionCache(GetCurrentProcess(), h->site, 5)) return 0;
    if (!VirtualProtect(h->site, 5, h->protection, &ignored)) return 0;
    return 1;
}
static void prepare_hook(CallHook *h, uint8_t *site, uint8_t *destination)
{
    memset(h, 0, sizeof(*h)); h->site = site; memcpy(h->original, site, 5);
    h->patch[0] = 0xe8;
    put_u32(h->patch + 1, (uint32_t)(uintptr_t)destination - (uint32_t)(uintptr_t)(site + 5));
}
static int rollback_all(void)
{
    int i, retry, ok = 1;
    for (i = 3; i >= 0; --i) {
        for (retry = 0; retry < 3 && hooks[i].changed; ++retry) restore_hook(&hooks[i]);
        if (hooks[i].changed) ok = 0;
    }
    if (!ok || installation_failed) {
        return 0;
    }
    if (clock_code) VirtualFree(clock_code, 0, MEM_RELEASE);
    if (clock_state) VirtualFree(clock_state, 0, MEM_RELEASE);
    clock_code = clock_state = NULL; engine_installed = radio_installed = 0;
    return 1;
}
static int install_all(uint8_t *engine, uint8_t *server)
{
    static const uint8_t clock_signature[] = {0x8b,0x11,0xff,0x52,0x38,0xd9,0x5c,0x24,0x04,0x8b,0x74,0x24,0x10,0x85,0xf6};
    static const uint8_t pause_signature[] = {0xe8,0x5b,0xf0,0x00,0x00,0x85,0xc0,0xa3};
    static const uint8_t radio_signature[] = {0x6a,0x01,0x8b,0xce,0xe8,0x68,0x60,0xdd,0xff};
    static const uint8_t activate_signature[] = {0x8b,0xce,0xe8,0x12,0x4d,0xdd,0xff,0x83,0xbe,0x4c,0x07,0x00,0x00,0xff};
    DWORD old; unsigned i;
    if (engine_installed || radio_installed || installation_failed || clock_code) return 0;
    if (!engine || !server || has_old_spcode(engine) ||
        !unique_code_signature(engine, clock_signature, sizeof(clock_signature), CLOCK_HOOK_RVA) ||
        !unique_code_signature(engine, pause_signature, sizeof(pause_signature), PAUSE_HOOK_RVA) ||
        !unique_code_signature(server, radio_signature, sizeof(radio_signature), RADIO_SIGNATURE_RVA) ||
        !unique_code_signature(server, activate_signature, sizeof(activate_signature), RADIO_ACTIVATE_CALL_RVA - 2) ||
        memcmp(server + RADIO_FAKE_SILENCE_THUNK_RVA, "\xe9\x47\x67\x0a\x00", 5) ||
        memcmp(server + RADIO_BASE_ACTIVATE_THUNK_RVA, "\xe9\x95\xf9\x09\x00", 5)) {
        return 0;
    }
    engine_module = engine; server_module = server;
    original_fake_silence = (FakeSilenceFn)(server + RADIO_FAKE_SILENCE_THUNK_RVA);
    original_base_activate = (BaseActivateFn)(server + RADIO_BASE_ACTIVATE_THUNK_RVA);
    clock_code = (uint8_t *)VirtualAlloc(NULL, 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    clock_state = (uint8_t *)VirtualAlloc(NULL, 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!clock_code || !clock_state) { rollback_all(); return 0; }
    memcpy(clock_code, kClockCode, CLOCK_CODE_SIZE); relocate_helpers(clock_code, clock_state, engine);
    ((ClockState *)clock_state)->radio_phase = radio_sample_phase;
    if (!VirtualProtect(clock_code, 0x1000, PAGE_EXECUTE_READ, &old) ||
        !FlushInstructionCache(GetCurrentProcess(), clock_code, CLOCK_CODE_SIZE)) { rollback_all(); return 0; }
    prepare_hook(&hooks[0], engine + CLOCK_HOOK_RVA, clock_code + CLOCK_CLOCK_OFFSET);
    prepare_hook(&hooks[1], engine + PAUSE_HOOK_RVA, clock_code + CLOCK_PAUSE_OFFSET);
    prepare_hook(&hooks[2], server + RADIO_ACTIVATE_CALL_RVA, (uint8_t *)radio_base_activate);
    prepare_hook(&hooks[3], server + RADIO_CALL_RVA, (uint8_t *)radio_fake_silence);
    for (i = 0; i < 4; ++i) if (!install_hook(&hooks[i])) { rollback_all(); return 0; }
    engine_installed = radio_installed = 1;
    return 1;
}
__declspec(dllexport) void loaded_engine(void)
{
    /* Loader callback order may differ. Installation waits for both modules. */
    uint8_t *engine = (uint8_t *)GetModuleHandleA("engine.dll");
    uint8_t *server = (uint8_t *)GetModuleHandleA("vampire.dll");
    if (engine && server) install_all(engine, server);
}
__declspec(dllexport) void loaded_vampire(void) { loaded_engine(); }
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)instance; (void)reason; (void)reserved; return TRUE;
}
