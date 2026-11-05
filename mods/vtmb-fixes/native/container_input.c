/* Original integration source. Behavior continues the owner's installed
   Wesp5/Claude extension. Helpers contain native addresses only, never VTM
   pointers, and published pages remain RX until process exit. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
typedef unsigned char B;
typedef uint32_t U;
typedef struct{B *site,before[5],after[5];unsigned size;DWORD protection;int published,pending;} Patch;
static B *client,*page;static Patch hooks[2];static int state;
static void put(B *p,U n){memcpy(p,&n,4);}
static int protect_again(Patch *p){DWORD ignored;int i;for(i=0;i<2;i++)if(VirtualProtect(p->site,p->size,p->protection,&ignored)){p->pending=0;return 1;}p->pending=1;return 0;}
static int flush(B *at,unsigned size){int i;for(i=0;i<2;i++)if(FlushInstructionCache(GetCurrentProcess(),at,size))return 1;return 0;}
static int restore(Patch *p){
 DWORD old,ignored;int i,ok=1;
 if(!p->published)return !p->pending||protect_again(p);
 if(memcmp(p->site,p->after,p->size)&&memcmp(p->site,p->before,p->size))return 0;
 for(i=0;i<2;i++)if(VirtualProtect(p->site,p->size,PAGE_EXECUTE_READWRITE,&old))break;
 if(i==2)return 0;
 if(memcmp(p->site,p->after,p->size)&&memcmp(p->site,p->before,p->size)){VirtualProtect(p->site,p->size,old,&ignored);return 0;}
 memcpy(p->site,p->before,p->size);if(!flush(p->site,p->size))ok=0;if(!protect_again(p))ok=0;
 if(ok)p->published=0;return ok;
}
static int rollback(void){int i,ok=1;for(i=1;i>=0;i--)if(!restore(hooks+i))ok=0;return ok;}
static int identity(B *b){IMAGE_DOS_HEADER *d=(void *)b;IMAGE_NT_HEADERS32 *n;
 if(!b||d->e_magic!=IMAGE_DOS_SIGNATURE||d->e_lfanew<0||d->e_lfanew>0x1000)return 0;
 n=(void *)(b+d->e_lfanew);return n->Signature==IMAGE_NT_SIGNATURE&&n->FileHeader.Machine==0x14c&&n->OptionalHeader.Magic==0x10b&&n->FileHeader.TimeDateStamp==0x41afaf63&&n->OptionalHeader.SizeOfImage==0x6e9000;
}
static int supported(B *b){
 B expected[]={0x6a,0,0x68,0,0,0,0,0xe8,0xc4,0xfc,0xff,0xff,0x83,0xc4,8,0xc3};
 put(expected+3,(U)(uintptr_t)(b+0x4d2fa4));
 return identity(b)&&*(U *)(b+0x24aa90)==(U)(uintptr_t)(b+0x1b4360)&&
 !memcmp(b+0x1b4360,"\x8b\x44\x24\x04\x56\x83\xf8\x41",8)&&!memcmp(b+0x102150,expected,16)&&
 !memcmp(b+0xf0ed0,"\x53\x56\x8b\x5c\x24\x0c\x57\x8b\xf9",9)&&
 !memcmp(b+0x101e20,"\x8a\x44\x24\x08\x56\x57\x83\xcf",8);
}
static unsigned emit(B *p,unsigned at,B byte){p[at++]=byte;return at;}
static unsigned value(B *p,unsigned at,U n){put(p+at,n);return at+4;}
static unsigned call(B *p,unsigned at,void *to){p[at++]=0xe8;put(p+at,(U)((uintptr_t)to-(uintptr_t)(p+at+4)));return at+4;}
static void helpers(void){
 B key[]={0x8b,0x44,0x24,4,0x83,0xf8,0x40,0x74,0x0c,0x83,0xf8,0x41,0x74,7,0xb8,0,0,0,0,0xff,0xe0,0xc2,4,0};
 B *p=page+64;unsigned n=0,j1,j2,j3,native;
 put(key+15,(U)(uintptr_t)(client+0x1b4360));memcpy(page,key,sizeof(key));
 n=emit(p,n,0x53);n=emit(p,n,0xbb);n=value(p,n,(U)(uintptr_t)client);
 memcpy(p+n,"\x8d\x8b",2);n+=2;n=value(p,n,0x4cfe38);
 n=emit(p,n,0x68);n=value(p,n,(U)(uintptr_t)(client+0x27b3d0));n=call(p,n,client+0xf0ed0);
 memcpy(p+n,"\x85\xc0\x74",3);n+=3;j1=n++;
 memcpy(p+n,"\x80\xb8\xd8\x04\0\0\0\x74",8);n+=8;j2=n++;
 memcpy(p+n,"\x80\xb8\x81\x01\0\0\0\x75",8);n+=8;j3=n++;
 n=emit(p,n,0x5b);n=emit(p,n,0xc3);native=n;
 n=emit(p,n,0x6a);n=emit(p,n,0);n=emit(p,n,0x68);n=value(p,n,(U)(uintptr_t)(client+0x4d2fa4));
 n=call(p,n,client+0x101e20);memcpy(p+n,"\x83\xc4\x08\x5b\xc3",5);
 p[j1]=(B)(native-j1-1);p[j2]=(B)(native-j2-1);p[j3]=(B)(native-j3-1);
}
__declspec(dllexport) void loaded_client(void){
 DWORD old;unsigned i;int published=0;
 if(state)return;client=(B *)GetModuleHandleA("client.dll");if(!client)return;
 if(!supported(client)){state=-1;return;}
 page=VirtualAlloc(NULL,192,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!page){state=-1;return;}
 helpers();if(!FlushInstructionCache(GetCurrentProcess(),page,192)||!VirtualProtect(page,192,PAGE_EXECUTE_READ,&old))goto fail_unpublished;
 memset(hooks,0,sizeof(hooks));hooks[0].site=client+0x24aa90;hooks[0].size=4;put(hooks[0].after,(U)(uintptr_t)page);
 hooks[1].site=client+0x102150;hooks[1].size=5;hooks[1].after[0]=0xe9;
 put(hooks[1].after+1,(U)((uintptr_t)(page+64)-(uintptr_t)(hooks[1].site+5)));
 for(i=0;i<2;i++)memcpy(hooks[i].before,hooks[i].site,hooks[i].size);
 /* Preflight all signatures before the first write; then recheck each owner. */
 if(!supported(client))goto fail_unpublished;
 for(i=0;i<2;i++){
  Patch *p=hooks+i;
  if(memcmp(p->site,p->before,p->size)||!VirtualProtect(p->site,p->size,PAGE_EXECUTE_READWRITE,&p->protection))goto fail;
  p->pending=1;
  if(memcmp(p->site,p->before,p->size)){protect_again(p);goto fail;}
  memcpy(p->site,p->after,p->size);p->published=1;published=1;
  if(!FlushInstructionCache(GetCurrentProcess(),p->site,p->size)||!protect_again(p))goto fail;
 }
 state=1;return;
fail:
 state=rollback()?-1:-2;if(published)return;
fail_unpublished:
 VirtualFree(page,0,MEM_RELEASE);page=NULL;if(!state)state=-1;
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID reserved){
 (void)h;if(reason==DLL_PROCESS_DETACH&&!reserved&&client&&(B *)GetModuleHandleA("client.dll")==client)rollback();
 return TRUE;
}
