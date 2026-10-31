#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "runtime.h"
#include <math.h>

#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
#define CC __attribute__((cdecl))

/* Native melee policy for the supported UP 12.0 image; unified INI owns activation. */
enum {
    ENTITY_TABLE = 0x566458, SHADOW_VTABLE = 0x4b2184,
    GET_WEAPON = 0x32e7b0, GIVE_WEAPON = 0x32e120,
    CAN_EQUIP = 0x334c20, REMOVE_ENTITY = 0x24f7b0,
    INVENTORY_FRONT = 0x335780,
    FISTS_STRING = 0x585f08, KATANA_STRING = 0x587668,
    WEAPON_TRANSLATE = 0x24f210, ABS_ORIGIN = 0xb31b0, SEQUENCE_DESC = 0x8d990,
    ATTACK_MELEE = 75, ATTACK_FRENZY = 0xf18, ATTACK_KATANA = 0x99f
};
typedef struct { const char *name; int frenzy_animation; } WeaponProfile;
/* Exact player-weapon allowlist. NPC-only weapons and Protean are excluded.
   Tiger retains the original Frenzy animation, not its ordinary Chang combo. */
static const WeaponProfile profiles[] = {
    {"item_w_knife",0}, {"item_w_tire_iron",0}, {"item_w_baton",0},
    {"item_w_baseball_bat",0}, {"item_w_severed_arm",0}, {"item_w_torch",0},
    {"item_w_sledgehammer",0}, {"item_w_fireaxe",0}, {"item_w_bush_hook",0},
    {"item_w_katana",0}, {"item_w_avamp_blade",0}, {"item_w_chang_blade",0},
    {"item_w_occultblade",0}, {"item_w_chang_claw",1}
};
static const unsigned char weapon_translate_prefix[] =
    "\x83\xec\x0c\x53\x55\x56\x8b\xf1\x57\x8b\x06\xff\x90\xa8\x05\x00\x00";
typedef unsigned char (TC *CheckFn)(void *);
typedef int (TC *SequenceFn)(void *, int, void *);
typedef void (TC *EventFn)(void *, void *);
typedef void (TC *EndFn)(void *, int, int);
typedef void *(TC *DestroyFn)(void *, unsigned int);
typedef void *(TC *GetWeaponFn)(void *);
typedef void *(TC *GiveWeaponFn)(void *, const char *);
typedef unsigned char (TC *CanEquipFn)(void *, void *);
typedef void (TC *EquipFn)(void *, void *, int);
typedef void (TC *InventoryAddFn)(void *, void *);
typedef void (TC *SelectFn)(void *, const char *, int);
typedef void (TC *RemoveFn)(void *);
typedef int (TC *FeatFn)(void *, void *);
typedef int (TC *TranslateFn)(void *, int);
typedef void (TC *ActivityFn)(void *, int);
typedef void (TC *ExplicitActivityFn)(void *, int, int, int);
typedef unsigned char (TC *MeleeFn)(void *, int, int, int);
typedef int (TC *DamageFn)(void *, void *);
typedef void (TC *SwingFn)(void *, void *, void *, float, float);
typedef int (TC *HealthPercentFn)(void *);
typedef void (TC *ThinkFn)(void *);
typedef const char *(TC *SequenceNameFn)(void *, int);
typedef const float *(TC *OriginFn)(void *);
typedef const uint8_t *(TC *SequenceDescFn)(void *, int);
typedef unsigned char (TC *SuitabilityFn)(void *, void *, void *, int, int *);
typedef int (CC *EntitiesBoxFn)(void **, int, const float *, const float *, int, int);
typedef void (CC *ClipEntityFn)(const void *, unsigned int, void *, void *);
typedef float (TC *IntervalMovementFn)(void *,float,void *,void *,void *);
static IntervalMovementFn original_interval_movement;
typedef unsigned char (CC *SequenceMovementFn)(void *,int,float,float,const float *,float *,float *);
static SequenceMovementFn original_sequence_movement;
typedef struct {
    void *actor;
    unsigned int strike;
    int weapon,sequence,applied;
    float previous,current;
} MovementContext;
static MovementContext movement_context;
static float movement_previous;
static int movement_valid;
static const unsigned char origin_prefix[] = "\x56\x8b\xf1\x85\xf6\x74\x11\x8b\x8e\x6c\x02\x00\x00";
static const unsigned char descriptor_prefix[] = "\x53\x55\x8b\xe9\x56\x85\xed\x57\x74\x11\x8b\x8d\x6c\x02\x00\x00";

static uint8_t *module;
static CheckFn original_check;
static SequenceFn original_sequence;
static SequenceFn original_heaviest;
static EndFn original_end;
static DestroyFn original_destroy;
static EquipFn original_equip;
/* Native Inventory_MoveToFront updates both handles and each item's +73C,
   preserving the order of the other weapons in that category. */
static const unsigned char inventory_front_prefix[] = "\x53\x55\x56\x8b\xf1\x85\xf6\x57\x74\x11";
static const unsigned char inventory_front_rotate[] =
    "\x8d\x6f\xff\x8b\xce\x55\xe8\x0c\xa8\xcd\xff\x50\x57\x8b\xce\xe8\x9d\xbd\xcd\xff"
    "\x57\x8b\xce\xe8\xfb\xa7\xcd\xff\x89\xb8\x3c\x07\x00\x00";
static TranslateFn original_early_activity;
static ActivityFn original_set_activity, original_reset_sequence;
static MeleeFn original_melee;
static SwingFn original_swing;
static ThinkFn original_frenzy_end;
static ThinkFn original_leave_grapple;
/* Exit policy is independent of the Katana animation/feat scope. */
static int policy_player = -1, policy_shadow = -1, policy_katana = -1;
static int policy_claws;
static void *exit_player;
static int exit_katana = -1, exit_claws;
static int deferred_player=-1, deferred_partner=-1, deferred_katana=-1, deferred_claws;
static void *pending_player;
static int pending_katana;
static int player_handle = -1, shadow_handle = -1;
static int katana_handle = -1;
static int player_katana_handle = -1, pending_weapon_handle = -1;
/* Legacy handle names above are retained for capsule regression continuity;
   they now bind any allowlisted melee, never an arbitrary inventory object. */
