/* Read an independent native audio-file handle, never the playing stream.
   The supported Miles decoder and Source byte-loop skip one MPEG frame at
   wrap. Only the caption coordinate wraps; catch-up always decodes forward. */
typedef void *(__thiscall *AudioOpenFn)(void *, const char *);
typedef int (__thiscall *AudioReadFn)(void *, void *, int, void *);
typedef void (__thiscall *AudioCloseFn)(void *, void *);

static int mpeg_loop_samples(const uint8_t *data, unsigned size, int rate)
{
    static const unsigned kbps[16] = {0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0};
    static const int rates[3] = {44100,48000,32000};
    unsigned at = 0, frames = 0;
    while (at + 4 <= size) {
        uint32_t h = ((uint32_t)data[at] << 24) | ((uint32_t)data[at+1] << 16) |
                     ((uint32_t)data[at+2] << 8) | data[at+3];
        unsigned bi = (h >> 12) & 15, ri = (h >> 10) & 3, length;
        if ((h >> 21) != 2047 || ((h >> 19) & 3) != 3 || ((h >> 17) & 3) != 1 ||
            !kbps[bi] || ri == 3 || rates[ri] != rate) return 0;
        length = 144000 * kbps[bi] / (unsigned)rate + ((h >> 9) & 1);
        if (length < 4 || length > size - at) return 0;
        at += length; ++frames;
    }
    return at == size && frames > 1 && frames < 1000000 ? (int)(frames - 1) * 1152 : 0;
}
static int supported_loop_reader(uint8_t *mixer)
{
    uint8_t *miles = (uint8_t *)GetModuleHandleA("mssmp3.asi");
    uint8_t *audio = (uint8_t *)GetModuleHandleA("vaudio_miles.dll");
    uint8_t *decoder = *(uint8_t **)(mixer + 0x2c);
    static const uint8_t process_signature[] = {0x51,0x55,0x8b,0x6c,0x24,0x14,0x56,0x57,0x33,0xf6,0x33,0xff,0x3b,0xee,0x89,0x6c,0x24,0x0c,0x89,0x7c,0x24,0x1c};
    static const uint8_t byte_loop_signature[] = {0x8b,0xc8,0x49,0x4f,0x85,0xc9,0x8b,0xc7,0x74,0x16,0x99,0xf7,0xf9,0x5f,0x5e,0x8b,0xc2,0x40,0xc2,0x04,0x00};
    if (!miles || !audio || !decoder || *(uint8_t **)decoder != audio + 0xd184 ||
        *(uint8_t **)(decoder + 0x24) != miles + 0x5ad0) return 0;
    return unique_code_signature(miles, process_signature, sizeof(process_signature), 0x5ad0) &&
           unique_code_signature(engine_module, byte_loop_signature, sizeof(byte_loop_signature), 0x137b93);
}
static int ensure_loop_samples(RadioState *s, RadioChannel *c)
{
    uint8_t *io; void **v; void *handle; uint8_t *data; int size, got, period = 0;
    if (s->loop_checked && s->phase_channel == c->channel && s->phase_source == c->source &&
        s->phase_mixer == c->mixer && s->phase_sfx == c->sfx) return s->loop_samples;
    s->phase_channel = c->channel; s->phase_source = c->source;
    s->phase_mixer = c->mixer; s->phase_sfx = c->sfx;
    s->loop_checked = 1; s->loop_samples = 0;
    size = *(int *)(c->source + 12);
    io = *(uint8_t **)(engine_module + 0x197144);
    if (!io || size < 8 || size > 16 * 1024 * 1024 || !c->source[0x14] ||
        !supported_loop_reader(c->mixer)) return 0;
    v = *(void ***)io;
    if (v != (void **)(engine_module + 0x1735dc) || v[0] != engine_module + 0x2a90 ||
        v[1] != engine_module + 0x2b20 || v[2] != engine_module + 0x2bb0 ||
        memcmp(v[0], "\x81\xec\x00\x02\x00\x00\x53\x6a\x04", 9) ||
        memcmp(v[1], "\x8b\x44\x24\x0c\x85\xc0\x75\x03\xc2\x0c\x00", 11) ||
        memcmp(v[2], "\x56\x8b\x74\x24\x08\x85\xf6\x74\x11", 9)) return 0;
    data = (uint8_t *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)size);
    if (!data) return 0;
    handle = ((AudioOpenFn)v[0])(io, (const char *)c->sfx + 1);
    if (handle) {
        got = ((AudioReadFn)v[1])(io, data, size, handle);
        if (got == size) period = mpeg_loop_samples(data, (unsigned)size, c->rate);
        ((AudioCloseFn)v[2])(io, handle);
    }
    HeapFree(GetProcessHeap(), 0, data); s->loop_samples = period;
    return period;
}
static int __cdecl radio_sample_phase(uint8_t *channel, int position, int rate)
{
    unsigned i; uint8_t *table = entity_table(); RadioChannel c;
    if (!channel || position < 0 || !table) return position;
    for (i = 0; i < MAX_RADIOS; ++i) {
        RadioState *s = &radios[i];
        if (!s->entity || s->generation != location_generation ||
            s->index != *(uint32_t *)(channel + 0x2c) ||
            *(void **)(table + s->index * 12 + 4) != s->entity ||
            *(uint32_t *)(table + s->index * 12 + 8) != s->serial) continue;
        if (find_radio_stream_channel(s, &c) && c.channel == channel && c.rate == rate &&
            ensure_loop_samples(s, &c)) return position % s->loop_samples;
        break;
    }
    return position;
}
