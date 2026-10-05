"""Generate the exact relocated drawing-block reference for the supported client."""
import argparse, hashlib, sys
from pathlib import Path
EXPECTED='E88BEAE0DD03AF06493C71C5E8D87A6993B54E590CB6AD37CD3513C588582870'
START=0xF1AD9;END=0xF1BAF;BRANCH=0xF1AE5;EPILOGUE=0xF1BA9
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--client',required=True);ap.add_argument('--dependency-dir',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    sys.path.insert(0,a.dependency_dir);import pefile
    data=Path(a.client).read_bytes();assert hashlib.sha256(data).hexdigest().upper()==EXPECTED,'Unsupported client bytes'
    pe=pefile.PE(data=data);assert pe.FILE_HEADER.Machine==0x14c and pe.OPTIONAL_HEADER.ImageBase==0x10000000
    raw=pe.get_data(START,END-START)
    rel=[e.rva-START for b in pe.DIRECTORY_ENTRY_BASERELOC for e in b.entries if e.type==3 and START<=e.rva<END]
    assert rel==[1,19,38,126]
    assert pe.get_data(BRANCH,6)==bytes.fromhex('0f84be000000')
    text='/* Generated from the pinned original client. Game code is a verification reference. */\n'
    text+='static const unsigned char draw_reference[] = {\n'
    for i in range(0,len(raw),16):text+='    '+','.join('0x%02x'%b for b in raw[i:i+16])+',\n'
    text+='};\nstatic const unsigned reloc_offsets[] = {'+','.join(map(str,rel))+'};\n'
    text+='#define DRAW_RVA 0xF1AD9u\n#define BRANCH_OFFSET 12u\n#define EPILOGUE_OFFSET 208u\n'
    Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(text,encoding='ascii')
if __name__=='__main__':main()