static const WeaponProfile *pending_profile, *active_profile;
static int attack_activity = ATTACK_FRENZY;
static int installed;
static unsigned int strike_serial,active_strike;
static unsigned int pending_strike;
static int pending_attacker = -1, pending_attack_weapon = -1, pending_attack_sequence = -1;

static void *resolve_handle(int handle)
{
    uint8_t *table, *entry;
    if (handle == -1 || !module) return NULL;
    table = *(uint8_t **)(module + ENTITY_TABLE);
    if (!table) return NULL;
    entry = table + ((uint32_t)handle & 0x1fff) * 12 + 4;
    if (*(uint32_t *)(entry + 4) != (uint32_t)handle >> 13) return NULL;
    return *(void **)entry;
}

static int handle_of(void *entity)
{
    uint8_t *table = *(uint8_t **)(module + ENTITY_TABLE);
    unsigned int i;
    if (!entity || !table) return -1;
    for (i = 0; i < 8192; ++i) {
        uint8_t *entry = table + i * 12 + 4;
        if (*(void **)entry == entity)
            return (int)(i | (*(uint32_t *)(entry + 4) << 13));
    }
    return -1;
}

static const char *classname(void *entity)
{
    const char *name = entity ? *(const char **)((uint8_t *)entity + 0x11c) : NULL;
    return name ? name : "<none>";
}

static const WeaponProfile *weapon_profile(void *weapon)
{
    unsigned int i;
    for(i=0;i<sizeof(profiles)/sizeof(profiles[0]);++i)
        if(!strcmp(classname(weapon),profiles[i].name)) return profiles+i;
    return NULL;
}

static void clear_policy(void)
{
    policy_player=policy_shadow=policy_katana=-1;
    policy_claws=0;
}

static void clear_deferred(void)
{
    deferred_player=deferred_partner=deferred_katana=-1; deferred_claws=0;
}

static int policy_matches(void *player)
{
    void *shadow;
    if (!player || resolve_handle(policy_player)!=player) return 0;
    shadow=resolve_handle(policy_shadow);
    if (!shadow || *(void **)shadow!=module+SHADOW_VTABLE ||
        *(int *)((uint8_t *)player+0x1db0)!=policy_shadow) {
        clear_policy(); return 0;
    }
    return 1;
}

/* Find only a registered inventory object; never create or copy equipment. */
static void *inventory_weapon(void *player, const char *name, int exact)
{
    unsigned int i;
    for(i=0;i<224;++i) {
        int h=*(int *)((uint8_t *)player+0x1624+i*4);
        void *item=resolve_handle(h);
        if(item && (exact==-1 || h==exact) &&
            *(unsigned int *)((uint8_t *)item+0x73c)==i && !strcmp(classname(item),name)) return item;
    }
    return NULL;
}

static void *exit_weapon(void *player)
{
    void *item;
    item=resolve_handle(exit_katana);
    if(item && weapon_profile(item) && inventory_weapon(player,classname(item),exit_katana)==item) return item;
    if(exit_claws && *(int *)((uint8_t *)player+0x1380)>=2 &&
        (item=inventory_weapon(player,"item_w_claws",-1))) return item;
    return inventory_weapon(player,"item_w_fists",-1);
}

/* Finish the complete native cleanup first, then make one ordinary weapon
   selection. Native inventory restoration/feeding/holster stays intact; no
   per-frame enforcement or interception of future manual selections. */
static void FC frenzy_end(void *character, void *unused)
{
    void *player=*(void **)((uint8_t *)character+0xa8);
    void *saved_exit=exit_player;
    int saved_katana=exit_katana, saved_claws=exit_claws;
    int confirmed=policy_matches(player);
    (void)unused;
    if(confirmed) {
        exit_player=player; exit_katana=policy_katana; exit_claws=policy_claws;
        
    }
    original_frenzy_end(character);
    if(confirmed) {
        void *desired=exit_weapon(player);
        if(desired && *(unsigned char *)((uint8_t *)player+0x1481) &&
            !*(unsigned char *)((uint8_t *)player+0x200) &&
            *(int *)((uint8_t *)player+0x146c)==0 &&
            *(int *)((uint8_t *)player+0x1db0)==-1) {
            ((SelectFn)(*(void ***)player)[0x724/4])(player,classname(desired),0);
            
            if(((GetWeaponFn)(module+GET_WEAPON))(player)!=desired &&
                resolve_handle(*(int *)((uint8_t *)player+0x1538)) &&
                *(int *)((uint8_t *)player+0x153c)!=-1) {
                deferred_player=handle_of(player);deferred_partner=*(int *)((uint8_t *)player+0x1538);
                deferred_katana=exit_katana;deferred_claws=exit_claws;
                
            }
        }

        clear_policy();
    }
    exit_player=saved_exit; exit_katana=saved_katana; exit_claws=saved_claws;
}

/* Native LeaveGrappleState clears +1538/+153C, restores presentation and the
   ordinary sequence. Finish a single blocked exit selection only after it
   returns, for the exact player AND original grapple partner serial. */
static void FC leave_grapple(void *self, void *unused)
{
    int confirmed=self && self==resolve_handle(deferred_player) &&
        *(int *)((uint8_t *)self+0x1538)==deferred_partner && resolve_handle(deferred_partner);
    int retained=deferred_katana, claws=deferred_claws;
    (void)unused;
    if(self==resolve_handle(deferred_player)) clear_deferred();
    original_leave_grapple(self);
    if(confirmed && *(int *)((uint8_t *)self+0x146c)==0 &&
        *(int *)((uint8_t *)self+0x1db0)==-1 && *(int *)((uint8_t *)self+0x1538)==-1 &&
        *(int *)((uint8_t *)self+0x153c)==-1 && *(unsigned char *)((uint8_t *)self+0x1481) &&
        !*(unsigned char *)((uint8_t *)self+0x200)) {
        void *saved_exit=exit_player, *desired;
        int saved_katana=exit_katana,saved_claws=exit_claws;
        exit_player=self;exit_katana=retained;exit_claws=claws;
        desired=exit_weapon(self);
        if(desired) ((SelectFn)(*(void ***)self)[0x724/4])(self,classname(desired),0);
        
        exit_player=saved_exit;exit_katana=saved_katana;exit_claws=saved_claws;
    }
}

