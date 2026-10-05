#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static unsigned calls,fail_mask,occupy_on_protect;
static BOOL fake_protect(LPVOID p,SIZE_T n,DWORD x,PDWORD previous) {
    (void)n;(void)x;*previous=PAGE_EXECUTE_READ;
    if(calls==0 && occupy_on_protect)((unsigned char *)p)[0]=0xcc;
    return !(fail_mask & (1u<<calls++));
}
static BOOL fake_flush(HANDLE h,LPCVOID p,SIZE_T n) {
    (void)h;(void)p;(void)n;return !(fail_mask & (1u<<calls++));
}
#define VirtualProtect fake_protect
#define FlushInstructionCache fake_flush
#define SUBTITLE_BACKGROUND_TEST
#include "../plugin/subtitle_background.c"
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint8_t *fixture(void) {
    uint8_t *b=(uint8_t *)calloc(1,0x110000);IMAGE_NT_HEADERS32 *nt;IMAGE_SECTION_HEADER *s;
    CHECK(b);((IMAGE_DOS_HEADER *)b)->e_magic=IMAGE_DOS_SIGNATURE;((IMAGE_DOS_HEADER *)b)->e_lfanew=0x80;
    nt=(IMAGE_NT_HEADERS32 *)(b+0x80);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->FileHeader.NumberOfSections=1;
    nt->FileHeader.SizeOfOptionalHeader=sizeof(IMAGE_OPTIONAL_HEADER32);
    nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x110000;
    s=IMAGE_FIRST_SECTION(nt);memcpy(s->Name,".text",5);s->VirtualAddress=0x1000;s->Misc.VirtualSize=0x100000;
    reference_for(b,b+DRAW_RVA);return b;
}
int main(void) {
    unsigned failure;uint8_t *b,*site,old[6];int result;
    (void)installed;
    b=fixture();site=b+DRAW_RVA+BRANCH_OFFSET;memcpy(old,site,6);calls=fail_mask=0;
    CHECK(install_patch(b)==1);CHECK(site[0]==0xe9 && site[5]==0x90);
    CHECK(site+5+*(int32_t *)(site+1)==b+DRAW_RVA+EPILOGUE_OFFSET);CHECK(calls==3);free(b);
    for(failure=0;failure<3;failure++) {
        b=fixture();site=b+DRAW_RVA+BRANCH_OFFSET;calls=0;fail_mask=1u<<failure;
        result=install_patch(b);CHECK(result==0);CHECK(!memcmp(site,old,6));free(b);
    }
    b=fixture();calls=0;fail_mask=(1u<<1)|(1u<<2)|(1u<<3);CHECK(install_patch(b)==-1);
    CHECK(!memcmp(b+DRAW_RVA+BRANCH_OFFSET,old,6));free(b);
    b=fixture();b[DRAW_RVA+BRANCH_OFFSET]=0xe9;calls=fail_mask=0;CHECK(install_patch(b)==0 && calls==0);free(b);
    b=fixture();b[DRAW_RVA+50]^=1;calls=fail_mask=0;CHECK(install_patch(b)==0 && calls==0);free(b);
    b=fixture();reference_for(b,b+0x1000);calls=fail_mask=0;CHECK(install_patch(b)==0 && calls==0);free(b);
    b=fixture();((IMAGE_DOS_HEADER *)b)->e_magic=0;calls=fail_mask=0;CHECK(install_patch(b)==0 && calls==0);free(b);
    b=fixture();calls=fail_mask=0;occupy_on_protect=1;CHECK(install_patch(b)==0 && calls==2);
    CHECK(b[DRAW_RVA+BRANCH_OFFSET]==0xcc);free(b);
    b=fixture();calls=0;fail_mask=1u<<1;CHECK(install_patch(b)==-1 && calls==2);
    CHECK(b[DRAW_RVA+BRANCH_OFFSET]==0xcc);free(b);
    puts("PASS relocated signature, target, occupied/unsupported/duplicate refusal and all installation failure/rollback paths");return 0;
}
