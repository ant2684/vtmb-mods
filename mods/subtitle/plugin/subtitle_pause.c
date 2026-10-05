#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "generated_clock.h"

/* All addresses below are guarded anchors for the recorded UP 11.5 modules. */
enum {
    CLOCK_HOOK_RVA = 0x1188b0, PAUSE_HOOK_RVA = 0x2d130,
    RADIO_CALL_RVA = 0x22c807, RADIO_SIGNATURE_RVA = 0x22c803,
    RADIO_FAKE_SILENCE_THUNK_RVA = 0x2874,
    RADIO_ACTIVATE_CALL_RVA = 0x22c50f, RADIO_BASE_ACTIVATE_THUNK_RVA = 0x1226,
    PAUSED_RVA = 0x314874, PLAT_TIME_IAT_RVA = 0x173324,
    CHANNEL_COUNT_RVA = 0x13107d4, CHANNEL_ARRAY_RVA = 0x1310b08,
    CHANNEL_SIZE = 0xa0, MAX_CHANNELS = 128, MAX_RADIOS = 32
};

typedef struct {
    uint32_t initialized, paused;
    double pause_start, total_paused, raw_now, logical_now;
    int (__cdecl *radio_phase)(uint8_t *, int, int);
} ClockState;

typedef struct {
    uint8_t *channel, *source, *sfx, *mixer;
    int position, rate;
} RadioChannel;

typedef struct {
    void *entity;
    uint8_t *channel, *source, *mixer, *sfx;
    uint32_t index, serial, generation, activation;
    double epoch, off_time;
    int epoch_valid, off_position, off_rate, seen_on, armed;
    uint8_t *phase_source, *phase_mixer, *phase_sfx, *phase_channel;
    int loop_samples, loop_checked;
} RadioState;

typedef void (__thiscall *FakeSilenceFn)(void *, int);
typedef int (__thiscall *MixerDecodeFn)(void *, void **, int, int);
typedef int (__thiscall *SourceIntegerFn)(void *);
typedef double (__cdecl *PlatformTimeFn)(void);

static uint8_t *engine_module, *clock_code, *clock_state;
static uint8_t *server_module, *location_table;
static uint32_t location_player = 0xffffffff, location_generation, activation_generation;
static double location_last_time = -1.0;
typedef void (__thiscall *BaseActivateFn)(void *);
static BaseActivateFn original_base_activate;
static FakeSilenceFn original_fake_silence;
static RadioState radios[MAX_RADIOS];
static int engine_installed, radio_installed;

static int unique_code_signature(uint8_t *module, const uint8_t *signature,
                                 size_t length, uint32_t expected_rva)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)module;
    IMAGE_NT_HEADERS32 *nt;
    IMAGE_SECTION_HEADER *section;
    unsigned int matches = 0;
    unsigned int index;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 || dos->e_lfanew > 0x1000)
        return 0;
    nt = (IMAGE_NT_HEADERS32 *)(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC)
        return 0;
    if ((uint64_t)expected_rva + length > nt->OptionalHeader.SizeOfImage) return 0;
    section = IMAGE_FIRST_SECTION(nt);
    for (index = 0; index < nt->FileHeader.NumberOfSections; ++index) {
        uint32_t start = section[index].VirtualAddress;
        uint32_t size = section[index].Misc.VirtualSize;
        uint32_t at;
        if (!(section[index].Characteristics & IMAGE_SCN_MEM_EXECUTE) ||
            (uint64_t)start + size > nt->OptionalHeader.SizeOfImage || size < length)
            continue;
        for (at = start; (uint64_t)at + length <= (uint64_t)start + size; ++at)
            if (memcmp(module + at, signature, length) == 0) {
                if (at != expected_rva) return 0;
                ++matches;
            }
    }
    return matches == 1;
}

static int has_old_spcode(uint8_t *module)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)module;
    IMAGE_NT_HEADERS32 *nt;
    IMAGE_SECTION_HEADER *section;
    unsigned int i;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 || dos->e_lfanew > 0x1000)
        return 0;
    nt = (IMAGE_NT_HEADERS32 *)(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return 0;
    section = IMAGE_FIRST_SECTION(nt);
    for (i = 0; i < nt->FileHeader.NumberOfSections; ++i)
        if (memcmp(section[i].Name, ".spcode", 7) == 0) return 1;
    return 0;
}

static void put_u32(uint8_t *address, uint32_t value)
{
    memcpy(address, &value, sizeof(value));
}

static void relocate_helpers(uint8_t *code, uint8_t *state, uint8_t *engine)
{
    unsigned int i;
    for (i = 0; i < CLOCK_FIXUP_COUNT; ++i) {
        const ClockFixup *fixup = &kClockFixups[i];
        uint32_t value;
        if (fixup->kind == 1)
            value = (uint32_t)(uintptr_t)(engine + fixup->target_rva) -
                    (uint32_t)(uintptr_t)(code + fixup->offset + 4);
        else if (fixup->kind == 2)
            value = (uint32_t)(uintptr_t)state -
                    (uint32_t)(uintptr_t)(code + fixup->anchor);
        else
            value = (uint32_t)(uintptr_t)(engine + fixup->target_rva) -
                    (uint32_t)(uintptr_t)state;
        put_u32(code + fixup->offset, value);
    }
}

static double logical_now(void)
{
    ClockState *clock = (ClockState *)clock_state;
    PlatformTimeFn platform_time;
    double now;
    uint32_t paused;
    if (!engine_module || !clock) return -1.0;
    platform_time = *(PlatformTimeFn *)(engine_module + PLAT_TIME_IAT_RVA);
    if (!platform_time) return -1.0;
    now = platform_time();
    paused = *(uint32_t *)(engine_module + PAUSED_RVA) != 0;
    clock->raw_now = now;
    if (!clock->initialized) {
        clock->initialized = 1;
        clock->total_paused = 0.0;
        clock->pause_start = now;
        clock->paused = paused;
    } else if (paused != clock->paused) {
        if (paused) clock->pause_start = now;
        else clock->total_paused += now - clock->pause_start;
        clock->paused = paused;
    }
    clock->logical_now = (paused ? clock->pause_start : now) - clock->total_paused;
    return clock->logical_now;
}

#include "radio_sync.h"
#include "install_hooks.h"
