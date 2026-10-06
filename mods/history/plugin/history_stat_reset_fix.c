#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>

/* UP 11.5 Plus vampire.dll (SHA-256 C546F4DE...E48A76F). */
enum {
    HISTORY_SIGNATURE_RVA = 0x0d6dca,
    HISTORY_HOOK_RVA = 0x0d6dd8,
    HISTORY_HOOK_SIZE = 9,
    HISTORY_RETURN_RVA = 0x0d6de1,
    NONE_SIGNATURE_RVA = 0x0d6de2,
    NONE_HOOK_RVA = 0x0d6deb,
    NONE_HOOK_SIZE = 9,
    NONE_RETURN_RVA = 0x0d6df4,
    CLAN_GUARD_SIGNATURE_RVA = 0x206ac4,
    CLAN_GUARD_HOOK_RVA = 0x206ad1,
    CLAN_GUARD_HOOK_SIZE = 8,
    CLAN_RESET_BODY_RVA = 0x206ad9,
    CLAN_RESET_SKIP_RVA = 0x206bcf,
    GET_CLAN_RVA = 0x0040d9,
    SET_HISTORY_RVA = 0x005024,
    SET_CLAN_RVA = 0x011004,
    GET_RAW_RVA = 0x0048e5,
    SET_RAW_RVA = 0x011e46,
    CLAN_MANAGER_RVA = 0x74f028,
    GUARD_HELPER_OFFSET = 0x100,
    NONE_HELPER_OFFSET = 0x200
};

static const uint8_t kHistorySignature[] = {
    0x0f,0x84,0x4c,0x01,0x00,0x00,0x57,0x8b,0xce,0xe8,0x4c,0xe2,0xf2,0xff,
    0x5f,0x5e,0x5b,0x81,0xc4,0xa0,0x00,0x00,0x00,0xc3,0x6a,0xff
};

static const uint8_t kClanGuardSignature[] = {
    0x8b,0x74,0x24,0x38,0x8b,0xce,0xe8,0x0a,0xd6,0xdf,0xff,0x8b,0xe8,
    0x3b,0xdd,0x0f,0x84,0xf6,0x00,0x00,0x00,0x6a,0xff,0x8b,0xce,
    0xe8,0x42,0xe5,0xdf,0xff
};

static const uint8_t kNoneSignature[] = {
    0x6a,0xff,0x8b,0xce,0xe8,0x39,0xe2,0xf2,0xff,0x5f,0x5e,0x5b,
    0x81,0xc4,0xa0,0x00,0x00,0x00,0xc3
};

static void *volatile allow_same_clan_once;
static uint8_t *helper_page;
static uint8_t *server_module;
static uint8_t *client_module;
static int attempted;

typedef int (__thiscall *GetClanFn)(void *);
typedef void (__thiscall *SetClanFn)(void *, int, void *);
typedef int (__thiscall *GetRawFn)(void *, int);
typedef void (__thiscall *SetRawFn)(void *, int, int);
typedef void (__thiscall *InitCreationPoolFn)(void *, int);

/* Stock Reset Stats uses this initializer to read all seven category budgets
   from ClanDoc. The server reset does not reset the separate Sheet counters.
   Its creation flag is the same explicit flag used by the stock UI guard. */
static void reset_creation_pool(int clan)
{
    uint8_t *character, *sheet;
    if (!client_module) return;
    character = *(uint8_t **)(client_module + 0x5fb14c);
    if (!character || !*(int *)(character + 0x274)) return;
    sheet = *(uint8_t **)(character + 0xedc);
    if (sheet) ((InitCreationPoolFn)(client_module + 0x17d930))(sheet, clan);
}

static void *attribute_group(void *player)
{
    uint8_t *p = (uint8_t *)player;
    int count = *(int *)(p + 0x13bc), i;
    uint8_t **groups = *(uint8_t ***)(p + 0x13c0);
    if (!groups || count <= 0 || count > 32) return NULL;
    for (i = 0; i < count; ++i)
        if (groups[i] && *(int *)(groups[i] + 0x10) == 0 &&
            *(int *)(groups[i] + 4) == 35) return groups[i];
    return NULL;
}

/* The creation UI funds purchases with Experience. SetClan clears that stat
   along with the old allocation, even for None. Preserve the existing value
   through native accessors; never synthesize XP. Reinitialize creation-only
   category counters through the stock initializer, independently of XP. */
