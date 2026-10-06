#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* Exact, relocated in-memory anchors for the recorded engine/GameUI build.
   Console activation uses GameUI::ActivateGameUI (queued setpause), then hides
   the base menu. Both HideConsole and Frame::OnClose hide the console without
   releasing that request. Balance only the request issued by that activation. */
typedef void (__cdecl *ShowFn)(void);
typedef int (__thiscall *CommandFn)(void *,const char *);
typedef void (__thiscall *VisibleFn)(void *,int);
typedef unsigned char (__thiscall *IsVisibleFn)(void *);
typedef void (__thiscall *HideFn)(void *,int);
typedef void (__cdecl *EngineHideFn)(int);
typedef const char *(__thiscall *LevelFn)(void *);
typedef int (__thiscall *ActivateFn)(void *);
typedef void *(__thiscall *FindFn)(void *,const char *,int);
typedef struct { uint8_t *site,*trampoline; size_t length; uint8_t old[16]; } Hook;
static Hook hooks[4];
static uint8_t *engine,*ui;
static ShowFn original_show;
static CommandFn original_command;
static VisibleFn original_visible;
static HideFn original_hide;
static int installed,show_scope,show_was_visible,console_owned,console_skipped;
static int hide_scope,hide_resume,hide_console,hide_menu,hide_skipped;
static int input_owned,previous_menu;
static int restore_menu_scope;
static void *context_dialog;
static double context_time;
static char context_level[128];
static EngineHideFn engine_hide;
static VisibleFn minimize_visible;
static void *console_dialog(void);
static void *menu_panel(void) { return *(void **)(ui+0x6c338); }
static const char *level_name(void) {
    void *client=*(void **)(ui+0x6c330);void **v;
    if(!client)return "";v=*(void ***)client;
    return ((LevelFn)v[0x1a8/4])(client);
}
static int same_context(void) {
    const char *level=level_name();
    return context_dialog==console_dialog() && level && !strcmp(level,context_level) &&
           *(double *)(engine+0x314890)>=context_time;
}

static uint32_t word(uint32_t rva) { return *(uint32_t *)(engine+rva); }
static void *console_dialog(void) {
    uint8_t *object=*(uint8_t **)(engine+0x13064a8);
    return object && *(int *)(object+4) ? *(void **)(object+8) : NULL;
}
static int visible(void *panel) {
    void **v;
    if(!panel)return 0;
    v=*(void ***)panel;
    return ((IsVisibleFn)v[0x58/4])(panel)!=0;
}

static void hide_minimize(void *dialog) {
    void *menu,*item;void **v;
    if(!dialog)return;
    minimize_visible(dialog,0);
    /* New native title menus derive Minimize availability from this button.
       An existing menu is cached, so update its one item explicitly. */
    menu=*(void **)((uint8_t *)dialog+0xcc);
    if(!menu)return;
    v=*(void ***)menu;
    item=((FindFn)v[0x98/4])(menu,"Minimize",0);
    if(item) {
        v=*(void ***)item;
        ((VisibleFn)v[0xb8/4])(item,0);
    }
}