static void clear_active(const char *reason)
{
    (void)reason;
    
    player_handle = shadow_handle = katana_handle = player_katana_handle = -1;
    active_profile=NULL; attack_activity=ATTACK_FRENZY;
    strike_serial = active_strike = 0;
    pending_strike = 0;
    movement_valid=0;movement_previous=0;memset(&movement_context,0,sizeof(movement_context));
    pending_attacker = pending_attack_weapon = pending_attack_sequence = -1;
}

static int scoped_shadow(void *self)
{
    void *player, *shadow;
    if (shadow_handle == -1) return 0;
    player = resolve_handle(player_handle);
    shadow = resolve_handle(shadow_handle);
    if (!player || !shadow || *(void **)shadow != module + SHADOW_VTABLE) {
        clear_active("entity identity invalidated");
        return 0;
    }
    /* CheckForPlayerFrenzy publishes its controller before the caller applies
       the Frenzy counter/effect. Do not mistake that transient zero for end. */
    if (pending_player != player &&
        *(int *)((uint8_t *)player + 0x1db0) != shadow_handle) {
        clear_active("Frenzy ended or controller changed");
        return 0;
    }
    if (self != shadow) return 0;
    return 1;
}

static int katana_shadow(void *self)
{
    void *weapon;
    if (!scoped_shadow(self)) return 0;
    weapon = ((GetWeaponFn)(module + GET_WEAPON))(self);
    
    return active_profile && weapon && weapon==resolve_handle(katana_handle) &&
        !strcmp(classname(weapon),active_profile->name);
}

static const char *sequence_name(void *actor, int sequence)
{
    if (!actor || sequence < 0 || sequence > 8191) return "<invalid>";
    return ((SequenceNameFn)(module + 0x8fe80))(actor, sequence);
}

static int inventory_provider_available(void){return pfi_inventory_ready;}
#include "short_attacks.inc"

static void FC set_activity(void *self, void *unused, int activity)
{
    int scoped = katana_shadow(self), selected = activity;
    (void)unused;
    if (scoped && activity == ATTACK_FRENZY) selected = attack_activity;
    original_set_activity(self, selected);
    
}

/* Native MeleeAttack now receives the weapon activity BEFORE distance/box
   selection. Preserve its entire selected triple: SetActivity(int) here would
   reroll the sequence and discard the native suitability decision. */

static void FC reset_sequence(void *self, void *unused, int sequence)
{
    int scoped = scoped_shadow(self);
    (void)unused;
    original_reset_sequence(self, sequence);
    if(scoped) movement_valid=0;
    
}

/* Observe the real native answer without an extra selection or reroll. */

static int FC early_activity(void *self, void *unused, int activity)
{
    int selected = activity, scoped = katana_shadow(self), result;
    (void)unused;
    if (scoped && activity == ATTACK_FRENZY) selected = attack_activity;
    result = original_early_activity(self, selected);
    
    return result;
}

/* UP OnFrenzyBegin requests Corpus_Vampirus claws after native Spawn. Its
   eventual player-fists request is real inventory restoration, not presentation.
   Never substitute a retained Katana for that request. */
static void *retained_weapon(void *self, void *requested)
{
    void *katana, *shadow = resolve_handle(shadow_handle);
    int is_player = self && self == resolve_handle(player_handle);
    if (!scoped_shadow(shadow) || (self != shadow && !is_player)) return requested;
    if (is_player && !strcmp(classname(requested), "item_w_fists")) {
        
        return requested;
    }
    katana = resolve_handle(is_player ? player_katana_handle : katana_handle);
    if (!katana || !active_profile || strcmp(classname(katana),active_profile->name)) {
        clear_active("temporary katana invalidated; original equip fallback");
        return requested;
    }
    
    return katana;
}

static void FC equip_shadow_weapon(void *self, void *unused, void *weapon, int flags)
{
    void *selected = retained_weapon(self, weapon);
    (void)unused;
    original_equip(self, selected, flags);
    if (selected != weapon && ((GetWeaponFn)(module + GET_WEAPON))(self) != selected) {
        clear_active("retained katana equip failed; original equip fallback");
        original_equip(self, weapon, flags);
    }
}

static void restore_fists_order(void *player, void *fists)
{
    unsigned int slot, i, j;
    int handle, seen_katana=0;
    void *item;
    if (!player || !fists || strcmp(classname(fists),"item_w_fists")) return;
    slot=*(unsigned int *)((uint8_t *)fists+0x73c);
    handle=handle_of(fists);
    if (!slot) return;
    /* Fists belong to the first, 32-slot melee category on this native build.
       Validate a contiguous, internally consistent prefix before native rotate.
       Do not repair an unknown/corrupted inventory or move another category. */
    if (slot>=32 || handle==-1) goto refused;
    for(i=0;i<=slot;++i) {
        int h=*(int *)((uint8_t *)player+0x1624+i*4);
        item=resolve_handle(h);
        if (!item || strncmp(classname(item),"item_w_",7) ||
            *(unsigned int *)((uint8_t *)item+0x73c)!=i ||
            (i==slot && item!=fists)) goto refused;
        if (h==player_katana_handle || policy_matches(player) || player==exit_player) seen_katana=1;
        for(j=0;j<224;++j)
            if (j!=i && *(int *)((uint8_t *)player+0x1624+j*4)==h) goto refused;
    }
    if (!seen_katana) goto refused;
    ((InventoryAddFn)(module+INVENTORY_FRONT))(player,fists);
    
    return;
refused:
    return;
}

