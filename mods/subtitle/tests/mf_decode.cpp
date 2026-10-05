// Read-only Media Foundation decoding of retained source audio for correlation.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <initguid.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <stdio.h>
#include <stdlib.h>
static void check(HRESULT hr,const char *where){if(FAILED(hr)){fprintf(stderr,"%s %08lx\n",where,(unsigned long)hr);exit(2);}}
int wmain(int argc,wchar_t **argv){
 if(argc!=3)return 1;check(CoInitializeEx(nullptr,COINIT_MULTITHREADED),"COM");check(MFStartup(MF_VERSION,MFSTARTUP_LITE),"MFStartup");
 IMFSourceReader *reader=nullptr;check(MFCreateSourceReaderFromURL(argv[1],nullptr,&reader),"SourceReader");
 IMFMediaType *type=nullptr;check(MFCreateMediaType(&type),"CreateType");check(type->SetGUID(MF_MT_MAJOR_TYPE,MFMediaType_Audio),"Major");check(type->SetGUID(MF_MT_SUBTYPE,MFAudioFormat_PCM),"PCM");
 check(reader->SetCurrentMediaType(MF_SOURCE_READER_FIRST_AUDIO_STREAM,nullptr,type),"SetType");type->Release();type=nullptr;check(reader->GetCurrentMediaType(MF_SOURCE_READER_FIRST_AUDIO_STREAM,&type),"GetType");
 WAVEFORMATEX *fmt=nullptr;UINT32 fmtSize=0;check(MFCreateWaveFormatExFromMFMediaType(type,&fmt,&fmtSize,MFWaveFormatExConvertFlag_Normal),"Format");
 FILE *f=_wfopen(argv[2],L"wbx");if(!f)return 3;DWORD size=0;fwrite("RIFF",1,4,f);fwrite(&size,4,1,f);fwrite("WAVEfmt ",1,8,f);size=16;fwrite(&size,4,1,f);fwrite(fmt,1,16,f);fwrite("data",1,4,f);size=0;fwrite(&size,4,1,f);
 for(;;){DWORD flags=0;IMFSample *sample=nullptr;LONGLONG stamp=0;check(reader->ReadSample(MF_SOURCE_READER_FIRST_AUDIO_STREAM,0,nullptr,&flags,&stamp,&sample),"ReadSample");
  if(sample){IMFMediaBuffer *buf=nullptr;check(sample->ConvertToContiguousBuffer(&buf),"Buffer");BYTE *data=nullptr;DWORD n=0;check(buf->Lock(&data,nullptr,&n),"Lock");if(fwrite(data,1,n,f)!=n)return 4;size+=n;buf->Unlock();buf->Release();sample->Release();}
  if(flags&MF_SOURCE_READERF_ENDOFSTREAM)break;
 }
 fseek(f,4,SEEK_SET);DWORD length=size+36;fwrite(&length,4,1,f);fseek(f,40,SEEK_SET);fwrite(&size,4,1,f);fclose(f);
 printf("rate=%lu channels=%u bits=%u seconds=%.6f\n",(unsigned long)fmt->nSamplesPerSec,fmt->nChannels,fmt->wBitsPerSample,(double)size/fmt->nAvgBytesPerSec);
 CoTaskMemFree(fmt);type->Release();reader->Release();MFShutdown();CoUninitialize();return 0;
}
