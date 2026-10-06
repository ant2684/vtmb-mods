#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
static void *test_engine,*test_ui;static int vp_calls,fail_at,fail_again;
static HMODULE WINAPI test_module(LPCSTR name){return !strcmp(name,"engine.dll")?(HMODULE)test_engine:(HMODULE)test_ui;}
static BOOL WINAPI test_protect(LPVOID a,SIZE_T n,DWORD p,PDWORD old){vp_calls++;if(vp_calls==fail_at || vp_calls==fail_again)return FALSE;return VirtualProtect(a,n,p,old);}
#define GetModuleHandleA test_module
#define VirtualProtect test_protect
#include "../plugin/console_pause.c"
#undef GetModuleHandleA
#undef VirtualProtect
static void check(int ok,const char *label){if(!ok){printf("FAIL %s\n",label);ExitProcess(1);}}
static void put(void *a,uint32_t v){memcpy(a,&v,4);}
static void image(uint8_t *p,size_t size) {
    IMAGE_DOS_HEADER *d=(void *)p;IMAGE_NT_HEADERS32 *n=(void *)(p+0x80);IMAGE_SECTION_HEADER *s;
    memset(p,0,size);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x80;
    n->Signature=IMAGE_NT_SIGNATURE;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    n->FileHeader.SizeOfOptionalHeader=sizeof(n->OptionalHeader);n->FileHeader.NumberOfSections=1;
    n->OptionalHeader.SizeOfImage=(DWORD)size;s=IMAGE_FIRST_SECTION(n);
    s->VirtualAddress=0x1000;s->Misc.VirtualSize=(DWORD)size-0x1000;s->Characteristics=IMAGE_SCN_MEM_EXECUTE;
}
static void fixtures(void) {
    unsigned i;
    for(i=0;i<4;i++)if(hooks[i].trampoline)VirtualFree(hooks[i].trampoline,0,MEM_RELEASE);
    memset(hooks,0,sizeof(hooks));installed=0;vp_calls=0;
    image(test_engine,0x1400000);image(test_ui,0x80000);engine=test_engine;ui=test_ui;
    memcpy(engine+0x10dc10,"\x8b\x0d\0\0\0\0\x85\xc9\x0f\x84\x85\0\0\0\x8b\x01\xff\x50\x0c",19);
    put(engine+0x10dc12,(uint32_t)(uintptr_t)(engine+0x13064a4));
    memcpy(engine+0x10d650,"\x8b\x0d\0\0\0\0\x85\xc9\x0f\x84\x83\0\0\0\x8b\x54\x24\x04",18);
    put(engine+0x10d652,(uint32_t)(uintptr_t)(engine+0x13064a4));
    memcpy(engine+0x1a570,"\x8b\x44\x24\x04\x50\xe8\xe6\x1c\0\0\x83\xc4\x04\xc2\x04\0",16);
    memcpy(ui+0x22070,"\x8b\x44\x24\x04\x56\x50\x8b\xf1\xe8\x03\xac\xff\xff",13);
    memcpy(ui+0x59d0,"\x56\x8b\xf1\x8b\x0d\0\0\0\0\x8b\x01\xff\x90\xa8\x01\0\0",17);
    put(ui+0x59d5,(uint32_t)(uintptr_t)(ui+0x6c330));
    memcpy(ui+0x220e0,"\x8b\x89\xb4\0\0\0\x8b\x54\x24\x04\x89\x54\x24\x04\x8b\x01\xff\x60\x54",19);
    memcpy(ui+0x21e30,"\x53\x56\x8b\xf1\x57\x8b\x86\xcc\0\0\0\x85\xc0\x0f\x85\x37\x01\0\0",19);
    memcpy(ui+0x21ee7,"\x8b\x8e\xcc\0\0\0\x6a\0\x68\0\0\0\0\x8b\x11\xff\x92\x98\0\0\0\x8b\xf8\x85\xff\x74\x16\x8b\x8e\xb4\0\0\0\x8b\x1f\x8b\x01\xff\x50\x58\x50\x8b\xcf\xff\x93\xb8\0\0\0",49);
    put(ui+0x21ef0,(uint32_t)(uintptr_t)(ui+0x66b0c));
}
static uint8_t expected[4][16];static const uint32_t rvas[4]={0x10dc10,0x1a570,0x22070,0x59d0};
static uint8_t *site(unsigned i){return (i<2?engine:ui)+rvas[i];}
static void remember(void){unsigned i;for(i=0;i<4;i++)memcpy(expected[i],site(i),16);}
static void unchanged(void){unsigned i;for(i=0;i<4;i++)check(!memcmp(expected[i],site(i),16),"exact rollback");}
static void *vt[0x60],*client_vt[0x80];static uint8_t dlg[0x110],obj[12],menu[16];
static int dlg_visible,menu_visible,queued_set,queued_un;
static int mouse_enabled,helper_calls;
static uint8_t min_button[16],title_menu[16],min_item[16];
static void *button_vt[0x60],*title_vt[0x60],*item_vt[0x60];
static int min_visible,min_enabled,min_calls,find_calls,item_present=1,other_enabled=1;
static void __thiscall button_visible(void *self,int value){check(self==min_button && value==0,"minimize native ECX/argument");min_visible=value;min_calls++;}
static void *__thiscall find_item(void *self,const char *name,int recurse){check(self==title_menu && !strcmp(name,"Minimize") && !recurse,"cached menu lookup ABI/scope");find_calls++;return item_present?min_item:NULL;}
static void __thiscall item_enabled(void *self,int value){check(self==min_item && value==0,"only Minimize disabled");min_enabled=value;}
static void minimize_fixture(void){
 button_vt[0x54/4]=button_visible;title_vt[0x98/4]=find_item;item_vt[0xb8/4]=item_enabled;
 put(min_button,(uint32_t)(uintptr_t)button_vt);put(title_menu,(uint32_t)(uintptr_t)title_vt);put(min_item,(uint32_t)(uintptr_t)item_vt);
 put(dlg+0xb4,(uint32_t)(uintptr_t)min_button);put(dlg+0xcc,0);min_visible=min_enabled=other_enabled=item_present=1;min_calls=find_calls=0;
}
static const char *__thiscall mock_level(void *self){check(self==obj,"level ECX");return "qa_map";}
static unsigned char __thiscall mock_visible(void *self){return self==dlg?(unsigned char)dlg_visible:(unsigned char)menu_visible;}
static int __thiscall mock_command(void *self,const char *text){check(self==obj,"ECX command forwarding");if(!strcmp(text,"setpause"))queued_set++;if(!strcmp(text,"unpause"))queued_un++;return 0x12345678;}
static void __thiscall mock_set_visible(void *self,int value){check(self==dlg || self==menu,"ECX panel forwarding");if(self==dlg)dlg_visible=value;else menu_visible=value;}
static void __thiscall mock_hide(void *self,int resume){check(self==obj,"ECX hide forwarding");set_visible(dlg,NULL,0);if(resume)command(obj,NULL,"unpause");}
static void __cdecl mock_show(void){check(command(obj,NULL,"setpause")==0x12345678 || console_skipped || show_was_visible,"return forwarding");set_visible(menu,NULL,0);set_visible(dlg,NULL,1);mouse_enabled=0;min_visible=1;}
static int __thiscall mock_activate(void *self){check(self==obj,"activate ECX");check(command(obj,NULL,"setpause")==1,"menu restoration suppresses new request");menu_visible=1;return 1;}
static void __cdecl mock_engine_hide(int resume){check(resume==0,"engine helper argument");helper_calls++;hide_gameui(obj,NULL,resume);mouse_enabled=1;}
static void drain(void){while(queued_set-- >0){put(engine+0xb4378c,word(0xb4378c)+1);put(engine+0x12b0758,1);}queued_set=0;while(queued_un-- >0){uint32_t d=word(0xb4378c);if(d)put(engine+0xb4378c,--d);if(!d)put(engine+0x12b0758,0);}queued_un=0;}
static void reset_logic(unsigned depth,unsigned paused) {
    console_owned=console_skipped=show_scope=show_was_visible=hide_scope=0;
    input_owned=previous_menu=restore_menu_scope=0;context_dialog=NULL;mouse_enabled=1;helper_calls=0;
    dlg_visible=menu_visible=queued_set=queued_un=0;
    put(engine+0xb4378c,depth);put(engine+0xb43788,0);put(engine+0x12b0758,paused);
    original_show=mock_show;original_command=(CommandFn)mock_command;original_visible=(VisibleFn)mock_set_visible;original_hide=(HideFn)mock_hide;
    engine_hide=mock_engine_hide;minimize_visible=(VisibleFn)(ui+0x220e0);minimize_fixture();
}
static __declspec(noinline) void visible_abi(void *self,int value) {
    uint32_t before,after;
    register uint32_t bx __asm__("ebx")=0x11223344;
    register uint32_t si __asm__("esi")=0x55667788;
    register uint32_t di __asm__("edi")=0x99aabbcc;
    VisibleFn volatile fn=(VisibleFn)(void *)set_visible;
    __asm__ volatile("" : "+r"(bx),"+r"(si),"+r"(di));
    __asm__ volatile("movl %%esp,%0" : "=m"(before));
    fn(self,value);
    __asm__ volatile("movl %%esp,%0" : "=m"(after));
    __asm__ volatile("" : "+r"(bx),"+r"(si),"+r"(di));
    check(before==after,"native thiscall ESP restored");
    check(bx==0x11223344 && si==0x55667788 && di==0x99aabbcc,"native callee-saved registers");
}
static __declspec(noinline) void minimize_abi(void *self) {
    uint32_t before,after;
    register uint32_t bx __asm__("ebx")=0x11223344;
    register uint32_t si __asm__("esi")=0x55667788;
    register uint32_t di __asm__("edi")=0x99aabbcc;
    typedef void (__cdecl *MinFn)(void *);
    MinFn volatile fn=(MinFn)(void *)hide_minimize;
    __asm__ volatile("" : "+r"(bx),"+r"(si),"+r"(di));
    __asm__ volatile("movl %%esp,%0" : "=m"(before));
    fn(self);
    __asm__ volatile("movl %%esp,%0" : "=m"(after));
    __asm__ volatile("" : "+r"(bx),"+r"(si),"+r"(di));
    check(before==after,"native thiscall ESP restored");
    check(bx==0x11223344 && si==0x55667788 && di==0x99aabbcc,"native callee-saved registers");
}
int main(void) {
    unsigned i;test_engine=VirtualAlloc(NULL,0x1400000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    test_ui=VirtualAlloc(NULL,0x80000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);check(test_engine && test_ui,"fixture allocation");
    for(i=1;i<=12;i++){fixtures();remember();fail_at=(int)i;loaded_gameui();check(!installed,"failed install refused");unchanged();}
    fixtures();remember();fail_at=10;fail_again=11;loaded_gameui();check(!installed,"rollback failure refuses successful install");for(i=0;i<4;i++)check(hooks[i].trampoline!=NULL,"failed rollback retains callable trampolines");fail_again=0;
    fixtures();ui[0x59d0]=0xcc;remember();fail_at=0;loaded_gameui();check(!installed && vp_calls==0,"occupied late hook refusal before mutation");unchanged();
    fixtures();engine[0x10d650]=0xcc;remember();fail_at=0;loaded_gameui();check(!installed && vp_calls==0,"occupied input helper refused before mutation");unchanged();
    for(i=0;i<3;i++){
        static const uint32_t anchors[]={0x220e0,0x21e30,0x21ee7};static const unsigned sizes[]={19,19,49};
        fixtures();remember();ui[anchors[i]]=0xcc;fail_at=0;loaded_gameui();check(!installed && vp_calls==0,"new incompatible anchor refuses before writes");unchanged();
        fixtures();remember();memcpy(ui+0x30000,ui+anchors[i],sizes[i]);loaded_gameui();check(!installed && vp_calls==0,"new duplicate anchor refuses before writes");unchanged();
    }
    fixtures();remember();fail_at=0;loaded_gameui();check(installed,"complete atomic install");
    for(i=0;i<4;i++){check(site(i)[0]==0xe9,"installed detour");check(!memcmp(hooks[i].trampoline,expected[i],hooks[i].length),"displaced bytes");}
    vt[0x58/4]=(void *)mock_visible;put(dlg,(uint32_t)(uintptr_t)vt);put(menu,(uint32_t)(uintptr_t)vt);
    put(obj+4,1);put(obj+8,(uint32_t)(uintptr_t)dlg);put(engine+0x13064a8,(uint32_t)(uintptr_t)obj);put(ui+0x6c330,(uint32_t)(uintptr_t)obj);put(ui+0x6c338,(uint32_t)(uintptr_t)menu);
    client_vt[0x1a8/4]=(void *)mock_level;client_vt[0x0c/4]=(void *)mock_activate;put(obj,(uint32_t)(uintptr_t)client_vt);put(engine+0x13064a4,(uint32_t)(uintptr_t)obj);
    reset_logic(0,0);hide_minimize(NULL);minimize_abi(dlg);min_calls=0;check(!min_calls,"null console skipped");
    show_console();check(!min_visible && min_calls==1 && !find_calls,"button hidden without creating title menu");
    put(dlg+0xcc,(uint32_t)(uintptr_t)title_menu);minimize_abi(dlg);find_calls=0;min_enabled=1;show_console();check(!min_visible && !min_enabled && find_calls==1 && other_enabled,"cached Minimize disabled only");
    min_visible=min_enabled=1;show_console();check(!min_visible && !min_enabled && find_calls==2,"repeated opening suppresses both controls");
    item_present=0;show_console();check(find_calls==3 && other_enabled,"missing item is safe");
    set_visible(menu,NULL,1);check(other_enabled && find_calls==3,"unrelated panel leaves title menu alone");
    reset_logic(0,0);show_console();drain();check(word(0xb4378c)==1 && console_owned,"console request ownership");set_visible(dlg,NULL,0);drain();check(!word(0xb4378c) && !word(0x12b0758),"X/tilde close balances once");set_visible(dlg,NULL,0);check(!queued_un,"duplicate hide does not unpause");
    reset_logic(0,0);show_console();set_visible(dlg,NULL,0);drain();check(!word(0xb4378c) && !word(0x12b0758),"same-frame queued close order");
    reset_logic(0,1);show_console();check(console_skipped && !queued_set,"manual pause retained on open");set_visible(dlg,NULL,0);drain();check(word(0x12b0758)==1 && !queued_un,"manual pause retained on X");
    reset_logic(0,1);show_console();hide_gameui(obj,NULL,1);drain();check(word(0x12b0758)==1 && !word(0xb4378c),"manual pause retained on native hide");
    reset_logic(1,1);menu_visible=1;show_console();drain();set_visible(dlg,NULL,0);drain();check(word(0xb4378c)==1 && word(0x12b0758)==1,"existing menu reference retained");
    reset_logic(0,0);show_console();drain();hide_gameui(obj,NULL,1);drain();check(!word(0xb4378c) && !word(0x12b0758),"native hide balances exactly once");
    reset_logic(0,0);set_visible(menu,NULL,0);check(!queued_un,"unrelated panels untouched");
    reset_logic(0,0);show_console();drain();set_visible(dlg,NULL,0);drain();check(mouse_enabled && helper_calls==1,"native engine input restoration");set_visible(dlg,NULL,0);check(helper_calls==1,"duplicate hide skips helper");
    reset_logic(0,1);show_console();set_visible(dlg,NULL,0);check(mouse_enabled && helper_calls==1 && word(0x12b0758)==1,"input ownership independent of pause");
    reset_logic(0,0);show_console();drain();hide_gameui(obj,NULL,0);drain();check(helper_calls==0,"outer native hide(false) never re-enters engine helper");
    reset_logic(1,1);menu_visible=1;show_console();drain();check(!menu_visible,"realistic Show hides menu");set_visible(dlg,NULL,0);drain();check(menu_visible && !mouse_enabled && helper_calls==0 && word(0xb4378c)==1,"menu context restored without extra request");
    reset_logic(0,0);show_console();drain();put(engine+0xb43788,1);hide_gameui(obj,NULL,0);drain();check(word(0xb4378c)==0 && word(0xb43788)==1 && word(0x12b0758)==1,"new script pause survives console reference release");
    reset_logic(0,0);show_console();drain();show_console();drain();check(word(0xb4378c)==1,"duplicate Show preserves context and one reference");set_visible(dlg,NULL,0);drain();check(helper_calls==1,"duplicate Show still restores once");
    reset_logic(0,0);show_console();drain();visible_abi(dlg,0);drain();check(mouse_enabled && helper_calls==1,"native thiscall detour restores input");
    reset_logic(0,0);*(double *)(engine+0x314890)=10;show_console();drain();*(double *)(engine+0x314890)=0;set_visible(dlg,NULL,0);check(!helper_calls && !queued_un,"reload context invalidates native restoration");
    puts("PASS compiled x86 ownership/input helper ABI/ordinary pause/menu/recursion/script overlap/queued order/atomic install/rollback");return 0;
}
