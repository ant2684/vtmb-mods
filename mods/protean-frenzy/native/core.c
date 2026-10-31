#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "runtime.h"
#include "generated_server.h"
#include "generated_client.h"

typedef struct {
    uint32_t rva;
    const uint8_t *bytes;
    uint32_t size;
    const char *mask;
} Signature;

typedef struct {
    uint16_t offset;
    uint8_t kind;
    uint32_t target_rva;
    uint16_t anchor;
} RuntimeFixup;

static int server_installed;
static int client_installed;







static IMAGE_NT_HEADERS32 *pe_headers(uint8_t *module)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)module;
    IMAGE_NT_HEADERS32 *nt;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 || dos->e_lfanew > 0x1000)
        return NULL;
    nt = (IMAGE_NT_HEADERS32 *)(module + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC)
        return NULL;
    return nt;
}

static int signature_match(const uint8_t *at, const Signature *signature)
{
    unsigned int i;
    for (i = 0; i < signature->size; ++i)
        if ((!signature->mask || signature->mask[i] == 'x') && at[i] != signature->bytes[i])
            return 0;
    return 1;
}

static int unique_signature(uint8_t *module, const Signature *signature)
{
    IMAGE_NT_HEADERS32 *nt = pe_headers(module);
    IMAGE_SECTION_HEADER *sections;
    unsigned int section_index;
    unsigned int matches = 0;
    if (!nt || (uint64_t)signature->rva + signature->size > nt->OptionalHeader.SizeOfImage)
        return 0;
    if (signature->mask && strlen(signature->mask) != signature->size) return 0;
    sections = IMAGE_FIRST_SECTION(nt);
    for (section_index = 0; section_index < nt->FileHeader.NumberOfSections; ++section_index) {
        uint32_t start = sections[section_index].VirtualAddress;
        uint32_t size = sections[section_index].Misc.VirtualSize;
        uint32_t rva;
        if (!(sections[section_index].Characteristics & IMAGE_SCN_MEM_EXECUTE) ||
            (uint64_t)start + size > nt->OptionalHeader.SizeOfImage || size < signature->size)
            continue;
        for (rva = start; (uint64_t)rva + signature->size <= (uint64_t)start + size; ++rva)
            if (signature_match(module + rva, signature)) {
                if (rva != signature->rva) return 0;
                ++matches;
            }
    }
    return matches == 1;
}

static void put_u32(uint8_t *at, uint32_t value)
{
    memcpy(at, &value, 4);
}

static void relocate_code(uint8_t *code, uint8_t *module,
                          const RuntimeFixup *fixups, unsigned int count)
{
    unsigned int i;
    for (i = 0; i < count; ++i) {
        const RuntimeFixup *f = fixups + i;
        uint32_t target = (uint32_t)(uintptr_t)(module + f->target_rva);
        uint32_t source = (uint32_t)(uintptr_t)(code + (f->kind == 1 ? f->offset + 4 : f->anchor));
        put_u32(code + f->offset, target - source);
    }
}



static void make_jump(uint8_t *output, unsigned int count, uint8_t *site, uint8_t *destination)
{
    unsigned int i;
    output[0] = 0xe9;
    put_u32(output + 1, (uint32_t)(uintptr_t)destination - (uint32_t)(uintptr_t)(site + 5));
    for (i = 5; i < count; ++i) output[i] = 0x90;
}

static int is_jump_to(uint8_t *module, uint32_t site_rva, uint32_t target_rva)
{
    int32_t displacement;
    if (module[site_rva] != 0xe9) return 0;
    memcpy(&displacement, module + site_rva + 1, 4);
    return (uint32_t)(site_rva + 5 + displacement) == target_rva;
}

static const uint8_t server_gate_signature[] =
    {0x83,0xb8,0x68,0x01,0x00,0x00,0x1e,0x74,0x0a,0x8a,0x88,0xdc,0x1e,0x00,0x00,0x84,0xc9,0x74,0x27};
static const uint8_t server_sync_signature[] =
    {0x8a,0x85,0xdc,0x1e,0x00,0x00,0x84,0xc0,0x74,0x5c,0x8b,0x45};
static const uint8_t server_reentry_signature[] =
    {0x68,0x9f,0x86,0x01,0x00,0x8b,0xc8,0xc7,0x80,0x6c,0x14};
static const uint8_t server_expire_signature[] =
    {0x8b,0xbd,0xa8,0x00,0x00,0x00,0x68,0xe0,0x6b,0x5a,0x10,0x8b,0xcf,0xe8,0x0a,0x3b,0xe1,0xff,0xbb,0x02,0x00,0x00,0x00,0xb9};
static const uint8_t server_input_signature[] =
    {0x38,0x8f,0xdc,0x1e,0x00,0x00,0x75,0x52,0x89,0x4e};
static const uint8_t server_feat_signature[] =
    {0x83,0xec,0x10,0x53,0x56,0x8b,0x5c,0x24,0x1c,0x57};
static const uint8_t server_extra_signature[] =
    {0x83,0xec,0x0c,0x8b,0x54,0x24,0x10,0x56,0x33,0xf6,0x57,0x3b,0xd6,0x89,0x4c,0x24,
     0x10,0x89,0x74,0x24,0x08,0x0f,0x84,0xbe,0x00,0x00,0x00,0x8b,0x79,0x24};

