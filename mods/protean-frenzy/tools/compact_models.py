"""Lossless, rooted v2531 repack; no appended donor models or orphan clips."""
from pathlib import Path
import struct, sys, hashlib, json

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'_support'))
from mdl import i, f, cs, put, seqs, anims, bones, samples

BASES = {'male': '3afe70db551c93aedbfe9ff39609596fe47d299229ed528805fec566e16b131e',
         'female': '57c4304507dc8bd433c51206c5996055ad06aba509d95b9867cbcd4beff054a8'}
def sha(d): return hashlib.sha256(d).hexdigest()
def text(d, q, k): return cs(d, q+i(d,q+k)) if i(d,q+k)>0 else None
def activity(d,q): return cs(d,q+i(d,q+4)) if i(d,q+4) else ''
def cells(d,q): return struct.unpack_from('<256h',d,q+56)
def rooted(d):
    ss=seqs(d)
    keep={n for n,q in ss.items() if activity(d,q) and i(d,q+16)>0}
    pending=list(keep)
    while pending:
        n=pending.pop();q=ss[n]
        assert i(d,q+568)==0 and i(d,q+668)==0, (n,'unsupported blend/weight data')
        targets=[text(d,q,k) for k in [744,748]]
        if i(d,q+660):
            p=q+i(d,q+664)
            targets += [list(ss)[i(d,p+j*4)] for j in range(i(d,q+660))]
        # nextseq (652) is an index used for automatic transitions, zero=none.
        if i(d,q+652): targets.append(list(ss)[i(d,q+652)])
        for t in targets:
            if t:
                assert t in ss,(n,t)
                if t not in keep:keep.add(t);pending.append(t)
    return [n for n in ss if n in keep]

def rle(d,p,frames):
    start=p;done=0
    while done<frames:
        valid,total=d[p:p+2];assert 0<valid<=total
        done+=total;p+=2+2*valid
    return d[start:p]

class Packer:
    def __init__(self,d):
        self.d=d;self.out=bytearray(d[:424]);self.strings={};self.blocks={}
    def alloc(self,data,alignment=4):
        self.out.extend(bytes((-len(self.out))%alignment));p=len(self.out);self.out.extend(data);return p
    def string(self,s,minimum=-1):
        if s not in self.strings or self.strings[s]<=minimum:self.strings[s]=self.alloc(s.encode('ascii')+b'\0',1)
        return self.strings[s]
    def st(self,new,field,old,source=None):
        source=self.d if source is None else source
        value=i(source,old+field)
        put(self.out,new+field,self.string(cs(source,old+value),new)-new if value else 0)
    def block(self,p,size):
        if not size:return 0
        key=(p,size)
        if key not in self.blocks:self.blocks[key]=self.alloc(self.d[p:p+size])
        return self.blocks[key]
    def relative_array(self,new,old,field,count,size):
        assert count>=0
        p=self.block(old+i(self.d,old+field),count*size) if count else 0
        put(self.out,new+field,p-new if count else 0)
        return p

