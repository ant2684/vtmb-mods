/* Technical fixtures only. Never included by the gameplay plugin. */
static unsigned switch_calls, nested_switch;
static void __thiscall switch_stub(void *self,int active)
{
    CHECK(spawning_radio==self); ++switch_calls;
    if(nested_switch && self==radio) {
        /* An unrelated ordinary unmute must still fail closed. */
        radio_fake_silence(other_radio,NULL,0);CHECK(other_radio[0x104]==1);
        radio_spawn_switch(other_radio,NULL,active);
        CHECK(spawning_radio==radio && other_radio[0x104]==!active);
    }
    ((uint8_t*)self)[0x734]=(uint8_t)active;
    radio_fake_silence(self,NULL,!active);
}
static void test_startup_scope(void)
{
    unsigned i;void *sentinel=other_radio;
    original_radio_switch=switch_stub;switch_calls=nested_switch=0;
    /* Even the entity table/clock may be unavailable at the startup call. */
    server_module=(uint8_t*)1;
    call_abi((FakeSilenceFn)(void*)radio_spawn_switch,radio,1);
    CHECK(!spawning_radio && !radio[0x104] && radio[0x734]==1 && switch_calls==1);
    for(i=0;i<MAX_RADIOS;i++)CHECK(!radios[i].entity);
    server_module=ts;
    spawning_radio=sentinel;nested_switch=1;
    call_abi((FakeSilenceFn)(void*)radio_spawn_switch,radio,0);
    CHECK(spawning_radio==sentinel && radio[0x104]==1 && !radio[0x734] && switch_calls==3);
    spawning_radio=NULL;nested_switch=0;
    on_abi(0);CHECK(silence && !radio_state(radio)->epoch_valid);
}

