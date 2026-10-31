/* Native labels, independently resolved for each actor/model. No resource writes. */
/* Positive stock attacks except jumps (including hammer D1), strong push
   finishers and sword far_roll. Duration is deliberately not a criterion. */
typedef struct { const char *weapon; const char *prefix; const char *labels[32]; } ShortFamily;
static const ShortFamily short_families[] = {
    {"item_w_knife", "knife_attack_", {"med","med2","Slash","Slash2","npc_Slash","W1","far","medcombo","farcombo","heavy",NULL}},
    {"item_w_tire_iron", "tireiron_attack_", {"hack","hack2","slash","slash2","W2","W1","medcombo","lowcombo",NULL}},
    {"item_w_baseball_bat", "baseballbat_attack_", {"med","low","Center2","W2","A1","W1","A2","Center1","medcombo","lowcombo","farcombo",NULL}},
    {"item_w_bush_hook", "bushhook_attack_", {"midright","W1","W2","SwingRight","SwingRight_2nd","shortmed","shortmedcombo","medcombo","farcombo",NULL}},
    {"item_w_sledgehammer", "sledgehammer_", {"attack_low","attack_midright","combo_A2","combo_B2","attack_W1","attack_SwingRight","attack_SwingRight_2nd","attack_far","attack_shortmedcombo","attack_medcombo","attack_farcombo","attack_heavy","combo_A1","combo_B1","combo_C2",NULL}},
    {"item_w_katana", "katana_", {"attack_med","attack_Left_Right","attack_Left_Right2","attack_heavy","combo_A1","combo_A2","combo_B1","combo_B2","combo_C1","combo_C2","combo_D1","combo_D2","attack_far_spin","attack_Run","attack_SweepKickCombo","attack_medcombo","running_attack",NULL}}
};
typedef int (TC *CollectorFn)(void *,int,int *,int *,void *);
typedef int (TC *NextAttackFn)(void *);
typedef float (TC *DurationFn)(void *,int);
static CollectorFn original_collector;
static NextAttackFn original_next_attack;

static const ShortFamily *short_family(const WeaponProfile *profile)
{
    const char *name;
    unsigned int i;
    if(!profile || profile->frenzy_animation) return NULL;
    name=profile->name;
    if(!strcmp(name,"item_w_baton") || !strcmp(name,"item_w_torch") ||
       !strcmp(name,"item_w_severed_arm")) name="item_w_tire_iron";
    if(!strcmp(name,"item_w_fireaxe")) name="item_w_sledgehammer";
    if(!strcmp(name,"item_w_avamp_blade") || !strcmp(name,"item_w_chang_blade") ||
       !strcmp(name,"item_w_occultblade")) name="item_w_katana";
    for(i=0;i<sizeof(short_families)/sizeof(short_families[0]);++i)
        if(!strcmp(name,short_families[i].weapon)) return short_families+i;
    return NULL;
}

static int short_allowed(void *actor,int sequence,const ShortFamily *family)
{
    const uint8_t *desc;
    const char *name;
    unsigned int i;
    size_t prefix;
    if(!family || sequence<0 || sequence>8191) return 0;
    desc=((SequenceDescFn)(module+SEQUENCE_DESC))(actor,sequence);
    if(!desc || *(int *)(desc+0x10)<=0 || *(int *)(desc+0x2ec)>0) return 0;
    name=sequence_name(actor,sequence);prefix=strlen(family->prefix);
    /* Stock labels/continuation references vary in case (Knife, BushHook, etc.). */
    if(_strnicmp(name,family->prefix,prefix)) return 0;
    for(i=0;family->labels[i];++i)
        if(!_stricmp(name+prefix,family->labels[i])) return 1;
    return 0;
}

static int short_filter(void *actor,const ShortFamily *family,int *ids,int *weights,int count)
{
    int i,n=0;
    if(count<=0) return count;
    if(count>2048 || !ids || !weights) return 0;
    for(i=0;i<count;++i) if(weights[i]>0 && short_allowed(actor,ids[i],family)) {
        ids[n]=ids[i];weights[n]=weights[i];++n;
    }
    return n;
}

static int short_preflight(void *actor,int activity,const WeaponProfile *profile)
{
    int ids[2048],weights[2048],count,i;
    unsigned int found=0,j,required=0;
    const ShortFamily *family=short_family(profile);
    if(!inventory_provider_available()) return 0;
    if(!family) return profile && profile->frenzy_animation;
    count=original_collector(actor,activity,ids,weights,(void *)-1);
    if(count<=0 || count>2048) return 0;
    /* Inspect model metadata, not an activity's candidate list: heavy/composite
       sequences have distinct native activities and need not be in that list.
       The already guarded helper returns NULL after the combined model table. */
    for(i=0;i<8192;++i) {
        const uint8_t *desc=((SequenceDescFn)(module+SEQUENCE_DESC))(actor,i);
        const char *name;
        if(!desc) break;
        name=sequence_name(actor,i);
        if(_strnicmp(name,family->prefix,strlen(family->prefix))) continue;
        if(*(int *)(desc+0x2ec)>0) return 0;
        for(j=0;family->labels[j];++j) {
            size_t prefix=strlen(family->prefix);
            if(*(int *)(desc+16)>0 && !_strnicmp(name,family->prefix,prefix) &&
               !_stricmp(name+prefix,family->labels[j])) found|=1u<<j;
        }
    }
    if(i==8192) return 0;
    for(j=0;family->labels[j];++j) required|=1u<<j;
    if(found!=required) return 0;
    return short_filter(actor,family,ids,weights,count)>0;
}

static int FC collect_short_attacks(void *self,void *unused,int activity,int *ids,int *weights,void *stat)
{
    int count=original_collector(self,activity,ids,weights,stat);
    (void)unused;
    if(activity==attack_activity && katana_shadow(self) && short_family(active_profile))
        return short_filter(self,short_family(active_profile),ids,weights,count);
    return count;
}

static int FC next_short_attack(void *self,void *unused)
{
    int sequence=original_next_attack(self);
    (void)unused;
    if(sequence>=0 && katana_shadow(self) && short_family(active_profile) &&
       *(int *)((uint8_t *)self+0xfec)==attack_activity &&
       !short_allowed(self,sequence,short_family(active_profile))) return -1;
    return sequence;
}