def pack(d,sex):
    assert sha(d)==BASES[sex]
    ss=seqs(d);aa=anims(d);oldraw=list(aa);keep=rooted(d)
    rawused={oldraw[j] for n in keep for j in cells(d,ss[n]) if j>=0}
    names=[n for n in aa if n in rawused];rawids={n:j for j,n in enumerate(names)}
    ids={n:j for j,n in enumerate(keep)}
    p=Packer(d);o=p.out
    # Preserve the complete bone/hitbox/attachment numeric prefix. Re-intern
    # strings, since originals live after the old geometry and sequence tables.
    assert i(d,244)==424 and i(d,240)==55 and i(d,248)==0
    assert i(d,332)==9224 and i(d,328)==1 and i(d,260)==9284 and i(d,256)==1
    assert i(d,9288)==18 and i(d,9292)==12
    o.extend(d[424:9872])
    for j in range(55):
        q=424+160*j;assert i(d,q+140)==i(d,q+144)==0
        p.st(q,0,q);p.st(q,152,q)
    p.st(9224,0,9224);p.st(9284,0,9284)
    put(o,252,0)  # empty controller table
    # Copy the contiguous stock group/body/model/pose/mesh/vertex/tangent block.
    # All internal numeric offsets are retained, external strings re-interned.
    start,end=i(d,288),i(d,296)
    assert i(d,284)==i(d,292)==i(d,300)==i(d,308)==i(d,312)==i(d,320)==1
    assert i(d,336)==i(d,344)==i(d,352)==i(d,360)==i(d,368)==i(d,376)==0
    geom=p.alloc(d[start:end]);delta=geom-start
    for field in [288,324,388]:put(o,field,i(d,field)+delta)
    for field in [340,348,356,364,372,380,400,408]:put(o,field,0)
    group=geom
    assert end-start<80000 and i(d,start+8)==i(d,start+12)==0
    for field in [0,4]:p.st(group,field,start)
    body=i(d,324);newbody=body+delta;p.st(newbody,0,body)
    assert i(d,body+4)==1
    model=body+i(d,body+12)
    assert i(d,model+136)==1 and i(d,model+156)==0
    for count,off in [(192,196),(200,204),(208,212),(216,220)]:
        assert i(d,model+count)==0;put(o,model+delta+off,0)
    assert i(d,384)==2
    for j in range(2):q=i(d,388)+20*j;p.st(q+delta,0,q)
    # Texture (20 bytes), absolute texture search-path pointers and skin table.
    oldtex=i(d,296);tex=p.block(oldtex,20);put(o,296,tex);p.st(tex,0,oldtex)
    # Texture suffix includes a nonzero material scalar; retain it verbatim.
    paths=p.alloc(bytes(4));put(o,304,paths)
    put(o,paths,p.string(cs(d,i(d,i(d,304)))))
    skins=p.block(i(d,316),2);put(o,316,skins)
    put(o,392,p.string(cs(d,i(d,392))))
    assert i(d,396)==i(d,404)==0
    # Copy exact compressed channels. Do not requantize poses/scales. Streams
    # must follow each raw track table: native decoders ignore negative offsets.
    table=p.alloc(bytes(72*len(names)));put(o,264,len(names));put(o,268,table)
    for index,n in enumerate(names):
        q=aa[n];z=table+72*index;o[z:z+72]=d[q:q+72];p.st(z,0,q)
        p.relative_array(z,q,20,i(d,q+16),44)
        assert i(d,q+52)==0;put(o,z+56,0)
        oldtracks=q+i(d,q+48);tracks=p.alloc(d[oldtracks:oldtracks+55*32]);put(o,z+48,tracks-z)
        cache={}
        for j in range(55):
            b=oldtracks+32*j;t=tracks+32*j
            for c in range(7):
                off=i(d,b+4+c*4)
                if off>0:
                    source=b+off
                    if source not in cache:cache[source]=p.alloc(rle(d,source,i(d,q+12)),2)
                    assert cache[source]>t
                    put(o,t+4+c*4,cache[source]-t)
                else:put(o,t+4+c*4,0)
    # Copy only selected sequence descriptors, with every grid and metadata
    # pointer rebuilt. Native event payloads are fixed 76-byte records.
    table=p.alloc(bytes(764*len(keep)));put(o,272,len(keep));put(o,276,table)
    tracecache={}
    for index,n in enumerate(keep):
        q=ss[n];z=table+764*index;o[z:z+764]=d[q:q+764]
        p.st(z,0,q);p.st(z,4,q)
        for j,v in enumerate(cells(d,q)):
            struct.pack_into('<h',o,z+56+2*j,rawids[oldraw[v]] if v>=0 else v)
        p.relative_array(z,q,24,i(d,q+20),76)
        p.relative_array(z,q,704,i(d,q+700),24)
        count=i(d,q+708);old=q+i(d,q+712)
        if count:
            key=(old,count)
            if key not in tracecache:
                new=p.block(old,count*188);tracecache[key]=new
                for j in range(count):
                    for k in [120,136,152,168]:
                        src=old+188*j;dst=new+188*j;value=i(d,src+k)
                        assert value>=0,(n,j,k,value)
                        put(o,dst+k,p.string(cs(d,src+value),dst)-dst if value else 0)
            put(o,z+712,tracecache[key]-z)
        else:put(o,z+712,0)
        count=i(d,q+660)
        if count:
            a=p.relative_array(z,q,664,count,4);before=q+i(d,q+664)
            for j in range(count):put(o,a+j*4,ids[list(ss)[i(d,before+j*4)]])
        else:put(o,z+664,0)
        assert i(d,q+568)==i(d,q+668)==0
        for k in [740,744,748]:
            value=text(d,q,k);put(o,z+k,p.string(value,z)-z if value else -1)
        if i(d,q+652):put(o,z+652,ids[list(ss)[i(d,q+652)]])
    put(o,140,len(o))
    result=bytes(o)
    assert result.count(b'IDST')==1,'Embedded model/donor residue'
    assert rooted(result)==keep and list(anims(result))==names
    return result,dict(before_sha256=sha(d),sha256=sha(result),before_bytes=len(d),bytes=len(result),
        sequences=keep,raws=names,removed_sequences=[n for n in ss if n not in ids],removed_raws=[n for n in aa if n not in rawids])

