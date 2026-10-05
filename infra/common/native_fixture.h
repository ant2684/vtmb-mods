#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static inline void check(int ok,const char *label){if(!ok){fprintf(stderr,"FAIL %s\n",label);ExitProcess(1);}}
static inline void put(void *at,uint32_t v){memcpy(at,&v,4);}
static inline uint8_t *map_image(const char *path){FILE *f=fopen(path,"rb");long n;uint8_t *raw,*image;IMAGE_NT_HEADERS32 *nt;IMAGE_SECTION_HEADER *s;unsigned i;uint32_t delta;
 check(f!=NULL,"open supported native fixture");fseek(f,0,SEEK_END);n=ftell(f);rewind(f);raw=malloc(n);check(fread(raw,1,n,f)==(size_t)n,"read fixture");fclose(f);
 nt=(void *)(raw+((IMAGE_DOS_HEADER *)raw)->e_lfanew);image=VirtualAlloc(NULL,nt->OptionalHeader.SizeOfImage,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);check(image!=NULL,"map fixture");memcpy(image,raw,nt->OptionalHeader.SizeOfHeaders);s=IMAGE_FIRST_SECTION(nt);
 for(i=0;i<nt->FileHeader.NumberOfSections;i++)memcpy(image+s[i].VirtualAddress,raw+s[i].PointerToRawData,s[i].SizeOfRawData);
 delta=(uint32_t)(uintptr_t)image-nt->OptionalHeader.ImageBase;
 if(delta){IMAGE_DATA_DIRECTORY d=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC];uint8_t *p=image+d.VirtualAddress,*end=p+d.Size;
  while(p<end){IMAGE_BASE_RELOCATION *b=(void *)p;uint16_t *r=(void *)(p+8);unsigned j;check(b->SizeOfBlock>=8,"relocation block");for(j=0;j<(b->SizeOfBlock-8)/2;j++){unsigned type=r[j]>>12;if(type==3)*(uint32_t *)(image+b->VirtualAddress+(r[j]&4095))+=delta;else check(type==0,"supported relocation type");}p+=b->SizeOfBlock;}
 }free(raw);return image;
}
static inline void imports(HMODULE h,const char *name,void *replacement){IMAGE_NT_HEADERS32 *nt=(void *)((uint8_t *)h+((IMAGE_DOS_HEADER *)h)->e_lfanew);IMAGE_IMPORT_DESCRIPTOR *d=(void *)((uint8_t *)h+nt->OptionalHeader.DataDirectory[1].VirtualAddress);
 for(;d->Name;d++){IMAGE_THUNK_DATA32 *names=(void *)((uint8_t *)h+d->OriginalFirstThunk),*iat=(void *)((uint8_t *)h+d->FirstThunk);for(;names->u1.AddressOfData;names++,iat++)if(!(names->u1.Ordinal&IMAGE_ORDINAL_FLAG32)){IMAGE_IMPORT_BY_NAME *n=(void *)((uint8_t *)h+names->u1.AddressOfData);if(!strcmp((char *)n->Name,name)){DWORD old,ignored;VirtualProtect(&iat->u1.Function,4,PAGE_READWRITE,&old);iat->u1.Function=(DWORD)(uintptr_t)replacement;VirtualProtect(&iat->u1.Function,4,old,&ignored);return;}}}check(0,"mock import exists");
}
static inline void jump(uint8_t *at,void *to){at[0]=0xe9;put(at+1,(uint32_t)(uintptr_t)to-(uint32_t)(uintptr_t)(at+5));FlushInstructionCache(GetCurrentProcess(),at,5);}
static inline uint8_t *destination(uint8_t *at){check(at[0]==0xe9,"installed jump");return at+5+*(int32_t *)(at+1);}