static const uint8_t *native_file;
static IMAGE_NT_HEADERS32 *native_nt;
static const uint8_t *native_rva(uint32_t rva)
{
    IMAGE_SECTION_HEADER *sec=IMAGE_FIRST_SECTION(native_nt);unsigned i;
    for(i=0;i<native_nt->FileHeader.NumberOfSections;i++)
        if(rva>=sec[i].VirtualAddress && rva<sec[i].VirtualAddress+sec[i].SizeOfRawData)
            return native_file+sec[i].PointerToRawData+rva-sec[i].VirtualAddress;
    CHECK(0);return NULL;
}
static void native_span(uint32_t rva,unsigned length)
{
    IMAGE_DATA_DIRECTORY dir=native_nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC];
    uint32_t at=0,delta=(uint32_t)(uintptr_t)ts-native_nt->OptionalHeader.ImageBase;
    memcpy(ts+rva,native_rva(rva),length);
    while(at<dir.Size) {
        const IMAGE_BASE_RELOCATION *block=(const void*)native_rva(dir.VirtualAddress+at);
        const WORD *entries=(const void*)(block+1);unsigned i,count;
        CHECK(block->SizeOfBlock>=8);count=(block->SizeOfBlock-8)/2;
        for(i=0;i<count;i++) {
            uint32_t operand=block->VirtualAddress+(entries[i]&0xfff);
            if(operand>=rva && operand<rva+length) {
                CHECK((entries[i]>>12)==IMAGE_REL_BASED_HIGHLOW && operand+4<=rva+length);
                put(ts+operand,*(uint32_t*)(ts+operand)+delta);
            }
        }
        at+=block->SizeOfBlock;
    }
}
static unsigned sound_calls;static uint32_t trace_depth,trace_rows[9];
static void __thiscall sound_stub(void *controller,void *self,int sound,int flags,int volume,int pitch)
{
    CHECK(controller==ts+0x73dc00 && self==radio);
    CHECK(sound==17 || sound==23);CHECK(flags==2 && volume==0x3f800000 && pitch==0x3fa00000);
    ++sound_calls;
}
static void test_native_startup(void)
{
    char game[MAX_PATH],path[MAX_PATH+40];FILE *file;long size;unsigned flag;
    if(!GetEnvironmentVariableA("VTMB_VERIFY_GAME",game,sizeof(game))) {
        puts("SKIP native Spawn/switch fixture: exact-image suite supplies VTMB_VERIFY_GAME");return;
    }
    CHECK(snprintf(path,sizeof(path),"%s/Vampire/dlls/vampire.dll",game)>0);
    file=fopen(path,"rb");CHECK(file);CHECK(!fseek(file,0,SEEK_END));size=ftell(file);CHECK(size>0);rewind(file);
    native_file=malloc((size_t)size);CHECK(native_file);CHECK(fread((void*)native_file,1,(size_t)size,file)==(size_t)size);fclose(file);
    native_nt=(void*)(native_file+((const IMAGE_DOS_HEADER*)native_file)->e_lfanew);
    CHECK(native_nt->Signature==IMAGE_NT_SIGNATURE && native_nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386);
    for(flag=0;flag<=1;flag++) {
        BaseActivateFn spawn_entry,activate_entry;RadioState *s;uint32_t before,after;double x87;
        reset();logic();sound_calls=trace_depth=0;memset(trace_rows,0,sizeof(trace_rows));
        native_span(0x22c34e,23);native_span(0x331e,5);native_span(0x22c750,0xc7);
        native_span(0x22c50d,7);
        /* Only the native tracing and sound service endpoints are stubbed. */
        put(ts+0x9f3680,(uint32_t)(uintptr_t)&trace_depth);put(ts+0x9f3620,(uint32_t)(uintptr_t)trace_rows);
        put(ts+0x750fec,17);put(ts+0x750ff0,23);jump(ts+0x119fa,sound_stub);
        original_radio_switch=(FakeSilenceFn)(ts+0x331e);
        prepare_hook(&hooks[3],site(3),(uint8_t*)radio_fake_silence);CHECK(install_hook(&hooks[3]));
        /* Small ABI entry/exit fixtures surround the unchanged Spawn slice. */
        memcpy(ts+0x22c34b,"\x56\x8b\xf1",3);memcpy(ts+0x22c365,"\x5e\xc3",2);
        spawn_entry=(BaseActivateFn)(ts+0x22c34b);radio[0x204]=(uint8_t)flag;
        /* The preceding release must reproduce the regression on start-on. */
        if(flag) {spawn_entry(radio);CHECK(radio[0x104]==1 && radio[0x734]==1);sound_calls=0;}
        memset(radios,0,sizeof(radios));radio[0x104]=(uint8_t)flag;
        prepare_hook(&hooks[4],site(4),(uint8_t*)radio_spawn_switch);CHECK(install_hook(&hooks[4]));
        __asm__ volatile("fld1; movl %%esp,%0":"=m"(before));spawn_entry(radio);
        __asm__ volatile("movl %%esp,%0; fstpl %1":"=m"(after),"=m"(x87));
        CHECK(before==after && x87==1.0 && !spawning_radio && sound_calls==1 && trace_depth==0);
        CHECK(radio[0x104]==!flag && radio[0x734]==flag);
        CHECK(!radios[0].entity); /* Bypass precedes any state/clock lookup. */
        /* Execute the native Activate callsite after its initial-state call. */
        memcpy(ts+0x22c50a,"\x56\x8b\xf1",3);memcpy(ts+0x22c514,"\x5e\xc3",2);
        prepare_hook(&hooks[2],site(2),(uint8_t*)radio_base_activate);CHECK(install_hook(&hooks[2]));
        activate_entry=(BaseActivateFn)(ts+0x22c50a);activate_entry(radio);
        s=radio_state(radio);CHECK(activate_calls==1 && s->epoch_valid && s->seen_on==(int)flag);
        on_abi(1);on_abi(0);CHECK(silence); /* No supported loop: strict guard remains. */
    }
    free((void*)native_file);native_file=NULL;
    puts("PASS actual relocated native Spawn flag branches, full switch sound/skin/silence, old-path failure, scoped fix, Activate and post-scope refusal");
}