static unsigned char FC check_frenzy(void *self, void *unused)
{
    unsigned char result;
    void *weapon;
    void *saved_player = pending_player;
    int saved_pending = pending_katana;
    const WeaponProfile *saved_profile=pending_profile;
    int saved_weapon_handle = pending_weapon_handle;
    int started_claws;
    (void)unused;
    if (*(int *)((uint8_t *)self + 0x146c) <= 0) { clear_active("new attempt"); clear_policy(); clear_deferred(); }
    weapon = ((GetWeaponFn)(module + GET_WEAPON))(self);
    started_claws=!strcmp(classname(weapon),"item_w_claws") && *(int *)((uint8_t *)self+0x1380)>=2;
    pending_player = self;
    pending_profile=weapon_profile(weapon);
    pending_katana = pending_profile!=NULL;
    pending_weapon_handle = pending_katana ? handle_of(weapon) : -1;
    
    result = original_check(self);
    if(result && !policy_matches(self)) {
        int h=*(int *)((uint8_t *)self+0x1db0);
        void *shadow=resolve_handle(h);
        if(shadow && *(void **)shadow==module+SHADOW_VTABLE) {
            policy_player=handle_of(self); policy_shadow=h;
            policy_katana=shadow_handle==h && katana_handle!=-1 ? pending_weapon_handle : -1;
            policy_claws=started_claws;
            
        }
    }
    if (result && shadow_handle != -1) {
        void *controller = resolve_handle(shadow_handle);
        unsigned int field;
        if (controller) {
            
            for (field = 0x98; field <= 0x9c; field += 4) {
                void *actor = *(void **)((uint8_t *)controller + field);
                
            }
        }
    }
    if (!result && shadow_handle != -1 && player_handle == handle_of(self) &&
        *(int *)((uint8_t *)self + 0x146c) <= 0)
        clear_active("creation failed");
    
    pending_player = saved_player;
    pending_katana = saved_pending;
    pending_profile = saved_profile;
    pending_weapon_handle = saved_weapon_handle;
    
    return result;
}

static void CC select_start_weapon(void *player)
{
    const char *name = (const char *)(module + FISTS_STRING);
    if (player == pending_player && pending_katana && pending_profile)
        name = pending_profile->name;
    ((SelectFn)(*(void ***)player)[0x724 / 4])(player, name, 0);
}

/* NULL requests the exact original fists prefix. Only a successfully equipped
   temporary katana skips that prefix. The player's inventory is never copied. */
static void *CC prepare_shadow(void *self)
{
    void *weapon, *original;
    int selected, player_sequence, shadow_sequence;
    if (!pending_player || !pending_katana || !pending_profile ||
        *(void **)self != module + SHADOW_VTABLE) {
        
        return NULL;
    }
    original=resolve_handle(pending_weapon_handle);
    if(!original || weapon_profile(original)!=pending_profile) {
         return NULL;
    }
    weapon = ((GiveWeaponFn)(module + GIVE_WEAPON))(self,pending_profile->name);
    if (!weapon || weapon==original || weapon_profile(weapon)!=pending_profile ||
        !((CanEquipFn)(module + CAN_EQUIP))(self, weapon)) {
        if (weapon && weapon!=original) ((RemoveFn)(module + REMOVE_ENTITY))(weapon);
        
        return NULL;
    }
    ((EquipFn)(*(void ***)self)[0x5fc / 4])(self, weapon, 0);
    if (((GetWeaponFn)(module + GET_WEAPON))(self) != weapon) {
        ((RemoveFn)(module + REMOVE_ENTITY))(weapon);
        
        return NULL;
    }
    /* The native weapon helper walks its ordered mapping table and verifies
       availability on the owner model. Then independently check BOTH actors:
       never transplant a sequence ID from one model into the other. */
    selected=pending_profile->frenzy_animation ? ATTACK_FRENZY :
        ((TranslateFn)(module+WEAPON_TRANSLATE))(weapon,ATTACK_MELEE);
    player_sequence=original_heaviest(pending_player,
        ((TranslateFn)(*(void ***)pending_player)[0x5e0/4])(pending_player,selected),(void *)-1);
    shadow_sequence=original_heaviest(self,
        ((TranslateFn)(*(void ***)self)[0x5e0/4])(self,selected),(void *)-1);
    if((!pending_profile->frenzy_animation && (selected==ATTACK_MELEE || selected==ATTACK_FRENZY)) ||
       player_sequence<0 || shadow_sequence<0 ||
       !short_preflight(pending_player,((TranslateFn)(*(void ***)pending_player)[0x5e0/4])(pending_player,selected),pending_profile) ||
       !short_preflight(self,((TranslateFn)(*(void ***)self)[0x5e0/4])(self,selected),pending_profile)) {
        
        ((RemoveFn)(module+REMOVE_ENTITY))(weapon);
        return NULL;
    }
    player_handle = handle_of(pending_player);
    shadow_handle = handle_of(self);
    katana_handle = handle_of(weapon);
    player_katana_handle = pending_weapon_handle;
    if (player_handle == -1 || shadow_handle == -1 || katana_handle == -1 ||
        player_katana_handle == -1) {
        ((RemoveFn)(module + REMOVE_ENTITY))(weapon);
        clear_active("missing entity handle");
        
        return NULL;
    }
    active_profile=pending_profile; attack_activity=selected;

    return weapon;
}

static int FC select_sequence(void *self, void *unused, int activity, void *stat)
{
    int sequence, selected = activity;
    int scoped = katana_shadow(self);
    (void)unused;
    if (scoped && activity == ATTACK_FRENZY) selected = attack_activity;
    sequence = original_sequence(self, selected, stat);
    if (scoped && selected != activity && sequence < 0) {
        
        sequence = original_sequence(self, activity, stat);
        selected = activity;
    }
    
    return sequence;
}

static int FC select_heaviest(void *self, void *unused, int activity, void *stat)
{
    int scoped = katana_shadow(self), selected = activity, sequence;
    (void)unused;
    if (scoped && activity == ATTACK_FRENZY) selected = attack_activity;
    sequence = original_heaviest(self, selected, stat);
    if (scoped && selected != activity && sequence < 0) {
        selected = activity;
        sequence = original_heaviest(self, activity, stat);
        
    }
    
    return sequence;
}

/* Translate only the serial-bound TEMPORARY Shadow weapon before native
   candidate enumeration, distance/box selection and assignment. Parameters
   a/b, return value and the complete native attack path remain unchanged. */
