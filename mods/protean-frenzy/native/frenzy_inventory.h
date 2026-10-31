/* Own the inventory policy here, shared by the exact component fixtures. */
#include "frenzy_inventory_catalog.h"
static int frenzy_inventory_scope(B *actor,B *item){
    const char *name,*candidate;B *shadow,*table,*owner;unsigned h,j;
    if(!actor||!item)return 0;
    name=*(const char **)(item+0x11c);if(!name)return 0;
    for(candidate=frenzy_inventory_catalog;*candidate;candidate+=strlen(candidate)+1)
        if(!strcmp(candidate,name))break;
    if(!*candidate||(unsigned)handle_of(item)==0xffffffffu)return 0;
    if(isclass(actor,"player")){
        shadow=resolve(u(actor,0x1db0));
        return (unsigned)handle_of(actor)!=0xffffffffu&&isclass(shadow,"npc_VFrenzyShadow");
    }
    if(!isclass(actor,"npc_VFrenzyShadow"))return 0;
    h=handle_of(actor);if(h==0xffffffffu)return 0;
    table=*(B **)(module+0x566458);if(!table)return 0;
    for(j=0;j<8192;++j){
        owner=*(B **)(table+j*12+4);
        if(isclass(owner,"player")&&u(owner,0x1db0)==h)return 1;
    }
    return 0;
}
static int frenzy_inventory_registered(B *actor,B *item){
    unsigned h=handle_of(item),owner=handle_of(actor),slot=u(item,0x73c);
    return h!=0xffffffffu&&owner!=0xffffffffu&&slot<224&&u(item,0x88c)==owner&&
        u(actor,0x1624+slot*4)==h;
}