static int __fastcall command(void *self,void *unused,const char *text) {
    (void)unused;
    if(restore_menu_scope && text && !strcmp(text,"setpause"))return 1;
    if(show_scope && text && strcmp(text,"setpause")==0) {
        if(show_was_visible)return 1;
        /* An ordinary pause or v_setpause already owns the paused state. Do not
           create a new menu request that would later clear that independent pause. */
        if(word(0xb4378c)==0 && (word(0x12b0758)!=0 || word(0xb43788)!=0)) {
            console_skipped=1;console_owned=0;return 1;
        }
        console_owned=1;console_skipped=0;
    }
    /* HideGameUI(true) already balances the console in the stock route. For a
       console over an independent pause, we deliberately issued no setpause. */
    if(hide_scope && hide_resume && hide_console && !hide_menu && hide_skipped &&
       text && strcmp(text,"unpause")==0) {return 1;}
    return original_command(self,text);
}
static void __cdecl show_console(void) {
    int previous_scope=show_scope,previous_visible=show_was_visible;

    show_was_visible=visible(console_dialog());
    if(!show_was_visible) {
        const char *level=level_name();
        input_owned=1;previous_menu=visible(menu_panel());context_dialog=console_dialog();
        context_time=*(double *)(engine+0x314890);
        snprintf(context_level,sizeof(context_level),"%s",level?level:"");
    }
    show_scope=1;
    original_show();
    hide_minimize(console_dialog());
    show_scope=previous_scope;show_was_visible=previous_visible;
}
static void __fastcall set_visible(void *self,void *unused,int value) {
    int is_console=self==console_dialog(),restore_input,restore_menu,owned,valid;
    (void)unused;
    original_visible(self,value);
    if(!is_console || value)return;
    
    if(!input_owned)return;
    valid=same_context();restore_input=valid && !hide_scope;restore_menu=previous_menu;
    owned=console_owned;
    /* Disarm both lifetimes before native hiding recursively reaches this hook. */
    input_owned=console_owned=0;console_skipped=0;context_dialog=NULL;
    if(owned && valid) {
        void *client=*(void **)(ui+0x6c330);
        if(!(hide_scope && hide_resume) && client) {
            /* Use the normal command queue: even a same-frame open/close keeps
               setpause before unpause and releases exactly one reference. */
            if(word(0xb43788)>0 && word(0xb4378c)>0) {
                /* Native unpause clears the server flag even during v_setpause.
                   Release only our applied menu reference; the script owns the
                   paused flag and its own native v_unpause will resume later. */
                *(uint32_t *)(engine+0xb4378c)=word(0xb4378c)-1;
            } else original_command(client,"unpause");
            
        }
    }
    if(restore_input) {
        if(restore_menu) {
            void *gameui=*(void **)(engine+0x13064a4);void **v;
            if(gameui) {
                v=*(void ***)gameui;restore_menu_scope=1;
                ((ActivateFn)v[0x0c/4])(gameui);
                restore_menu_scope=0;
            }
        } else engine_hide(0);
    }
}
static void __fastcall hide_gameui(void *self,void *unused,int resume) {
    int old_scope=hide_scope,old_resume=hide_resume,old_console=hide_console;
    int old_menu=hide_menu,old_skipped=hide_skipped;
    (void)unused;
    hide_scope=1;hide_resume=resume;hide_console=visible(console_dialog());
    hide_menu=visible(*(void **)(ui+0x6c338));hide_skipped=console_skipped;
    original_hide(self,resume);
    hide_scope=old_scope;hide_resume=old_resume;hide_console=old_console;
    hide_menu=old_menu;hide_skipped=old_skipped;
}

