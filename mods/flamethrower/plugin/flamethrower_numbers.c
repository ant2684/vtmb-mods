/* Original MIT workspace source. Interoperability constants identify the
   locally supplied Bloodlines server; no game module is distributed here. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#define SITE 0x3e3673u
#define BYTE (SITE + 1u)
static uint8_t *server;
static int installed, pending_protection;
static DWORD pending_old;
static const uint8_t site_signature[] = {0x6a,0x01,0x8d,0x4c,0x24,0x20,0xe8,0x17,0xd5,0xc2,0xff};
static const uint8_t setter_signature[] = {0x8a,0x44,0x24,0x04,0x88,0x41,0x4a,0xc2,0x04,0x00};
static const uint8_t gate_signature[] = {0x8b,0xcd,0xe8,0xb5,0xa2,0xcd,0xff,0x84,0xc0,0x75,0x3c};
static const uint8_t builder_signature[] = {0x81,0xec,0xe0,0x00,0x00,0x00,0x53,0x55,0x56,0x57};
static int equal(const uint8_t *a, const uint8_t *b, unsigned n)
{
    unsigned i;
    for (i = 0; i < n; ++i) if (a[i] != b[i]) return 0;
    return 1;
}
static int site_matches(uint8_t value)
{
    unsigned i;
    for (i = 0; i < sizeof(site_signature); ++i)
        if (server[SITE + i] != (i == 1 ? value : site_signature[i])) return 0;
    return 1;
}
static int supported(uint8_t *module)
{
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    if (!module) return 0;
    dos = (IMAGE_DOS_HEADER *)module;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 || dos->e_lfanew > 0x1000) return 0;
    nt = (IMAGE_NT_HEADERS32 *)(module + dos->e_lfanew);
    return nt->Signature == IMAGE_NT_SIGNATURE && nt->FileHeader.Machine == IMAGE_FILE_MACHINE_I386 &&
        nt->FileHeader.TimeDateStamp == 0x41afafae && nt->OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC &&
        nt->OptionalHeader.SizeOfImage == 0xab9000 &&
        equal(module + SITE, site_signature, sizeof(site_signature)) &&
        equal(module + 0x1c2b10, setter_signature, sizeof(setter_signature)) &&
        equal(module + 0x33054c, gate_signature, sizeof(gate_signature)) &&
        equal(module + 0x3e3570, builder_signature, sizeof(builder_signature));
}
static void restore_protection(DWORD old)
{
    DWORD ignored;
    pending_old = old;
    pending_protection = !VirtualProtect(server + BYTE, 1, old, &ignored);
    if (pending_protection)
        pending_protection = !VirtualProtect(server + BYTE, 1, old, &ignored);
}
static int enable_numbers(void)
{
    DWORD old, ignored;
    if (!VirtualProtect(server + BYTE, 1, PAGE_EXECUTE_READWRITE, &old)) return 0;
    if (!site_matches(1)) {
        restore_protection(old);
        return 0;
    }
    *(volatile uint8_t *)(server + BYTE) = 0;
    if (FlushInstructionCache(GetCurrentProcess(), server + BYTE, 1) &&
        VirtualProtect(server + BYTE, 1, old, &ignored)) return 1;
    /* A failed transaction never keeps the new operand. No trampoline or
       pointer into this DLL is installed, including in OS-failure cases. */
    *(volatile uint8_t *)(server + BYTE) = 1;
    FlushInstructionCache(GetCurrentProcess(), server + BYTE, 1);
    restore_protection(old);
    return 0;
}
__declspec(dllexport) void loaded_vampire(void)
{
    uint8_t *module;
    if (installed || pending_protection) return;
    module = (uint8_t *)GetModuleHandleA("vampire.dll");
    if (!supported(module)) return;
    server = module;
    installed = enable_numbers();
}
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    DWORD old;
    (void)instance;
    if (reason == DLL_PROCESS_DETACH && !reserved && server &&
        (uint8_t *)GetModuleHandleA("vampire.dll") == server) {
        if (installed && site_matches(0) &&
            VirtualProtect(server + BYTE, 1, PAGE_EXECUTE_READWRITE, &old)) {
            *(volatile uint8_t *)(server + BYTE) = 1;
            FlushInstructionCache(GetCurrentProcess(), server + BYTE, 1);
            restore_protection(old);
        } else if (pending_protection) restore_protection(pending_old);
    }
    return TRUE;
}