static unsigned char FC melee_attack(void *self, void *unused, int activity, int a, int b)
{
    void *shadow = resolve_handle(shadow_handle);
    int scoped = shadow && katana_shadow(shadow) &&
        (self == resolve_handle(katana_handle) || self == resolve_handle(player_katana_handle));
    unsigned int previous = active_strike;
    unsigned char result;
    int selected = activity, early_map = scoped && self==resolve_handle(katana_handle) &&
        resolve_handle(*(int *)((uint8_t *)self+0x88c))==shadow &&
        activity==ATTACK_FRENZY && attack_activity!=ATTACK_FRENZY;
    (void)unused;
    if (scoped) {
        if (!active_strike) active_strike = ++strike_serial;
        if (early_map) {
            selected=attack_activity;

        }
        
    }
    result = original_melee(self, selected, a, b);
    
    if (scoped && result) {
        void *owner = resolve_handle(*(int *)((uint8_t *)self + 0x88c));
        /* Native collision is evaluated by MeleeSwingStep on later frames.
           +0x1c58 is a player-only notice cache, NOT a Shadow victim cache. */
        if (owner == shadow || owner == resolve_handle(player_handle)) {
            pending_strike = active_strike;
            pending_attacker = handle_of(owner);
            pending_attack_weapon = handle_of(self);
            pending_attack_sequence = *(int *)((uint8_t *)owner + 0x6f0);
            movement_previous=*(float *)((uint8_t *)owner+0x6f8);
            movement_valid=early_map && owner==shadow && isfinite(movement_previous) &&
                movement_previous>=0 && movement_previous<=1;

        }
    }
    
    active_strike = previous;
    return result;
}

static int movement_bound(void *self)
{
    void *weapon;
    if(!katana_shadow(self) || !active_profile || active_profile->frenzy_animation ||
       attack_activity==ATTACK_FRENZY || !pending_strike || pending_attacker!=handle_of(self) ||
       pending_attack_weapon!=katana_handle ||
       *(int *)((uint8_t *)self+0x6f0)!=pending_attack_sequence ||
       *(int *)((uint8_t *)self+0xfec)!=attack_activity ||
       *(unsigned char *)((uint8_t *)self+0x65d)) return 0;
    weapon=resolve_handle(katana_handle);
    return weapon && resolve_handle(*(int *)((uint8_t *)weapon+0x88c))==self;
}

/* Only the native NPC movement call inside this exact attack gets elapsed
   cycles. No actor cycle, pose, sequence or position is written. Native model
   blending/root rotation/collision and the original sequence stay intact. */
static unsigned char sequence_movement_at(void *caller,void *header,int sequence,float from,float to,
                                         const float *pose,float *position,float *angles)
{
    MovementContext *context=&movement_context;
    if(caller==module+0x094c83 && context->actor && !context->applied &&
       context->strike==pending_strike && context->weapon==katana_handle &&
       context->sequence==sequence && movement_bound(context->actor) &&
       pose==(const float *)((uint8_t *)context->actor+0x690) && header && position && angles) {
        from=context->previous;to=context->current;context->applied=1;
    }
    return original_sequence_movement(header,sequence,from,to,pose,position,angles);
}

static unsigned char CC sequence_movement(void *header,int sequence,float from,float to,
                                         const float *pose,float *position,float *angles)
{
    return sequence_movement_at(__builtin_return_address(0),header,sequence,from,to,pose,position,angles);
}

static float interval_movement_at(void *caller,void *self,float interval,void *finished,void *position,void *angles)
{
    int scoped=movement_bound(self), corrected=0;
    float cycle=self?*(float *)((uint8_t *)self+0x6f8):0;
    float result,previous=movement_previous;
    MovementContext saved=movement_context;
    memset(&movement_context,0,sizeof(movement_context));
    if(scoped && caller==module+0x280af1 && movement_valid && finished && position && angles &&
       isfinite(interval) && interval>0 && isfinite(cycle) && cycle>=previous && cycle<=1) {
        movement_context.actor=self;movement_context.strike=pending_strike;
        movement_context.weapon=katana_handle;movement_context.sequence=pending_attack_sequence;
        movement_context.previous=previous;movement_context.current=cycle;
    }
    result=original_interval_movement(self,interval,finished,position,angles);
    if(movement_context.applied && movement_context.strike==pending_strike && movement_bound(self)) {
        corrected=1;movement_previous=cycle;
        /* Native completion originally describes the future interval. Report
           completion of the elapsed non-looping interval instead. */
        *(unsigned char *)finished=(unsigned char)(cycle>=1);
    } else if(scoped && caller==module+0x280af1) movement_valid=0;
    movement_context=saved;

    return result;
}

static float FC interval_movement(void *self,void *unused,float interval,void *finished,void *position,void *angles)
{
    (void)unused;
    return interval_movement_at(__builtin_return_address(0),self,interval,finished,position,angles);
}

/* Actual native collision/damage stage. Mirrored player animation must not
   perform a second attack: only the confirmed temporary Shadow katana swings.
   No trace hook, artificial damage, activity holding, or vtable mutation. */
static void FC swing_step(void *self,void *unused,void *position,void *angles,float cycle,float previous_cycle)
{
    void *shadow=resolve_handle(shadow_handle);
    (void)unused;
    if(shadow && katana_shadow(shadow) && self==resolve_handle(player_handle)) return;
    original_swing(self,position,angles,cycle,previous_cycle);
}

static void FC end_controller(void *self, void *unused, int a, int b)
{
    (void)unused;
    if (resolve_handle(player_handle) == self) clear_active("controller removal");
    original_end(self, a, b);
    if(self!=exit_player && resolve_handle(policy_player)==self) clear_policy();
}

static void *FC destroy_shadow(void *self, void *unused, unsigned int flags)
{
    (void)unused;
    if (resolve_handle(shadow_handle) == self) clear_active("Shadow destruction");
    if (resolve_handle(policy_shadow)==self) clear_policy();
    return original_destroy(self, flags);
}

/* Intercept only the engine's forwarding thunks, NOT the feat entry points
   occupied by Protean Improved. Forward through those entries normally so its
   own guards and any original bonuses still run, exactly once. */
static void *feat_character(void *character)
{
    void *shadow = resolve_handle(shadow_handle), *player;
    
    if (!character || !katana_shadow(shadow) ||
        *(void **)((uint8_t *)shadow + 0x9c) != character)
        return character;
    player = resolve_handle(player_handle);
    if (player && *(void **)((uint8_t *)player + 0x9c)) {
        
        return *(void **)((uint8_t *)player + 0x9c);
    }
    return character;
}