static unsigned static_calls;
static uint32_t __cdecl static_stub(uint32_t a,uint32_t b,uint32_t c,uint32_t d,
    uint32_t e,uint32_t f,uint32_t g,uint32_t h,uint32_t i,uint32_t j,uint32_t l,uint32_t m)
{
    CHECK(a==222 && b==6 && c==(uint32_t)(uintptr_t)sfx && d==4 && e==5 && f==6 &&
          g==0x3f800000 && h==8 && i==9 && j==100 && l==11 && m==0x3f000000);
    ++static_calls;return 0x12345678;
}
static void witness(void)
{
    StaticSoundFn volatile fn=radio_static_sound;uint32_t before,after,result;double x87;
    original_static_sound=static_stub;
    __asm__ volatile("fld1; movl %%esp,%0":"=m"(before));
    result=fn(222,6,(uint32_t)(uintptr_t)sfx,4,5,6,0x3f800000,8,9,100,11,0x3f000000);
    __asm__ volatile("movl %%esp,%0; fstpl %1":"=m"(after),"=m"(x87));
    CHECK(result==0x12345678 && before==after && x87==1.0);
}

/* Native Use toggles +734 before SetFakeSilence. Calling Activate alone
   would miss the user-visible three-press regression. */
static void ordinary_switch(int active)
{
    radio[0x734]=(uint8_t)active;
    on_abi(!active);
}
static void ordinary_use(void) { ordinary_switch(!radio[0x734]); }
static void test_early_landmark_off(void)
{
    RadioState *s; unsigned n;
    for(n=0;n<2;n++) {
        reset();logic();radio[0x104]=0;radio[0x734]=1;
        *(float*)(globals+12)=1;radio_base_activate(radio,NULL);s=radio_state(radio);
        put(te+CHANNEL_COUNT_RVA,0);ordinary_switch(0);
        CHECK(radio[0x104]==1 && !radio[0x734] && !s->armed && !s->seen_on && s->initial_pending);
        ordinary_switch(0);CHECK(!s->seen_on && s->initial_pending);
        if(n) {ordinary_use();CHECK(silence && radio[0x734]);ordinary_switch(0);}
        put(te+CHANNEL_COUNT_RVA,1);witness();cached_loop();*(float*)(globals+12)=21;
        ordinary_use();CHECK(!silence && radio[0x734] && decoded==20*44100 && !s->initial_pending);
        *(double*)(mixer+8)=22*44100;decoded=22*44100;*(float*)(globals+12)=23;
        ordinary_use();CHECK(silence && !radio[0x734] && s->armed);
        *(float*)(globals+12)=30;ordinary_use();CHECK(!silence && radio[0x734] && decoded==29*44100);
    }
    /* Observed native startup playback ends readiness before any manual
       switch. Later stream loss must remain a checkpoint failure. */
    reset();logic();radio[0x104]=0;radio[0x734]=1;radio_base_activate(radio,NULL);cached_loop();
    *(double*)(mixer+8)=44100;
    CHECK(radio_sample_phase(te+CHANNEL_ARRAY_RVA,44100,44100)==44100);
    s=radio_state(radio);CHECK(!s->initial_pending);put(te+CHANNEL_COUNT_RVA,0);ordinary_use();
    CHECK(silence && s->seen_on && !s->armed);put(te+CHANNEL_COUNT_RVA,1);*(float*)(globals+12)=5;
    ordinary_use();CHECK(silence && radio[0x734]);
    puts("PASS early landmark off before readiness, first ordinary Use, delayed readiness, repeated Use and established-stream loss refusal");
}

