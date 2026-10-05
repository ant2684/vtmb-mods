/* Included in subtitle_pause.c. Location game time is the broadcast epoch;
   PlatformTime is used only to initialize the caption clock coordinate. */
static double game_now(void)
{
    uint8_t *globals = server_module ? *(uint8_t **)(server_module + 0x70b228) : NULL;
    double now = globals ? (double)*(float *)(globals + 12) : -1.0;
    return now >= 0.0 && now < 1.0e8 ? now : -1.0;
}
static uint8_t *entity_table(void)
{
    return server_module ? *(uint8_t **)(server_module + 0x566458) : NULL;
}
static int identity(void *entity, uint32_t *index, uint32_t *serial)
{
    uint8_t *table = entity_table(); uint32_t i;
    if (!table || !entity) return 0;
    for (i = 0; i < 8192; ++i)
        if (*(void **)(table + i * 12 + 4) == entity) {
            *index = i; *serial = *(uint32_t *)(table + i * 12 + 8); return 1;
        }
    return 0;
}
static uint32_t player_identity(void)
{
    uint8_t *table = entity_table(); uint32_t i;
    if (!table) return 0xffffffff;
    for (i = 0; i < 8192; ++i) {
        uint8_t *entity = *(uint8_t **)(table + i * 12 + 4);
        const char *name = entity ? *(const char **)(entity + 0x11c) : NULL;
        if (name && !strcmp(name, "player"))
            return i | (*(uint32_t *)(table + i * 12 + 8) << 13);
    }
    return 0xffffffff;
}
static void refresh_location(double now)
{
    uint8_t *table = entity_table(); uint32_t player = player_identity(); unsigned i;
    if (table == location_table && location_player == 0xffffffff && player != 0xffffffff)
        location_player = player; /* player becomes available during this load */
    if (table != location_table || player != location_player ||
        (now >= 0.0 && location_last_time >= 0.0 && now < location_last_time)) {
        ++location_generation; memset(radios, 0, sizeof(radios));
        location_table = table; location_player = player;
    }
    location_last_time = now;
    for (i = 0; i < MAX_RADIOS; ++i) {
        RadioState *s = &radios[i];
        if (s->entity && (!table || s->generation != location_generation ||
            *(void **)(table + s->index * 12 + 4) != s->entity ||
            *(uint32_t *)(table + s->index * 12 + 8) != s->serial))
            memset(s, 0, sizeof(*s));
    }
}
static RadioState *radio_state(void *entity)
{
    RadioState *free_slot = NULL; uint32_t index, serial; unsigned i;
    refresh_location(game_now());
    if (!identity(entity, &index, &serial)) return NULL;
    for (i = 0; i < MAX_RADIOS; ++i) {
        if (radios[i].entity == entity && radios[i].index == index && radios[i].serial == serial)
            return &radios[i];
        if (!radios[i].entity && !free_slot) free_slot = &radios[i];
    }
    if (free_slot) {
        free_slot->entity = entity; free_slot->index = index; free_slot->serial = serial;
        free_slot->generation = location_generation;
    }
    return free_slot;
}
static int has_radio_loop_name(const char *name)
{
    unsigned i; if (!name) return 0;
    for (i = 0; i < 240 && name[i]; ++i)
        if (!strncmp(name + i, "radio_loop_", 11)) return 1;
    return 0;
}
static int find_radio_stream_channel(RadioState *state, RadioChannel *out)
{
    int count, i, matches = 0;
    if (!engine_module || !state) return 0;
    count = *(int *)(engine_module + CHANNEL_COUNT_RVA);
    if (count < 0 || count > MAX_CHANNELS) return 0;
    for (i = 0; i < count; ++i) {
        uint8_t *channel = engine_module + CHANNEL_ARRAY_RVA + i * CHANNEL_SIZE;
        uint8_t *sfx = *(uint8_t **)channel, *mixer, *source; void **v, **sv;
        double position; int rate;
        if (!sfx || *(uint32_t *)(channel + 0x2c) != state->index ||
            !has_radio_loop_name((const char *)(sfx + 4))) continue;
        mixer = *(uint8_t **)(channel + 4); source = *(uint8_t **)(sfx + 0x104);
        if (!mixer || !source) continue;
        v = *(void ***)mixer; sv = *(void ***)source;
        if (v != (void **)(engine_module + 0x188600) || sv != (void **)(engine_module + 0x188394) ||
            v[12] != engine_module + 0x139c80 || sv[3] != engine_module + 0x137970) continue;
        position = *(double *)(mixer + 8); rate = ((SourceIntegerFn)sv[3])(source);
        if (!(position >= 0.0 && position < 2147483647.0) || rate < 8000 || rate > 192000) continue;
        if (++matches > 1) return 0;
        out->channel = channel; out->sfx = sfx; out->source = source; out->mixer = mixer;
        out->position = (int)position; out->rate = rate;
    }
    return matches == 1;
}
#include "radio_loop.h"
/* Narrow CPropRadio::Activate call to its base Activate. This native lifecycle
   recreates the loop on map/load. Reset even an identical reused address/serial. */
