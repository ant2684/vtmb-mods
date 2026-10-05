#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "draw_reference.h"

/* CHudChat's PaintBackground keeps its normal visibility/disable handling.
   The single conditional branch below leads to two drawing calls during a
   cinematic camera fade: black fill and grey outline. Turning that existing
   branch into an unconditional jump skips only the draw-only block. No
   trampoline, text/caption interception, timing state or per-frame work. */
static int installed;

static void reference_for(uint8_t *base,uint8_t *out) {
    unsigned i;uint32_t delta=(uint32_t)(uintptr_t)base-0x10000000u;
    memcpy(out,draw_reference,sizeof(draw_reference));
    for(i=0;i<sizeof(reloc_offsets)/sizeof(reloc_offsets[0]);i++) {
        uint32_t value;memcpy(&value,out+reloc_offsets[i],4);value+=delta;
        memcpy(out+reloc_offsets[i],&value,4);
    }
}
static uint8_t *validated_site(uint8_t *base) {
    IMAGE_DOS_HEADER *dos;IMAGE_NT_HEADERS32 *nt;IMAGE_SECTION_HEADER *sections;
    uint8_t expected[sizeof(draw_reference)],*match=NULL;unsigned i,j,count=0;
    dos=(IMAGE_DOS_HEADER *)base;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 || dos->e_lfanew>0x1000)return NULL;
    nt=(IMAGE_NT_HEADERS32 *)(base+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386 ||
       nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC || nt->FileHeader.NumberOfSections>32 ||
       nt->OptionalHeader.SizeOfImage<DRAW_RVA+sizeof(draw_reference))return NULL;
    sections=IMAGE_FIRST_SECTION(nt);reference_for(base,expected);
    for(i=0;i<nt->FileHeader.NumberOfSections;i++) {
        uint32_t rva=sections[i].VirtualAddress,size=sections[i].Misc.VirtualSize;
        if(memcmp(sections[i].Name,".text",5)!=0)continue;
        if(rva>nt->OptionalHeader.SizeOfImage || size>nt->OptionalHeader.SizeOfImage-rva || size<sizeof(expected))return NULL;
        for(j=0;j<=size-sizeof(expected);j++) {
            if(base[rva+j]!=expected[0] || memcmp(base+rva+j,expected,sizeof(expected)))continue;
            match=base+rva+j;count++;
        }
    }
    if(count!=1 || match!=base+DRAW_RVA)return NULL;
    return match+BRANCH_OFFSET;
}
static int install_patch(uint8_t *base) {
    uint8_t *site=validated_site(base),old[6],patch[6]={0xe9,0,0,0,0,0x90};
    DWORD protection,ignored;int32_t displacement=(int32_t)(EPILOGUE_OFFSET-BRANCH_OFFSET-5);
    if(!site)return 0;
    memcpy(old,site,sizeof(old));memcpy(patch+1,&displacement,4);
    if(!VirtualProtect(site,6,PAGE_EXECUTE_READWRITE,&protection))return 0;
    /* Recheck immediately before the only write; refuse a newly occupied site. */
    if(memcmp(site,old,6)) {return VirtualProtect(site,6,protection,&ignored) ? 0 : -1;}
    memcpy(site,patch,6);
    if(FlushInstructionCache(GetCurrentProcess(),site,6) && VirtualProtect(site,6,protection,&ignored))return 1;
    /* Either failed operation leaves the page writable. Restore original bytes
       first, then flush and restore the original protection independently. */
    memcpy(site,old,6);
    {int flushed=FlushInstructionCache(GetCurrentProcess(),site,6)!=0;
     int protected_again=VirtualProtect(site,6,protection,&ignored)!=0;
     return flushed && protected_again ? 0 : -1;}
}
#ifndef SUBTITLE_BACKGROUND_TEST
__declspec(dllexport) void loaded_client(void) {
    uint8_t *base;int result;
    if(installed)return;
    base=(uint8_t *)GetModuleHandleA("client.dll");if(!base)return;
    result=install_patch(base);
    if(result==1)installed=1;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
    (void)module;(void)reason;(void)reserved;return TRUE;
}
#endif
