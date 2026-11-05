#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#define FC __attribute__((fastcall))
#define TC __attribute__((thiscall))
typedef unsigned char B;
typedef uint32_t U;
typedef struct {U rva,size;B old[6],patch[6];DWORD protection;int writable,changed;} Site;
static B *client;
static Site sites[3];
__declspec(dllexport) U victim_bar_status[2];
static U rd(const void *p,U off){return *(const U *)((const B *)p+off);}
#include "hud_victim_signatures.inc"

/* These checks are local to CFeedBar.Paint. Never change player/network flags. */
static int __attribute__((used,noinline)) feed_active(B *p){
 float duration;U bits,max,blood;
 if(!p)return 0;
 if(p[0x14d4])return 1;
 duration=*(float *)(p+0x14d0);memcpy(&bits,&duration,4);
 max=rd(p,0x14cc);blood=rd(client,0x3ede94);
 return (bits&0x7f800000u)!=0x7f800000u&&duration>0.f&&max>0&&max<=255&&blood>0&&blood<15&&blood<=max;
}
/* Replaces MOV AL,[EBP+14D4]. Preserve every other register and the upper EAX
   bytes. Both native continuations immediately TEST AL,AL. No FPU value is live. */
static void __attribute__((naked)) active_bridge(void){
 __asm__ volatile("push %ecx\n push %edx\n push %eax\n push %ebp\n call _feed_active\n add $4,%esp\n mov %al,(%esp)\n pop %eax\n pop %edx\n pop %ecx\n ret");
}
static void FC feed_paint(B *self,void *unused){
 B *p=*(B **)(client+0x4a0d50);U max,blood;(void)unused;
 if(p){
  max=rd(p,0x14cc);blood=rd(client,0x3ede94);
  /* A user message can precede its maximum-pool network property. Wait for
     coherent values rather than displaying the native fallback denominator15. */
  if(!max||max>255||blood>max)return;
  *(U *)(self+0x1ac)=max;
  *(U *)(self+0x1a8)=100*blood/max;
 }
 ((void(TC *)(void *))(client+0x50560))(self);
}
static int supported(B *m){
 IMAGE_DOS_HEADER *d=(void *)m;IMAGE_NT_HEADERS32 *n;
 if(!m||d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<0||d->e_lfanew>0x1000)return 0;
 n=(void *)(m+d->e_lfanew);
 return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&n->FileHeader.TimeDateStamp==CLIENT_TIMESTAMP&&n->OptionalHeader.SizeOfImage==CLIENT_SIZE&&anchors_match(m);
}
static int restore(Site *s){
 DWORD old,ignored;int retry;
 if(!s->changed)return 1;
 if(memcmp(client+s->rva,s->patch,s->size)&&memcmp(client+s->rva,s->old,s->size))return 0;
 if(!VirtualProtect(client+s->rva,s->size,PAGE_EXECUTE_READWRITE,&old))return 0;
 if(memcmp(client+s->rva,s->patch,s->size)&&memcmp(client+s->rva,s->old,s->size)){VirtualProtect(client+s->rva,s->size,s->protection,&ignored);return 0;}
 memcpy(client+s->rva,s->old,s->size);
 if(!FlushInstructionCache(GetCurrentProcess(),client+s->rva,s->size))return 0;
 for(retry=0;retry<3;retry++)if(VirtualProtect(client+s->rva,s->size,s->protection,&ignored)){s->changed=s->writable=0;return 1;}
 return 0;
}
__declspec(dllexport) void loaded_client(void){
 B *m;U i,j;DWORD ignored;HMODULE pinned;int ok=1;
 if(victim_bar_status[0]||victim_bar_status[1])return;
 m=(B *)GetModuleHandleA("client.dll");if(!supported(m)){victim_bar_status[1]=1;return;}client=m;
 sites[0]=(Site){.rva=0x50576,.size=6};sites[1]=(Site){.rva=0x5079b,.size=6};sites[2]=(Site){.rva=0x22890c,.size=4};
 for(i=0;i<3;i++){
  Site *s=&sites[i];B *at=m+s->rva;
  if((i<2&&memcmp(at,"\x8a\x85\xd4\x14\x00\x00",6))||(i==2&&rd(at,0)!=(U)(uintptr_t)(m+0x50560))){victim_bar_status[1]=2;return;}
  memcpy(s->old,at,s->size);
  if(i<2){s->patch[0]=0xe8;*(U *)(s->patch+1)=(U)(uintptr_t)active_bridge-(U)(uintptr_t)(at+5);s->patch[5]=0x90;}
  else *(U *)s->patch=(U)(uintptr_t)feed_paint;
 }
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(const char *)loaded_client,&pinned)){victim_bar_status[1]=3;return;}
 for(i=0;i<3;i++){Site *s=&sites[i];if(!VirtualProtect(m+s->rva,s->size,PAGE_EXECUTE_READWRITE,&s->protection)){ok=0;break;}s->writable=1;}
 if(ok)for(i=0;i<3;i++){Site *s=&sites[i];if(memcmp(m+s->rva,s->old,s->size)){ok=0;break;}memcpy(m+s->rva,s->patch,s->size);s->changed=1;if(!FlushInstructionCache(GetCurrentProcess(),m+s->rva,s->size)){ok=0;break;}}
 for(i=0;i<3;i++)if(sites[i].writable&&!VirtualProtect(m+sites[i].rva,sites[i].size,sites[i].protection,&ignored))ok=0;
 if(!ok){
  for(j=3;j>0;j--)restore(&sites[j-1]);
  for(i=0;i<3;i++)if(sites[i].writable&&!sites[i].changed)VirtualProtect(m+sites[i].rva,sites[i].size,sites[i].protection,&ignored);
  victim_bar_status[1]=4;for(i=0;i<3;i++)if(sites[i].changed)victim_bar_status[1]=5;return;
 }
 victim_bar_status[0]=1;
}
