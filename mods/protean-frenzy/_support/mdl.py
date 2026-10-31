"""Bloodlines v2531 model IO, deterministic lossless reading of animation keys."""
import math, struct

def i(d,o): return struct.unpack_from('<i',d,o)[0]
def f(d,o): return struct.unpack_from('<f',d,o)[0]
def put(d,o,v): struct.pack_into('<i',d,o,v)
def cs(d,o):
    assert 0 <= o < len(d)
    return bytes(d[o:d.index(0,o)]).decode('ascii')
def seqs(d):
    assert d[:4]==b'IDST' and i(d,4)==2531 and i(d,140)==len(d)
    n,t=struct.unpack_from('<2i',d,272)
    assert 0<n<1000 and 424<=t<=len(d)-764*n
    return {cs(d,q+i(d,q)):q for q in range(t,t+764*n,764)}
def anims(d):
    n,t=struct.unpack_from('<2i',d,264)
    return {cs(d,q+i(d,q)).lstrip('@'):q for q in range(t,t+72*n,72)}
def bones(d):
    n,t=struct.unpack_from('<2i',d,240)
    out=[]
    for j in range(n):
        q=t+160*j
        out.append(dict(name=cs(d,q+i(d,q)),parent=i(d,q+4),flags=i(d,q+136),
                        base=struct.unpack_from('<7f',d,q+32),scale=struct.unpack_from('<7f',d,q+60)))
    return out
def track(d,p,frames):
    out=[]
    while len(out)<frames:
        valid,total=struct.unpack_from('<2B',d,p)
        assert 0<valid<=total
        keys=struct.unpack_from('<%dh'%valid,d,p+2)
        out.extend(keys);out.extend([keys[-1]]*(total-valid));p+=2+2*valid
    return out[:frames]
def samples(d,q):
    frames=i(d,q+12);a=q+i(d,q+48);bs=bones(d);out=[]
    for j,b in enumerate(bs):
        z=a+j*32;offsets=struct.unpack_from('<7i',d,z+4)
        channels=[track(d,z+off,frames) if off>0 else [0]*frames for off in offsets]
        # v2531 translations are bind-relative, but quaternion components are
        # ABSOLUTE when a stream is present. Absent streams use the bind value.
        out.append([[(b['base'][k]+b['scale'][k]*channels[k][frame] if k<3 else
                      b['scale'][k]*channels[k][frame] if offsets[k]>0 else b['base'][k])
                     for k in range(7)] for frame in range(frames)])
    return out
def norm(q):
    l=math.sqrt(sum(x*x for x in q));assert l>1e-8
    return tuple(x/l for x in q)
def mul(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return (w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z)
def inv(q):
    q=norm(q);return (-q[0],-q[1],-q[2],q[3])
def rotate(q,v): return mul(mul(q,(*v,0)),inv(q))[:3]
def retarget(src,dst,q):
    sb,tb=bones(src),bones(dst);by={b['name']:j for j,b in enumerate(sb)};ss=samples(src,q);frames=i(src,q+12);out=[]
    for b in tb:
        if b['name'] not in by:
            out.append([list(b['base']) for _ in range(frames)]);continue
        j=by[b['name']];s=sb[j];sr,tr=norm(s['base'][3:]),norm(b['base'][3:]);align=mul(tr,inv(sr))
        # Translation lives in the parent coordinate system; preserve target
        # bind lengths and rotate authored displacements into its parent basis.
        pa=norm((0,0,0,1))
        if s['parent']>=0 and b['parent']>=0:
            sp=sb[s['parent']];tp=tb[b['parent']]
            assert sp['name']==tp['name'],(b['name'],sp['name'],tp['name'])
            pa=mul(norm(tp['base'][3:]),inv(sp['base'][3:]))
        vals=[]
        for pose in ss[j]:
            delta=rotate(pa,[pose[k]-s['base'][k] for k in range(3)])
            rot=norm(mul(align,norm(pose[3:])))
            if sum(x*y for x,y in zip(rot,tr))<0:rot=tuple(-x for x in rot)
            vals.append([b['base'][k]+delta[k] for k in range(3)]+list(rot))
        out.append(vals)
    return out
def encode_stream(keys):
    # Valid unoptimized RLE: bounded literal blocks. Deterministic and exact.
    out=bytearray()
    for p in range(0,len(keys),255):
        chunk=keys[p:p+255];out.extend(bytes((len(chunk),len(chunk))))
        out.extend(struct.pack('<%dh'%len(chunk),*chunk))
    return out
def quantize(poses,bs):
    out=[];overflow=[];maxerr=0
    for j,(frames,b) in enumerate(zip(poses,bs)):
        channels=[]
        for c in range(7):
            scale=b['scale'][c];base=b['base'][c] if c<3 else 0;keys=[]
            if all(abs(pose[c]-b['base'][c])<1e-12 for pose in frames):
                channels.append(None);continue
            for frame,pose in enumerate(frames):
                delta=pose[c]-base
                key=round(delta/scale) if scale else 0
                if not scale and abs(delta)>1e-5 or not -32768<=key<=32767:overflow.append((b['name'],c,frame,key,delta,scale))
                keys.append(key)
                maxerr=max(maxerr,abs(base+key*scale-pose[c]))
            channels.append(keys)
        out.append(channels)
    return out,overflow,maxerr
