/* Transactional installation. Never free a helper while a surviving jump
   can still reference it. Never overwrite bytes owned by another patch. */
typedef struct {
    uint8_t *site, original[9], patch[9];
    unsigned int size;
    DWORD protection;
    int changed;
} Hook;
static Hook hooks[3];

static void prepare_hook(Hook *h, uint8_t *site, unsigned int size, uint8_t *dest)
{
    memset(h, 0, sizeof(*h)); h->site = site; h->size = size;
    memcpy(h->original, site, size); make_jump(h->patch, size, site, dest);
}
static int install_hook(Hook *h)
{
    DWORD ignored;
    if (memcmp(h->site, h->original, h->size)) return 0;
    if (!VirtualProtect(h->site, h->size, PAGE_EXECUTE_READWRITE, &h->protection)) return 0;
    if (memcmp(h->site, h->original, h->size)) {
        VirtualProtect(h->site, h->size, h->protection, &ignored); return 0;
    }
    memcpy(h->site, h->patch, h->size); h->changed = 1;
    if (!FlushInstructionCache(GetCurrentProcess(), h->site, h->size)) return 0;
    if (!VirtualProtect(h->site, h->size, h->protection, &ignored)) return 0;
    return memcmp(h->site, h->patch, h->size) == 0;
}
static int restore_hook(Hook *h)
{
    DWORD old, ignored; int ok = 1;
    if (!h->changed) return 1;
    if (memcmp(h->site, h->patch, h->size) && memcmp(h->site, h->original, h->size)) return 0;
    if (!VirtualProtect(h->site, h->size, PAGE_EXECUTE_READWRITE, &old)) return 0;
    if (memcmp(h->site, h->patch, h->size) && memcmp(h->site, h->original, h->size)) {
        VirtualProtect(h->site, h->size, h->protection, &ignored); return 0;
    }
    memcpy(h->site, h->original, h->size);
    if (!FlushInstructionCache(GetCurrentProcess(), h->site, h->size)) ok = 0;
    if (!VirtualProtect(h->site, h->size, h->protection, &ignored)) ok = 0;
    if (ok) h->changed = 0;
    return ok;
}
static int rollback_all(void)
{
    int i, retry, ok = 1;
    for (i = 2; i >= 0; --i) {
        for (retry = 0; retry < 3 && hooks[i].changed; ++retry) restore_hook(&hooks[i]);
        if (hooks[i].changed) ok = 0;
    }
    if (ok && helper_page) { VirtualFree(helper_page, 0, MEM_RELEASE); helper_page = NULL; }
    return ok;
}
