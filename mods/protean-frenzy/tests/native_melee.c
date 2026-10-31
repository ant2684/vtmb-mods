#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>
/* Windows toolchain may define NDEBUG: technical checks must still execute. */
static void harness_failure(const char *expression, int line) {
    fprintf(stderr,"CHECK FAILED line %d: %s\n",line,expression);
    ExitProcess(1);
}
#undef assert
#define assert(expression) ((expression) ? (void)0 : harness_failure(#expression,__LINE__))
static HMODULE WINAPI mock_module(LPCSTR name);
static void __attribute__((thiscall)) mock_explicit_activity(void *,int,int,int);
static int __attribute__((thiscall)) mock_damage(void *,void *);
static unsigned int protection_calls, fail_protection_call;
static BOOL WINAPI mock_protect(LPVOID address, SIZE_T size, DWORD protect, PDWORD old) {
    if (++protection_calls == fail_protection_call) return FALSE;
    return VirtualProtect(address,size,protect,old);
}
#define GetModuleHandleA mock_module
#define VirtualProtect mock_protect
#include "../native/melee.c"
#include "../native/patch.c"
int pfi_inventory_ready=1;

static HMODULE WINAPI mock_module(LPCSTR name) {
 return !strcmp(name,"vampire.dll")?(HMODULE)module:NULL;
}
/* The duplicate policy is compiled from its single production owner. The mock
   Equip below still models native non-idempotent insertion after this policy. */
typedef uint8_t B;
static unsigned u(B *p,unsigned offset){return *(unsigned *)(p+offset);}
static int isclass(B *p,const char *name){return p&&!strcmp(classname(p),name);}
#define resolve resolve_handle
#include "../native/frenzy_inventory.h"
#undef resolve
static InventoryAddFn inventory_fixture_original;
static void inventory_delegate(void *self,void *unused,void *weapon){
    (void)unused;
    if(frenzy_inventory_scope(self,weapon)&&frenzy_inventory_registered(self,weapon))return;
    inventory_fixture_original(self,weapon);
    if(isclass(self,"player")&&isclass(weapon,"item_w_fists"))restore_fists_order(self,weapon);
}


/* Separate test executable; never installed into the game or shipped as payload. */
static int TC mock_activity(void *self, int activity) { (void)self; return activity; }
static int set_activity_calls;
static void TC mock_set_activity(void *self, int activity) { ++set_activity_calls; *(int *)((uint8_t *)self+0xfec)=activity; }
static int explicit_original_calls, explicit_translated, explicit_sequence;
static uint8_t *damage_target;
static int damage_original_calls, melee_original_calls;
static int melee_activity, melee_a, melee_b, melee_result=1, select_in_melee;
static void *melee_self;
static int suitability_calls, suitability_activity, suitability_selected=820;
static unsigned char suitability_result;
static void *suitability_self,*suitability_weapon,*suitability_target;
static int *suitability_output;
static int box_calls,clip_calls;
static void **box_list;
static void *box_result;
static const float *box_lo,*box_hi;
static int CC mock_box(void **list,int capacity,const float *lo,const float *hi,int mask,int type) {
    ++box_calls;assert(list==box_list && capacity==2 && lo==box_lo && hi==box_hi && mask==0x22102080 && type==1);
    list[0]=box_result;return 1;
}
static const void *clip_ray;
static void *clip_actor,*clip_output;
static void CC mock_clip(const void *ray,unsigned int mask,void *entity,void *trace) {
    ++clip_calls;assert(ray==clip_ray && mask==0x200400b && entity==clip_actor && trace==clip_output);
    *(float *)((uint8_t *)trace+0x2c)=0.375f;
}
static int interval_calls;
static void *interval_self,*interval_finished,*interval_position,*interval_angles;
static float TC mock_interval(void *self,float interval,void *finished,void *position,void *angles) {
    ++interval_calls;
    assert(self==interval_self && interval==0.125f && finished==interval_finished &&
           position==interval_position && angles==interval_angles);
    if(finished) *(unsigned char *)finished=1;
    if(position) ((float *)position)[0]=123.25f;
    if(angles) ((float *)angles)[2]=-45.5f;
    return 17.625f;
}
static unsigned char TC mock_suitability(void *self,void *weapon,void *target,int activity,int *sequence) {
    ++suitability_calls;suitability_self=self;suitability_weapon=weapon;
    suitability_target=target;suitability_activity=activity;suitability_output=sequence;
    if(sequence) *sequence=suitability_selected;
    return suitability_result;
}
static int root_calls;
static float root_from,root_to;
static void *root_header;
static const float *root_pose;
static unsigned char CC mock_root(void *header,int sequence,float from,float to,const float *pose,float *position,float *angles) {
    ++root_calls;root_from=from;root_to=to;
    assert(header==root_header && sequence==812 && pose==root_pose);
    if(position) position[0]=(to*to-from*from)*100;
    if(angles) angles[1]=12.5f;
    return 7;
}
static float TC mock_interval_root(void *self,float interval,void *finished,void *position,void *angles) {
    float current=*(float *)((uint8_t *)self+0x6f8);
    assert(interval==0.125f);
    assert(sequence_movement_at(module+0x94c83,root_header,812,current,current+.1f,root_pose,position,angles)==7);
    *(unsigned char *)finished=1;
    return ((float *)position)[0];
}
static const float *TC mock_origin(void *self) { return (float *)((uint8_t *)self+0x404); }
static const uint8_t *TC mock_descriptor(void *self, int sequence) {
    static uint8_t descriptor[764]; (void)self;(void)sequence;
    *(float *)(descriptor+0x2cc)=40;*(float *)(descriptor+0x2d0)=80;return descriptor;
}
static int swing_original_calls;
static void *swing_packet;
static float swing_position[3]={1,2,3},swing_angles[3]={4,5,6};
static void TC mock_swing(void *self, void *position, void *angles, float cycle, float previous_cycle) {
    (void)self;
    if (position!=swing_position || angles!=swing_angles || cycle!=0.5f || previous_cycle!=3.0f) abort();
    ++swing_original_calls;
    assert(mock_damage(damage_target,swing_packet)==7);
}
static int TC mock_damage(void *self, void *info) {
    ++damage_original_calls;
    if (info) *(int *)((uint8_t *)self+0x210)-=(int)*(float *)((uint8_t *)info+0x30);
    return 7;
}
static unsigned char TC mock_melee(void *self, int activity, int a, int b) {
    ++melee_original_calls;melee_self=self;melee_activity=activity;melee_a=a;melee_b=b;
    if(select_in_melee) {
        void *owner=resolve_handle(*(int *)((uint8_t *)self+0x88c));
        mock_explicit_activity(owner,activity,activity,812);
    }
    return (unsigned char)melee_result;
}
static void TC mock_explicit_activity(void *self, int activity, int translated, int sequence) {
    ++explicit_original_calls;explicit_translated=translated;explicit_sequence=sequence;
    *(int *)((uint8_t *)self+0xfec)=activity;
    *(int *)((uint8_t *)self+0x6f0)=sequence;
}
static int TC mock_sequence(void *self, int activity, void *stat) {
    (void)self; (void)stat; return activity;
}
static void *equip_self, *equip_weapon;
static int equip_flags, equip_calls;
static void *fixture_player, *fixture_shadow;
static void *creation_weapon;
static int creation_fail, creation_refuse, creation_unequipped, removed_count, unavailable_actor;
static int translated_weapon_activity;
static void *TC mock_give(void *self, const char *name) {
    assert(self==fixture_shadow && pending_profile && !strcmp(name,pending_profile->name));
    return creation_fail?NULL:creation_weapon;
}
static unsigned char TC mock_can_equip(void *self, void *weapon) {
    assert(self==fixture_shadow && weapon==creation_weapon);return !creation_refuse;
}
static void TC mock_remove(void *weapon) { assert(weapon==creation_weapon);++removed_count; }
static int TC mock_weapon_translate(void *weapon, int activity) {
    assert(weapon==creation_weapon && activity==ATTACK_MELEE);return translated_weapon_activity;
}
static void TC mock_creation_equip(void *self, void *weapon, int flags) {
    assert(self==fixture_shadow && weapon==creation_weapon && flags==0);
    if(!creation_unequipped) *(void **)((uint8_t *)self+0x80)=weapon;
}
static int TC mock_available_sequence(void *self, int activity, void *stat) {
    assert(stat==(void *)-1);
    if((unavailable_actor==1 && self==fixture_player) || (unavailable_actor==2 && self==fixture_shadow)) return -1;
    assert(activity==translated_weapon_activity || activity==ATTACK_FRENZY);
    return self==fixture_player?700:800; /* Deliberately model-local IDs. */
}