static int FC evaluate_feat(void *feat, void *unused, void *character)
{
    void *selected = feat_character(character);
    int result;
    (void)unused;
    result = ((FeatFn)(module + 0x1e56e0))(feat, selected);
    
    return result;
}

static int FC evaluate_extra_feat(void *feat, void *unused, void *character)
{
    (void)unused;
    return ((FeatFn)(module + 0x1e5b30))(feat, feat_character(character));
}

typedef struct {
    uint32_t rva;
    unsigned int size;
    unsigned int signature_size;
    uint8_t expected[64];
    void *replacement;
    uint8_t *trampoline;
    uint8_t saved[20];
} Hook;

static Hook hooks[] = {
    {0x161fc0, 9,14, {0x56,0x8b,0xf1,0x8b,0x86,0x38,0x15,0,0,0x83,0xf8,0xff,0x74,0x3d}, (void *)check_frenzy, NULL, {0}},
    {0x162038,17,22, {0x8b,0x06,0x6a,0,0x68,0x08,0x5f,0x58,0x10,0x8b,0xce,0xff,0x90,0x24,0x07,0,0,0x68,0x78,0x62,0x58,0x10}, NULL, NULL, {0}},
    {0x375c80, 7,16, {0x56,0x57,0x68,0x08,0x5f,0x58,0x10,0x8b,0xf1,0xe8,0x26,0x54,0xc9,0xff,0x8b,0xf8}, NULL, NULL, {0}},
    {0x08dc40, 5,12, {0xb8,0,0x40,0,0,0xe8,0xa6,0x36,0x3a,0,0x85,0xc9}, (void *)select_sequence, NULL, {0}},
    {0x012503,5,10, {0xe9,0xd8,0xf3,0x14,0,0xe9,0x03,0x8c,0x0e,0}, (void *)end_controller, NULL, {0}},
    {0x376f20, 8,13, {0x56,0x8b,0xf1,0xe8,0x87,0xb4,0xc9,0xff,0xf6,0x44,0x24,0x08,0x01}, (void *)destroy_shadow, NULL, {0}},
    {0x00f03d, 5, 5, {0xe9,0x9e,0x66,0x1d,0}, (void *)evaluate_feat, NULL, {0}},
    {0x00c036, 5, 5, {0xe9,0xf5,0x9a,0x1d,0}, (void *)evaluate_extra_feat, NULL, {0}},
    {0x08dd30, 5,12, {0xb8,0,0x40,0,0,0xe8,0xb6,0x35,0x3a,0,0x85,0xc9}, (void *)select_heaviest, NULL, {0}},
    {0x0032b0, 5,10, {0xe9,0xcb,0xa0,0x32,0,0xe9,0xf6,0x74,0x40,0}, (void *)equip_shadow_weapon, NULL, {0}},
    {0x00d4e0, 5,10, {0xe9,0x4b,0xab,0x31,0,0xe9,0x66,0x27,0x19,0}, (void *)early_activity, NULL, {0}},
    /* Native AI also calls the implementation directly, bypassing its thunk. */
    {0x2725d0, 7,16, {0x8b,0x44,0x24,0x04,0x56,0x8b,0xf1,0x8b,0x8e,0xec,0x0f,0,0,0x3b,0xc8,0x74}, (void *)set_activity, NULL, {0}},
    {0x00d0b2, 5,10, {0xe9,0x99,0x39,0x25,0,0xe9,0x84,0x87,0x12,0}, (void *)reset_sequence, NULL, {0}},
    {0x3e9e00, 5,16, {0xb8,0x28,0x40,0,0,0xe8,0xe6,0x74,0x04,0,0x53,0x55,0x56,0x57,0x8b,0xd9}, (void *)melee_attack, NULL, {0}},
    {0x343020, 5,16, {0xb8,0x4c,0x6d,0,0,0xe8,0xc6,0xe2,0x0e,0,0x53,0x8b,0xd9,0x55,0x56,0x85}, (void *)swing_step, NULL, {0}},
    /* EquipWeapon calls this free inventory-add forwarding thunk. */
    {0x33f6d0,10,20, {0x56,0x8b,0xf1,0xc6,0x86,0x74,0x14,0,0,0,0xc7,0x86,0x6c,0x14,0,0,0,0,0,0}, (void *)frenzy_end,NULL,{0}},
    {0x329a70,9,17, {0x81,0xec,0xc0,0x01,0,0,0x56,0x8b,0xf1,0x85,0xf6,0x74,0x11,0x8b,0x8e,0x6c,0x02}, (void *)leave_grapple,NULL,{0}},
    {0x094b70,6,57, {0x83,0xec,0x18,0x56,0x8b,0xf1,0x85,0xf6,0x57,0x74,0x11,0x8b,0x8e,0x6c,0x02,0,0,0x85,0xc9,0x75,0x0c,0xb9,0x40,0x85,0x6b,0x10,0xeb,0x05,0xb9,0xdc,0x87,0x53,0x10,0xa1,0x80,0x36,0x9f,0x10,0x6a,0xff,0x8b,0,0x8d,0x14,0x40,0xa1,0x20,0x36,0x9f,0x10,0xc7,0x04,0x90,0xfc,0xff,0x54,0x10}, (void *)interval_movement,NULL,{0}},
    {0x012512,5,10,{0xe9,0xf9,0x37,0x0b,0,0xe9,0x14,0x44,0x03,0},(void *)sequence_movement,NULL,{0}},
    {0x00b230,5,10,{0xe9,0x8b,0x28,0x08,0,0xe9,0xf6,0x26,0x3a,0},(void *)collect_short_attacks,NULL,{0}},
    {0x006fbe,5,10,{0xe9,0xbd,0xe4,0x33,0,0xe9,0xb8,0xd9,0x1b,0},(void *)next_short_attack,NULL,{0}}
};
typedef char trampoline_region_must_fit[(sizeof(hooks)/sizeof(hooks[0])*64 <= 0x800) ? 1 : -1];

static uint8_t *hook_trampoline(uint32_t rva) {
    unsigned int i;for(i=0;i<sizeof(hooks)/sizeof(hooks[0]);++i)
        if(hooks[i].rva==rva) return hooks[i].trampoline;
    return NULL;
}

