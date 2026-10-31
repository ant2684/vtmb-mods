"""Separate stock Frenzy sequences from unchanged player combo sequences."""
import struct
from compact_models import Packer, cells, text, rle
from mdl import i, put, cs, seqs, anims, bones, samples, encode_stream

PREFIX='pfi_frenzy_'

def merge(player, stock):
    pb,sb=bones(player),bones(stock)
    assert len(pb)==len(sb)==55
    for a,b in zip(pb,sb):
        assert all(a[k]==b[k] for k in ['name','parent','flags','base'])
    # Keep geometry, attachments, skeleton and materials verbatim. Rebuild the
    # animation/sequence tail once; no embedded donor or abandoned model tables.
    p=Packer(player);p.out=bytearray(player[:i(player,268)]);o=p.out
    sources=[(player,''),(stock,PREFIX)]
    rawrows=[];seqrows=[];rawids={};seqids={}
    for d,prefix in sources:
        for name,q in anims(d).items():
            rawids[prefix+name]=len(rawrows);rawrows.append((d,prefix,name,q))
        for name,q in seqs(d).items():
            seqids[prefix+name]=len(seqrows);seqrows.append((d,prefix,name,q))
    table=p.alloc(bytes(72*len(rawrows)));put(o,264,len(rawrows));put(o,268,table)
    for index,(d,prefix,name,q) in enumerate(rawrows):
        z=table+72*index;o[z:z+72]=d[q:q+72]
        put(o,z,p.string(prefix+name,z)-z)
        count=i(d,q+16);put(o,z+20,p.alloc(d[q+i(d,q+20):q+i(d,q+20)+44*count])-z if count else 0)
        assert i(d,q+52)==0;put(o,z+56,0)
        old=q+i(d,q+48);tracks=p.alloc(d[old:old+55*32]);put(o,z+48,tracks-z)
        for j in range(55):
            b=old+32*j;t=tracks+32*j
            for c in range(7):
                off=i(d,b+4+c*4)
                if off<=0:put(o,t+4+c*4,0);continue
                stream=rle(d,b+off,i(d,q+12))
                if prefix and sb[j]['scale'][c]!=pb[j]['scale'][c]:
                    # Bind and hierarchy are identical; only the shared model's
                    # compression scales differ. Requantize stock keys once.
                    from mdl import track
                    keys=track(d,b+off,i(d,q+12))
                    keys=[round(k*sb[j]['scale'][c]/pb[j]['scale'][c]) for k in keys]
                    assert all(-32768<=k<=32767 for k in keys)
                    stream=encode_stream(keys)
                put(o,t+4+c*4,p.alloc(stream,2)-t)
    table=p.alloc(bytes(764*len(seqrows)));put(o,272,len(seqrows));put(o,276,table)
    for index,(d,prefix,name,q) in enumerate(seqrows):
        z=table+764*index;o[z:z+764]=d[q:q+764]
        put(o,z,p.string(prefix+name,z)-z);p.st(z,4,q,d)
        names=list(anims(d))
        for j,v in enumerate(cells(d,q)):
            struct.pack_into('<h',o,z+56+2*j,rawids[prefix+names[v]] if v>=0 else v)
        for countfield,field,size in [(20,24,76),(700,704,24)]:
            count=i(d,q+countfield);old=q+i(d,q+field)
            put(o,z+field,p.alloc(d[old:old+count*size])-z if count else 0)
        count=i(d,q+708);old=q+i(d,q+712)
        if count:
            new=p.alloc(d[old:old+188*count]);put(o,z+712,new-z)
            for j in range(count):
                for k in [120,136,152,168]:
                    src=old+188*j;dst=new+188*j;value=i(d,src+k)
                    assert value>=0
                    put(o,dst+k,p.string(cs(d,src+value),dst)-dst if value else 0)
        else:put(o,z+712,0)
        count=i(d,q+660);old=q+i(d,q+664)
        if count:
            new=p.alloc(bytes(4*count));put(o,z+664,new-z)
            for j in range(count):put(o,new+4*j,seqids[prefix+list(seqs(d))[i(d,old+4*j)]])
        else:put(o,z+664,0)
        assert i(d,q+568)==i(d,q+668)==0
        for k in [740,744,748]:
            value=text(d,q,k)
            if prefix and k in [744,748] and value:
                assert value in seqs(d),(name,value)
                value=prefix+value
            put(o,z+k,p.string(value,z)-z if value else -1)
        if i(d,q+652):put(o,z+652,seqids[prefix+list(seqs(d))[i(d,q+652)]])
    put(o,140,len(o))
    return bytes(o)

def verify_pools(player,stock,combined):
    from compact_models import verify
    # Existing lossless verifier checks every original player key, descriptor,
    # event, link, bound and trace. Added stock records are checked separately.
    verify(player,combined,{'removed_sequences':[],'removed_raws':[]},extra_prefix=PREFIX)
    outseq=seqs(combined);outraw=anims(combined);outnames=list(outraw)
    assert [n for n in outseq if not n.startswith(PREFIX)]==list(seqs(player))
    assert [n[len(PREFIX):] for n in outseq if n.startswith(PREFIX)]==list(seqs(stock))
    for name,q in seqs(stock).items():
        z=outseq[PREFIX+name];before=bytearray(stock[q:q+764]);after=bytearray(combined[z:z+764])
        for k in [0,4,24,664,704,712,740,744,748,652]:put(before,k,0);put(after,k,0)
        before[56:568]=after[56:568]=bytes(512)
        assert before==after,(name,'stock descriptor')
        assert cs(stock,q+i(stock,q+4))==cs(combined,z+i(combined,z+4))
        assert [list(anims(stock))[v] if v>=0 else v for v in cells(stock,q)]==[outnames[v][len(PREFIX):] if v>=0 else v for v in cells(combined,z)]
        for countfield,ptr,size in [(20,24,76),(700,704,24)]:
            count=i(stock,q+countfield);assert stock[q+i(stock,q+ptr):q+i(stock,q+ptr)+count*size]==combined[z+i(combined,z+ptr):z+i(combined,z+ptr)+count*size]
        for k in [744,748]:assert text(combined,z,k)==(PREFIX+text(stock,q,k) if text(stock,q,k) else None)
    maxerror=0.;combined_bones=bones(combined)
    for name,q in anims(stock).items():
        z=outraw[PREFIX+name];a=samples(stock,q);b=samples(combined,z)
        before=bytearray(stock[q:q+72]);after=bytearray(combined[z:z+72])
        for k in [0,20,48,56]:put(before,k,0);put(after,k,0)
        assert before==after,(name,'stock raw timing/flags')
        count=i(stock,q+16)
        assert stock[q+i(stock,q+20):q+i(stock,q+20)+44*count]==combined[z+i(combined,z+20):z+i(combined,z+20)+44*count],(name,'root movement')
        for j in range(55):
            for frame in range(len(a[j])):
                for c in range(7):
                    error=abs(a[j][frame][c]-b[j][frame][c]);maxerror=max(maxerror,error)
                    assert error<=abs(combined_bones[j]['scale'][c])*.501+1e-7,(name,j,c,error)
    assert combined.count(b'IDST')==1
    return dict(player_data_exact=True,stock_descriptors_events_links_exact=True,
                stock_raw_error_within_half_quantum=True,max_channel_error=maxerror,
                stock_sequences=len(seqs(stock)),player_sequences=len(seqs(player)))