def verify(a,b,report,extra_prefix=None):
    sa,sb=seqs(a),seqs(b);aa,ab=anims(a),anims(b);an,bn=list(aa),list(ab)
    if extra_prefix:
        sb={n:q for n,q in sb.items() if not n.startswith(extra_prefix)}
        ab={n:q for n,q in ab.items() if not n.startswith(extra_prefix)}
    assert bones(a)==bones(b)
    for n,z in ab.items():
        q=aa[n];before=bytearray(a[q:q+72]);after=bytearray(b[z:z+72])
        for k in [0,20,48,56]:put(before,k,0);put(after,k,0)
        assert before==after,n
        assert samples(a,q)==samples(b,z),n
        for j in range(55):
            x=q+i(a,q+48)+j*32;y=z+i(b,z+48)+j*32
            assert a[x:x+4]==b[y:y+4]
            for c in range(7):
                ox,oy=i(a,x+4+c*4),i(b,y+4+c*4)
                assert (ox>0)==(oy>0)
                if ox>0:assert rle(a,x+ox,i(a,q+12))==rle(b,y+oy,i(b,z+12))
        count=i(a,q+16);assert a[q+i(a,q+20):q+i(a,q+20)+44*count]==b[z+i(b,z+20):z+i(b,z+20)+44*count]
    for n,z in sb.items():
        q=sa[n];before=bytearray(a[q:q+764]);after=bytearray(b[z:z+764])
        assert [an[v] if v>=0 else v for v in cells(a,q)]==[bn[v] if v>=0 else v for v in cells(b,z)]
        for k in [0,4,24,664,704,712,740,744,748,652]:put(before,k,0);put(after,k,0)
        before[56:568]=after[56:568]=bytes(512)
        assert before==after,(n,'descriptor')
        assert activity(a,q)==activity(b,z)
        for k in [740,744,748]:assert text(a,q,k)==text(b,z,k)
        for countfield,ptr,size in [(20,24,76),(700,704,24)]:
            count=i(a,q+countfield);x=q+i(a,q+ptr);y=z+i(b,z+ptr);assert a[x:x+count*size]==b[y:y+count*size],(n,ptr)
        for j in range(i(a,q+708)):
            x=q+i(a,q+712)+188*j;y=z+i(b,z+712)+188*j
            xrec=bytearray(a[x:x+188]);yrec=bytearray(b[y:y+188])
            for k in [120,136,152,168]:
                assert (cs(a,x+i(a,x+k)) if i(a,x+k)>0 else None)==(cs(b,y+i(b,y+k)) if i(b,y+k)>0 else None)
                put(xrec,k,0);put(yrec,k,0)
            assert xrec==yrec,(n,'trace',j)
    assert all(n.encode()+b'\0' not in b for n in report['removed_sequences'] if n not in ab)
    assert all(n.encode()+b'\0' not in b for n in report['removed_raws'] if n not in sb)
    return dict(passed=True,exact_keys_tracks_weights_and_movement=True,exact_kept_descriptor_semantics=True,
                exact_events_bounds_traces_reactions_and_links=True,no_embedded_models_or_orphan_names=True)
