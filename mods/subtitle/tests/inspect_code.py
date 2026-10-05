from pathlib import Path
import sys
sys.path.insert(0,r'LOCAL_DEPENDENCY_DIR_REQUIRED')
import pefile,capstone
game=Path(r'LOCAL_GAME_ROOT_REQUIRED')
pe=pefile.PE(str(game/'Vampire/dlls/vampire.dll'));base=pe.OPTIONAL_HEADER.ImageBase
d=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
for start,size in ((0x2c1170,0x200),(0x2c0520,0x250),(0x3a0670,0x3a0),(0x22c730,0x180)):
 print('FUNCTION',hex(start))
 for i in d.disasm(pe.get_data(start,size),base+start):print(hex(i.address-base),i.mnemonic,i.op_str)
