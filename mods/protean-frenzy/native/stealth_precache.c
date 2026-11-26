/* Register children before their parent emitters at native server precache. */
#include "runtime.h"
#include <string.h>

typedef int (__attribute__((thiscall)) *PrecacheParticle)(void *, const char *, int);

static unsigned char *server;
static void (*original_precache)(void);

static void __cdecl precache_finisher(void)
{
    static const char *const names[] = {
        "pfi_wound_blood_mm", "pfi_wound_blood_mf",
        "pfi_wound_blood_fm", "pfi_wound_blood_ff", "pfi_claws_stock",
        "pfi_wound_jet_mm", "pfi_wound_jet_mf",
        "pfi_wound_jet_fm", "pfi_wound_jet_ff",
        "pfi_stealth_mm", "pfi_stealth_mf", "pfi_stealth_fm", "pfi_stealth_ff"
    };
    void *engine_server = *(void **)(server + 0x70b22c);
    void **table = *(void ***)engine_server;
    PrecacheParticle precache = (PrecacheParticle)table[0x44 / sizeof(void *)];
    for (unsigned i = 0; i < sizeof(names) / sizeof(*names); ++i)
        precache(engine_server, names[i], 1);
}

/* Keep the original call and the register state it leaves to its caller. */
__attribute__((naked)) static void __cdecl precache_bridge(void)
{
    __asm__ volatile(
        "calll *%0\n\t"
        "pushfl\n\t"
        "pushal\n\t"
        "subl $528, %%esp\n\t"
        "leal 15(%%esp), %%eax\n\t"
        "andl $-16, %%eax\n\t"
        "fxsave (%%eax)\n\t"
        "calll %c1\n\t"
        "leal 15(%%esp), %%eax\n\t"
        "andl $-16, %%eax\n\t"
        "fxrstor (%%eax)\n\t"
        "addl $528, %%esp\n\t"
        "popal\n\t"
        "popfl\n\t"
        "retl\n\t"
        : : "m"(original_precache), "i"(precache_finisher) : "memory");
}

void pfi_stealth_precache_server(void)
{
    if (server)
        return;
    unsigned char *base = (void *)GetModuleHandleA("vampire.dll");
    if (!base)
        return;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew != 0xe0)
        return;
    const IMAGE_NT_HEADERS32 *pe = (const IMAGE_NT_HEADERS32 *)(base + dos->e_lfanew);
    if (pe->Signature != IMAGE_NT_SIGNATURE || pe->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        pe->FileHeader.TimeDateStamp != 0x41afafae || pe->OptionalHeader.SizeOfImage != 0xab9000)
        return;
    /* This exact call follows the vanilla particle-precache list. Resolve
       the original branch and the relocated adjacent interface pointer. */
    unsigned char *site = base + 0x33fd45;
    static const unsigned char before[] = {0x8b, 0x01, 0xff, 0x50, 0x44};
    unsigned char *original_engine_slot;
    int32_t target;
    memcpy(&target, site + 1, sizeof(target));
    memcpy(&original_engine_slot, site + 7, sizeof(original_engine_slot));
    if (memcmp(site - sizeof(before), before, sizeof(before)) != 0 ||
        site[0] != 0xe8 || site + 5 + target != base + 0x15695 ||
        site[5] != 0x8b || site[6] != 0x0d || original_engine_slot != base + 0x70b22c ||
        memcmp(base + 0x622a34, "Stealth_claws_emitter", sizeof("Stealth_claws_emitter")) != 0)
        return;
    original_precache = (void (*)(void))(site + 5 + target);
    server = base;
    int32_t replacement = (int32_t)((uintptr_t)precache_bridge - (uintptr_t)(site + 5));
    PfiPatch patch = {.site = site + 1, .size = sizeof(replacement)};
    memcpy(patch.before, &target, sizeof(target));
    memcpy(patch.after, &replacement, sizeof(replacement));
    if (pfi_commit(&patch, 1) == 0) {
        server = NULL;
        original_precache = NULL;
    }
}
