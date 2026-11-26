#include <string.h>
#include "runtime.h"

#define TC __attribute__((thiscall))
#define FC __attribute__((fastcall))
typedef unsigned char B;
typedef void (TC *InputFn)(B *);
typedef void (__cdecl *CommandFn)(void);

static B *client;
static InputFn stock_weapon_camera;
static int installed,manual_depth;
static struct {
    B *actor, *player, *input, *event_weapon;
    unsigned player_handle, event_handle, wanted_weapon;
    float deadline;
    int desired_third, returning, human, expired;
} camera;

static B *local_player(void){return *(B **)(client+0x4a0d50);}
static B *camera_input(void){return *(B **)(client+0x27ba58);}
static unsigned read_u(const B *p,unsigned offset){return *(const unsigned *)(p+offset);}
static unsigned entity_handle(B *p){
    const unsigned *h=((const unsigned *(TC *)(B *))(*(void ***)p)[1])(p);
    return h?*h:0xffffffffu;
}
static int same_client(B *input){
    B *p=local_player();
    return p&&p==camera.player&&input&&input==camera.input&&entity_handle(p)==camera.player_handle;
}
static int other_camera(B *p,B *input){
    return input[0xf9]||input[0x1b8]||read_u(p,0x16e0)||read_u(p,0x15e8);
}
static B *selected_weapon(B *p){
    return ((B *(TC *)(B *))(*(void ***)p)[0x250/4])(p);
}
static int weapon_auto_enabled(void){
    B *cv=*(B **)(client+0x49d914);
    return cv&&!((unsigned char (TC *)(B *))(*(void ***)cv)[1])(cv)&&read_u(cv,0x2c);
}

void pfi_morph_camera_reset(void){
    if(camera.actor&&same_client(camera_input()))camera.input[0xf0]=(B)camera.desired_third;
    memset(&camera,0,sizeof(camera));
}

void pfi_morph_camera_scene(B *actor,int entering){
    /* The loader can notify before the client has constructed its ConCommands. */
    if(!installed)pfi_morph_camera_client();
    if(!installed)return;
    B *p=local_player(),*input=camera_input();
    if(!p||!input||other_camera(p,input))return;
    if(camera.actor&&(!same_client(input)||actor!=camera.actor))pfi_morph_camera_reset();
    if(!camera.actor){
        unsigned h=entity_handle(p);
        if(h==0xffffffffu)return;
        camera.actor=actor;camera.player=p;camera.input=input;camera.player_handle=h;
        camera.desired_third=input[0xf0]!=0;
    }
    camera.human=0;camera.returning=!entering;camera.event_weapon=NULL;
    ((InputFn)(client+0xff7c0))(input);
}

int pfi_morph_camera_owns(B *actor){return camera.actor==actor;}

void pfi_morph_camera_update(B *actor,int returning,int human,unsigned weapon,float now){
    if(camera.actor!=actor)return;
    if(!same_client(camera_input())){pfi_morph_camera_reset();return;}
    if(returning&&!camera.returning){camera.returning=1;camera.event_weapon=NULL;}
    if(human&&(!camera.human||camera.wanted_weapon!=weapon)){
        camera.wanted_weapon=weapon;
        /* Safety bound for a weapon whose draw notification never arrives. */
        camera.deadline=now+1.5f;
    }
    camera.expired=human&&now>=camera.deadline;
    camera.human=human;
}

static void FC weapon_camera(B *weapon,void *unused){
    (void)unused;
    B *input=camera.actor?camera_input():NULL;
    int owned=!manual_depth&&weapon&&same_client(input)&&!other_camera(camera.player,input)&&
        ((B *(TC *)(B *))(client+0x7bab0))(weapon)==camera.player;
    stock_weapon_camera(weapon);
    if(owned){
        if(camera.returning){
            camera.event_weapon=weapon;camera.event_handle=entity_handle(weapon);
        }
        input[0xf0]=1;
    }
}