static const Signature server_signatures[] = {
    {0x33ed64, server_gate_signature, sizeof(server_gate_signature), NULL},
    {0x16c558, server_sync_signature, sizeof(server_sync_signature), NULL},
    {0x33e9be, server_reentry_signature, sizeof(server_reentry_signature), NULL},
    {0x1f9177, server_expire_signature, sizeof(server_expire_signature), "xxxxxxx????xxxxxxxxxxxxx"},
    {0x3510d7, server_input_signature, sizeof(server_input_signature), NULL},
    {0x1e56e0, server_feat_signature, sizeof(server_feat_signature), NULL},
    {0x1e5b30, server_extra_signature, sizeof(server_extra_signature), NULL},
};

static const uint8_t client_signature_bytes[] =
    {0xa1,0x2c,0x99,0x61,0x10,0x83,0xff,0x01,0x7c,0x3a,0x3b,0xf8,0x74,0x4c};
static const Signature client_signature =
    {0x19da73, client_signature_bytes, sizeof(client_signature_bytes), "x????xxxxxxxxx"};

void pfi_core_server(void)
{
    static const uint32_t hook_rvas[] = {0x16c558,0x33e9be,0x1f9177,0x3510d7,0x1e56e0,0x1e5b30};
    static const uint8_t hook_sizes[] = {6,5,6,6,5,7};
    static const uint16_t helper_offsets[] = {SERVER_SYNC_OFFSET,SERVER_REENTRY_OFFSET,
        SERVER_EXPIRE_OFFSET,SERVER_INPUT_OFFSET,SERVER_FEAT_OFFSET,SERVER_EXTRA_OFFSET};
    uint8_t *module = (uint8_t *)GetModuleHandleA("vampire.dll");
    IMAGE_NT_HEADERS32 *nt;
    uint8_t *code;
    uint8_t old[6][7];
    uint8_t patch[7];
    unsigned int i;
    PfiPatch batch[7];int committed;
    if (server_installed || !module || !pfi_options[PFI_WARFORM]) return;
    nt = pe_headers(module);
    if (!nt) return;
    if (module[0x33ed75] == 0xeb &&
        is_jump_to(module, 0x16c558, 0x16000) &&
        is_jump_to(module, 0x33e9be, 0x16100) &&
        is_jump_to(module, 0x1f9177, 0x16200) &&
        is_jump_to(module, 0x3510d7, 0x16400) &&
        is_jump_to(module, 0x1e56e0, 0x16500) &&
        is_jump_to(module, 0x1e5b30, 0x16600)) {
        
        return;
    }
    for (i = 0; i < sizeof(server_signatures) / sizeof(server_signatures[0]); ++i)
        if (!unique_signature(module, &server_signatures[i])) {
            
            return;
        }
    {
        uint32_t global_pointer;
        memcpy(&global_pointer, module + 0x1f917e, 4);
        if (global_pointer != (uint32_t)(uintptr_t)(module + 0x5a6be0)) {
            
            return;
        }
    }
    for (i = 0; i < SERVER_FIXUP_COUNT; ++i)
        if (kServerFixups[i].target_rva >= nt->OptionalHeader.SizeOfImage) {
            
            return;
        }
    code = (uint8_t *)VirtualAlloc(NULL, 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!code) {  return; }
    memcpy(code, kServerCode, SERVER_CODE_SIZE);
    relocate_code(code, module, (const RuntimeFixup *)kServerFixups, SERVER_FIXUP_COUNT);
    if(!pfi_code_ready(code,0x1000)){VirtualFree(code,0,MEM_RELEASE);return;}
    for(i=0;i<6;++i)pfi_jump(batch+i,module+hook_rvas[i],hook_sizes[i],code+helper_offsets[i]);
    batch[6].site=module+0x33ed75;batch[6].size=1;
    batch[6].before[0]=module[0x33ed75];batch[6].after[0]=0xeb;
    committed=pfi_commit(batch,7);
    if(committed==1)server_installed=1;
    else if(!committed)VirtualFree(code,0,MEM_RELEASE);
}

void pfi_core_client(void)
{
    uint8_t *module = (uint8_t *)GetModuleHandleA("client.dll");
    IMAGE_NT_HEADERS32 *nt;
    uint8_t *code;
    uint8_t old[5];
    uint8_t patch[5];
    PfiPatch batch[7];int committed;
    uint32_t pointer;
    unsigned int i;
    if (client_installed || !module || !pfi_options[PFI_FILTER]) return;
    nt = pe_headers(module);
    if (!nt) return;
    if (module[0x19da73] == 0xe9) return;
    if (!unique_signature(module, &client_signature)) {
        
        return;
    }
    memcpy(&pointer, module + 0x19da74, 4);
    if (pointer != (uint32_t)(uintptr_t)(module + 0x61992c)) {
        
        return;
    }
    for (i = 0; i < CLIENT_FIXUP_COUNT; ++i)
        if (kClientFixups[i].target_rva >= nt->OptionalHeader.SizeOfImage) {
            
            return;
        }
    code = (uint8_t *)VirtualAlloc(NULL, 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!code) {  return; }
    memcpy(code, kClientCode, CLIENT_CODE_SIZE);
    relocate_code(code, module, (const RuntimeFixup *)kClientFixups, CLIENT_FIXUP_COUNT);
    if(!pfi_code_ready(code,0x1000)){VirtualFree(code,0,MEM_RELEASE);return;}
    pfi_jump(batch,module+0x19da73,5,code);
    committed=pfi_commit(batch,1);
    if(committed==1)client_installed=1;
    else if(!committed)VirtualFree(code,0,MEM_RELEASE);
}
