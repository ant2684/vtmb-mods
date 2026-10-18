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
