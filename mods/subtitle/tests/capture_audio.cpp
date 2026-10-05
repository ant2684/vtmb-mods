// Diagnostic process-only WASAPI capture. No audio device/settings changes.
// API contract: Microsoft's ApplicationLoopback sample (see technical README).
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

class Completion final : public IActivateAudioInterfaceCompletionHandler {
    LONG refs=1;
public:
    HANDLE done=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    HRESULT result=E_PENDING;
    IAudioClient *client=nullptr;
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void **out) override {
        if(!out)return E_POINTER; *out=nullptr;
        if(IsEqualIID(id,IID_IUnknown)||IsEqualIID(id,IID_IActivateAudioInterfaceCompletionHandler)||IsEqualIID(id,IID_IAgileObject)) {
            *out=static_cast<IActivateAudioInterfaceCompletionHandler*>(this);AddRef();return S_OK;
        }return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override{return InterlockedIncrement(&refs);}
    ULONG STDMETHODCALLTYPE Release() override{LONG n=InterlockedDecrement(&refs);if(!n)delete this;return n;}
    HRESULT STDMETHODCALLTYPE ActivateCompleted(IActivateAudioInterfaceAsyncOperation *op) override {
        IUnknown *p=nullptr;HRESULT activation=E_FAIL;
        result=op->GetActivateResult(&activation,&p);
        if(SUCCEEDED(result))result=activation;
        if(SUCCEEDED(result)&&p)result=p->QueryInterface(IID_IAudioClient,(void**)&client);
        if(p)p->Release();SetEvent(done);return S_OK;
    }
    ~Completion(){if(client)client->Release();CloseHandle(done);}
};

static void check(HRESULT hr,const char *what){if(FAILED(hr)){fprintf(stderr,"%s: HRESULT %08lx\n",what,(unsigned long)hr);exit(2);}}
static double qpc(){LARGE_INTEGER a,b;QueryPerformanceCounter(&a);QueryPerformanceFrequency(&b);return (double)a.QuadPart/b.QuadPart;}
int wmain(int argc,wchar_t **argv){
    if(argc!=5){fprintf(stderr,"pid creationTicks output.wav durationSeconds\n");return 2;}
    DWORD pid=wcstoul(argv[1],nullptr,10);
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,pid);
    FILETIME created,exitTime,kernel,user;
    if(!process||!GetProcessTimes(process,&created,&exitTime,&kernel,&user))return 3;
    uint64_t ticks=((uint64_t)created.dwHighDateTime<<32)|created.dwLowDateTime;
    if(ticks+504911232000000000ULL!=_wcstoui64(argv[2],nullptr,10))return 4;
    check(CoInitializeEx(nullptr,COINIT_MULTITHREADED),"CoInitializeEx");
    // AUDIOCLIENT_ACTIVATION_PARAMS ABI: type, target PID, INCLUDE_TARGET_TREE.
    DWORD params[3]={1,pid,0};PROPVARIANT pv={};pv.vt=VT_BLOB;pv.blob.cbSize=sizeof(params);pv.blob.pBlobData=(BYTE*)params;
    auto handler=new Completion;IActivateAudioInterfaceAsyncOperation *op=nullptr;
    check(ActivateAudioInterfaceAsync(L"VAD\\Process_Loopback",IID_IAudioClient,&pv,handler,&op),"ActivateAudioInterfaceAsync");
    if(WaitForSingleObject(handler->done,10000)!=WAIT_OBJECT_0)return 5;
    check(handler->result,"ActivateCompleted");
    IAudioClient *client=handler->client;
    WAVEFORMATEX fmt={};fmt.wFormatTag=WAVE_FORMAT_PCM;fmt.nChannels=2;fmt.nSamplesPerSec=44100;
    fmt.wBitsPerSample=16;fmt.nBlockAlign=4;fmt.nAvgBytesPerSec=176400;
    HANDLE ready=CreateEventW(nullptr,FALSE,FALSE,nullptr);
    check(client->Initialize(AUDCLNT_SHAREMODE_SHARED,AUDCLNT_STREAMFLAGS_LOOPBACK|AUDCLNT_STREAMFLAGS_EVENTCALLBACK|AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM,0,0,&fmt,nullptr),"Initialize");
    check(client->SetEventHandle(ready),"SetEventHandle");
    IAudioCaptureClient *capture=nullptr;check(client->GetService(IID_IAudioCaptureClient,(void**)&capture),"GetService");
    FILE *f=_wfopen(argv[3],L"wbx");if(!f)return 6;
    wchar_t metaPath[32768];swprintf(metaPath,32768,L"%s.packets.jsonl",argv[3]);FILE *meta=_wfopen(metaPath,L"wbx");if(!meta)return 7;
    unsigned char header[44]={};fwrite(header,1,44,f);uint32_t bytes=0;
    double start=qpc(),end=start+wcstod(argv[4],nullptr);
    check(client->Start(),"Start");printf("READY %.9f\n",start);fflush(stdout);
    fprintf(meta,"{\"start_qpc\":%.9f,\"pid\":%lu,\"rate\":44100}\n",start,(unsigned long)pid);
    while(qpc()<end&&WaitForSingleObject(process,0)==WAIT_TIMEOUT){
        WaitForSingleObject(ready,50);UINT32 available=0;check(capture->GetNextPacketSize(&available),"GetNextPacketSize");
        while(available){BYTE *data=nullptr;UINT32 frames=0;DWORD flags=0;UINT64 pos=0,stamp=0;
            check(capture->GetBuffer(&data,&frames,&flags,&pos,&stamp),"GetBuffer");
            fprintf(meta,"{\"offset_frames\":%u,\"frames\":%u,\"flags\":%lu,\"device_position\":%llu,\"qpc_100ns\":%llu}\n",bytes/4,frames,(unsigned long)flags,(unsigned long long)pos,(unsigned long long)stamp);
            if(flags&AUDCLNT_BUFFERFLAGS_SILENT){unsigned char zero[4096]={};uint32_t left=frames*4;while(left){uint32_t n=left>4096?4096:left;fwrite(zero,1,n,f);left-=n;}}
            else fwrite(data,4,frames,f);
            bytes+=frames*4;check(capture->ReleaseBuffer(frames),"ReleaseBuffer");check(capture->GetNextPacketSize(&available),"GetNextPacketSize");
        }
    }
    check(client->Stop(),"Stop");fseek(f,0,SEEK_SET);
    fwrite("RIFF",1,4,f);uint32_t length=bytes+36;fwrite(&length,4,1,f);fwrite("WAVEfmt ",1,8,f);length=16;fwrite(&length,4,1,f);
    fwrite(&fmt,1,16,f);fwrite("data",1,4,f);fwrite(&bytes,4,1,f);fclose(f);fclose(meta);
    capture->Release();op->Release();handler->Release();CloseHandle(ready);CloseHandle(process);CoUninitialize();
    printf("DONE frames=%u seconds=%.3f\n",bytes/4,(double)bytes/176400);return 0;
}