static int unique(uint8_t *module,const uint8_t *sig,size_t length,uint32_t rva) {
    IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER *)module;IMAGE_NT_HEADERS32 *nt;
    IMAGE_SECTION_HEADER *s;unsigned count=0,i;uint32_t at;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 || dos->e_lfanew>0x1000)return 0;
    nt=(IMAGE_NT_HEADERS32 *)(module+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC)return 0;
    if((uint64_t)rva+length>nt->OptionalHeader.SizeOfImage)return 0;
    s=IMAGE_FIRST_SECTION(nt);
    for(i=0;i<nt->FileHeader.NumberOfSections;i++) {
        uint32_t start=s[i].VirtualAddress,size=s[i].Misc.VirtualSize;
        if(!(s[i].Characteristics&IMAGE_SCN_MEM_EXECUTE) || (uint64_t)start+size>nt->OptionalHeader.SizeOfImage || size<length)continue;
        for(at=start;(uint64_t)at+length<=(uint64_t)start+size;at++)if(!memcmp(module+at,sig,length)) {
            if(at!=rva)return 0;count++;
        }
    }
    return count==1;
}
static int write_bytes(uint8_t *site,const uint8_t *bytes,size_t size) {
    DWORD old,ignored;
    if(!VirtualProtect(site,size,PAGE_EXECUTE_READWRITE,&old))return 0;
    memcpy(site,bytes,size);FlushInstructionCache(GetCurrentProcess(),site,size);
    return VirtualProtect(site,size,old,&ignored)!=0;
}
static void jump(uint8_t *bytes,uint8_t *site,void *destination) {
    int32_t rel=(int32_t)((uintptr_t)destination-(uintptr_t)(site+5));
    bytes[0]=0xe9;memcpy(bytes+1,&rel,4);
}
static int prepare(Hook *h,uint8_t *site,size_t length) {
    DWORD old;
    h->site=site;h->length=length;memcpy(h->old,site,length);
    h->trampoline=VirtualAlloc(NULL,32,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if(!h->trampoline)return 0;
    /* Displaced instructions contain no PC-relative operands. Absolute module
       operands are copied from the relocated live module, never preferred VAs. */
    memcpy(h->trampoline,site,length);jump(h->trampoline+length,h->trampoline+length,site+length);
    return VirtualProtect(h->trampoline,32,PAGE_EXECUTE_READ,&old)!=0;
}
__declspec(dllexport) void loaded_gameui(void) {
    uint8_t show_sig[]={0x8b,0x0d,0,0,0,0,0x85,0xc9,0x0f,0x84,0x85,0,0,0,0x8b,0x01,0xff,0x50,0x0c};
    uint8_t hide_sig[]={0x56,0x8b,0xf1,0x8b,0x0d,0,0,0,0,0x8b,0x01,0xff,0x90,0xa8,0x01,0,0};
    uint8_t resume_sig[]={0x8b,0x0d,0,0,0,0,0x85,0xc9,0x0f,0x84,0x83,0,0,0,0x8b,0x54,0x24,0x04};
    static const uint8_t cmd_sig[]={0x8b,0x44,0x24,0x04,0x50,0xe8,0xe6,0x1c,0,0,0x83,0xc4,0x04,0xc2,0x04,0};
    static const uint8_t vis_sig[]={0x8b,0x44,0x24,0x04,0x56,0x50,0x8b,0xf1,0xe8,0x03,0xac,0xff,0xff};
    static const uint8_t min_sig[]={0x8b,0x89,0xb4,0,0,0,0x8b,0x54,0x24,0x04,0x89,0x54,0x24,0x04,0x8b,0x01,0xff,0x60,0x54};
    static const uint8_t menu_sig[]={0x53,0x56,0x8b,0xf1,0x57,0x8b,0x86,0xcc,0,0,0,0x85,0xc0,0x0f,0x85,0x37,0x01,0,0};
    uint8_t item_sig[]={0x8b,0x8e,0xcc,0,0,0,0x6a,0,0x68,0,0,0,0,0x8b,0x11,0xff,0x92,0x98,0,0,0,0x8b,0xf8,0x85,0xff,0x74,0x16,0x8b,0x8e,0xb4,0,0,0,0x8b,0x1f,0x8b,0x01,0xff,0x50,0x58,0x50,0x8b,0xcf,0xff,0x93,0xb8,0,0,0};
    uint32_t ptr;uint8_t patch[16];unsigned i,applied=0;int rollback=1;
    void *destinations[4]={(void *)show_console,(void *)command,(void *)set_visible,(void *)hide_gameui};
    if(installed)return;
    engine=(uint8_t *)GetModuleHandleA("engine.dll");ui=(uint8_t *)GetModuleHandleA("GameUI.dll");
    if(!engine || !ui)return;
    ptr=(uint32_t)(uintptr_t)(engine+0x13064a4);memcpy(show_sig+2,&ptr,4);
    memcpy(resume_sig+2,&ptr,4);
    ptr=(uint32_t)(uintptr_t)(ui+0x6c330);memcpy(hide_sig+5,&ptr,4);
    ptr=(uint32_t)(uintptr_t)(ui+0x66b0c);memcpy(item_sig+9,&ptr,4);
    if(!unique(engine,show_sig,sizeof(show_sig),0x10dc10) || !unique(engine,cmd_sig,sizeof(cmd_sig),0x1a570) ||
       !unique(ui,vis_sig,sizeof(vis_sig),0x22070) || !unique(ui,hide_sig,sizeof(hide_sig),0x59d0) ||
       !unique(engine,resume_sig,sizeof(resume_sig),0x10d650) ||
       !unique(ui,min_sig,sizeof(min_sig),0x220e0) || !unique(ui,menu_sig,sizeof(menu_sig),0x21e30) ||
       !unique(ui,item_sig,sizeof(item_sig),0x21ee7))return;
    engine_hide=(EngineHideFn)(engine+0x10d650);
    minimize_visible=(VisibleFn)(ui+0x220e0);
    if(!prepare(hooks,engine+0x10dc10,6) || !prepare(hooks+1,engine+0x1a570,5) ||
       !prepare(hooks+2,ui+0x22070,5) || !prepare(hooks+3,ui+0x59d0,9))goto fail;
    original_show=(ShowFn)hooks[0].trampoline;original_command=(CommandFn)hooks[1].trampoline;
    original_visible=(VisibleFn)hooks[2].trampoline;original_hide=(HideFn)hooks[3].trampoline;
    for(i=0;i<4;i++) {
        memset(patch,0x90,hooks[i].length);jump(patch,hooks[i].site,destinations[i]);
        applied=i+1;
        if(!write_bytes(hooks[i].site,patch,hooks[i].length))goto fail;
    }
    installed=1;return;
fail:
    while(applied) {applied--;if(!write_bytes(hooks[applied].site,hooks[applied].old,hooks[applied].length))rollback=0;}
    /* If rollback ever fails, retain all callable trampoline memory. */
    if(rollback)for(i=0;i<4;i++)if(hooks[i].trampoline){VirtualFree(hooks[i].trampoline,0,MEM_RELEASE);hooks[i].trampoline=NULL;}
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
    (void)module;(void)reason;(void)reserved;return TRUE;
}
