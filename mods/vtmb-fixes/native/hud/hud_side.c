#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
typedef unsigned char B;
typedef uint32_t U;
typedef B (TC *InitFn)(void *,void *,void *);
typedef const char *(TC *NameFn)(void *);
typedef void (TC *DrawFn)(void *,int,int,int,int,int *,int);
typedef void (TC *ColorFn)(void *,int,int,int,int,int *,int,int,int,int);
typedef struct {U rva,target;void *replacement;B old[5],patch[5];DWORD protection;int writable,changed;} Site;
static B *client;
static Site sites[6];
static int clock_enabled=1,alignment_enabled=1;
__declspec(dllexport) U hud_fix_status[3];
static U rd(const void *p,U off){return *(const U *)((const B *)p+off);}
#include "hud_side_signatures.inc"
static int path_equal(const char *a,const char *b){
 unsigned i;for(i=0;i<128;i++){
  unsigned char x=(unsigned char)a[i],y=(unsigned char)b[i];
  if(x=='\\')x='/';if(x>='A'&&x<='Z')x+=32;
  if(x!=y)return 0;if(!x)return 1;
 }return 0;
}
/* Keep native Init/OnBind, timing source, loop behavior and pause semantics.
   These two decorative loops need no material-creation epoch. */
static B FC hud_init(void *self,void *unused,void *material,void *keys){
 B ok;const char *name;float rate;void **v;(void)unused;
 ok=((InitFn)(client+0x7a740))(self,material,keys);
 if(!ok||!material||!rd(self,4)||!rd(self,8)||!*((B *)self+16))return ok;
 v=*(void ***)material;name=((NameFn)v[0])(material);if(!name)return ok;
 rate=*(float *)((B *)self+12);
 if((rate==15.0f&&path_equal(name,"hud/new_ui/bloodbar/bloodbar"))||
    (rate==10.0f&&path_equal(name,"hud/new_ui/healthbar/healthbar")))
  *(float *)((B *)self+20)=0.0f;
 return ok;
}

/* The native HUD owns this linked list on its drawing thread. Do not retain
   panel pointers across a new game or recreation of the viewport. */
