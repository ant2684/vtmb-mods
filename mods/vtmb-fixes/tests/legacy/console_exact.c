#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef void (__cdecl *ShowFn)(void);
typedef int (__thiscall *CommandFn)(void *,const char *);
typedef void (__thiscall *VisibleFn)(void *,int);
typedef void (__thiscall *HideFn)(void *,int);
static uint8_t *engine,*ui;static HMODULE plugin;
static ShowFn show;static CommandFn command;static VisibleFn visible;static HideFn hide;
static int protection_calls,fail_at;
static int dlg_visible,menu_visible,queued_set,queued_un,mouse_enabled,helper_calls;
static uint8_t dlg[0x110],obj[12],menu[16];static void *vt[0x60],*client_vt[0x80];
static void check(int ok,const char *label){if(!ok){fprintf(stderr,"FAIL %s\n",label);ExitProcess(1);}}
static void put(void *at,uint32_t value){memcpy(at,&value,4);}
static uint32_t word(uint32_t rva){return *(uint32_t *)(engine+rva);}
static HMODULE WINAPI module_api(LPCSTR name){if(!strcmp(name,"engine.dll"))return (HMODULE)engine;if(!strcmp(name,"GameUI.dll"))return (HMODULE)ui;return NULL;}
static BOOL WINAPI protect_api(LPVOID at,SIZE_T n,DWORD p,PDWORD old){protection_calls++;if(protection_calls==fail_at)return FALSE;return VirtualProtect(at,n,p,old);}
static void imports(HMODULE h,const char *name,void *replacement){
 IMAGE_NT_HEADERS32 *nt=(void *)((uint8_t *)h+((IMAGE_DOS_HEADER *)h)->e_lfanew);
 IMAGE_IMPORT_DESCRIPTOR *d=(void *)((uint8_t *)h+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
 for(;d->Name;d++){
  IMAGE_THUNK_DATA32 *names=(void *)((uint8_t *)h+d->OriginalFirstThunk),*iat=(void *)((uint8_t *)h+d->FirstThunk);
  for(;names->u1.AddressOfData;names++,iat++)if(!(names->u1.Ordinal&IMAGE_ORDINAL_FLAG32)){
   IMAGE_IMPORT_BY_NAME *n=(void *)((uint8_t *)h+names->u1.AddressOfData);
   if(!strcmp((char *)n->Name,name)){DWORD old,ignored;VirtualProtect(&iat->u1.Function,4,PAGE_READWRITE,&old);iat->u1.Function=(DWORD)(uintptr_t)replacement;VirtualProtect(&iat->u1.Function,4,old,&ignored);return;}
  }
 }check(0,"mock import found");
}
static void image(uint8_t *p,size_t size){IMAGE_DOS_HEADER *d=(void *)p;IMAGE_NT_HEADERS32 *n=(void *)(p+0x80);IMAGE_SECTION_HEADER *s;
 memset(p,0,size);d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x80;n->Signature=IMAGE_NT_SIGNATURE;n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;
 n->FileHeader.SizeOfOptionalHeader=sizeof(n->OptionalHeader);n->FileHeader.NumberOfSections=1;n->OptionalHeader.SizeOfImage=(DWORD)size;s=IMAGE_FIRST_SECTION(n);s->VirtualAddress=0x1000;s->Misc.VirtualSize=(DWORD)size-0x1000;s->Characteristics=IMAGE_SCN_MEM_EXECUTE;
}
static void fixtures(void){
 image(engine,0x1400000);image(ui,0x80000);protection_calls=0;
 memcpy(engine+0x10dc10,"\x8b\x0d\0\0\0\0\x85\xc9\x0f\x84\x85\0\0\0\x8b\x01\xff\x50\x0c",19);put(engine+0x10dc12,(uint32_t)(uintptr_t)(engine+0x13064a4));
 memcpy(engine+0x10d650,"\x8b\x0d\0\0\0\0\x85\xc9\x0f\x84\x83\0\0\0\x8b\x54\x24\x04",18);put(engine+0x10d652,(uint32_t)(uintptr_t)(engine+0x13064a4));
 memcpy(engine+0x1a570,"\x8b\x44\x24\x04\x50\xe8\xe6\x1c\0\0\x83\xc4\x04\xc2\x04\0",16);
 memcpy(ui+0x22070,"\x8b\x44\x24\x04\x56\x50\x8b\xf1\xe8\x03\xac\xff\xff",13);
 memcpy(ui+0x59d0,"\x56\x8b\xf1\x8b\x0d\0\0\0\0\x8b\x01\xff\x90\xa8\x01\0\0",17);put(ui+0x59d5,(uint32_t)(uintptr_t)(ui+0x6c330));
    memcpy(ui+0x220e0,"\x8b\x89\xb4\0\0\0\x8b\x54\x24\x04\x89\x54\x24\x04\x8b\x01\xff\x60\x54",19);
    memcpy(ui+0x21e30,"\x53\x56\x8b\xf1\x57\x8b\x86\xcc\0\0\0\x85\xc0\x0f\x85\x37\x01\0\0",19);
    memcpy(ui+0x21ee7,"\x8b\x8e\xcc\0\0\0\x6a\0\x68\0\0\0\0\x8b\x11\xff\x92\x98\0\0\0\x8b\xf8\x85\xff\x74\x16\x8b\x8e\xb4\0\0\0\x8b\x1f\x8b\x01\xff\x50\x58\x50\x8b\xcf\xff\x93\xb8\0\0\0",49);
    put(ui+0x21ef0,(uint32_t)(uintptr_t)(ui+0x66b0c));
}
static void *target(uint8_t *site){return site+5+*(int32_t *)(site+1);}
static void jump(uint8_t *at,void *destination){DWORD old,ignored;VirtualProtect(at,16,PAGE_EXECUTE_READWRITE,&old);at[0]=0xe9;put(at+1,(uint32_t)(uintptr_t)destination-(uint32_t)(uintptr_t)(at+5));FlushInstructionCache(GetCurrentProcess(),at,5);VirtualProtect(at,16,old,&ignored);}
static uint8_t *trampoline(void *handler,uint8_t *old,size_t length){
 IMAGE_NT_HEADERS32 *nt=(void *)((uint8_t *)plugin+((IMAGE_DOS_HEADER *)plugin)->e_lfanew);
 uint8_t *base=(uint8_t *)plugin;unsigned r;void *found=NULL;(void)handler;
 for(r=0;r+4<nt->OptionalHeader.SizeOfImage;r+=4){uint8_t *p=*(uint8_t **)(base+r);MEMORY_BASIC_INFORMATION m;
  if(VirtualQuery(p,&m,sizeof(m)) && m.State==MEM_COMMIT && m.Type==MEM_PRIVATE && !(m.Protect&(PAGE_NOACCESS|PAGE_GUARD)) && m.Protect==PAGE_EXECUTE_READ && !memcmp(p,old,length) && p[length]==0xe9){check(!found||found==p,"unique trampoline pointer");found=p;}
 }check(found!=NULL,"installed trampoline discovered");return found;
}
static uint8_t min_button[16],title_menu[16],min_item[16];
static void *button_vt[0x60],*title_vt[0x60],*item_vt[0x60];
static int min_visible,min_enabled,min_calls,find_calls,item_present=1,other_enabled=1;
static void __thiscall button_visible(void *self,int value){check(self==min_button && value==0,"minimize native ECX/argument");min_visible=value;min_calls++;}
static void *__thiscall find_item(void *self,const char *name,int recurse){check(self==title_menu && !strcmp(name,"Minimize") && !recurse,"cached menu lookup ABI/scope");find_calls++;return item_present?min_item:NULL;}
static void __thiscall item_enabled(void *self,int value){check(self==min_item && value==0,"only Minimize disabled");min_enabled=value;}
static void minimize_fixture(void){
 button_vt[0x54/4]=button_visible;title_vt[0x98/4]=find_item;item_vt[0xb8/4]=item_enabled;
 put(min_button,(uint32_t)(uintptr_t)button_vt);put(title_menu,(uint32_t)(uintptr_t)title_vt);put(min_item,(uint32_t)(uintptr_t)item_vt);
 put(dlg+0xb4,(uint32_t)(uintptr_t)min_button);put(dlg+0xcc,0);min_visible=min_enabled=other_enabled=item_present=1;min_calls=find_calls=0;
}
static const char *__thiscall level(void *self){check(self==obj,"level ECX");return "fixture_map";}
static unsigned char __thiscall is_visible(void *self){return self==dlg?(unsigned char)dlg_visible:(unsigned char)menu_visible;}
static int __thiscall original_command(void *self,const char *text){check(self==obj,"command ECX");if(!strcmp(text,"setpause"))queued_set++;if(!strcmp(text,"unpause"))queued_un++;return 0x12345678;}
static void __thiscall original_visible(void *self,int value){check(self==dlg||self==menu,"panel ECX");if(self==dlg)dlg_visible=value;else menu_visible=value;}
static void __thiscall original_hide(void *self,int resume){check(self==obj,"hide ECX");visible(dlg,0);if(resume)command(obj,"unpause");}
static void __cdecl original_show(void){command(obj,"setpause");visible(menu,0);visible(dlg,1);mouse_enabled=0;min_visible=1;}
static int __thiscall activate(void *self){check(self==obj,"menu ECX");check(command(obj,"setpause")==1,"menu suppresses new pause");menu_visible=1;return 1;}
static void __cdecl engine_hide(int resume){check(!resume,"helper argument");helper_calls++;hide(obj,resume);mouse_enabled=1;}
static void drain(void){while(queued_set>0){queued_set--;put(engine+0xb4378c,word(0xb4378c)+1);put(engine+0x12b0758,1);}while(queued_un>0){uint32_t d=word(0xb4378c);queued_un--;if(d)put(engine+0xb4378c,--d);if(!d)put(engine+0x12b0758,0);}}
static uint32_t sites[]={0x10dc10,0x1a570,0x22070,0x59d0};static size_t lengths[]={6,5,5,9};
static uint8_t *site(unsigned i){return (i<2?engine:ui)+sites[i];}
static void open_plugin(const char *path){plugin=LoadLibraryA(path);check(plugin!=NULL,"load exact DLL");imports(plugin,"GetModuleHandleA",module_api);imports(plugin,"VirtualProtect",protect_api);}
static __declspec(noinline) void show_abi(void) {
 uint32_t before,after;
 register uint32_t bx __asm__("ebx")=0x11223344;
 register uint32_t si __asm__("esi")=0x55667788;
 register uint32_t di __asm__("edi")=0x99aabbcc;
 ShowFn volatile fn=show;
 __asm__ volatile("" : "+r"(bx),"+r"(si),"+r"(di));
 __asm__ volatile("movl %%esp,%0" : "=m"(before));
 fn();
 __asm__ volatile("movl %%esp,%0" : "=m"(after));
 __asm__ volatile("" : "+r"(bx),"+r"(si),"+r"(di));
 check(before==after,"exact show/minimize helper ESP restored");
 check(bx==0x11223344 && si==0x55667788 && di==0x99aabbcc,"exact show/minimize callee-saved registers");
}
static void logic(const char *path){uint8_t old[4][16];void *native[]={original_show,original_command,original_visible,original_hide};unsigned i;
 fixtures();fail_at=0;open_plugin(path);for(i=0;i<4;i++)memcpy(old[i],site(i),lengths[i]);((ShowFn)GetProcAddress(plugin,"loaded_gameui"))();
 for(i=0;i<4;i++){check(site(i)[0]==0xe9,"installed four detours");jump(trampoline(target(site(i)),old[i],lengths[i]),native[i]);}
 show=(ShowFn)target(site(0));command=(CommandFn)target(site(1));visible=(VisibleFn)target(site(2));hide=(HideFn)target(site(3));jump(engine+0x10d650,engine_hide);
 vt[0x58/4]=is_visible;put(dlg,(uint32_t)(uintptr_t)vt);put(menu,(uint32_t)(uintptr_t)vt);put(obj+4,1);put(obj+8,(uint32_t)(uintptr_t)dlg);put(engine+0x13064a8,(uint32_t)(uintptr_t)obj);put(ui+0x6c330,(uint32_t)(uintptr_t)obj);put(ui+0x6c338,(uint32_t)(uintptr_t)menu);
 client_vt[0x1a8/4]=level;client_vt[3]=activate;put(obj,(uint32_t)(uintptr_t)client_vt);put(engine+0x13064a4,(uint32_t)(uintptr_t)obj);
 dlg_visible=menu_visible=queued_set=queued_un=helper_calls=0;mouse_enabled=1;minimize_fixture();
 show_abi();check(!min_visible && min_calls==1 && !find_calls,"exact native minimize hide");
 put(dlg+0xcc,(uint32_t)(uintptr_t)title_menu);show_abi();check(!min_visible && !min_enabled && find_calls==1 && other_enabled,"exact cached menu scoped disable");
 min_visible=min_enabled=1;show();check(!min_visible && !min_enabled && find_calls==2,"exact repeated opening");
 item_present=0;show();check(find_calls==3 && other_enabled,"exact missing menu item safe");put(dlg+0xcc,0);item_present=1;
 visible(dlg,0);drain();helper_calls=0;
 show();drain();check(word(0xb4378c)==1,"own pause");visible(dlg,0);drain();check(!word(0xb4378c)&&!word(0x12b0758)&&mouse_enabled&&helper_calls==1,"close resumes once");visible(dlg,0);check(helper_calls==1,"duplicate hide");
 show();visible(dlg,0);drain();check(!word(0xb4378c)&&!word(0x12b0758),"same-frame queue order");
 put(engine+0x12b0758,1);show();visible(dlg,0);drain();check(word(0x12b0758)==1&&!word(0xb4378c),"ordinary pause remains");put(engine+0x12b0758,0);
 put(engine+0xb4378c,1);put(engine+0x12b0758,1);menu_visible=1;show();drain();visible(dlg,0);drain();check(menu_visible&&word(0xb4378c)==1,"menu restored");menu_visible=0;put(engine+0xb4378c,0);put(engine+0x12b0758,0);
 show();drain();put(engine+0xb43788,1);visible(dlg,0);drain();check(!word(0xb4378c)&&word(0xb43788)==1&&word(0x12b0758)==1,"script ownership remains");put(engine+0xb43788,0);put(engine+0x12b0758,0);
 *(double *)(engine+0x314890)=10;show();drain();*(double *)(engine+0x314890)=0;helper_calls=0;visible(dlg,0);check(!helper_calls&&!queued_un,"reload refuses stale context");
 FreeLibrary(plugin);
}
int main(int argc,char **argv){unsigned i,j;uint8_t old[4][16];check(argc==2,"DLL argument");engine=VirtualAlloc(NULL,0x1400000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);ui=VirtualAlloc(NULL,0x80000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);check(engine&&ui,"fixture allocation");
 for(i=1;i<=12;i++){fixtures();fail_at=(int)i;for(j=0;j<4;j++)memcpy(old[j],site(j),lengths[j]);open_plugin(argv[1]);((ShowFn)GetProcAddress(plugin,"loaded_gameui"))();for(j=0;j<4;j++)check(!memcmp(old[j],site(j),lengths[j]),"exact failure rollback");FreeLibrary(plugin);}
 fixtures();fail_at=0;ui[0x59d0]=0xcc;open_plugin(argv[1]);((ShowFn)GetProcAddress(plugin,"loaded_gameui"))();check(protection_calls==0,"occupied hook refuses before writing");FreeLibrary(plugin);
 for(i=0;i<3;i++){
  static const uint32_t anchors[]={0x220e0,0x21e30,0x21ee7};static const unsigned sizes[]={19,19,49};
  for(j=0;j<2;j++){unsigned k;fixtures();for(k=0;k<4;k++)memcpy(old[k],site(k),lengths[k]);
   if(j)memcpy(ui+0x30000,ui+anchors[i],sizes[i]);else ui[anchors[i]]=0xcc;
   open_plugin(argv[1]);((ShowFn)GetProcAddress(plugin,"loaded_gameui"))();check(protection_calls==0,"exact new anchor refusal before writes");
   for(k=0;k<4;k++)check(!memcmp(old[k],site(k),lengths[k]),"exact refused install unchanged");FreeLibrary(plugin);
  }
 }
 logic(argv[1]);puts("PASS exact delivered DLL ownership/menu/script/context/ABI and12 installation failures");return 0;
}
