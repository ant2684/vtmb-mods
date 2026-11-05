/* Original MIT source. Native signatures are interoperability constants.
   The standalone helper contains no addresses into this plugin. Once its
   address has been published, retain its page until process exit: even a
   failed cache flush or a concurrent in-flight jump cannot reach freed code. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#define SITE 0x16dfa4u
#define NEXT 0x16dfb6u
#define SKIP 0x16e6b7u
static uint8_t *client, *helper;
static int state; /* 0 uninstalled, 1 installed, 2 failed/published or pending */
static DWORD original_protection;
static int protection_pending;
static int ui_cache_safe=1;
#define CAP_SITE 0x16fe4au
static uint8_t *cap_helper;
static int cap_state,cap_pending;
static DWORD cap_protection;
static const uint8_t cap_original[]={0x8a,0x44,0x24,0x13,0x84,0xc0,0x0f,0x85,0xaa,0,0,0};
static const uint8_t donor_anchor[]={0xa1,0x84,0xd9,0x49,0x10,0x53,0x55,0x33,0xed,0x33,0xdb,0x85,0xc0,0x7e,0x64};
#define PRICE_SITE 0xda3cbu
static uint8_t *server, *price_helper;
static int price_state, price_pending;
static DWORD price_protection;
static const uint8_t price_original[]={0x0f,0x84,0x86,0,0,0};
static const uint8_t buy_anchor[]={0x85,0xc0,0x74,0x05,0xc6,0x44,0x24,0x10,0x01,0x8b,0x07,0x8b,0xcf,0xff,0x90,0xcc,0x05,0,0,0x84,0xc0,0x0f,0x84,0x86,0,0,0,0x57,0x8b,0xcd,0xe8,0xa7,0xf0,0xf2,0xff};
static const uint8_t cost_anchor[]={0x8b,0x44,0x24,0x10,0x8b,0xcf,0x50,0x55,0x56,0xe8,0x46,0x2f,0xf3,0xff,0x8b,0xd8,0x8b,0xce,0x53,0xe8,0xcc,0xfe,0xf2,0xff,0x53,0x8b,0xcd,0xe8,0xef,0x00,0xf3,0xff};
static const uint8_t original[18] = {0x8b,0x44,0x24,0x34,0x8a,0x88,0x81,0x01,0,0,0x84,0xc9,0x0f,0x84,0x01,0x07,0,0};
static const uint8_t owner_anchor[] = {0x8b,0x16,0x8b,0xce,0xc6,0x44,0x24,0x44,0,0xff,0x92,0xa4,0x02,0,0,0x50,0x8b,0x06,0x8b,0xce,0xff,0x90,0x7c,0x03,0,0};
static const uint8_t stack_anchor[] = {0x8b,0x13,0x8b,0xcb,0xff,0x92,0xe8,0x03,0,0,0x84,0xc0,0x0f,0x84,0xae,0,0,0};
static int equal(const uint8_t *a,const uint8_t *b,unsigned n) {
    unsigned i;for(i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;
}
static void copy(uint8_t *a,const uint8_t *b,unsigned n) {
    unsigned i;for(i=0;i<n;i++)a[i]=b[i];
}
static void value(uint8_t *at,uint32_t n) {
    unsigned i;for(i=0;i<4;i++)at[i]=(uint8_t)(n>>(8*i));
}
static void branch(uint8_t *at,uint8_t *to) {
    at[0]=0xe9;value(at+1,(uint32_t)(uintptr_t)to-(uint32_t)(uintptr_t)(at+5));
}
static int identity(uint8_t *base,DWORD stamp,DWORD size) {
    IMAGE_DOS_HEADER *dos;IMAGE_NT_HEADERS32 *nt;
    if(!base)return 0;
    dos=(void *)base;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 || dos->e_lfanew>0x1000)return 0;
    nt=(void *)(base+dos->e_lfanew);
    return nt->Signature==IMAGE_NT_SIGNATURE && nt->FileHeader.Machine==IMAGE_FILE_MACHINE_I386 &&
        nt->FileHeader.TimeDateStamp==stamp && nt->OptionalHeader.Magic==IMAGE_NT_OPTIONAL_HDR32_MAGIC &&
        nt->OptionalHeader.SizeOfImage==size;
}
static int supported(uint8_t *base) {
    return identity(base,0x41afaf63,0x6e9000) &&
        equal(base+SITE,original,sizeof(original)) &&
        equal(base+0x16df25,owner_anchor,sizeof(owner_anchor)) &&
        equal(base+0x16f9ef,stack_anchor,sizeof(stack_anchor)) &&
        equal(base+CAP_SITE,cap_original,12) &&
        base[0x16ebe0]==0xa1 && *(uint32_t *)(base+0x16ebe1)==(uint32_t)(uintptr_t)(base+0x49d984) &&
        equal(base+0x16ebe5,donor_anchor+5,sizeof(donor_anchor)-5);
}
static int price_supported(uint8_t *base) {
    return identity(base,0x41afafae,0xab9000) &&
        equal(base+0xda3b6,buy_anchor,sizeof(buy_anchor)) &&
        equal(base+0xda4ec,cost_anchor,sizeof(cost_anchor));
}
static void price_patch(uint8_t *patch) {
    branch(patch,price_helper);
    value(patch+1,(uint32_t)(uintptr_t)price_helper-(uint32_t)(uintptr_t)(server+PRICE_SITE+5));
    patch[5]=0x90;
}
static int price_restore_page(void) {
    DWORD ignored;int i;
    for(i=0;i<2;i++)if(VirtualProtect(server+PRICE_SITE,6,price_protection,&ignored)) {
        price_pending=0;return 1;
    }
    price_pending=1;return 0;
}
static int restore_page(void) {
    DWORD ignored;int i;
    for(i=0;i<2;i++)if(VirtualProtect(client+SITE,sizeof(original),original_protection,&ignored)) {
        protection_pending=0;return 1;
    }
    protection_pending=1;return 0;
}
static int flush(void *p,unsigned n) {
    int i;for(i=0;i<2;i++)if(FlushInstructionCache(GetCurrentProcess(),p,n))return 1;return 0;
}
static void cap_patch(uint8_t *patch) {
    unsigned i;for(i=0;i<12;i++)patch[i]=0x90;
    branch(patch,cap_helper);
    value(patch+1,(uint32_t)(uintptr_t)cap_helper-(uint32_t)(uintptr_t)(client+CAP_SITE+5));
}
static int cap_restore_page(void) {
    DWORD ignored;int i;
    for(i=0;i<2;i++)if(VirtualProtect(client+CAP_SITE,12,cap_protection,&ignored)) {cap_pending=0;return 1;}
    cap_pending=1;return 0;
}
static void remove_cap(void) {
    DWORD old;uint8_t patch[12];
    if(!client || (void *)GetModuleHandleA("client.dll")!=client)return;
    if(cap_state==1) {
        cap_patch(patch);
        if(equal(client+CAP_SITE,patch,12) && VirtualProtect(client+CAP_SITE,12,PAGE_EXECUTE_READWRITE,&old)) {
            cap_protection=old;copy(client+CAP_SITE,cap_original,12);flush(client+CAP_SITE,12);cap_restore_page();cap_state=2;
        }
    } else if(cap_pending)cap_restore_page();
}
static int install_cap(void) {
    /* Only Give/Sell in barter mode. Use the native donor cache and validated
       EHANDLEs; item-data index identifies the same stack type. Native stack
       limit comes from GetItemData (7B160), not an item-specific constant.
       PUSHFD/PUSHAD preserve all state; only the original full-stack local
       [ESP+13] may become 1. Then replay the original button-disable branch.
       This independent helper has no plugin pointers and remains RX for life. */
    static const uint8_t code[]={0x9c,0x60,0x80,0xbe,0x81,0x01,0x00,0x00,0x00,0x0f,0x85,0xd3,0x00,0x00,0x00,0x8b,0x86,0xd4,0x04,0x00,0x00,0x83,0xf8,0x02,0x0f,0x84,0x09,0x00,0x00,0x00,0x83,0xf8,0x04,0x0f,0x85,0xbb,0x00,0x00,0x00,0x85,0xdb,0x0f,0x84,0xb3,0x00,0x00,0x00,0x8b,0xcb,0x8b,0x01,0xff,0x90,0xe8,0x03,0x00,0x00,0x84,0xc0,0x0f,0x84,0xa1,0x00,0x00,0x00,0x8b,0xcb,0xe8,0x00,0x00,0x00,0x00,0x85,0xc0,0x0f,0x84,0x92,0x00,0x00,0x00,0x8b,0xb8,0xa8,0xfe,0x04,0x00,0x0f,0xb7,0xab,0x5e,0x09,0x00,0x00,0x81,0xfd,0xff,0xff,0x00,0x00,0x0f,0x84,0x79,0x00,0x00,0x00,0xb8,0x00,0x00,0x00,0x00,0x8b,0x08,0x85,0xc9,0x0f,0x8e,0x6a,0x00,0x00,0x00,0xb8,0x00,0x00,0x00,0x00,0x8b,0x30,0xb8,0x00,0x00,0x00,0x00,0x8b,0x18,0x8b,0x06,0x83,0xf8,0xff,0x0f,0x84,0x47,0x00,0x00,0x00,0x89,0xc2,0x25,0xff,0x1f,0x00,0x00,0xc1,0xea,0x0d,0x8d,0x04,0x40,0x8d,0x04,0x83,0x39,0x50,0x08,0x0f,0x85,0x2e,0x00,0x00,0x00,0x8b,0x40,0x04,0x85,0xc0,0x0f,0x84,0x23,0x00,0x00,0x00,0x66,0x39,0xa8,0x5e,0x09,0x00,0x00,0x0f,0x85,0x16,0x00,0x00,0x00,0x39,0xb8,0x54,0x09,0x00,0x00,0x0f,0x8c,0x0a,0x00,0x00,0x00,0xc6,0x44,0x24,0x37,0x01,0xe9,0x0a,0x00,0x00,0x00,0x83,0xc6,0x04,0x49,0x0f,0x85,0xa4,0xff,0xff,0xff,0x61,0x9d,0x8a,0x44,0x24,0x13,0x84,0xc0,0x0f,0x85,0x00,0x00,0x00,0x00,0xe9,0x00,0x00,0x00,0x00};
    DWORD old,ignored;uint8_t patch[12];
    cap_helper=VirtualAlloc(NULL,sizeof(code),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!cap_helper)return 0;
    copy(cap_helper,code,sizeof(code));
    value(cap_helper+68,(uint32_t)(uintptr_t)(client+0x7b160)-(uint32_t)(uintptr_t)(cap_helper+72));
    value(cap_helper+236,(uint32_t)(uintptr_t)(client+0x16ff00)-(uint32_t)(uintptr_t)(cap_helper+240));
    branch(cap_helper+240,client+0x16fe56);
    value(cap_helper+106,(uint32_t)(uintptr_t)(client+0x49d984));
    value(cap_helper+121,(uint32_t)(uintptr_t)(client+0x49d978));
    value(cap_helper+128,(uint32_t)(uintptr_t)(client+0x2b8e98));
    if(!FlushInstructionCache(GetCurrentProcess(),cap_helper,sizeof(code)) || !VirtualProtect(cap_helper,sizeof(code),PAGE_EXECUTE_READ,&old)) {
        VirtualFree(cap_helper,0,MEM_RELEASE);cap_helper=NULL;return 0;
    }
    cap_patch(patch);
    if(!VirtualProtect(client+CAP_SITE,12,PAGE_EXECUTE_READWRITE,&old)) {
        VirtualFree(cap_helper,0,MEM_RELEASE);cap_helper=NULL;return 0;
    }
    cap_protection=old;
    if(!equal(client+CAP_SITE,cap_original,12)) {
        cap_restore_page();VirtualFree(cap_helper,0,MEM_RELEASE);cap_helper=NULL;return 0;
    }
    cap_state=2;copy(client+CAP_SITE,patch,12);
    if(FlushInstructionCache(GetCurrentProcess(),client+CAP_SITE,12) && VirtualProtect(client+CAP_SITE,12,cap_protection,&ignored)) {cap_state=1;return 1;}
    copy(client+CAP_SITE,cap_original,12);flush(client+CAP_SITE,12);cap_restore_page();return 0;
}
static int install_price(void) {
    /* Original JZ keeps the nonstack/ammunition path. Only the stackable
       fallthrough clears the local ammunition-price flag. MOV/JMP preserve
       every register, ESP and the original TEST flags. */
    static const uint8_t code[]={0x0f,0x84,0,0,0,0,0xc6,0x44,0x24,0x10,0,0xe9,0,0,0,0};
    DWORD old,ignored;uint8_t patch[6];
    price_helper=VirtualAlloc(NULL,sizeof(code),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!price_helper)return 0;
    copy(price_helper,code,sizeof(code));
    value(price_helper+2,(uint32_t)(uintptr_t)(server+0xda457)-(uint32_t)(uintptr_t)(price_helper+6));
    branch(price_helper+11,server+0xda3d1);
    if(!FlushInstructionCache(GetCurrentProcess(),price_helper,sizeof(code)) || !VirtualProtect(price_helper,sizeof(code),PAGE_EXECUTE_READ,&old)) {
        VirtualFree(price_helper,0,MEM_RELEASE);price_helper=NULL;return 0;
    }
    price_patch(patch);
    if(!VirtualProtect(server+PRICE_SITE,6,PAGE_EXECUTE_READWRITE,&old)) {
        VirtualFree(price_helper,0,MEM_RELEASE);price_helper=NULL;return 0;
    }
    price_protection=old;
    if(!equal(server+PRICE_SITE,price_original,6)) {
        price_restore_page();VirtualFree(price_helper,0,MEM_RELEASE);price_helper=NULL;return 0;
    }
    price_state=2;copy(server+PRICE_SITE,patch,6);
    if(FlushInstructionCache(GetCurrentProcess(),server+PRICE_SITE,6) && VirtualProtect(server+PRICE_SITE,6,price_protection,&ignored)) {price_state=1;return 1;}
    copy(server+PRICE_SITE,price_original,6);flush(server+PRICE_SITE,6);price_restore_page();return 0;
}
static void remove_price(void) {
    DWORD old;uint8_t patch[6];
    if(!server || (void *)GetModuleHandleA("vampire.dll")!=server)return;
    if(price_state==1) {
        price_patch(patch);
        if(equal(server+PRICE_SITE,patch,6) && VirtualProtect(server+PRICE_SITE,6,PAGE_EXECUTE_READWRITE,&old)) {
            price_protection=old;copy(server+PRICE_SITE,price_original,6);flush(server+PRICE_SITE,6);price_restore_page();price_state=2;
        }
    } else if(price_pending)price_restore_page();
}
static int make_helper(void) {
    /* Replay the original UI mode read and TEST before saving flags/registers.
       ECX=ESI invokes donor IsStackable thiscall, bool in AL. POPAD/POPFD
       restore the original post-TEST machine state on both outcomes. */
    static const uint8_t code[]={
        0x8b,0x44,0x24,0x34,0x8a,0x88,0x81,0x01,0,0,0x84,0xc9,
        0x0f,0x85,0,0,0,0, /* JNZ NEXT */
        0x9c,0x60,0x8b,0xce,0x85,0xc9,0x74,0x0c,
        0x8b,0x01,0xff,0x90,0xe8,0x03,0,0,0x84,0xc0,0x75,0x07,
        0x61,0x9d,0xe9,0,0,0,0, /* not stackable -> SKIP */
        0x61,0x9d,0xe9,0,0,0,0  /* stackable -> NEXT */
    };
    DWORD old;
    helper=VirtualAlloc(NULL,sizeof(code),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!helper)return 0;
    copy(helper,code,sizeof(code));
    value(helper+14,(uint32_t)(uintptr_t)(client+NEXT)-(uint32_t)(uintptr_t)(helper+18));
    branch(helper+40,client+SKIP);branch(helper+47,client+NEXT);
    if(!FlushInstructionCache(GetCurrentProcess(),helper,sizeof(code)) || !VirtualProtect(helper,sizeof(code),PAGE_EXECUTE_READ,&old)) {
        VirtualFree(helper,0,MEM_RELEASE);helper=NULL;return 0;
    }
    return 1;
}
static void install_client(void) {
    DWORD old,ignored;uint8_t patch[sizeof(original)];unsigned i;
    if(state || protection_pending)return;
    client=(void *)GetModuleHandleA("client.dll");
    /* Both client sites/anchors were checked before publishing cap. */
    if(!make_helper())return;
    for(i=0;i<sizeof(patch);i++)patch[i]=0x90;
    branch(patch,helper);
    /* branch() used the local array address; encode for the actual site. */
    value(patch+1,(uint32_t)(uintptr_t)helper-(uint32_t)(uintptr_t)(client+SITE+5));
    if(!VirtualProtect(client+SITE,sizeof(original),PAGE_EXECUTE_READWRITE,&old)) {
        VirtualFree(helper,0,MEM_RELEASE);helper=NULL;return;
    }
    original_protection=old;
    if(!equal(client+SITE,original,sizeof(original))) {
        restore_page();VirtualFree(helper,0,MEM_RELEASE);helper=NULL;return;
    }
    state=2;ui_cache_safe=0;copy(client+SITE,patch,sizeof(patch));
    if(FlushInstructionCache(GetCurrentProcess(),client+SITE,sizeof(patch)) && VirtualProtect(client+SITE,sizeof(original),original_protection,&ignored)) {state=1;return;}
    /* A flush refusal leaves RW access. A failed restore_page also leaves RW.
       Roll bytes back, retry both operations, and retain published helper. */
    copy(client+SITE,original,sizeof(original));ui_cache_safe=flush(client+SITE,sizeof(original));restore_page();
}
static void install(void) {
    if(state || price_state || protection_pending || price_pending)return;
    client=(void *)GetModuleHandleA("client.dll");server=(void *)GetModuleHandleA("vampire.dll");
    /* Never expose duplicate Buy rows without the matching payment fix.
       Either module load order is accepted; no site changes until both match. */
    if(!supported(client) || !price_supported(server))return;
    if(!install_price())return;
    if(!install_cap()) {remove_price();state=2;return;}
    install_client();
    if(state!=1) {remove_cap();if(ui_cache_safe)remove_price();state=2;}
}
__declspec(dllexport) void loaded_client(void) {install();}
__declspec(dllexport) void loaded_server(void) {install();}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved) {
    DWORD old;uint8_t patch[sizeof(original)];unsigned i;
    (void)instance;
    if(reason!=DLL_PROCESS_DETACH || reserved)return TRUE;
    remove_cap();
    if(!client || (void *)GetModuleHandleA("client.dll")!=client) {remove_price();return TRUE;}
    if(state==1) {
        for(i=0;i<sizeof(patch);i++)patch[i]=0x90;
        branch(patch,helper);value(patch+1,(uint32_t)(uintptr_t)helper-(uint32_t)(uintptr_t)(client+SITE+5));
        if(equal(client+SITE,patch,sizeof(patch)) && VirtualProtect(client+SITE,sizeof(original),PAGE_EXECUTE_READWRITE,&old)) {
            original_protection=old;copy(client+SITE,original,sizeof(original));ui_cache_safe=flush(client+SITE,sizeof(original));restore_page();
        }
    } else if(protection_pending)restore_page();
    /* If the visibility hook cannot be removed, keep the independent price
       helper installed as well. Both published pages outlive this DLL. */
    if(ui_cache_safe && equal(client+SITE,original,sizeof(original)))remove_price();
    return TRUE;
}