static int policy_female, policy_alt, policy_bad, collector_calls, collector_count=3, next_result=104;
static int policy_count(const WeaponProfile *p);
static const char *TC policy_name(void *self,int seq) {
    static char names[32][100];
    const ShortFamily *f=short_family(pending_profile?pending_profile:active_profile);
    int index=seq%100;
    (void)self;
    if(!f || index<0 || index>=32 || !f->labels[index]) return "forbidden_far_roll";
    snprintf(names[index],sizeof(names[index]),"%s%s",f->prefix,f->labels[index]);return names[index];
}
static const uint8_t *TC policy_desc(void *self,int seq) {
    static uint8_t d[764];(void)self;
    if(seq%100>policy_count(pending_profile?pending_profile:active_profile))return NULL;
    memset(d,0,sizeof(d));*(int *)(d+16)=policy_bad?0:3;*(int *)(d+0x2ec)=policy_alt?20:-1;
    return d;
}
static float TC policy_duration(void *self,int seq) { (void)self;(void)seq;return policy_female?1.3f:.8f; }
static int policy_count(const WeaponProfile *p) {
    const ShortFamily *f=short_family(p);int n=0;
    if(!f)return 5;
    while(f->labels[n])++n;
    return n;
}
static int TC policy_collect(void *self,int activity,int *ids,int *weights,void *stat) {
    int i; (void)activity;(void)stat;++collector_calls;
    if((unavailable_actor==1 && self==fixture_player) || (unavailable_actor==2 && self==fixture_shadow)) return 0;
    if(collector_count<0) return collector_count;
    for(i=0;i<collector_count;++i) { ids[i]=(self==fixture_player?100:200)+i;weights[i]=i+1; }
    return collector_count;
}
static int TC policy_next(void *self) { (void)self;return next_result; }

