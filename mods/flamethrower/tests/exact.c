/* Actual finalized VTM loading in a standalone fixture, never the game. */
#include "../../../infra/common/native_fixture.h"
#define SITE 0x3e3673u
#define BYTE (SITE + 1u)
static uint8_t *server;
static int missing_module, protect_calls, flush_calls;
static int protect_fail_at, protect_fail_from, flush_fail_at, flush_fail_from;
static int change_on_protect;
static HMODULE WINAPI modules(LPCSTR name)
{
    return !missing_module && !strcmp(name, "vampire.dll") ? (HMODULE)server : NULL;
}
static BOOL WINAPI protect(LPVOID at, SIZE_T n, DWORD flags, PDWORD old)
{
    ++protect_calls;
    if (protect_calls == protect_fail_at || (protect_fail_from && protect_calls >= protect_fail_from)) return FALSE;
    {
        BOOL result = VirtualProtect(at, n, flags, old);
        if (result && change_on_protect && flags == PAGE_EXECUTE_READWRITE) {
            server[BYTE] = 2;
            change_on_protect = 0;
        }
        return result;
    }
}
static BOOL WINAPI flush(HANDLE process, LPCVOID at, SIZE_T n)
{
    ++flush_calls;
    if (flush_calls == flush_fail_at || (flush_fail_from && flush_calls >= flush_fail_from)) return FALSE;
    return FlushInstructionCache(process, at, n);
}
static DWORD page_protection(void)
{
    MEMORY_BASIC_INFORMATION info;
    check(VirtualQuery(server + BYTE, &info, sizeof(info)) == sizeof(info), "query patch-page protection");
    return info.Protect;
}
static void writable(void)
{
    DWORD old;
    check(VirtualProtect(server + BYTE, 1, PAGE_EXECUTE_READWRITE, &old), "prepare fixture code page");
}
static void readonly(void)
{
    DWORD old;
    check(VirtualProtect(server + BYTE, 1, PAGE_EXECUTE_READ, &old), "fixture original RX page");
}
static HMODULE open_plugin(const char *path)
{
    HMODULE h = LoadLibraryA(path);
    check(h != NULL, "actual clean candidate loads at relocated address");
    imports(h, "GetModuleHandleA", modules);
    imports(h, "VirtualProtect", protect);
    imports(h, "FlushInstructionCache", flush);
    protect_calls = flush_calls = 0;
    return h;
}
static void load(HMODULE h)
{
    void (__cdecl *fn)(void) = (void *)GetProcAddress(h, "loaded_vampire");
    check(fn != NULL, "sole loader callback is available");
    fn();
}
static void no_faults(void)
{
    protect_fail_at = protect_fail_from = flush_fail_at = flush_fail_from = 0;
}
static void exact_difference(const uint8_t *before, unsigned size)
{
    unsigned i, differences = 0;
    for (i = 0; i < size; ++i) {
        if (server[i] != before[i]) {
            ++differences;
            check(i == BYTE && before[i] == 1 && server[i] == 0, "only flamethrower suppression operand changes");
        }
    }
    check(differences == 1, "exactly one changed native byte");
}
int main(int argc, char **argv)
{
    HMODULE h;
    IMAGE_NT_HEADERS32 *nt;
    uint8_t *before;
    unsigned anchors[] = {SITE, SITE + 2, 0x1c2b10, 0x33054c, 0x3e3570};
    unsigned i, size;
    FILE *certificate;
    check(argc == 4, "plugin/server/certificate arguments");
    server = map_image(argv[2]);
    nt = (void *)(server + ((IMAGE_DOS_HEADER *)server)->e_lfanew);
    size = nt->OptionalHeader.SizeOfImage;
    before = malloc(size); check(before != NULL, "full native-image comparison buffer");
    memcpy(before, server, size);
    missing_module = 1; h = open_plugin(argv[1]); load(h);
    check(!protect_calls && !memcmp(before, server, size), "missing module refuses without writes");
    FreeLibrary(h); missing_module = 0;
    for (i = 0; i < sizeof(anchors)/sizeof(anchors[0]); ++i) {
        uint8_t saved = server[anchors[i]]; server[anchors[i]] ^= 0xff;
        h = open_plugin(argv[1]); load(h);
        check(!protect_calls && server[BYTE] == 1, "mismatched signature refuses before memory protection");
        FreeLibrary(h); server[anchors[i]] = saved;
    }
    {DWORD saved = nt->FileHeader.TimeDateStamp; nt->FileHeader.TimeDateStamp ^= 1;
     h = open_plugin(argv[1]); load(h); check(!protect_calls, "unsupported server timestamp refuses");
     FreeLibrary(h); nt->FileHeader.TimeDateStamp = saved;}
    {DWORD saved = nt->OptionalHeader.SizeOfImage; nt->OptionalHeader.SizeOfImage ^= 0x1000;
     h = open_plugin(argv[1]); load(h); check(!protect_calls, "unsupported image size refuses");
     FreeLibrary(h); nt->OptionalHeader.SizeOfImage = saved;}
    server[BYTE] = 0; h = open_plugin(argv[1]); load(h);
    check(!protect_calls, "already modified operand not claimed");
    FreeLibrary(h); check(server[BYTE] == 0, "foreign zero operand retained on unload"); server[BYTE] = 1;
    readonly();
    change_on_protect = 1; h = open_plugin(argv[1]); load(h);
    check(server[BYTE] == 2 && page_protection() == PAGE_EXECUTE_READ, "site revalidation preserves modification during protection API");
    FreeLibrary(h); writable(); server[BYTE] = 1; readonly();
    for (i = 1; i <= 2; ++i) {
        protect_fail_at = (int)i; h = open_plugin(argv[1]); load(h);
        check(server[BYTE] == 1 && page_protection() == PAGE_EXECUTE_READ, "protection refusal rolls bytes and RX protection back");
        no_faults(); FreeLibrary(h);
    }
    flush_fail_at = 1; h = open_plugin(argv[1]); load(h);
    check(server[BYTE] == 1 && page_protection() == PAGE_EXECUTE_READ, "cache-flush refusal restores original operand and RX page");
    no_faults(); FreeLibrary(h);
    flush_fail_from = 1; h = open_plugin(argv[1]); load(h);
    check(server[BYTE] == 1 && page_protection() == PAGE_EXECUTE_READ, "persistent flush refusal leaves no patch/trampoline");
    no_faults(); FreeLibrary(h);
    protect_fail_from = 2; h = open_plugin(argv[1]); load(h);
    check(server[BYTE] == 1, "persistent protection refusal restores original byte");
    no_faults(); FreeLibrary(h);
    check(page_protection() == PAGE_EXECUTE_READ, "pending original protection restored on unload after OS recovers");
    h = open_plugin(argv[1]); load(h);
    exact_difference(before, size);
    check(page_protection() == PAGE_EXECUTE_READ, "successful install preserves RX page");
    {int saved = protect_calls; load(h); check(protect_calls == saved, "duplicate loader callback is idempotent");}
    certificate = fopen(argv[3], "wb"); check(certificate != NULL, "write external fixture certificate");
    fprintf(certificate, "{\"rva\":%u,\"operand\":%u,\"changed_bytes\":1,\"scope\":\"actual finalized VTM in standalone Windows fixture\"}\n", BYTE, server[BYTE]);
    fclose(certificate);
    check(FreeLibrary(h), "candidate unloads");
    check(!memcmp(before, server, size) && page_protection() == PAGE_EXECUTE_READ, "owned byte and original page restored on unload");
    h = open_plugin(argv[1]); load(h); writable(); server[BYTE] = 2; readonly();
    check(FreeLibrary(h) && server[BYTE] == 2, "unload preserves later foreign operand");
    writable(); server[BYTE] = 1; readonly();
    check(!memcmp(before, server, size), "fixture native image ultimately matches its original");
    free(before); VirtualFree(server, 0, MEM_RELEASE);
    puts("PASS exact clean VTM: identity/signature/conflict guards, API refusals, one byte only, idempotence, RX protection and owned unload");
    return 0;
}
