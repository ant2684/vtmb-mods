#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned calls, fail_at, fail_from, occupy_at;
static BOOL WINAPI test_protect(LPVOID p,SIZE_T n,DWORD protection,PDWORD old) {
    (void)n; (void)protection; *old=PAGE_EXECUTE_READ;
    ++calls; if(calls==occupy_at)((unsigned char *)p)[0]=0xcc;
    return calls!=fail_at && (!fail_from || calls<fail_from);
}
static BOOL WINAPI test_flush(HANDLE process,LPCVOID p,SIZE_T n) {
    (void)process;(void)p;(void)n;++calls;
    return calls!=fail_at && (!fail_from || calls<fail_from);
}
#define VirtualProtect test_protect
#define FlushInstructionCache test_flush
#include "../plugin/subtitle_pause.c"
#undef VirtualProtect
#undef FlushInstructionCache
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint8_t *te,*ts;static uint8_t expected[4][5];
static void put(void *p,uint32_t x){memcpy(p,&x,4);}
static void image(uint8_t *p,size_t size) {
    IMAGE_DOS_HEADER *d=(void*)p;IMAGE_NT_HEADERS32 *n=(void*)(p+0x80);IMAGE_SECTION_HEADER *s;
    memset(p,0,size);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x80;n->Signature=IMAGE_NT_SIGNATURE;
    n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;n->FileHeader.NumberOfSections=1;n->FileHeader.SizeOfOptionalHeader=sizeof(n->OptionalHeader);
    n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;n->OptionalHeader.SizeOfImage=(DWORD)size;
    s=IMAGE_FIRST_SECTION(n);s->VirtualAddress=0x1000;s->Misc.VirtualSize=(DWORD)size-0x1000;s->Characteristics=IMAGE_SCN_MEM_EXECUTE;
}
static uint8_t *site(unsigned i){static const unsigned r[]={CLOCK_HOOK_RVA,PAUSE_HOOK_RVA,RADIO_ACTIVATE_CALL_RVA,RADIO_CALL_RVA};return (i<2?te:ts)+r[i];}
static void reset(void) {
    unsigned i;
    if(clock_code)VirtualFree(clock_code,0,MEM_RELEASE);if(clock_state)VirtualFree(clock_state,0,MEM_RELEASE);
    clock_code=clock_state=NULL;engine_installed=radio_installed=installation_failed=0;memset(hooks,0,sizeof(hooks));
    calls=fail_at=fail_from=occupy_at=0;
    image(te,0x1400000);image(ts,0xb00000);
    memcpy(te+CLOCK_HOOK_RVA,"\x8b\x11\xff\x52\x38\xd9\x5c\x24\x04\x8b\x74\x24\x10\x85\xf6",15);
    memcpy(te+PAUSE_HOOK_RVA,"\xe8\x5b\xf0\x00\x00\x85\xc0\xa3",8);
    memcpy(ts+RADIO_SIGNATURE_RVA,"\x6a\x01\x8b\xce\xe8\x68\x60\xdd\xff",9);
    memcpy(ts+RADIO_ACTIVATE_CALL_RVA-2,"\x8b\xce\xe8\x12\x4d\xdd\xff\x83\xbe\x4c\x07\x00\x00\xff",14);
    memcpy(ts+RADIO_FAKE_SILENCE_THUNK_RVA,"\xe9\x47\x67\x0a\x00",5);
    memcpy(ts+RADIO_BASE_ACTIVATE_THUNK_RVA,"\xe9\x95\xf9\x09\x00",5);
    for(i=0;i<4;i++)memcpy(expected[i],site(i),5);
}
static void unchanged(void){unsigned i;for(i=0;i<4;i++)CHECK(!memcmp(expected[i],site(i),5));}
static uint8_t table[8192*12],player[0x140],radio[0x140],sfx[0x108],source[0x80],mixer[0x80],globals[32];
static int decoded,decode_limit=-1,silence,activate_calls;
static void __thiscall silence_stub(void *self,int value){CHECK(self==radio);silence=value;radio[0x104]=(uint8_t)value;}
static void __thiscall activate_stub(void *self){CHECK(self==radio);activate_calls++;}
static int __thiscall decode_stub(void *self,void **pcm,int count,int unknown) {
    static int sample;CHECK(self==mixer && unknown==0);
    if(decode_limit>=0 && decoded>=decode_limit)return 0;
    *pcm=&sample;decoded+=count;return count;
}
static void jump(uint8_t *p,void *target){p[0]=0xe9;put(p+1,(uint32_t)(uintptr_t)target-(uint32_t)(uintptr_t)(p+5));}
static void logic(void) {
    uint8_t *ch;void **v,**sv;
    memset(radios,0,sizeof(radios));location_table=NULL;location_player=0xffffffff;location_generation=activation_generation=0;location_last_time=-1;
    memset(table,0,sizeof(table));memset(radio,0,sizeof(radio));memset(player,0,sizeof(player));memset(sfx,0,sizeof(sfx));memset(mixer,0,sizeof(mixer));memset(source,0,sizeof(source));
    put(ts+0x566458,(uint32_t)(uintptr_t)table);put(ts+0x70b228,(uint32_t)(uintptr_t)globals);
    put(table+12+4,(uint32_t)(uintptr_t)player);put(player+0x11c,(uint32_t)(uintptr_t)"player");
    put(table+222*12+4,(uint32_t)(uintptr_t)radio);put(table+222*12+8,3);put(radio+0x11c,(uint32_t)(uintptr_t)"prop_radio");
    *(float*)(globals+12)=0;decoded=0;decode_limit=-1;activate_calls=0;radio[0x104]=1;
    original_fake_silence=silence_stub;original_base_activate=activate_stub;engine_module=te;server_module=ts;
    ch=te+CHANNEL_ARRAY_RVA;memset(ch,0,CHANNEL_SIZE);put(te+CHANNEL_COUNT_RVA,1);put(ch,(uint32_t)(uintptr_t)sfx);put(ch+4,(uint32_t)(uintptr_t)mixer);put(ch+0x2c,222);*(float*)(ch+0x98)=100;
    strcpy((char*)sfx+1,"radio/radio_loop_1.mp3");put(sfx+0x104,(uint32_t)(uintptr_t)source);
    put(mixer,(uint32_t)(uintptr_t)(te+0x188600));put(source,(uint32_t)(uintptr_t)(te+0x188394));put(source+8,44100);
    v=(void**)(te+0x188600);sv=(void**)(te+0x188394);v[12]=te+0x139c80;sv[3]=te+0x137970;
    memcpy(te+0x137970,"\x8b\x41\x08\xc3",4);jump(te+0x139c80,decode_stub);
}
static void on_abi(int value) {
    uint32_t before,after;double x87=0;
    register uint32_t bx __asm__("ebx")=0x11223344,si __asm__("esi")=0x55667788,di __asm__("edi")=0x99aabbcc;
    FakeSilenceFn volatile fn=(FakeSilenceFn)(void*)radio_fake_silence;
    __asm__ volatile("fld1; movl %%esp,%0":"=m"(before):"r"(bx),"r"(si),"r"(di));
    fn(radio,value);
    __asm__ volatile("movl %%esp,%0; fstpl %1":"=m"(after),"=m"(x87):"r"(bx),"r"(si),"r"(di));
    CHECK(before==after && x87==1.0 && bx==0x11223344 && si==0x55667788 && di==0x99aabbcc);
}
static void cached_loop(void) {
    RadioState *s=radio_state(radio);RadioChannel c;CHECK(s&&find_radio_stream_channel(s,&c));
    s->phase_channel=c.channel;s->phase_mixer=c.mixer;s->phase_source=c.source;s->phase_sfx=c.sfx;
    s->loop_checked=1;s->loop_samples=18801792;
}
int main(void) {
    unsigned i;RadioState *s;uint32_t activation;
    te=VirtualAlloc(NULL,0x1400000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);ts=VirtualAlloc(NULL,0xb00000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);CHECK(te&&ts);
    reset();CHECK(install_all(te,ts));CHECK(calls==14);
    for(i=1;i<=14;i++){reset();fail_at=i;CHECK(!install_all(te,ts));unchanged();CHECK(!clock_code&&!clock_state);}
    reset();ts[RADIO_CALL_RVA]=0xcc;memcpy(expected[3],site(3),5);CHECK(!install_all(te,ts)&&calls==0);unchanged();
    reset();memcpy(ts+0x4000,ts+RADIO_SIGNATURE_RVA,9);CHECK(!install_all(te,ts)&&calls==0);unchanged();
    reset();occupy_at=12;CHECK(!install_all(te,ts));CHECK(site(3)[0]==0xcc);for(i=0;i<3;i++)CHECK(!memcmp(expected[i],site(i),5));
    reset();fail_from=13;CHECK(!install_all(te,ts));CHECK(clock_code&&clock_state&&!radio_installed&&!engine_installed);CHECK(hooks[3].changed);
    reset();logic();radio_base_activate(radio,NULL);CHECK(activate_calls==1);s=radio_state(radio);CHECK(s&&s->epoch==0&&s->epoch_valid);activation=s->activation;
    cached_loop();*(float*)(globals+12)=20;on_abi(0);CHECK(!silence&&decoded==20*44100&&*(double*)(mixer+8)==20*44100);CHECK(s->seen_on);
    on_abi(0);CHECK(decoded==20*44100&&!silence); /* duplicate */
    *(double*)(mixer+8)=22*44100;decoded=22*44100;*(float*)(globals+12)=22;on_abi(1);CHECK(silence&&s->armed);
    *(float*)(globals+12)=42;on_abi(0);CHECK(!silence&&decoded==42*44100&&*(double*)(mixer+8)==42*44100);
    on_abi(1);on_abi(0);CHECK(!silence&&decoded==42*44100); /* paused game clock */
    on_abi(1);put(table+222*12+8,4);on_abi(0);CHECK(silence); /* serial reuse */
    radio_base_activate(radio,NULL);s=radio_state(radio);CHECK(s->activation!=activation&&s->epoch==42&&!s->seen_on);
    cached_loop();*(double*)(mixer+8)=0;decoded=0;*(float*)(globals+12)=43;on_abi(0);CHECK(!silence&&decoded==44100);
    on_abi(1);*(float*)(globals+12)=63;decode_limit=decoded;on_abi(0);CHECK(silence); /* incomplete catch-up */
    logic();radio_base_activate(radio,NULL);*(float*)(globals+12)=5;put(te+CHANNEL_ARRAY_RVA+0x2c,999);on_abi(0);CHECK(silence); /* other entity */
    logic();radio_base_activate(radio,NULL);s=radio_state(radio);activation=s->activation;radio_base_activate(radio,NULL);s=radio_state(radio);CHECK(s->activation!=activation&&!s->seen_on&&s->epoch==0); /* identical reuse */
    logic();radio_base_activate(radio,NULL);cached_loop();*(float*)(globals+12)=430;on_abi(0);CHECK(!silence&&decoded==430*44100); /* sequential discard across a loop */
    CHECK(radio_sample_phase(te+CHANNEL_ARRAY_RVA,430*44100,44100)==430*44100-18801792);
    CHECK(radio_sample_phase(te+CHANNEL_ARRAY_RVA,18801792,44100)==0);
    CHECK(radio_sample_phase(te+CHANNEL_ARRAY_RVA,2*18801792+123,44100)==123);
    put(te+CHANNEL_ARRAY_RVA+0x2c,65);
    CHECK(radio_sample_phase(te+CHANNEL_ARRAY_RVA,2*18801792+123,44100)==2*18801792+123); /* unchanged TV/speech owner */
    put(te+CHANNEL_ARRAY_RVA+0x2c,222);on_abi(1);put(te+CHANNEL_ARRAY_RVA+4,0);on_abi(0);CHECK(silence); /* missing/replaced stream */
    logic();radio_base_activate(radio,NULL);cached_loop();*(float*)(globals+12)=1;on_abi(0);on_abi(1);
    put(table+12+8,99);on_abi(0);CHECK(silence&&!radio_state(radio)->epoch_valid); /* new player/location generation */
    logic();radio[0x104]=0;*(float*)(globals+12)=1000;radio_base_activate(radio,NULL);cached_loop();
    s=radio_state(radio);CHECK(s->seen_on&&s->epoch==1000);*(double*)(mixer+8)=7*44100;decoded=7*44100;
    *(float*)(globals+12)=1007;on_abi(1);CHECK(s->armed);*(float*)(globals+12)=1010;on_abi(1);CHECK(s->off_time==1007);
    *(float*)(globals+12)=1012;on_abi(0);CHECK(!silence&&decoded==12*44100);
    {uint8_t frames[3*156];unsigned j;memset(frames,0,sizeof(frames));
     for(j=0;j<3;j++){frames[j*156]=0xff;frames[j*156+1]=0xfb;frames[j*156+2]=0x30;frames[j*156+3]=0xc0;}
     CHECK(mpeg_loop_samples(frames,sizeof(frames),44100)==2*1152);
     CHECK(!mpeg_loop_samples(frames,sizeof(frames)-1,44100));CHECK(!mpeg_loop_samples(frames,sizeof(frames),48000));
     frames[156]=0;CHECK(!mpeg_loop_samples(frames,sizeof(frames),44100));}
    puts("PASS compiled x86 radio ABI/x87, first/repeat catch-up, paused time, identity/stream generation, decoder failure, unique/conflicting hooks and all protection/flush/rollback failures");return 0;
}