static B *panel(U vtable_rva){
 B *root=*(B **)(client+0x3eec98),*node;unsigned count=0;
 if(!root)return NULL;node=*(B **)(root+0x170);
 while(node&&count++<128){
  B *sub=*(B **)node;
  if(sub){B *p=sub-0x170;if(rd(p,0)==(U)(uintptr_t)(client+vtable_rva))return p;}
  node=*(B **)(node+4);
 }return NULL;
}
static int frame_span(B *p,int health,double *top,double *scale){
 B *im;int height=*(int *)(client+0x4a5834),sy,sh;double y;
 if(!p||height<480||height>16384)return 0;
 im=*(B **)(p+(health?0x1a0:0x1a4));if(!im)return 0;
 sy=(int)rd(im,12);sh=(int)rd(im,20);
 if(sy!=76||sh!=(health?756:749)||rd(im,16)!=128)return 0;
 if(health){y=12.0;*scale=(height-12.0)/sh;}
 else{
  double origin=*(double *)(client+0x228108);
  if(!(origin>0&&origin<100))return 0;
  y=(int)((height/768.0)*origin);*scale=(height-19.0)/sh;
 }
 *top=y-sy*(*scale);return 1;
}
static void mapped(double origin,double scale,double first,double last,int *y,int *h){
 int begin=(int)(origin+first*scale),end=(int)(origin+last*scale);
 *y=begin;*h=end-begin;
}
static void FC blood_body(void *image,void *unused,int x,int y,int w,int h,int *clip,int alpha){
 B *p=panel(0x227f14);double origin,scale;(void)unused;
 if(p&&image==*(void **)(p+0x1cc)&&clip&&clip[2]==43&&clip[3]>=43&&clip[3]<=464&&frame_span(p,0,&origin,&scale))
  mapped(origin,scale,698.0-(clip[3]-clip[2]),698.0,&y,&h);
 ((DrawFn)(client+0x5c430))(image,x,y,w,h,clip,alpha);
}
static void FC blood_bottom(void *image,void *unused,int x,int y,int w,int h,int *clip,int alpha){
 B *p=panel(0x227f14);double origin,scale;int amount;(void)unused;
 if(p&&image==*(void **)(p+0x1d0)&&clip&&frame_span(p,0,&origin,&scale)){
  amount=(int)rd(p,0x1d8);
  if(amount>=0&&amount<=150){int span=amount*421/150;if(span>20)span=20;mapped(origin,scale,698.0-span,698.0,&y,&h);}
 }
 ((DrawFn)(client+0x5c430))(image,x,y,w,h,clip,alpha);
}
static void FC health_fill(void *image,void *unused,int x,int y,int w,int h,int *clip,int r,int g,int b,int alpha){
 B *p=panel(0x228b7c);double origin,scale;(void)unused;
 if(p&&image==*(void **)(p+0x1ac)&&clip&&clip[2]>=46&&clip[3]<=467&&clip[2]<=clip[3]&&frame_span(p,1,&origin,&scale)){
  /* Two source pixels of overlap are hidden beneath the opaque top rim.
     Both endpoints follow the frame, including separate damage layers. */
  double first=321.0+(clip[2]-46)*(423.0/421.0);
  double last =321.0+(clip[3]-46)*(423.0/421.0);
  mapped(origin,scale,first,last,&y,&h);
 }
 ((ColorFn)(client+0x5cda0))(image,x,y,w,h,clip,r,g,b,alpha);
}
/* Configuration is owned by the unified HUDIndicatorsFix switch. */
static void configure(void){}
static int supported(B *m){
 IMAGE_DOS_HEADER *d=(void *)m;IMAGE_NT_HEADERS32 *n;
 if(!m||d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<0||d->e_lfanew>0x1000)return 0;
 n=(void *)(m+d->e_lfanew);
 return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==IMAGE_FILE_MACHINE_I386&&
  n->FileHeader.TimeDateStamp==CLIENT_TIMESTAMP&&n->OptionalHeader.SizeOfImage==CLIENT_SIZE&&anchors_match(m);
}
static int restore(Site *s){
 DWORD old,ignored;int retry;
 if(!s->changed)return 1;
 if(memcmp(client+s->rva,s->patch,5)&&memcmp(client+s->rva,s->old,5))return 0;
 if(!VirtualProtect(client+s->rva,5,PAGE_EXECUTE_READWRITE,&old))return 0;
 if(memcmp(client+s->rva,s->patch,5)&&memcmp(client+s->rva,s->old,5)){
  VirtualProtect(client+s->rva,5,s->protection,&ignored);return 0;
 }
 memcpy(client+s->rva,s->old,5);
 if(!FlushInstructionCache(GetCurrentProcess(),client+s->rva,5))return 0;
 for(retry=0;retry<3;retry++)if(VirtualProtect(client+s->rva,5,s->protection,&ignored)){s->changed=0;s->writable=0;return 1;}
 return 0;
}
__declspec(dllexport) void loaded_client(void){
 B *m;unsigned i,j;HMODULE pinned;DWORD ignored;int ok=1;
 if(hud_fix_status[0]||hud_fix_status[1]||hud_fix_status[2])return;
 configure();if(!clock_enabled&&!alignment_enabled)return;
 m=(B *)GetModuleHandleA("client.dll");if(!supported(m)){hud_fix_status[2]=1;return;}
 client=m;
 sites[0]=(Site){.rva=0x79462,.target=0x7a740,.replacement=hud_init};
 sites[1]=(Site){.rva=0x4d07b,.target=0x5c430,.replacement=blood_body};
 sites[2]=(Site){.rva=0x4d18d,.target=0x5c430,.replacement=blood_bottom};
 sites[3]=(Site){.rva=0x51822,.target=0x5cda0,.replacement=health_fill};
 sites[4]=(Site){.rva=0x51946,.target=0x5cda0,.replacement=health_fill};
 sites[5]=(Site){.rva=0x51a7c,.target=0x5cda0,.replacement=health_fill};
 for(i=0;i<6;i++){
  Site *s=&sites[i];B *at=m+s->rva;
  if((i==0&&!clock_enabled)||(i!=0&&!alignment_enabled))continue;
  if(at[0]!=0xe8||at+5+*(int32_t *)(at+1)!=m+s->target){hud_fix_status[2]=2;return;}
  memcpy(s->old,at,5);memcpy(s->patch,at,5);
  *(U *)(s->patch+1)=(U)(uintptr_t)s->replacement-(U)(uintptr_t)(at+5);
 }
 /* Callbacks live for the process lifetime, even if a third party attempts
    FreeLibrary. No unload can leave native code calling an unmapped VTM. */
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(const char *)hud_init,&pinned)){hud_fix_status[2]=3;return;}
 for(i=0;i<6;i++){
  Site *s=&sites[i];if(!s->old[0])continue;
  if(!VirtualProtect(m+s->rva,5,PAGE_EXECUTE_READWRITE,&s->protection)){ok=0;break;}
  s->writable=1;
 }
 if(ok)for(i=0;i<6;i++){
  Site *s=&sites[i];if(!s->writable)continue;
  if(memcmp(m+s->rva,s->old,5)){ok=0;break;}
  memcpy(m+s->rva,s->patch,5);s->changed=1;
  if(!FlushInstructionCache(GetCurrentProcess(),m+s->rva,5)){ok=0;break;}
 }
 for(i=0;i<6;i++)if(sites[i].writable&&!VirtualProtect(m+sites[i].rva,5,sites[i].protection,&ignored))ok=0;
 if(!ok){
  for(j=6;j>0;j--)restore(&sites[j-1]);
  for(i=0;i<6;i++)if(sites[i].writable&&!sites[i].changed)VirtualProtect(m+sites[i].rva,5,sites[i].protection,&ignored);
  hud_fix_status[2]=4;for(i=0;i<6;i++)if(sites[i].changed)hud_fix_status[2]=5;
  return;
 }
 hud_fix_status[0]=(U)clock_enabled;hud_fix_status[1]=(U)alignment_enabled;
}