static void put32(uint8_t *at, uint32_t value) { memcpy(at, &value, 4); }
static void jump(uint8_t *at, void *target)
{
    at[0] = 0xe9;
    put32(at + 1, (uint32_t)((uint8_t *)target - (at + 5)));
}

static IMAGE_NT_HEADERS32 *headers(void)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)module;
    IMAGE_NT_HEADERS32 *nt;
    if (!module || dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 ||
        dos->e_lfanew > 0x1000) return NULL;
    nt = (IMAGE_NT_HEADERS32 *)(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != 0x10b ||
        nt->FileHeader.Machine != 0x14c || nt->FileHeader.TimeDateStamp != 0x41afafae ||
        nt->OptionalHeader.SizeOfImage != 0xab9000) return NULL;
    return nt;
}

static int signature_ok(Hook *h, IMAGE_NT_HEADERS32 *nt)
{
    IMAGE_SECTION_HEADER *sections = IMAGE_FIRST_SECTION(nt);
    unsigned int s, count = 0;
    uint8_t expected[64];
    memcpy(expected, h->expected, h->signature_size);
    /* Relocated absolute string operands at these two hook sites. */
    if (h->rva == 0x162038) {
        put32(expected + 5, (uint32_t)(uintptr_t)(module + FISTS_STRING));
        put32(expected + 18, (uint32_t)(uintptr_t)(module + 0x586278));
    }
    if (h->rva == 0x375c80) put32(expected + 3, (uint32_t)(uintptr_t)(module + FISTS_STRING));
    if (h->rva == 0x32ef60) {
        static const unsigned int operands[] = {0x16,0x1d,0x22,0x2c,0x33};
        unsigned int i;
        for (i = 0; i < sizeof(operands)/sizeof(operands[0]); ++i) {
            uint32_t address;
            memcpy(&address, expected + operands[i], 4);
            put32(expected + operands[i], address - 0x10000000 + (uint32_t)(uintptr_t)module);
        }
    }
    if(h->rva==0x094b70) {
        static const unsigned int operands[]={22,29,34,46,53};unsigned int i;
        for(i=0;i<sizeof(operands)/sizeof(operands[0]);++i) {
            uint32_t address;memcpy(&address,expected+operands[i],4);
            put32(expected+operands[i],address-0x10000000+(uint32_t)(uintptr_t)module);
        }
    }
    if (memcmp(module + h->rva, expected, h->signature_size)) return 0;
    for (s = 0; s < nt->FileHeader.NumberOfSections; ++s) {
        uint32_t i, start = sections[s].VirtualAddress, size = sections[s].Misc.VirtualSize;
        if (!(sections[s].Characteristics & IMAGE_SCN_MEM_EXECUTE)) continue;
        if ((uint64_t)start + size > nt->OptionalHeader.SizeOfImage || size < h->signature_size) return 0;
        for (i = 0; i <= size - h->signature_size; ++i)
            if (!memcmp(module + start + i, expected, h->signature_size)) {
                if (start + i != h->rva) return 0;
                ++count;
            }
    }
    return count == 1;
}

static uint8_t *call_stub(uint8_t *at, void *helper, int shadow_prefix)
{
    unsigned int n = 0;
    /* preserve flags/registers, call cdecl helper(ECX or ESI) */
    at[n++] = 0x9c; at[n++] = 0x60;
    at[n++] = shadow_prefix ? 0x51 : 0x56;
    at[n++] = 0xb8; put32(at + n, (uint32_t)(uintptr_t)helper); n += 4;
    at[n++] = 0xff; at[n++] = 0xd0;
    at[n++] = 0x83; at[n++] = 0xc4; at[n++] = 0x04;
    if (shadow_prefix) {
        /* write the return value to pushad's saved EAX */
        at[n++] = 0x89; at[n++] = 0x44; at[n++] = 0x24; at[n++] = 0x1c;
    }
    at[n++] = 0x61; at[n++] = 0x9d;
    if (!shadow_prefix) { jump(at + n, module + 0x162049); return at; }
    at[n++] = 0x85; at[n++] = 0xc0;
    at[n++] = 0x74; at[n++] = 0x0b;
    at[n++] = 0x56; at[n++] = 0x57;
    at[n++] = 0x8b; at[n++] = 0xf1;
    at[n++] = 0x8b; at[n++] = 0xf8;
    jump(at + n, module + 0x375cb6); n += 5;
    /* Exactly the displaced vanilla prefix; ECX, ESI and EDI retained. */
    at[n++] = 0x56; at[n++] = 0x57; at[n++] = 0x68;
    put32(at + n, (uint32_t)(uintptr_t)(module + FISTS_STRING)); n += 4;
    jump(at + n, module + 0x375c87);
    return at;
}

