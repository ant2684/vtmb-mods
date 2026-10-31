#ifndef PFI_RUNTIME_H
#define PFI_RUNTIME_H
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
enum {
 PFI_WARFORM,PFI_FILTER,PFI_INVENTORY,PFI_TRANSFORM,
 PFI_BUFFER,PFI_STEALTH,PFI_MELEE,PFI_GRIFFITH,PFI_COUNT
};
typedef struct {
 void *site;
 unsigned size;
 unsigned char before[24],after[24];
} PfiPatch;
extern int pfi_options[PFI_COUNT];
extern int pfi_inventory_ready;
int pfi_transform_active(void);
int pfi_commit(PfiPatch *patches,unsigned count);
int pfi_code_ready(void *code,unsigned size);
int pfi_write(void *site,const void *replacement,unsigned size);
void pfi_jump(PfiPatch *patch,void *site,unsigned size,const void *target);
void pfi_configure(void);
void pfi_lifecycle_server(void);
void pfi_core_server(void);
void pfi_core_client(void);
void pfi_flow_server(void);
void pfi_stealth_server(void);
void pfi_melee_server(void);
void pfi_claws_frenzy_server(void);
void pfi_griffith_server(void);
#endif
