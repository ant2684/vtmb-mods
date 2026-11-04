/* Test-process-only loader continuation. No OS input or window activation.
   Feed a press/release to this loader's own polling calls while its wait flag is
   set. All other callers retain the real API result. */
static unsigned char *test_exe;
static SHORT (WINAPI *real_async)(int);
static HWND (WINAPI *real_foreground)(void);
static BOOL (WINAPI *real_iswindow)(HWND);
static HWND waiting_window;
static unsigned poll_phase;
static DWORD poll_time;
__declspec(dllexport) unsigned test_loading_continues;
static BOOL WINAPI test_iswindow(HWND h){
 if(test_exe[0x3f32c]){
  waiting_window=h;
  if(GetTickCount()-poll_time>500)poll_phase=0;
 }
 return real_iswindow(h);
}
static SHORT WINAPI test_async(int key){
 if(test_exe[0x3f32c]){
  if(key==VK_RETURN){
   poll_time=GetTickCount();++poll_phase;
   if(poll_phase==2)return (SHORT)0x8000;
   if(poll_phase==3)++test_loading_continues;
  }
  return 0;
 }
 return real_async(key);
}
static HWND WINAPI test_foreground(void){
 return test_exe[0x3f32c]&&waiting_window?waiting_window:real_foreground();
}
static void test_iat(unsigned offset,void *hook,void **original){
 DWORD old,tmp;void **slot=(void **)(test_exe+offset);
 if(!VirtualProtect(slot,4,PAGE_READWRITE,&old))return;
 *original=*slot;*slot=hook;VirtualProtect(slot,4,old,&tmp);
}
__declspec(dllexport) void loaded_engine(void){
 test_exe=(void *)GetModuleHandleA(NULL);
 if(memcmp(test_exe+0x7779,"\x6a\x0d\xff\xd7",4)||
    memcmp(test_exe+0x785d,"\xc6\x05",2)||
    *(unsigned *)(test_exe+0x785f)!=(unsigned)(uintptr_t)(test_exe+0x3f32c))return;
 test_iat(0x21184,test_async,(void **)&real_async);
 test_iat(0x21188,test_iswindow,(void **)&real_iswindow);
 test_iat(0x2119c,test_foreground,(void **)&real_foreground);
}
