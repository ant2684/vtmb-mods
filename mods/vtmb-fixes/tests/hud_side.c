#include "native_fixture.h"
#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
static uint8_t *image;
static unsigned mask=3,protect_calls,flush_calls,fail_protect,fail_flush;
static int pin_fail;
static HMODULE WINAPI module(const char *name){return !_stricmp(name,"client.dll")?(HMODULE)image:NULL;}
static BOOL WINAPI pin(DWORD flags,const char *address,HMODULE *out){(void)flags;(void)address;if(pin_fail)return FALSE;*out=(HMODULE)image;return TRUE;}
static DWORD WINAPI filename(HMODULE h,char *out,DWORD size){const char *s="C:\\fixture\\hud-indicators-fix.vtm";(void)h;check(size>strlen(s),"filename buffer");strcpy(out,s);return (DWORD)strlen(s);}
static DWORD WINAPI setting(const char *section,const char *key,const char *fallback,char *out,DWORD size,const char *path){
 int on; (void)section;(void)fallback;(void)path;check(size>1,"INI buffer");on=!strcmp(key,"HUDIndicatorsFix")&&mask;out[0]=on?'1':'0';out[1]=0;return 1;
}
static BOOL WINAPI protection(void *at,SIZE_T n,DWORD flags,DWORD *old){if(++protect_calls==fail_protect)return FALSE;return VirtualProtect(at,n,flags,old);}
static BOOL WINAPI flush(HANDLE h,const void *at,SIZE_T n){if(++flush_calls==fail_flush)return FALSE;return FlushInstructionCache(h,at,n);}
static const unsigned rvas[]={0x79462,0x4d07b,0x4d18d,0x51822,0x51946,0x51a7c};
static void *call_target(uint8_t *at){check(at[0]==0xe8,"native CALL opcode");return at+5+*(int32_t *)(at+1);}
static void mock_jump(unsigned rva,void *target){DWORD old,ignored;check(VirtualProtect(image+rva,5,PAGE_EXECUTE_READWRITE,&old),"fixture patch");jump(image+rva,target);VirtualProtect(image+rva,5,old,&ignored);}
typedef struct {void **v;const char *name;} Material;
static const char *FC name_of(void *p,void *unused){(void)unused;return ((Material *)p)->name;}
static float init_rate;static unsigned init_loop=1,init_success=1;
static uint8_t FC init_base(void *p,void *unused,void *mat,void *kv){
 (void)unused;(void)mat;(void)kv;put((uint8_t *)p+4,0x1234);put((uint8_t *)p+8,0x5678);
 memcpy((uint8_t *)p+12,&init_rate,4);*((uint8_t *)p+16)=(uint8_t)init_loop;return (uint8_t)init_success;
}
static void check_init(void *entry,const char *name,float rate,int loop,int ok,int expected_zero){
 uint8_t proxy[32]={0};void *vtable[1]={(void *)name_of};Material mat={vtable,name};float start=706.f;
 init_rate=rate;init_loop=(unsigned)loop;init_success=(unsigned)ok;memcpy(proxy+20,&start,4);
 check(((uint8_t(TC *)(void *,void *,void *))entry)(proxy,&mat,NULL)==ok,"Init return preserved");
 check(*(float *)(proxy+20)==(expected_zero?0.f:706.f),"only supported looping HUD clocks changed");
}
static double now,dt=1.0/60;static unsigned num_frames,last_frame;
static void *texture;
static void *FC get_texture(void *self,void *unused){(void)self;(void)unused;return texture;}
static int FC get_count(void *self,void *unused){(void)self;(void)unused;return (int)num_frames;}
static double FC get_time(void *self,void *unused,int flag){(void)self;(void)unused;(void)flag;return now;}
static double FC get_delta(void *self,void *unused,int flag){(void)self;(void)unused;(void)flag;return dt;}
static void FC set_frame(void *self,void *unused,int value){(void)self;(void)unused;last_frame=(unsigned)value;}
static void check_native_cycles(float rate,unsigned n){
 uint8_t proxy[32]={0};void *pv[6]={0},*tv[20]={0},*xv[7]={0},*fv[6]={0},*ev[43]={0};
 void **t=tv,**x=xv,**f=fv,**e=ev;unsigned i,seen[35]={0};float zero=0;
 pv[4]=image+0x79470;pv[5]=image+0x79400;*(void ***)proxy=pv;*(void **)(proxy+4)=&t;*(void **)(proxy+8)=&f;
 memcpy(proxy+12,&rate,4);proxy[16]=1;memcpy(proxy+20,&zero,4);
 tv[0x48/4]=(void *)get_texture;xv[0x14/4]=(void *)get_count;fv[0x10/4]=(void *)set_frame;
 ev[0x9c/4]=(void *)get_time;ev[0xa4/4]=(void *)get_delta;texture=&x;num_frames=n;*(void **)(image+0x4a57d4)=&e;
 for(i=0;i<n*3;i++){now=146.22740173339844+(i+.25)/rate;((void(TC *)(void *,void *))(image+0x7a810))(proxy,NULL);check(last_frame<n,"native frame bounds");seen[last_frame]=1;}
 for(i=0;i<n;i++)check(seen[i],"native handler visits full cycle");
 now=100;((void(TC *)(void *,void *))(image+0x7a810))(proxy,NULL);i=last_frame;
 ((void(TC *)(void *,void *))(image+0x7a810))(proxy,NULL);check(last_frame==i,"paused clock retains frame");
 for(i=0;i<n;i++){now=(i+.25)/rate;((void(TC *)(void *,void *))(image+0x7a810))(proxy,NULL);check(last_frame<n,"rewound epoch remains bounded");}
}
static int draw_args[10],draw_calls;
static void FC draw(void *self,void *unused,int x,int y,int w,int h,int *clip,int alpha){
 (void)self;(void)unused;draw_args[0]=x;draw_args[1]=y;draw_args[2]=w;draw_args[3]=h;draw_args[4]=alpha;draw_args[5]=clip[2];draw_args[6]=clip[3];++draw_calls;
}
static void FC color(void *self,void *unused,int x,int y,int w,int h,int *clip,int r,int g,int b,int alpha){
 draw(self,unused,x,y,w,h,clip,alpha);draw_args[7]=r;draw_args[8]=g;draw_args[9]=b;
}
static void geometry(void){
 uint8_t root[0x180]={0},blood[0x1dc]={0},health[0x1b0]={0},bf[32]={0},hf[32]={0},body[32]={0},bottom[32]={0},fill[32]={0};
 void *bn[2]={blood+0x170,NULL},*hn[2]={health+0x170,bn};int bc[4]={46,21,43,464},hc[4]={46,21,46,467};double origin=29.576313931666043;unsigned pct;
 void *bentry=call_target(image+0x4d07b),*bcap=call_target(image+0x4d18d),*hentry=call_target(image+0x51a7c);
 *(void **)(image+0x3eec98)=root;*(void **)(root+0x170)=hn;put(blood,(uint32_t)(uintptr_t)(image+0x227f14));put(health,(uint32_t)(uintptr_t)(image+0x228b7c));
 *(void **)(blood+0x1a4)=bf;*(void **)(blood+0x1cc)=body;*(void **)(blood+0x1d0)=bottom;*(void **)(health+0x1a0)=hf;*(void **)(health+0x1ac)=fill;
 put(bf+12,76);put(bf+16,128);put(bf+20,749);put(hf+12,76);put(hf+16,128);put(hf+20,756);
 put(image+0x4a5834,1440);memcpy(image+0x228108,&origin,8);put(blood+0x1d8,150);
 mock_jump(0x5c430,(void *)draw);mock_jump(0x5cda0,(void *)color);
 ((void(TC *)(void *,int,int,int,int,int *,int))bentry)(body,2486,448,46,789,bc,255);
 check(draw_args[0]==2486&&draw_args[2]==46&&draw_args[4]==255,"blood horizontal/alpha forwarded");
 check(draw_args[1]>=435&&draw_args[1]<=437&&draw_args[1]+draw_args[3]>=1234&&draw_args[1]+draw_args[3]<=1236,"full blood anchored to actual frame");
 ((void(TC *)(void *,int,int,int,int,int *,int))bcap)(bottom,2486,1199,46,37,bc,255);
 check(draw_args[1]+draw_args[3]>=1234&&draw_args[1]+draw_args[3]<=1236,"blood cap shares bottom edge");
 for(pct=0;pct<=100;pct++){
  int expected=467-(int)(421*pct/100);hc[2]=expected;
  ((void(TC *)(void *,int,int,int,int,int *,int,int,int,int))hentry)(fill,33,485,46,789,hc,124,238,255,211);
  check(draw_args[0]==33&&draw_args[2]==46&&draw_args[4]==211,"health horizontal/alpha forwarded");
  check(draw_args[7]==124&&draw_args[8]==238&&draw_args[9]==255,"native damage color forwarded");
  check(draw_args[3]>=0&&draw_args[1]+draw_args[3]==1273,"all health levels share frame bottom");
  if(pct==0)check(draw_args[3]==0,"zero health has no false fill");
  if(pct==100)check(draw_args[1]==474,"health full fill overlaps top rim");
 }
 hc[2]=200;hc[3]=300;((void(TC *)(void *,int,int,int,int,int *,int,int,int,int))hentry)(fill,33,0,46,0,hc,255,181,28,255);
 check(draw_args[3]>0&&draw_args[7]==255&&draw_args[8]==181&&draw_args[9]==28,"aggravated damage layer retained");
 *(void **)(root+0x170)=NULL;bc[2]=43;bc[3]=464;
 ((void(TC *)(void *,int,int,int,int,int *,int))bentry)(body,1,2,3,4,bc,5);check(draw_args[1]==2&&draw_args[3]==4,"unmatched viewport forwards unchanged");
 check(draw_calls>100,"draw callbacks executed");
}
int main(int argc,char **argv){
 HMODULE plugin;void (__cdecl *load)(void);uint32_t *status;uint8_t original[6][5];unsigned i;int fail=0;
 check(argc==4,"plugin client scenario arguments");image=map_image(argv[2]);plugin=LoadLibraryA(argv[1]);check(plugin!=NULL,"load exact delivery");
 imports(plugin,"GetModuleHandleA",module);imports(plugin,"GetModuleHandleExA",pin);imports(plugin,"GetModuleFileNameA",filename);imports(plugin,"GetPrivateProfileStringA",setting);imports(plugin,"VirtualProtect",protection);imports(plugin,"FlushInstructionCache",flush);
 load=(void *)GetProcAddress(plugin,"loaded_client");status=(void *)GetProcAddress(plugin,"hud_fix_status");check(load&&status,"production exports");
 if(!strcmp(argv[3],"disabled"))mask=0;
 else if(!strcmp(argv[3],"clock"))mask=1;
 else if(!strcmp(argv[3],"alignment"))mask=2;
 else if(!strcmp(argv[3],"badstamp")){IMAGE_NT_HEADERS32 *n=(void *)(image+((IMAGE_DOS_HEADER *)image)->e_lfanew);n->FileHeader.TimeDateStamp++;fail=1;}
 else if(!strcmp(argv[3],"badsite")){image[0x51822]=0x90;fail=1;}
 else if(!strcmp(argv[3],"badanchor")){image[0x79470]=0x90;fail=1;}
 else if(!strcmp(argv[3],"pinfail")){pin_fail=1;fail=1;}
 else if(!strncmp(argv[3],"protect",7)){fail_protect=(unsigned)atoi(argv[3]+7);fail=1;}
 else if(!strncmp(argv[3],"flush",5)){fail_flush=(unsigned)atoi(argv[3]+5);fail=1;}
 for(i=0;i<6;i++)memcpy(original[i],image+rvas[i],5);
 load();
 if(fail){check(status[0]==0&&status[1]==0&&status[2]!=0,"failure refusal status");for(i=0;i<6;i++)check(!memcmp(original[i],image+rvas[i],5),"refusal/rollback preserves every site");}
 else{
  check(status[0]==(mask&1)&&status[1]==((mask>>1)&1)&&status[2]==0,"enabled groups installed");
  for(i=0;i<6;i++)check((memcmp(original[i],image+rvas[i],5)!=0)==(i?!!(mask&2):!!(mask&1)),"only enabled call sites changed");
  load();check(status[2]==0,"repeat callback idempotent");
  if(mask&1){void *entry=call_target(image+0x79462);mock_jump(0x7a740,(void *)init_base);
   check_init(entry,"hud/new_ui/bloodbar/bloodbar",15,1,1,1);check_init(entry,"HUD\\NEW_UI\\HEALTHBAR\\HEALTHBAR",10,1,1,1);
   check_init(entry,"world/water",15,1,1,0);check_init(entry,"hud/new_ui/bloodbar/bloodbar_extra",15,1,1,0);check_init(entry,"hud/new_ui/bloodbar/bloodbar",15,0,1,0);check_init(entry,"hud/new_ui/bloodbar/bloodbar",10,1,1,0);check_init(entry,"hud/new_ui/bloodbar/bloodbar",15,1,0,0);
   check_native_cycles(15,35);check_native_cycles(10,30);
  }
  if(mask&2)geometry();
 }
 printf("PASS exact HUD %s\n",argv[3]);return 0;
}
