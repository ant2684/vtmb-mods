#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "runtime.h"

void pfi_jump(PfiPatch *patch,void *site,unsigned size,const void *target){
 patch->site=site;patch->size=size;
 memcpy(patch->before,site,size);memset(patch->after,0x90,size);
 patch->after[0]=0xe9;
 *(uint32_t *)(patch->after+1)=(uint32_t)((uintptr_t)target-(uintptr_t)site-5);
}

int pfi_code_ready(void *code,unsigned size){
 DWORD old;
 return VirtualProtect(code,size,PAGE_EXECUTE_READ,&old)&&
        FlushInstructionCache(GetCurrentProcess(),code,size);
}

/* Return 1 only after instruction visibility and the ORIGINAL protection of
   every distinct page have been restored. 0 means full rollback. -1 means a
   published helper might still be reachable: callers must retain its storage.
   Duplicate/shared-page patches never restore a temporary RWX protection. */
int pfi_commit(PfiPatch *patches,unsigned count){
 struct Page {void *address;DWORD protection;int acquired;} pages[128];
 SYSTEM_INFO system;unsigned n=0,i,j,k,written=0;int success=1,restored=1;
 DWORD ignored;MEMORY_BASIC_INFORMATION info;uintptr_t size,first,last,address;
 if(!count||count>128)return 0;
 GetSystemInfo(&system);size=system.dwPageSize;if(!size||(size&(size-1)))return 0;
 memset(pages,0,sizeof(pages));
 for(i=0;i<count;++i){
  PfiPatch *p=patches+i;
  if(!p->size||p->size>sizeof(p->before)||!p->site||
     memcmp(p->site,p->before,p->size))return 0;
  for(j=0;j<i;++j)if((uintptr_t)p->site<(uintptr_t)patches[j].site+patches[j].size&&
      (uintptr_t)patches[j].site<(uintptr_t)p->site+p->size)return 0;
  first=(uintptr_t)p->site&~(size-1);last=((uintptr_t)p->site+p->size-1)&~(size-1);
  for(address=first;;address+=size){
   for(j=0;j<n&&pages[j].address!=(void *)address;++j){}
   if(j==n){
    if(n==128||!VirtualQuery((void *)address,&info,sizeof(info))||
       info.State!=MEM_COMMIT||(info.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return 0;
    pages[n].address=(void *)address;pages[n++].protection=info.Protect;
   }
   if(address==last)break;
  }
 }
 for(i=0;i<n;++i){
  if(!VirtualProtect(pages[i].address,size,PAGE_EXECUTE_READWRITE,&ignored)){success=0;break;}
  pages[i].acquired=1;
 }
 if(success)for(i=0;i<count;++i)if(memcmp(patches[i].site,patches[i].before,patches[i].size)){success=0;break;}
 if(success){
  for(i=0;i<count;++i){memcpy(patches[i].site,patches[i].after,patches[i].size);++written;}
  for(i=0;i<count;++i)if(!FlushInstructionCache(GetCurrentProcess(),patches[i].site,patches[i].size))success=0;
  for(i=n;i;){--i;if(!VirtualProtect(pages[i].address,size,pages[i].protection,&ignored))success=0;else pages[i].acquired=0;}
 }
 if(success)return 1;
 /* Reacquire pages because a failed commit may already have restored some. */
 if(written){
  for(i=0;i<n;++i){
   if(VirtualProtect(pages[i].address,size,PAGE_EXECUTE_READWRITE,&ignored))pages[i].acquired=1;
   else restored=0;
  }
  for(i=0;i<written;++i){
   PfiPatch *p=patches+i;int writable=1;
   first=(uintptr_t)p->site&~(size-1);last=((uintptr_t)p->site+p->size-1)&~(size-1);
   for(j=0;j<n;++j)if((uintptr_t)pages[j].address>=first&&(uintptr_t)pages[j].address<=last&&!pages[j].acquired)writable=0;
   if(!memcmp(p->site,p->before,p->size))continue;
   if(!writable||memcmp(p->site,p->after,p->size)){restored=0;continue;}
   memcpy(p->site,p->before,p->size);
   if(!FlushInstructionCache(GetCurrentProcess(),p->site,p->size))restored=0;
  }
 }
 for(i=n;i;){--i;if(pages[i].acquired){
  /* One transient OS refusal is retried, without accepting a different old protection. */
  for(k=0;k<2;++k)if(VirtualProtect(pages[i].address,size,pages[i].protection,&ignored))break;
  if(k==2)restored=0;
 }}
 return restored?0:-1;
}
int pfi_write(void *site,const void *replacement,unsigned size){
 PfiPatch p;if(size>sizeof(p.before))return 0;
 p.site=site;p.size=size;memcpy(p.before,site,size);memcpy(p.after,replacement,size);
 return pfi_commit(&p,1)==1;
}