static int inventory_add_calls;
static int inventory_front_calls;
static int end_original_calls, exit_select_calls;
static void *expected_exit;
static void TC mock_exit_select(void *player, const char *name, int index) {
    ++exit_select_calls;
    assert(index==0 && !strcmp(name,classname(expected_exit)));
    if(resolve_handle(*(int *)((uint8_t *)player+0x1538)) && *(int *)((uint8_t *)player+0x153c)!=-1) return;
    *(void **)((uint8_t *)player+0x80)=expected_exit;
}
static void TC mock_leave_grapple(void *self) {
    *(int *)((uint8_t *)self+0x1538)=-1;*(int *)((uint8_t *)self+0x153c)=-1;
}
static void TC mock_frenzy_end(void *character) {
    void *p=*(void **)((uint8_t *)character+0xa8);
    ++end_original_calls;
    if(exit_player) assert(exit_weapon(p)==expected_exit);
    *(int *)((uint8_t *)p+0x146c)=0;
    *(int *)((uint8_t *)p+0x1db0)=-1;
}
static void TC mock_inventory_front(void *self, void *weapon) {
    unsigned int slot=*(unsigned int *)((uint8_t *)weapon+0x73c),i;
    int h=handle_of(weapon);
    ++inventory_front_calls;
    assert(self==fixture_player && slot<32);
    for(i=slot;i>0;--i) {
        int previous=*(int *)((uint8_t *)self+0x1624+(i-1)*4);
        void *item=resolve_handle(previous);assert(item);
        *(int *)((uint8_t *)self+0x1624+i*4)=previous;
        *(unsigned int *)((uint8_t *)item+0x73c)=i;
    }
    *(int *)((uint8_t *)self+0x1624)=h;
    *(unsigned int *)((uint8_t *)weapon+0x73c)=0;
}
static void TC mock_inventory_add(void *self, void *weapon) {
    ++inventory_add_calls;
    if ((self==fixture_player || self==fixture_shadow) && weapon) {
        unsigned int slot;
        /* Model native full Equip's non-idempotent registration. A duplicate
           call must fail the slot-preservation regression, not be mocked away. */
        for(slot=0;slot<224;++slot) if (*(int *)((uint8_t *)self+0x1624+slot*4)==-1) {
            *(int *)((uint8_t *)self+0x1624+slot*4)=handle_of(weapon);
            *(int *)((uint8_t *)weapon+0x73c)=(int)slot;
            *(int *)((uint8_t *)weapon+0x88c)=handle_of(self);
            break;
        }
    }
}
static void TC mock_equip(void *self, void *weapon, int flags) {
    ++equip_calls;
    equip_self=self;equip_weapon=weapon;equip_flags=flags;
    if (self==fixture_player || self==fixture_shadow) {
        inventory_delegate(self,NULL,weapon);
        *(void **)((uint8_t *)self+0x80)=weapon;
    }
}
static void install_fixture(void) {
    unsigned int i;
    IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER *)module;
    IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32 *)(module+0x80);
    IMAGE_SECTION_HEADER *section;
    memset(module,0,0xb00000);
    dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=0x80;
    nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=0x14c;nt->FileHeader.TimeDateStamp=0x41afafae;
    nt->FileHeader.NumberOfSections=1;
    nt->FileHeader.SizeOfOptionalHeader=sizeof(IMAGE_OPTIONAL_HEADER32);
    nt->OptionalHeader.Magic=0x10b;nt->OptionalHeader.SizeOfImage=0xab9000;
    section=IMAGE_FIRST_SECTION(nt);
    section->VirtualAddress=0x1000;section->Misc.VirtualSize=0x420000;
    section->Characteristics=IMAGE_SCN_MEM_EXECUTE;
    for (i=0;i<sizeof(hooks)/sizeof(hooks[0]);++i)
        memcpy(module+hooks[i].rva,hooks[i].expected,hooks[i].signature_size);
    put32(module+0x162038+5,(uint32_t)(uintptr_t)(module+FISTS_STRING));
    put32(module+0x162038+18,(uint32_t)(uintptr_t)(module+0x586278));
    put32(module+0x375c80+3,(uint32_t)(uintptr_t)(module+FISTS_STRING));
    {
        static const unsigned int offsets[]={0x16,0x1d,0x22,0x2c,0x33};
        for(i=0;i<sizeof(offsets)/sizeof(offsets[0]);++i) {
            uint32_t address;
            memcpy(&address,module+0x32ef60+offsets[i],4);
            put32(module+0x32ef60+offsets[i],address-0x10000000+(uint32_t)(uintptr_t)module);
        }
    }
    memcpy(module+GET_WEAPON,"\x85\xc9\x74\x11\x8b\x91\x6c\x02\0\0",10);
    {
        static const unsigned int offsets[]={22,29,34,46,53};
        for(i=0;i<sizeof(offsets)/sizeof(offsets[0]);++i) {
            uint32_t address;memcpy(&address,module+0x94b70+offsets[i],4);
            put32(module+0x94b70+offsets[i],address-0x10000000+(uint32_t)(uintptr_t)module);
        }
    }
    memcpy(module+0x32e81a,"\x8b\x81\xa4\x19\0\0",6);
    memcpy(module+0x8fe80,"\x85\xc9\x74\x11\x8b\x91\x6c\x02\0\0",10);
    memcpy(module+ABS_ORIGIN,origin_prefix,sizeof(origin_prefix)-1);
    memcpy(module+0xb323b,"\x8d\x86\x04\x04\0\0\x5e\xc3",8);
    memcpy(module+SEQUENCE_DESC,descriptor_prefix,sizeof(descriptor_prefix)-1);
    memcpy(module+0x8da7d,"\xc2\x04\0",3);
    memcpy(module+0x1215c,"\xe9\x1f\x53\x0b\x00",5);
    memcpy(module+0xc7480,"\x53\x55\x56\x57\x8b\x7c\x24\x14\x33\xed\x3b\xfd\x0f\x84\x94\x00\x00\x00\x8b\x5c\x24\x18\x3b\xdd\x0f\x8c\x88\x00\x00\x00\x3b\x9f\x10\x01\x00\x00\x7d\x18",38);
    memcpy(module+0xc7526,"\x33\xc0\x5f\x5e\x5d\x5b\xc3",7);
    memcpy(module+0x32fe60,"\x53\x55\x56\x8b\xf1\x85\xf6\x57\x74\x11",10);
    memcpy(module+INVENTORY_FRONT,inventory_front_prefix,sizeof(inventory_front_prefix)-1);
    memcpy(module+0x33589d,inventory_front_rotate,sizeof(inventory_front_rotate)-1);
    memcpy(module+WEAPON_TRANSLATE,weapon_translate_prefix,sizeof(weapon_translate_prefix)-1);
    memcpy(module+0x24f2dc,"\xc2\x04\x00",3);
    memcpy(module+0x24f2e5,"\x83\xc4\x0c\xc2\x04\x00",6);
    memcpy(module+0x31e3bb,"\xc7\x05",2);
    put32(module+0x31e3bd,(uint32_t)(uintptr_t)(module+0x618c6c));
    put32(module+0x31e3c1,0x1380);
    strcpy((char *)(module+0x61be48),"m_iVActiveDisciplinesCurrent[ v_discipline_protean ]");
    strcpy((char *)(module+FISTS_STRING),"item_w_fists");
    strcpy((char *)(module+KATANA_STRING),"item_w_katana");
    memcpy(module+0x91080,"\x53\x55\x56\x8b\xf1\x85\xf6\x57\x74\x11",10);
    memcpy(module+0x911c6,"\xc2\x04\x00",3);
    installed=0;protection_calls=0;fail_protection_call=0;
}
int main(void)
{
    setbuf(stdout,NULL);
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    unsigned int i, j;
    uint8_t *code = VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    uint8_t *player, *shadow, *weapon, *player_weapon, *table;
    void *pc, *npc;
    module = VirtualAlloc(NULL, 0xb00000, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    player = calloc(1, 0x3000); shadow = calloc(1, 0x7000);
    weapon = calloc(1, 0x2000); table = calloc(8192, 12);
    player_weapon = calloc(1, 0x2000);
    /* These mocks also serve as requested equipment in forwarding tests. */
    pc = calloc(1, 0x200); npc = calloc(1, 0x2000);
    assert(module && code && player && shadow && weapon && table && pc && npc);
    for (i = 0; i < sizeof(hooks)/sizeof(hooks[0]); ++i) {
        printf("HOOK %x %u ", hooks[i].rva, hooks[i].size);
        for (j = 0; j < hooks[i].signature_size; ++j) printf("%02x", hooks[i].expected[j]);
        puts("");
    }
    for (i = 0; i < 2; ++i) {
        call_stub(code, (void *)0x20000000, i);
        printf("STUB %u %x %x ", i, (unsigned int)(uintptr_t)code, (unsigned int)(uintptr_t)module);
        for (j = 0; j < 80; ++j) printf("%02x", code[j]);
        puts("");
    }
    printf("HELPER 33589d ");
    for(j=0;j<sizeof(inventory_front_rotate)-1;++j) printf("%02x",inventory_front_rotate[j]);
    puts("");
    printf("HELPER 24f210 ");
    for(j=0;j<sizeof(weapon_translate_prefix)-1;++j) printf("%02x",weapon_translate_prefix[j]);
    puts("");
    *(void **)(module + ENTITY_TABLE) = table;
    *(void **)(table + 16) = player; *(uint32_t *)(table + 20) = 7;
    *(void **)(table + 28) = shadow; *(uint32_t *)(table + 32) = 8;
    *(void **)(table + 40) = weapon; *(uint32_t *)(table + 44) = 9;
    *(void **)(table + 52) = player_weapon; *(uint32_t *)(table + 56) = 10;
    *(void **)(table + 76) = npc; *(uint32_t *)(table + 80) = 12;
    fixture_player=player;fixture_shadow=shadow;
    *(const char **)(player+0x11c)="player";
    *(const char **)(shadow+0x11c)="npc_VFrenzyShadow";

    {
        unsigned char finished=0;float position[3]={0,0,0},angles[3]={0,0,0};
        original_interval_movement=mock_interval;
        interval_self=player;interval_finished=&finished;interval_position=position;interval_angles=angles;
        assert(interval_movement(player,NULL,0.125f,&finished,position,angles)==17.625f);
        assert(interval_calls==1 && finished==1 && position[0]==123.25f && angles[2]==-45.5f);
        interval_self=interval_finished=interval_position=interval_angles=NULL;
        assert(interval_movement(NULL,NULL,0.125f,NULL,NULL,NULL)==17.625f && interval_calls==2);
        puts("PASS interval observer: original once, exact arguments/float result/output, unrelated/null forwarding");
    }
    for(i=0;i<224;++i) {
        *(int *)(player+0x1624+i*4)=-1;
        *(int *)(shadow+0x1624+i*4)=-1;
    }
    player_handle = (7 << 13) | 1; shadow_handle = (8 << 13) | 2;
    katana_handle = (9 << 13) | 3;
    player_katana_handle = (10 << 13) | 4;
    *(void **)shadow = module + SHADOW_VTABLE;
    *(void **)(player + 0x9c) = pc; *(void **)(shadow + 0x9c) = npc;
    *(int *)(player + 0x146c) = 10; *(int *)(player + 0x1db0) = shadow_handle;
    *(const char **)(weapon + 0x11c) = "item_w_katana";
    *(const char **)(player_weapon + 0x11c) = "item_w_katana";
    active_profile=weapon_profile(weapon);attack_activity=ATTACK_KATANA;
    /* Distinct original player katana and temporary Shadow katana. */
    memcpy(module+GET_WEAPON,"\x8b\x81\x80\0\0\0\xc3",7);
    *(void **)(player+0x80)=player_weapon;*(void **)(shadow+0x80)=weapon;
    *(int *)(player+0x1628)=player_katana_handle;
    *(int *)(player_weapon+0x73c)=1;
    *(int *)(player_weapon+0x88c)=player_handle;
    *(int *)(shadow+0x1624)=katana_handle;
    *(int *)(weapon+0x73c)=0;
    FlushInstructionCache(GetCurrentProcess(), module, 0xb00000);
    jump(module+INVENTORY_FRONT,(void *)mock_inventory_front);
    FlushInstructionCache(GetCurrentProcess(),module+INVENTORY_FRONT,5);
    original_early_activity=mock_activity;
    original_sequence=original_heaviest=mock_sequence;
    original_equip=mock_equip;
    inventory_fixture_original=mock_inventory_add;
    original_set_activity=mock_set_activity;
    original_melee=mock_melee;
    jump(module+SEQUENCE_DESC,(void *)mock_descriptor);
    FlushInstructionCache(GetCurrentProcess(),module+SEQUENCE_DESC,5);
    *(int *)(weapon+0x88c)=shadow_handle;
    /* Every profile binds the exact original and temporary object. Tiger's
       explicit donor triple must pass through unchanged, including RUN. */
    for(i=0;i<sizeof(profiles)/sizeof(profiles[0]);++i) {
        *(const char **)(weapon+0x11c)=profiles[i].name;
        *(const char **)(player_weapon+0x11c)=profiles[i].name;
        active_profile=weapon_profile(weapon);assert(active_profile==profiles+i);
        attack_activity=profiles[i].frenzy_animation?ATTACK_FRENZY:2000+(int)i;
        set_activity(shadow,NULL,ATTACK_FRENZY);
        assert(*(int *)(shadow+0xfec)==attack_activity);
        mock_explicit_activity(shadow,ATTACK_FRENZY,777,888);
        assert(*(int *)(shadow+0xfec)==ATTACK_FRENZY && explicit_translated==777 && explicit_sequence==888);
        melee_original_calls=0;melee_result=1;select_in_melee=1;set_activity_calls=0;
        assert(melee_attack(weapon,NULL,ATTACK_FRENZY,17,23)==1);
        assert(melee_original_calls==1 && melee_self==weapon && melee_activity==attack_activity && melee_a==17 && melee_b==23);
        assert(*(int *)(shadow+0xfec)==attack_activity && *(int *)(shadow+0x6f0)==812 && explicit_sequence==812 && !set_activity_calls);
        select_in_melee=0;
        assert(early_activity(shadow,NULL,ATTACK_FRENZY)==attack_activity);
        assert(select_sequence(shadow,NULL,ATTACK_FRENZY,NULL)==attack_activity);
        assert(select_heaviest(shadow,NULL,ATTACK_FRENZY,NULL)==attack_activity);
        assert(retained_weapon(shadow,npc)==weapon && retained_weapon(player,npc)==player_weapon);
        assert(feat_character(npc)==pc);
        mock_explicit_activity(shadow,0xf17,0xf17,1587);
        assert(*(int *)(shadow+0xfec)==0xf17 && explicit_sequence==1587);
        exit_katana=player_katana_handle;
        assert(exit_weapon(player)==player_weapon);exit_katana=-1;
    }
    *(const char **)(weapon+0x11c)="item_w_sheriff_sword";assert(!weapon_profile(weapon));
    *(const char **)(weapon+0x11c)="item_w_claws";assert(!weapon_profile(weapon));
    *(const char **)(weapon+0x11c)="item_w_thirtyeight";assert(!weapon_profile(weapon));
    *(const char **)(weapon+0x11c)="item_w_katana";
    *(const char **)(player_weapon+0x11c)="item_w_katana";
    active_profile=weapon_profile(weapon);attack_activity=ATTACK_KATANA;
    explicit_original_calls=0;
    puts("PASS 14 exact melee profiles, Tiger original animation triple, native remap wrappers, RUN, live feats, retained instances and exit; unknown/Protean/firearm excluded");
    mock_explicit_activity(shadow,ATTACK_FRENZY,ATTACK_FRENZY,1584);
    assert(*(int *)(shadow+0xfec)==ATTACK_FRENZY && explicit_original_calls==1 && explicit_sequence==1584);
    mock_explicit_activity(shadow,0xf17,0xf17,1587);
    assert(*(int *)(shadow+0xfec)==0xf17 && explicit_original_calls==2 && explicit_sequence==1587 && explicit_translated==0xf17);
    mock_explicit_activity(player,ATTACK_FRENZY,ATTACK_FRENZY,1584);
    assert(*(int *)(player+0xfec)==ATTACK_FRENZY && explicit_original_calls==3 && explicit_sequence==1584);
    *(const char **)(weapon+0x11c)="item_w_claws";
    mock_explicit_activity(shadow,ATTACK_FRENZY,ATTACK_FRENZY,1584);
    assert(*(int *)(shadow+0xfec)==ATTACK_FRENZY && explicit_original_calls==4);
    *(const char **)(weapon+0x11c)="item_w_katana";
    {
        uint8_t packet[0x4c]={0}, saved_packet[0x4c];
        damage_target=calloc(1,0x3000);assert(damage_target);
        *(void **)(table+64)=damage_target;*(uint32_t *)(table+68)=11;
        *(const char **)(damage_target+0x11c)="npc_VHumanCombatant";
        *(const char **)(damage_target+0x26c)="unit_target";
        *(int *)(damage_target+0x210)=100;
        *(int *)(weapon+0x88c)=shadow_handle;
        *(void **)(packet+0x2c)=shadow;*(float *)(packet+0x30)=12;
        *(uint32_t *)(packet+0x38)=4;
        memcpy(saved_packet,packet,sizeof(packet));
        /* Read-only HealthToPercent fixture for these diagnostic ABI tests. */
        memcpy(module+0x32fe60,"\x8b\x81\x10\x02\0\0\xc3",7);
        module[0x8fe80]=0xb8;put32(module+0x8fe81,(uint32_t)(uintptr_t)"unit_katana_sequence");
        memcpy(module+0x8fe85,"\xc2\x04\0",3);
        FlushInstructionCache(GetCurrentProcess(),module+0x8fe80,8);
        FlushInstructionCache(GetCurrentProcess(),module+0x32fe60,7);
        jump(module+ABS_ORIGIN,(void *)mock_origin);
        jump(module+SEQUENCE_DESC,(void *)mock_descriptor);
        FlushInstructionCache(GetCurrentProcess(),module+ABS_ORIGIN,5);
        FlushInstructionCache(GetCurrentProcess(),module+SEQUENCE_DESC,5);

        melee_original_calls=0;strike_serial=active_strike=0;
        original_melee=mock_melee;
        original_swing=mock_swing;swing_packet=packet;
        assert(melee_attack(weapon,NULL,ATTACK_FRENZY,1,1)==1);
        assert(melee_original_calls==1 && pending_strike==1 && active_strike==0);
        assert(melee_activity==ATTACK_KATANA && melee_a==1 && melee_b==1);
        swing_step(player,NULL,swing_position,swing_angles,0.5f,3);
        assert(!swing_original_calls && !damage_original_calls);
        swing_step(shadow,NULL,swing_position,swing_angles,0.5f,3);
        assert(swing_original_calls==1 && damage_original_calls==1 && pending_strike==1 && active_strike==0 && *(int *)(damage_target+0x210)==88);
        assert(!memcmp(saved_packet,packet,sizeof(packet)));
        puts("PASS production SwingStep mirrored-player suppression and unmodified native damage packet");
    }
    /* Early mapping is never allowed for the original player instance,
       unrelated activities, stale owner serial or stale temporary serial. */
    melee_attack(player_weapon,NULL,ATTACK_FRENZY,3,4);
    assert(melee_activity==ATTACK_FRENZY && melee_a==3 && melee_b==4);
    melee_attack(weapon,NULL,0xf17,5,6);assert(melee_activity==0xf17);
    *(int *)(weapon+0x88c)=shadow_handle+(1<<13);
    melee_attack(weapon,NULL,ATTACK_FRENZY,7,8);assert(melee_activity==ATTACK_FRENZY);
    *(int *)(weapon+0x88c)=shadow_handle;
    melee_result=0;assert(melee_attack(weapon,NULL,ATTACK_FRENZY,9,10)==0);
    assert(melee_activity==ATTACK_KATANA && melee_a==9 && melee_b==10);melee_result=1;
    puts("PASS early temporary-only activity mapping, exact native triple preservation, original parameters/results and stale owner refusal");
    {
        unsigned char finished=0;float position[3]={0,0,0},angles[3]={0,0,0};int saved_activity=*(int *)(shadow+0xfec);
        *(int *)(shadow+0xfec)=attack_activity;*(int *)(shadow+0x6f0)=812;*(float *)(shadow+0x6f8)=.1f;
        pending_strike=11;pending_attacker=shadow_handle;pending_attack_weapon=katana_handle;pending_attack_sequence=812;
        movement_valid=1;movement_previous=0;
        root_header=(void *)0x12340000;root_pose=(const float *)(shadow+0x690);
        original_sequence_movement=mock_root;original_interval_movement=mock_interval_root;
        assert(fabsf(interval_movement_at(module+0x280af1,shadow,.125f,&finished,position,angles)-1)<.00001f);
        assert(root_calls==1 && root_from==0 && root_to==.1f && !finished && movement_previous==.1f && movement_valid);
        assert(*(float *)(shadow+0x6f8)==.1f && !movement_context.actor && angles[1]==12.5f);
        *(float *)(shadow+0x6f8)=.2f;
        assert(fabsf(interval_movement_at(module+0x280af1,shadow,.125f,&finished,position,angles)-3)<.00001f);
        assert(root_calls==2 && root_from==.1f && root_to==.2f && !finished);
        *(float *)(shadow+0x6f8)=1;
        interval_movement_at(module+0x280af1,shadow,.125f,&finished,position,angles);
        assert(root_to==1 && finished && *(float *)(shadow+0x6f8)==1);
        *(float *)(shadow+0x6f8)=.1f;movement_previous=0;movement_valid=1;
        interval_movement_at(module+0x915f0,shadow,.125f,&finished,position,angles);
        assert(root_from==.1f && root_to==.2f && finished && movement_previous==0);
        movement_context=(MovementContext){shadow,11,katana_handle,812,0,0,.1f};
        sequence_movement_at(module+0x94f5b,root_header,812,.3f,.4f,root_pose,position,angles);
        assert(root_from==.3f && root_to==.4f && !movement_context.applied);
        *(int *)(weapon+0x88c)=shadow_handle+(1<<13);
        sequence_movement_at(module+0x94c83,root_header,812,.3f,.4f,root_pose,position,angles);
        assert(root_from==.3f && !movement_context.applied);*(int *)(weapon+0x88c)=shadow_handle;
        movement_context.strike=10;
        sequence_movement_at(module+0x94c83,root_header,812,.3f,.4f,root_pose,position,angles);
        assert(root_from==.3f && !movement_context.applied);movement_context.strike=11;
        *(int *)(shadow+0xfec)=0xf17;
        sequence_movement_at(module+0x94c83,root_header,812,.3f,.4f,root_pose,position,angles);
        assert(root_from==.3f && !movement_context.applied);*(int *)(shadow+0xfec)=attack_activity;
        active_profile=&profiles[13];*(const char **)(weapon+0x11c)=profiles[13].name;
        attack_activity=ATTACK_FRENZY;*(int *)(shadow+0xfec)=ATTACK_FRENZY;
        sequence_movement_at(module+0x94c83,root_header,812,.3f,.4f,root_pose,position,angles);
        assert(root_from==.3f && !movement_context.applied);active_profile=&profiles[9];
        *(const char **)(weapon+0x11c)=profiles[9].name;attack_activity=ATTACK_KATANA;*(int *)(shadow+0xfec)=attack_activity;
        root_pose=(const float *)(player+0x690);
        sequence_movement_at(module+0x94c83,root_header,812,.3f,.4f,root_pose,position,angles);
        assert(root_from==.3f && !movement_context.applied);root_pose=(const float *)(shadow+0x690);
        *(uint32_t *)(table+44)=10;
        sequence_movement_at(module+0x94c83,root_header,812,.3f,.4f,root_pose,position,angles);
        assert(root_from==.3f && !movement_context.applied);*(uint32_t *)(table+44)=9;
        movement_context.actor=NULL;
        assert(sequence_movement(root_header,812,.3f,.4f,root_pose,position,angles)==7 && root_from==.3f);
        root_header=NULL;root_pose=NULL;
        assert(sequence_movement(NULL,812,.3f,.4f,NULL,NULL,NULL)==7 && root_from==.3f && root_to==.4f);
        memset(&movement_context,0,sizeof(movement_context));movement_valid=0;
        *(int *)(shadow+0xfec)=saved_activity;
        puts("PASS elapsed-cycle movement: native once, unchanged actor cycle/sequence/outputs, non-loop completion; exact caller/pose/strike/owner/serial/Tiger refusal");
    }
    set_activity(shadow,NULL,ATTACK_FRENZY);
    assert(*(int *)(shadow+0xfec)==ATTACK_KATANA);
    set_activity(shadow,NULL,0xf17); assert(*(int *)(shadow+0xfec)==0xf17);
    set_activity(player,NULL,ATTACK_FRENZY); assert(*(int *)(player+0xfec)==ATTACK_FRENZY);
    assert(early_activity(shadow,NULL,ATTACK_FRENZY)==ATTACK_KATANA);
    assert(early_activity(shadow,NULL,0xf17)==0xf17);
    assert(early_activity(player,NULL,ATTACK_FRENZY)==ATTACK_FRENZY);
    assert(select_sequence(shadow,NULL,ATTACK_FRENZY,NULL)==ATTACK_KATANA);
    assert(select_heaviest(shadow,NULL,ATTACK_FRENZY,NULL)==ATTACK_KATANA);
    assert(select_sequence(shadow,NULL,0xf17,NULL)==0xf17);
    equip_shadow_weapon(shadow,NULL,npc,7);
    assert(equip_calls==1 && !inventory_add_calls && *(int *)(shadow+0x1628)==-1 && *(int *)(weapon+0x73c)==0);
    equip_shadow_weapon(player,NULL,npc,5);
    assert(equip_calls==2 && !inventory_add_calls && *(int *)(player+0x1624)==-1 && *(int *)(player+0x1628)==player_katana_handle && *(int *)(player_weapon+0x73c)==1);
    *(const char **)((uint8_t *)npc+0x11c)="item_w_fists";
    equip_shadow_weapon(player,NULL,npc,5);
    assert(equip_calls==3 && inventory_add_calls==1 && equip_self==player && equip_weapon==npc && equip_flags==5);
    assert(*(int *)(player+0x1624)==handle_of(npc) && *(int *)(player+0x1628)==player_katana_handle && *(int *)(player_weapon+0x73c)==1);
    *(void **)(player+0x80)=player_weapon;
    equip_shadow_weapon(pc,NULL,player_weapon,9);
    assert(equip_calls==4 && equip_self==pc && equip_weapon==player_weapon && equip_flags==9);
    inventory_delegate(pc,NULL,player_weapon);assert(inventory_add_calls==2);
    *(int *)(player_weapon+0x73c)=0xff;
    inventory_delegate(player,NULL,player_weapon);assert(inventory_add_calls==3);
    *(int *)(player_weapon+0x73c)=1;
    *(int *)(player+0x162c)=-1; /* remove mock fallback's expected insertion */
    puts("PASS fists native restoration, retained Katana no duplicate slot registration, unrelated equip passthrough");
    /* Native claws removed fists and compacted Katana into slot zero. */
    *(int *)(player+0x1624)=player_katana_handle;
    *(int *)(player_weapon+0x73c)=0;
    *(int *)(player+0x1628)=-1;
    *(int *)((uint8_t *)npc+0x73c)=0xff;
    equip_shadow_weapon(player,NULL,npc,0);
    assert(inventory_front_calls==1 && *(int *)(player+0x1624)==handle_of(npc));
    assert(*(int *)(player+0x1628)==player_katana_handle && *(int *)(player_weapon+0x73c)==1);
    assert(*(int *)((uint8_t *)npc+0x73c)==0 && equip_weapon==npc);
    restore_fists_order(player,npc);assert(inventory_front_calls==1); /* already first */
    *(int *)(player_weapon+0x73c)=7;
    *(int *)(player+0x1624)=player_katana_handle;
    *(int *)(player+0x1628)=handle_of(npc);
    *(int *)((uint8_t *)npc+0x73c)=1;
    restore_fists_order(player,npc);assert(inventory_front_calls==1); /* refuse mismatch */
    *(int *)(player_weapon+0x73c)=0;
    *(int *)(player+0x162c)=player_katana_handle;
    restore_fists_order(player,npc);assert(inventory_front_calls==1); /* refuse alias */
    *(int *)(player+0x162c)=-1;
    restore_fists_order(player,npc);assert(inventory_front_calls==2);
    *(void **)(player+0x80)=player_weapon;
    puts("PASS native fists-first wrapper, stable Katana order, repeated restore, corrupt/aliased inventory refusal");
    puts("PASS actual compiled activity/equip wrappers, katana attack only, unchanged RUN/unrelated paths");
    assert(feat_character(npc) == pc);
    assert(retained_weapon(shadow, npc) == weapon);
    assert(retained_weapon(shadow, NULL) == weapon);
    assert(retained_weapon(player, npc) == npc);
    assert(retained_weapon(pc, npc) == npc);
    assert(retained_weapon(shadow, weapon) == weapon);
    assert(feat_character(pc) == pc); assert(feat_character(NULL) == NULL);
    *(const char **)(weapon + 0x11c) = "item_w_fists";
    assert(feat_character(npc) == npc);
    *(const char **)(weapon + 0x11c) = "item_w_katana";
    /* A new player wrapper is read immediately; there is no stat snapshot. */
    *(void **)(player + 0x9c) = weapon;
    assert(feat_character(npc) == weapon);
    *(int *)(player + 0x146c) = 0;
    assert(feat_character(npc) == weapon); /* published controller before counter */
    pending_player = NULL; /* native CheckForPlayerFrenzy has returned */
    *(int *)(player + 0x1db0) = -1;
    assert(feat_character(npc) == npc); assert(shadow_handle == -1);
    player_handle = (7 << 13) | 1; shadow_handle = (8 << 13) | 2;
    katana_handle = (9 << 13) | 3;
    *(int *)(player + 0x146c) = 10; *(int *)(player + 0x1db0) = shadow_handle;
    *(uint32_t *)(table + 32) = 9;
    assert(feat_character(npc) == npc); assert(shadow_handle == -1);
    puts("PASS live feat scope, non-katana, unrelated, null, end and stale handles");
    player_handle = (7 << 13) | 1; shadow_handle = (9 << 13) | 2;
    katana_handle = (9 << 13) | 3;
    *(int *)(player + 0x1db0) = shadow_handle;
    *(uint32_t *)(table + 44) = 10;
    assert(retained_weapon(shadow, npc) == npc);
    assert(shadow_handle == -1 && katana_handle == -1);
    puts("PASS retained temporary katana, unrelated equip and stale katana fallback");
    {
        int ph=(7<<13)|1, sh=(9<<13)|2, kh=(10<<13)|4;
        uint8_t *claws=calloc(1,0x2000), *character=calloc(1,0x200);
        assert(claws && character);
        *(void **)(table+88)=claws;*(uint32_t *)(table+92)=13;
        *(const char **)(claws+0x11c)="item_w_claws";*(int *)(claws+0x73c)=2;
        *(int *)(player+0x162c)=(13<<13)|7;
        *(int *)(player_weapon+0x73c)=1;
        *(void **)(character+0xa8)=player;
        player[0x1481]=1;
        { void **vt=calloc(0x728/4,sizeof(void *));assert(vt);vt[0x724/4]=(void *)mock_exit_select;*(void ***)player=vt; }
        original_frenzy_end=mock_frenzy_end;
        for(i=0;i<6;++i) {
            for(j=0;j<3;++j) {
                policy_player=ph;policy_shadow=sh;policy_katana=j==2?kh:-1;policy_claws=j==1;
                *(int *)(player+0x1db0)=sh;*(int *)(player+0x1380)=i;
                expected_exit=j==2?player_weapon:j==1 && i>=2?claws:npc;
                frenzy_end(character,NULL);
                assert(policy_player==-1 && !exit_player && exit_katana==-1);
            }
        }
        assert(end_original_calls==18 && exit_select_calls==18);
        policy_player=ph;policy_shadow=sh;policy_claws=0;policy_katana=-1;
        *(int *)(player+0x1db0)=sh;player[0x200]=1;expected_exit=npc;
        frenzy_end(character,NULL);assert(exit_select_calls==18 && policy_player==-1);
        player[0x200]=0;
        policy_player=ph;policy_shadow=sh+0x2000;*(int *)(player+0x1db0)=sh;
        frenzy_end(character,NULL);assert(exit_select_calls==18 && policy_player==-1);
        policy_player=ph;policy_shadow=sh;policy_katana=-1;policy_claws=1;
        *(int *)(player+0x1db0)=sh;*(int *)(player+0x1538)=sh;*(int *)(player+0x153c)=0;
        *(int *)(player+0x1380)=2;expected_exit=claws;*(void **)(player+0x80)=player_weapon;
        frenzy_end(character,NULL);assert(deferred_player==ph && deferred_partner==sh && exit_select_calls==19);
        original_leave_grapple=mock_leave_grapple;
        leave_grapple(shadow,NULL);assert(deferred_player==ph && exit_select_calls==19);
        *(int *)(player+0x1380)=0;expected_exit=npc;
        leave_grapple(player,NULL);assert(deferred_player==-1 && exit_select_calls==20 && *(void **)(player+0x80)==npc);
        leave_grapple(player,NULL);assert(exit_select_calls==20);
        deferred_player=ph;deferred_partner=sh;*(int *)(player+0x1538)=-1;
        leave_grapple(player,NULL);assert(deferred_player==-1 && exit_select_calls==20);
        puts("PASS native grapple deferred selection, unrelated actor, one-shot cleanup, expired Protean re-evaluation, changed partner refusal");
        /* Missing retained Katana/expired Protean must use registered fists. */
        exit_player=player;exit_katana=kh;exit_claws=1;
        *(int *)(player+0x1628)=-1;*(int *)(player+0x1380)=0;
        assert(exit_weapon(player)==npc);
        exit_player=NULL;exit_katana=-1;exit_claws=0;
        *(int *)(player+0x1628)=kh;
        puts("PASS exit matrix fists/firearm/Katana/Protean 0-5, expiry, missing weapon, one native selection, transaction cleanup");
    }
    {
        void **pvt=*(void ***)player;
        void **svt=(void **)(module+SHADOW_VTABLE);
        pvt[0x5e0/4]=(void *)mock_activity;
        svt[0x5e0/4]=(void *)mock_activity;svt[0x5fc/4]=(void *)mock_creation_equip;
        jump(module+GIVE_WEAPON,(void *)mock_give);
        jump(module+CAN_EQUIP,(void *)mock_can_equip);
        jump(module+REMOVE_ENTITY,(void *)mock_remove);
        jump(module+WEAPON_TRANSLATE,(void *)mock_weapon_translate);
        original_heaviest=mock_available_sequence;
        original_collector=policy_collect;collector_count=6;
        jump(module+SEQUENCE_DESC,(void *)policy_desc);
        jump(module+0x8fe80,(void *)policy_name);
        jump(module+0x91080,(void *)policy_duration);
        creation_weapon=weapon;
        /* Sequence names do not index the mock IDs (read-only stub above). */
        for(i=0;i<sizeof(profiles)/sizeof(profiles[0]);++i) {
            collector_count=policy_count(profiles+i)+1;
            *(const char **)(player_weapon+0x11c)=profiles[i].name;
            *(const char **)(weapon+0x11c)=profiles[i].name;
            for(j=0;j<7;++j) {
                clear_active("fixture reset");
                pending_player=player;pending_katana=1;pending_profile=profiles+i;
                pending_weapon_handle=handle_of(player_weapon);
                creation_fail=j==1;creation_refuse=j==2;creation_unequipped=j==3;
                unavailable_actor=j==4?1:j==5?2:0;
                translated_weapon_activity=j==6?ATTACK_MELEE:2000+(int)i;
                *(void **)(shadow+0x80)=NULL;
                removed_count=0;
                if(j==0 || (j==6 && profiles[i].frenzy_animation)) {
                    assert(prepare_shadow(shadow)==weapon && !removed_count);
                    assert(active_profile==profiles+i && player_katana_handle==handle_of(player_weapon));
                    assert(katana_handle==handle_of(weapon) && attack_activity==(profiles[i].frenzy_animation?ATTACK_FRENZY:translated_weapon_activity));
                } else {
                    assert(!prepare_shadow(shadow) && shadow_handle==-1 && !active_profile);
                    assert(removed_count==(creation_fail?0:1));
                }
            }
        }
        pending_player=NULL;pending_katana=0;pending_profile=NULL;
        clear_active("fixture complete");
        assert(!movement_valid && !movement_context.actor && movement_previous==0);
        puts("PASS all 14 native preparation routes; separate model-local sequence IDs; failed create/eligibility/equip/player-model/Shadow-model/translation removes only temporary weapon and falls back before binding");
    }

    {
        int ids[32],weights[32],count,sex;
        original_collector=policy_collect;original_next_attack=policy_next;
        /* All 14 class mappings, both native resource variants, preserve pairs. */
        for(i=0;i<sizeof(profiles)/sizeof(profiles[0]);++i) for(sex=0;sex<2;++sex) {
            const ShortFamily *f=short_family(profiles+i);
            clear_active("policy fixture");pending_profile=NULL;pending_player=NULL;
            player_handle=handle_of(player);shadow_handle=handle_of(shadow);
            katana_handle=handle_of(weapon);player_katana_handle=handle_of(player_weapon);
            active_profile=profiles+i;attack_activity=2000+(int)i;
            *(int *)(player+0x1db0)=shadow_handle;
            *(const char **)(weapon+0x11c)=profiles[i].name;*(void **)(shadow+0x80)=weapon;
            *(int *)(shadow+0xfec)=attack_activity;
            policy_female=sex;policy_alt=policy_bad=unavailable_actor=0;
            collector_count=policy_count(profiles+i)+1;collector_calls=0;
            count=collect_short_attacks(shadow,NULL,attack_activity,ids,weights,(void *)-1);
            assert(collector_calls==1);
            if(!f) assert(count==6);
            else {
                int expected=0;
                while(f->labels[expected]) ++expected;
                assert(count==expected);
                for(j=0;j<(unsigned int)count;++j) assert(ids[j]==200+(int)j && weights[j]==(int)j+1);
                assert(collect_short_attacks(player,NULL,attack_activity,ids,weights,NULL)==expected+1);
                assert(collect_short_attacks(shadow,NULL,attack_activity+1,ids,weights,NULL)==expected+1);
                next_result=299;assert(next_short_attack(shadow,NULL)==-1);
                next_result=200;assert(next_short_attack(shadow,NULL)==200);
                *(int *)(shadow+0xfec)=1;next_result=299;assert(next_short_attack(shadow,NULL)==299);
                *(int *)(shadow+0xfec)=attack_activity;
                collector_count=3;
                assert(short_preflight(shadow,attack_activity,profiles+i));
                pfi_inventory_ready=0;assert(!short_preflight(shadow,attack_activity,profiles+i));pfi_inventory_ready=1;
                policy_alt=1;assert(!short_preflight(shadow,attack_activity,profiles+i));policy_alt=0;
                policy_bad=1;assert(!short_preflight(shadow,attack_activity,profiles+i));policy_bad=0;
                collector_count=0;assert(collect_short_attacks(shadow,NULL,attack_activity,ids,weights,NULL)==0);
                collector_count=-1;assert(collect_short_attacks(shadow,NULL,attack_activity,ids,weights,NULL)==-1);
                collector_count=expected+1;*(const char **)(weapon+0x11c)="item_w_unknown";
                assert(collect_short_attacks(shadow,NULL,attack_activity,ids,weights,NULL)==expected+1);
            }
        }
        clear_active("policy complete");pending_profile=NULL;
        puts("PASS native melee policy: all 14 profiles/both variants, no duration cutoff, paired stable weights, actor/activity/Tiger scope, empty/negative native results, continuation stops, zero weights, alternate links, replaced weapon");
    }
    {
        enum { N=sizeof(hooks)/sizeof(hooks[0]) };
        uint8_t saved[N][20];
        install_fixture();
        for(i=0;i<N;++i) memcpy(saved[i],module+hooks[i].rva,hooks[i].size);
        module[0x31e3c1]=0xcc;
        pfi_melee_server();assert(!installed && protection_calls==0);
        for(i=0;i<N;++i) assert(!memcmp(saved[i],module+hooks[i].rva,hooks[i].size));
        install_fixture();module[WEAPON_TRANSLATE]=0xcc;
        pfi_melee_server();assert(!installed && protection_calls==0);
        install_fixture();module[ABS_ORIGIN]=0xcc;
        pfi_melee_server();assert(!installed && protection_calls==0);
        install_fixture();module[SEQUENCE_DESC]=0xcc;
        pfi_melee_server();assert(!installed && protection_calls==0);
        install_fixture();
        for(i=0;i<N;++i) memcpy(saved[i],module+hooks[i].rva,hooks[i].size);
        module[0x33589d]=0xcc;
        pfi_melee_server();assert(!installed && protection_calls==0);
        for(i=0;i<N;++i) assert(!memcmp(saved[i],module+hooks[i].rva,hooks[i].size));
        install_fixture();
        for(i=0;i<N;++i) memcpy(saved[i],module+hooks[i].rva,hooks[i].size);
        /* An occupied late hook must prevent every earlier write. */
        module[hooks[N-1].rva]=0xcc;
        pfi_melee_server();assert(!installed && protection_calls==0);
        for(i=0;i<N-1;++i) assert(!memcmp(saved[i],module+hooks[i].rva,hooks[i].size));
        install_fixture();
        fail_protection_call=8; /* fail while acquiring a page in the atomic transaction */
        pfi_melee_server();assert(!installed);
        for(i=0;i<N;++i) assert(!memcmp(saved[i],module+hooks[i].rva,hooks[i].size));
        install_fixture();pfi_melee_server();assert(installed);
        for(i=0;i<N;++i) assert(module[hooks[i].rva]==0xe9);
        for(i=0;i<N;++i) if(hooks[i].expected[0]==0xe9) {
            int32_t original_relative,trampoline_relative;
            memcpy(&original_relative,hooks[i].saved+1,4);memcpy(&trampoline_relative,hooks[i].trampoline+1,4);
            assert((uintptr_t)hooks[i].trampoline+5+trampoline_relative==
                   (uintptr_t)module+hooks[i].rva+5+original_relative);
        }
        puts("PASS every installed relative-jump trampoline preserves the exact native destination");
        assert(!hook_trampoline(0x3daf)&&!hook_trampoline(0x1618e0));
        assert(hook_trampoline(0x12503));
        puts("PASS actual installer, late occupied-hook refusal, injected partial-install rollback, complete install");
    }
    return 0;
}