static void __fastcall radio_base_activate(void *entity, void *unused)
{
    RadioState *s; double now; (void)unused;
    original_base_activate(entity);
    now = game_now(); s = radio_state(entity);
    if (!s || now < 0.0) return;
    memset(s, 0, sizeof(*s));
    if (!identity(entity, &s->index, &s->serial)) return;
    s->entity = entity; s->generation = location_generation;
    s->activation = ++activation_generation; s->epoch = now; s->epoch_valid = 1;
    s->seen_on = !*((uint8_t *)entity + 0x104); /* saved radio may already be on */
}
static void __fastcall radio_fake_silence(void *entity, void *unused, int silent)
{
    RadioState *s = radio_state(entity); RadioChannel c; double now = game_now();
    (void)unused;
    if (!original_fake_silence) return;
    if (!s) { original_fake_silence(entity, silent); return; }
    if (silent) {
        if (*((uint8_t *)entity + 0x104) && s->armed) {
            original_fake_silence(entity, silent); return; /* duplicate off keeps checkpoint */
        }
        if (!*((uint8_t *)entity + 0x104)) s->seen_on = 1;
        s->armed = 0;
        if (s->seen_on && now >= 0.0 && find_radio_stream_channel(s, &c)) {
            s->mixer = c.mixer; s->sfx = c.sfx; s->source = c.source; s->channel = c.channel;
            s->off_position = c.position; s->off_rate = c.rate; s->off_time = now; s->armed = 1;
        }
        original_fake_silence(entity, silent); return;
    }
    if (s->seen_on && !s->armed && !*((uint8_t *)entity + 0x104)) {
        original_fake_silence(entity, silent); return; /* duplicate on is idempotent */
    }
    if (!s->epoch_valid || now < s->epoch || !find_radio_stream_channel(s, &c) || !ensure_loop_samples(s, &c) ||
        (s->seen_on && (!s->armed || c.mixer != s->mixer || c.sfx != s->sfx ||
                       c.source != s->source || c.channel != s->channel || c.rate != s->off_rate))) {
        original_fake_silence(entity, 1); return;
    }
    {
        double target = s->seen_on ? (double)s->off_position + (now - s->off_time) * c.rate : (now - s->epoch) * c.rate;
        int remaining, skipped = 0; void **v = *(void ***)c.mixer;
        if (!(target >= 0.0 && target < 2147483647.0) ||
            (s->seen_on && (now < s->off_time || c.position < s->off_position || c.position - s->off_position > 4096))) {
            original_fake_silence(entity, 1); return;
        }
        remaining = (int)(target + 0.5) - c.position; if (remaining < 0) remaining = 0;
        while (remaining > 0) {
            void *pcm = NULL; int requested = remaining > 4096 ? 4096 : remaining;
            int got = ((MixerDecodeFn)v[12])(c.mixer, &pcm, requested, 0);
            if (got <= 0 || got > requested || !pcm) break;
            remaining -= got; skipped += got;
        }
        *(double *)(c.mixer + 8) = (double)c.position + skipped;
        if (remaining) { original_fake_silence(entity, 1); return; }
    }
    /* Seed a valid coordinate before the first visible dispatcher call. It
       subtracts this same value after adding the exact decoder time. */
    if (*(float *)(c.channel + 0x98) < 0.0f) *(float *)(c.channel + 0x98) = (float)logical_now();
    s->seen_on = 1; s->armed = 0;
    s->mixer = c.mixer; s->sfx = c.sfx; s->source = c.source; s->channel = c.channel;
    original_fake_silence(entity, silent);
}
