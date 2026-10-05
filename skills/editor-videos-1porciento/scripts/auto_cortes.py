import subprocess, numpy as np, imageio_ffmpeg, json, sys
FF=imageio_ffmpeg.get_ffmpeg_exe()
def cortes(path, min_sil=0.22, pad=0.07):
    raw=subprocess.run([FF,"-loglevel","error","-i",path,"-vn","-ac","1","-ar","16000","-af","highpass=f=100","-f","s16le","-"],capture_output=True).stdout
    a=np.frombuffer(raw,np.int16).astype(np.float32)/32768
    hop=160  # 10 ms
    r=np.sqrt(np.convolve(a**2,np.ones(480)/480,'same')[::hop]); db=20*np.log10(r+1e-7)
    floor=np.percentile(db,12); peak=np.percentile(db,95)
    thr=floor+0.28*(peak-floor)
    q=db<thr; out=[]; i=0
    while i<len(q):
        if q[i]:
            j=i
            while j<len(q) and q[j]: j+=1
            s,e=i*0.01,j*0.01
            if e-s>=min_sil+2*pad: out.append([round(s+pad,2),round(e-pad,2)])
            i=j
        else: i+=1
    return out, round(floor,1), round(thr,1), round(peak,1)
if __name__=="__main__":
    # uso: python auto_cortes.py video.mov [min_silencio=0.22]  -> imprime la lista "cortes" para el config
    ms = float(sys.argv[2]) if len(sys.argv) > 2 else 0.22
    c,f,t,p=cortes(sys.argv[1], ms); print(json.dumps(c))