void pfi_melee_server(void)
{
    IMAGE_NT_HEADERS32 *nt;
    uint8_t *code, patch[20];
    unsigned int i;
    DWORD old;
    if (installed) return;
    module = (uint8_t *)GetModuleHandleA("vampire.dll");
    nt = headers();
    if (!nt) {  return; }
    for (i = 0; i < sizeof(hooks) / sizeof(hooks[0]); ++i)
        if (!signature_ok(hooks + i, nt)) {
            
            return;
        }
    /* Helpers whose native ABI is used by this prototype. */
    /* Combined-model descriptor lookup must return NULL beyond its table. */
    if(memcmp(module+0x1215c,"\xe9\x1f\x53\x0b\x00",5) ||
       memcmp(module+0xc7480,"\x53\x55\x56\x57\x8b\x7c\x24\x14\x33\xed\x3b\xfd\x0f\x84\x94\x00\x00\x00\x8b\x5c\x24\x18\x3b\xdd\x0f\x8c\x88\x00\x00\x00\x3b\x9f\x10\x01\x00\x00\x7d\x18",38) ||
       memcmp(module+0xc7526,"\x33\xc0\x5f\x5e\x5d\x5b\xc3",7)) return;
    if(memcmp(module+0x91080,"\x53\x55\x56\x8b\xf1\x85\xf6\x57\x74\x11",10) ||
       memcmp(module+0x911c6,"\xc2\x04\x00",3)) return;
    if (memcmp(module + GET_WEAPON, "\x85\xc9\x74\x11\x8b\x91\x6c\x02\x00\x00", 10) ||
        memcmp(module+WEAPON_TRANSLATE,weapon_translate_prefix,sizeof(weapon_translate_prefix)-1) ||
        memcmp(module+0x24f2dc,"\xc2\x04\x00",3) ||
        memcmp(module+0x24f2e5,"\x83\xc4\x0c\xc2\x04\x00",6) ||
        memcmp(module + 0x32e81a, "\x8b\x81\xa4\x19\x00\x00", 6) ||
        memcmp(module + 0x8fe80, "\x85\xc9\x74\x11\x8b\x91\x6c\x02\x00\x00", 10) ||
        memcmp(module+ABS_ORIGIN,origin_prefix,sizeof(origin_prefix)-1) ||
        memcmp(module+0xb323b,"\x8d\x86\x04\x04\x00\x00\x5e\xc3",8) ||
        memcmp(module+SEQUENCE_DESC,descriptor_prefix,sizeof(descriptor_prefix)-1) ||
        memcmp(module+0x8da7d,"\xc2\x04\x00",3) ||
        memcmp(module + 0x32fe60, "\x53\x55\x56\x8b\xf1\x85\xf6\x57\x74\x11", 10) ||
        memcmp(module+INVENTORY_FRONT,inventory_front_prefix,sizeof(inventory_front_prefix)-1) ||
        memcmp(module+0x33589d,inventory_front_rotate,sizeof(inventory_front_rotate)-1) ||
        memcmp(module+0x31e3bb,"\xc7\x05\x6c\x8c\x61\x10\x80\x13\x00\x00",2) ||
        *(uint32_t *)(module+0x31e3bd)!=(uint32_t)(uintptr_t)(module+0x618c6c) ||
        *(uint32_t *)(module+0x31e3c1)!=0x1380 ||
        strcmp((const char *)(module+0x61be48),"m_iVActiveDisciplinesCurrent[ v_discipline_protean ]") ||
        strcmp((const char *)(module + FISTS_STRING), "item_w_fists") ||
        strcmp((const char *)(module + KATANA_STRING), "item_w_katana")) {
         return;
    }
    code = VirtualAlloc(NULL, 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!code) {  return; }
    for (i = 0; i < sizeof(hooks) / sizeof(hooks[0]); ++i) {
        hooks[i].trampoline = code + i * 64;
        memcpy(hooks[i].saved, module + hooks[i].rva, hooks[i].size);
        memcpy(hooks[i].trampoline, module + hooks[i].rva, hooks[i].size);
        if (hooks[i].rva == 0x376f20)
            put32(hooks[i].trampoline + 4,
                  (uint32_t)((module + 0x123af) - (hooks[i].trampoline + 8)));
        if (hooks[i].rva == 0x00f03d || hooks[i].rva == 0x00c036)
            jump(hooks[i].trampoline, module + (hooks[i].rva == 0xf03d ? 0x1e56e0 : 0x1e5b30));
        if (hooks[i].rva == 0x0032b0) jump(hooks[i].trampoline, module + 0x32d380);
        if (hooks[i].rva == 0x012503) jump(hooks[i].trampoline, module + 0x1618e0);
        if (hooks[i].rva == 0x00d4e0) jump(hooks[i].trampoline, module + 0x328030);
        if (hooks[i].rva == 0x00d0b2) jump(hooks[i].trampoline, module + 0x260a50);
        if (hooks[i].rva == 0x002a7c) jump(hooks[i].trampoline, module + 0x292de0);
        if (hooks[i].rva == 0x003f35) jump(hooks[i].trampoline, module + 0x1cca80);
        if (hooks[i].rva == 0x012328) jump(hooks[i].trampoline, module + 0x1d2530);
        if (hooks[i].rva == 0x00b230) jump(hooks[i].trampoline,module+0x8dac0);
        if (hooks[i].rva == 0x006fbe) jump(hooks[i].trampoline,module+0x345480);
        if (hooks[i].rva == 0x012512) jump(hooks[i].trampoline, module + 0x0c5d10);
        jump(hooks[i].trampoline + hooks[i].size, module + hooks[i].rva + hooks[i].size);
    }
    original_collector=(CollectorFn)hook_trampoline(0xb230);
    original_next_attack=(NextAttackFn)hook_trampoline(0x6fbe);
    original_check = (CheckFn)hook_trampoline(0x161fc0);
    original_sequence = (SequenceFn)hook_trampoline(0x8dc40);

    original_end = (EndFn)hook_trampoline(0x12503);
    original_destroy = (DestroyFn)hook_trampoline(0x376f20);
    original_heaviest = (SequenceFn)hook_trampoline(0x8dd30);
    original_equip = (EquipFn)hook_trampoline(0x32b0);
    original_early_activity = (TranslateFn)hook_trampoline(0xd4e0);
    original_set_activity = (ActivityFn)hook_trampoline(0x2725d0);
    original_reset_sequence = (ActivityFn)hook_trampoline(0xd0b2);

    original_melee = (MeleeFn)hook_trampoline(0x3e9e00);
    original_swing = (SwingFn)hook_trampoline(0x343020);

    original_interval_movement=(IntervalMovementFn)hook_trampoline(0x94b70);
    original_sequence_movement=(SequenceMovementFn)hook_trampoline(0x12512);
    original_frenzy_end = (ThinkFn)hook_trampoline(0x33f6d0);
    original_leave_grapple = (ThinkFn)hook_trampoline(0x329a70);
    /* Trampolines precede helpers; never overlap when hook count grows. */
    hooks[1].replacement = call_stub(code + 0x800, (void *)select_start_weapon, 0);
    hooks[2].replacement = call_stub(code + 0x880, (void *)prepare_shadow, 1);
    if(!pfi_code_ready(code,0x1000)){VirtualFree(code,0,MEM_RELEASE);return;}
    PfiPatch batch[sizeof(hooks)/sizeof(hooks[0])];int committed;
    for(i=0;i<sizeof(hooks)/sizeof(hooks[0]);++i)
        pfi_jump(batch+i,module+hooks[i].rva,hooks[i].size,hooks[i].replacement);
    committed=pfi_commit(batch,sizeof(hooks)/sizeof(hooks[0]));
    if(committed==1)installed=1;
    else if(!committed)VirtualFree(code,0,MEM_RELEASE);
}