static void test_initial_stream_guards(void)
{
    RadioState *s; unsigned variant; uint8_t *ch=te+CHANNEL_ARRAY_RVA;
    /* A created, zero-position stream is not a playback checkpoint. */
    reset();logic();radio[0x104]=0;radio[0x734]=1;
    *(float*)(globals+12)=100;radio_base_activate(radio,NULL);s=radio_state(radio);
    witness();*(float*)(globals+12)=105;ordinary_use();CHECK(silence && !s->seen_on && !s->armed && s->initial_pending==2);
    cached_loop();*(float*)(globals+12)=110;ordinary_use();CHECK(!silence && decoded==10*44100);
    /* Initial identity must survive zero-position readiness and reject a
       replacement, even when its decoder would otherwise be supported. */
    reset();logic();radio[0x104]=0;radio[0x734]=1;radio_base_activate(radio,NULL);ordinary_use();
    cached_loop();put(ch+4,(uint32_t)(uintptr_t)(mixer+4));ordinary_use();CHECK(silence);
    put(ch+4,(uint32_t)(uintptr_t)mixer);
    /* Malformed/ambiguous/time-invalid states cannot become readiness if a
       different valid stream appears later. Also guard missing-after-start
       without relying on a caption callback being enabled. */
    for(variant=0;variant<7;variant++) {
        reset();logic();radio[0x104]=0;radio[0x734]=1;radio_base_activate(radio,NULL);
        if(variant==0) put(mixer,(uint32_t)(uintptr_t)te);
        if(variant==1) put(source+8,0);
        if(variant==2) *(double*)(mixer+8)=-1;
        if(variant==3) {memcpy(ch+CHANNEL_SIZE,ch,CHANNEL_SIZE);put(te+CHANNEL_COUNT_RVA,2);}
        if(variant==4) *(float*)(globals+12)=-1;
        if(variant==5) {witness();*(float*)(globals+12)=2;put(te+CHANNEL_COUNT_RVA,0);}
        if(variant==6) {ordinary_use();witness();put(ch+4,0);}
        if(variant!=6) ordinary_use(); else ordinary_switch(0);
        s=radio_state(radio);CHECK(s->initial_pending==-1 && silence);
        put(mixer,(uint32_t)(uintptr_t)(te+0x188600));put(source+8,44100);*(double*)(mixer+8)=0;
        put(te+CHANNEL_COUNT_RVA,1);put(ch+4,(uint32_t)(uintptr_t)mixer);*(float*)(globals+12)=3;cached_loop();
        ordinary_switch(1);CHECK(silence);
    }
    /* A stream that already advanced uses its actual off checkpoint, without
       any caption callback. This preserves saved-on playback coordinates. */
    reset();logic();radio[0x104]=0;radio[0x734]=1;*(float*)(globals+12)=1000;
    radio_base_activate(radio,NULL);cached_loop();*(double*)(mixer+8)=7*44100;decoded=7*44100;
    *(float*)(globals+12)=1007;ordinary_use();s=radio_state(radio);CHECK(s->armed && !s->initial_pending);
    *(float*)(globals+12)=1012;ordinary_use();CHECK(!silence && decoded==12*44100);
    puts("PASS zero-position epoch, initial stream binding, malformed/ambiguous/time/loss guards and saved-on without caption callback");
}

static void test_static_creation(void)
{
    RadioState *s;StaticSoundFn entry;unsigned before;
    reset();logic();radio_base_activate(radio,NULL);s=radio_state(radio);static_calls=0;
    witness();CHECK(static_calls==1 && s->initial_pending==2 && s->mixer==mixer);
    witness();CHECK(static_calls==2 && s->initial_pending==-1); /* duplicate cannot reopen */
    reset();logic();radio_base_activate(radio,NULL);put(te+CHANNEL_COUNT_RVA,0);witness();
    CHECK(radio_state(radio)->initial_pending==-1); /* native creation failed */
    reset();logic();radio_base_activate(radio,NULL);s=radio_state(radio);
    /* Execute the actual guarded CALL and its native 48-byte caller cleanup. */
    prepare_hook(&hooks[5],site(5),(uint8_t*)radio_static_sound);CHECK(install_hook(&hooks[5]));
    /* cdecl fixture copies the caller's twelve words with the same offsets
       used by native argument pushes, then executes the real patched site. */
    {unsigned n;uint32_t esp_before,esp_after,result;double x87;
     for(n=0;n<12;n++)memcpy(te+STATIC_SOUND_CALL_RVA-48+n*4,"\xff\x74\x24\x30",4);
     memcpy(te+STATIC_SOUND_CALL_RVA+5,"\x83\xc4\x30\xc3",4);
     entry=(StaticSoundFn)(te+STATIC_SOUND_CALL_RVA-48);original_static_sound=static_stub;before=static_calls;
     __asm__ volatile("fld1; movl %%esp,%0":"=m"(esp_before));
     result=entry(222,6,(uint32_t)(uintptr_t)sfx,4,5,6,0x3f800000,8,9,100,11,0x3f000000);
     __asm__ volatile("movl %%esp,%0; fstpl %1":"=m"(esp_after),"=m"(x87));
     CHECK(result==0x12345678 && esp_before==esp_after && x87==1.0 && static_calls==before+1 && s->initial_pending==2);}
    puts("PASS static create cdecl twelve-word forwarding/return/x87, identity binding, failed and repeated creation refusal");
}