static void reset_same_clan(void *player)
{
    void *group = attribute_group(player);
    int experience, clan;
    if (!group || allow_same_clan_once) return;
    experience = ((GetRawFn)(server_module + GET_RAW_RVA))(group, 34);
    clan = ((GetClanFn)(server_module + GET_CLAN_RVA))(player);
    allow_same_clan_once = player;
    ((SetClanFn)(server_module + SET_CLAN_RVA))(
        server_module + CLAN_MANAGER_RVA,
        clan, player);
    allow_same_clan_once = NULL;
    group = attribute_group(player);
    if (group) ((SetRawFn)(server_module + SET_RAW_RVA))(group, 34, experience);
    reset_creation_pool(clan);
}

static IMAGE_NT_HEADERS32 *pe_headers(uint8_t *module)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)module;
    IMAGE_NT_HEADERS32 *nt;
    if (!module || dos->e_magic != IMAGE_DOS_SIGNATURE ||
        dos->e_lfanew < 0 || dos->e_lfanew > 0x1000) return NULL;
    nt = (IMAGE_NT_HEADERS32 *)(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC) return NULL;
    return nt;
}

static int unique_bytes(uint8_t *module, IMAGE_NT_HEADERS32 *nt,
                        uint32_t expected_rva, const uint8_t *pattern,
                        unsigned int pattern_size)
{
    IMAGE_SECTION_HEADER *sections = IMAGE_FIRST_SECTION(nt);
    unsigned int section_index, matches = 0;
    if ((uint64_t)expected_rva + pattern_size > nt->OptionalHeader.SizeOfImage)
        return 0;
    for (section_index = 0; section_index < nt->FileHeader.NumberOfSections; ++section_index) {
        uint32_t start = sections[section_index].VirtualAddress;
        uint32_t size = sections[section_index].Misc.VirtualSize;
        uint32_t rva;
        if (!(sections[section_index].Characteristics & IMAGE_SCN_MEM_EXECUTE) ||
            (uint64_t)start + size > nt->OptionalHeader.SizeOfImage || size < pattern_size)
            continue;
        for (rva = start; (uint64_t)rva + pattern_size <= (uint64_t)start + size; ++rva) {
            if (memcmp(module + rva, pattern, pattern_size) != 0) continue;
            if (rva != expected_rva) return 0;
            ++matches;
        }
    }
    return matches == 1;
}

static void put_u32(uint8_t *at, uint32_t value)
{
    memcpy(at, &value, sizeof(value));
}

static unsigned int emit_rel32(uint8_t *code, unsigned int at, uint8_t opcode,
                               uint8_t *destination)
{
    code[at++] = opcode;
    put_u32(code + at, (uint32_t)(uintptr_t)destination -
                       (uint32_t)(uintptr_t)(code + at + 4));
    return at + 4;
}

static void make_jump(uint8_t *output, unsigned int count,
                      uint8_t *site, uint8_t *destination)
{
    unsigned int i;
    output[0] = 0xe9;
    put_u32(output + 1, (uint32_t)(uintptr_t)destination -
                        (uint32_t)(uintptr_t)(site + 5));
    for (i = 5; i < count; ++i) output[i] = 0x90;
}

#include "install_hooks.h"

static unsigned int build_guard_helper(uint8_t *code, uint8_t *module)
{
    unsigned int at = 0;
    code[at++] = 0x3b; code[at++] = 0xdd;                 /* cmp ebx,ebp */
    code[at++] = 0x75; code[at++] = 0x12;                 /* jne reset */
    code[at++] = 0x39; code[at++] = 0x35;                 /* cmp [owner],esi */
    put_u32(code + at, (uint32_t)(uintptr_t)&allow_same_clan_once); at += 4;
    code[at++] = 0x75; code[at++] = 0x0f;                 /* jne skip */
    code[at++] = 0xc7; code[at++] = 0x05;                 /* consume owner */
    put_u32(code + at, (uint32_t)(uintptr_t)&allow_same_clan_once); at += 4;
    put_u32(code + at, 0); at += 4;
    at = emit_rel32(code, at, 0xe9, module + CLAN_RESET_BODY_RVA);
    at = emit_rel32(code, at, 0xe9, module + CLAN_RESET_SKIP_RVA);
    return at;
}

