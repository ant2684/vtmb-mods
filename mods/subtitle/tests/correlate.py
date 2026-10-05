"""Compare captured process PCM to source audio with normalized waveform correlation."""
import numpy as np,json,wave,sys
from pathlib import Path
def pcm(path):
 with wave.open(str(path)) as f:
  assert f.getsampwidth()==2
  rate=f.getframerate();channels=f.getnchannels();x=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,channels).astype(np.float64).mean(1)
 return rate,x
def match(source,fragment,rate):
 # Downsample from 44.1k to 4.41k. Channel mix/EQ still leave a measurable match.
 a=source[::10];b=fragment[::10];b-=b.mean();n=len(b);size=1<<(len(a)+n-2).bit_length()
 corr=np.fft.irfft(np.fft.rfft(a,size)*np.fft.rfft(b[::-1],size),size)[n-1:len(a)]
 sums=np.concatenate(([0.],np.cumsum(a)));sq=np.concatenate(([0.],np.cumsum(a*a)));energy=sq[n:]-sq[:-n]-(sums[n:]-sums[:-n])**2/n
 denom=np.sqrt(np.maximum(energy,0)*np.dot(b,b));score=corr/np.maximum(denom,1)
 i=int(np.argmax(score));return {'source_seconds':i*10/rate,'correlation':float(score[i])}
if __name__=='__main__':
 sr,source=pcm(sys.argv[1]);rate,capture=pcm(sys.argv[2]);assert rate==sr
 results=[]
 for v in sys.argv[3:]:
  start=float(v);end=start+2;r=match(source,capture[int(start*rate):int(end*rate)],rate);r['capture_seconds']=start;results.append(r)
 print(json.dumps(results,indent=2))