static void FC camera_frame(B *input,void *unused){
    (void)unused;
    if(camera.actor){
        if(!same_client(input)||other_camera(camera.player,input))pfi_morph_camera_reset();
        else if(camera.human){
            B *weapon=selected_weapon(camera.player);
            int observed=weapon&&weapon==camera.event_weapon&&camera.event_handle!=0xffffffffu&&
                (camera.event_handle&8191u)==(camera.wanted_weapon&8191u)&&
                entity_handle(weapon)==camera.event_handle;
            if(camera.wanted_weapon==0xffffffffu||!weapon_auto_enabled()||observed||camera.expired)pfi_morph_camera_reset();
            else input[0xf0]=1;
        }else input[0xf0]=1;
    }
    ((InputFn)(client+0xfc170))(input);
}

static const unsigned commands[]={0x4d2540,0x4d2568,0x4d183c};
static const unsigned command_entries[]={0xfbd70,0xfbd80,0xfbd90};

static void camera_command(unsigned which){
    B *input=camera.actor?camera_input():NULL;
    if(!same_client(input)){
        ((CommandFn)(client+command_entries[which]))();return;
    }
    /* Toggle should run from the user's stored view, not the temporary one. */
    input[0xf0]=(B)camera.desired_third;
    ++manual_depth;
    ((CommandFn)(client+command_entries[which]))();
    --manual_depth;
    camera.desired_third=which==0||(which==2&&!camera.desired_third);
    input[0xf0]=1;
}
static void __cdecl third_command(void){camera_command(0);}
static void __cdecl first_command(void){camera_command(1);}
static void __cdecl toggle_command(void){camera_command(2);}

void pfi_morph_camera_client(void){
    B *m=(B *)GetModuleHandleA("client.dll");
    if(!m||installed)return;
    IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER *)m;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<=0||dos->e_lfanew>0x1000)return;
    IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32 *)(m+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_I386||
       nt->FileHeader.TimeDateStamp!=0x41afaf63||nt->OptionalHeader.SizeOfImage!=0x6e9000||
       memcmp(m+0x9c250,"\x56\xe8\x0a\xef\xfd\xff\x8b\xb0\x40\x24\x00\x00",12)||
       memcmp(m+0xff1ce,"\xe8\x9d\xcf\xff\xff",5)||
       memcmp(m+0xfc170,"\x83\xec\x30\x56\x8b\xf1",6)||
       memcmp(m+0xff7c0,"\xc6\x81\xf0\x00\x00\x00\x01",7)||
       memcmp(m+0x7bab0,"\x8b\x81\x10\x09\x00\x00\x83\xf8\xff\x74\x23",11))return;
    for(unsigned i=0;i<3;++i)
        if(*(B **)(m+commands[i]+0x1c)!=m+command_entries[i])return;

    B *code=VirtualAlloc(NULL,0x1000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!code)return;
    code[0]=0x56;code[1]=0xe8;
    *(uintptr_t *)(code+2)=(uintptr_t)(m+0x7b160)-(uintptr_t)(code+6);
    code[6]=0xe9;*(uintptr_t *)(code+7)=(uintptr_t)(m+0x9c256)-(uintptr_t)(code+11);
    if(!pfi_code_ready(code,0x1000)){VirtualFree(code,0,MEM_RELEASE);return;}

    PfiPatch batch[5];
    pfi_jump(batch,m+0x9c250,6,weapon_camera);
    pfi_jump(batch+1,m+0xff1ce,5,camera_frame);batch[1].after[0]=0xe8;
    CommandFn replacements[]={third_command,first_command,toggle_command};
    for(unsigned i=0;i<3;++i){
        PfiPatch *patch=batch+2+i;
        patch->site=m+commands[i]+0x1c;patch->size=sizeof(CommandFn);
        CommandFn original=(CommandFn)(m+command_entries[i]);
        memcpy(patch->before,&original,patch->size);
        memcpy(patch->after,replacements+i,patch->size);
    }
    client=m;stock_weapon_camera=(InputFn)code;
    int committed=pfi_commit(batch,5);
    if(committed==1)installed=1;
    else if(!committed)VirtualFree(code,0,MEM_RELEASE);
}