static unsigned int build_history_helper(uint8_t *code, uint8_t *module,
                                         uint32_t return_rva)
{
    unsigned int at = 0;
    code[at++] = 0x56;                                    /* push esi (player) */
    at = emit_rel32(code, at, 0xe8, (uint8_t *)reset_same_clan);
    code[at++] = 0x83; code[at++] = 0xc4; code[at++] = 4;  /* cdecl argument */
    if (return_rva == NONE_RETURN_RVA) {
        code[at++] = 0x6a; code[at++] = 0xff;             /* None is always -1 */
    } else code[at++] = 0x57;                            /* selected History */
    code[at++] = 0x8b; code[at++] = 0xce;                 /* mov ecx,esi */
    at = emit_rel32(code, at, 0xe8, module + SET_HISTORY_RVA);
    code[at++] = 0x5f; code[at++] = 0x5e; code[at++] = 0x5b;
    code[at++] = 0x81; code[at++] = 0xc4; code[at++] = 0xa0;
    code[at++] = 0x00; code[at++] = 0x00; code[at++] = 0x00;
    at = emit_rel32(code, at, 0xe9, module + return_rva);
    return at;
}

__declspec(dllexport) void loaded_vampire(void)
{
    uint8_t *module, *guard_helper, *none_helper;
    IMAGE_NT_HEADERS32 *nt;
    DWORD old_protection;
    unsigned int i;

    if (attempted) return;
    attempted = 1;
    module = (uint8_t *)GetModuleHandleA("vampire.dll");
    nt = pe_headers(module);
    if (!nt) return;
    if (!unique_bytes(module, nt, HISTORY_SIGNATURE_RVA,
                      kHistorySignature, sizeof(kHistorySignature)) ||
        !unique_bytes(module, nt, CLAN_GUARD_SIGNATURE_RVA,
                      kClanGuardSignature, sizeof(kClanGuardSignature)) ||
        !unique_bytes(module, nt, NONE_SIGNATURE_RVA,
                      kNoneSignature, sizeof(kNoneSignature)) ||
        !unique_bytes(module, nt, GET_RAW_RVA, (const uint8_t *)"\xe9\xb6\xc3\x1f\x00", 5) ||
        !unique_bytes(module, nt, SET_RAW_RVA, (const uint8_t *)"\xe9\x95\xea\x1e\x00", 5)) return;
    server_module = module;

    helper_page = (uint8_t *)VirtualAlloc(NULL, 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!helper_page) return;
    guard_helper = helper_page + GUARD_HELPER_OFFSET;
    none_helper = helper_page + NONE_HELPER_OFFSET;
    build_history_helper(helper_page, module, HISTORY_RETURN_RVA);
    build_guard_helper(guard_helper, module);
    build_history_helper(none_helper, module, NONE_RETURN_RVA);
    if (!VirtualProtect(helper_page, 0x1000, PAGE_EXECUTE_READ, &old_protection) ||
        !FlushInstructionCache(GetCurrentProcess(), helper_page, 0x1000)) {
        VirtualFree(helper_page, 0, MEM_RELEASE); helper_page = NULL;
        return;
    }
    prepare_hook(&hooks[0], module + CLAN_GUARD_HOOK_RVA, CLAN_GUARD_HOOK_SIZE, guard_helper);
    prepare_hook(&hooks[1], module + HISTORY_HOOK_RVA, HISTORY_HOOK_SIZE, helper_page);
    prepare_hook(&hooks[2], module + NONE_HOOK_RVA, NONE_HOOK_SIZE, none_helper);
    for (i = 0; i < 3; ++i) if (!install_hook(&hooks[i])) { rollback_all(); return; }
}

/* No client hooks: validate the stock initializer and its creation-state global.
   Absolute operands are relocated to the actual module base before validation. */
__declspec(dllexport) void loaded_client(void)
{
    uint8_t *module = (uint8_t *)GetModuleHandleA("client.dll");
    IMAGE_NT_HEADERS32 *nt = pe_headers(module);
    uint8_t guard[] = {0xa1,0,0,0,0,0x85,0xc0,0x74,0x0c,0x8b,0x88,
        0x74,0x02,0,0,0x85,0xc9,0x0f,0x95,0xc0,0xc3,0x32,0xc0,0xc3};
    uint8_t init[] = {0x51,0x55,0x8b,0x2d,0,0,0,0,0x56,0x8b,0xf1,
        0x85,0xed,0x0f,0x84,0x51,0x02,0,0,0x53,0x57,0x8b,0x7c,0x24,0x18};
    if (client_module || !nt || nt->OptionalHeader.SizeOfImage < 0x5fb150) return;
    put_u32(guard + 1, (uint32_t)(uintptr_t)(module + 0x5fb14c));
    put_u32(init + 4, (uint32_t)(uintptr_t)(module + 0x4a0d50));
    if (!unique_bytes(module, nt, 0x1713e0, guard, sizeof(guard)) ||
        !unique_bytes(module, nt, 0x17d930, init, sizeof(init))) return;
    client_module = module;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)instance; (void)reason; (void)reserved;
    return TRUE;
}
