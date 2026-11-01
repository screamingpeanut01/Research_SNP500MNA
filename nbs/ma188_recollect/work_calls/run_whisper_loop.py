# 받기가 끝나 calls/로 옮겨진 음성을 차례로 받아쓴다. 모델은 한 번만 올린다. 31개가 끝나면 멈춘다.
import sys, time, json
from pathlib import Path
sys.path.insert(0, r"D:/KUfolio/Researches/Research_SNP500MNA/nbs/ma188_recollect")
import transcribe_calls as tc
src, out, total = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
import os, site
for sp in site.getsitepackages():
    for sub in ("cublas", "cudnn", "cuda_nvrtc"):
        d = Path(sp) / "nvidia" / sub / "bin"
        if d.exists():
            os.add_dll_directory(str(d)); os.environ["PATH"] = f"{d};{os.environ['PATH']}"
from faster_whisper import WhisperModel, BatchedInferencePipeline
model = BatchedInferencePipeline(WhisperModel("large-v3-turbo", device="cuda", compute_type="float16"))
while len(list(out.glob("*.json"))) < total:
    todo = [f for f in sorted(src.glob("*.m4a")) if not (out / f"{f.stem}.json").exists()]
    if not todo:
        time.sleep(30); continue
    f = todo[0]
    segs, info = model.transcribe(tc.load_audio(f), language="ko", batch_size=16, beam_size=1)
    rows = [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()} for s in segs]
    (out / f"{f.stem}.txt").write_text("\n".join(f"[{tc.fmt(r['start'])}] {r['text']}" for r in rows), encoding="utf-8")
    (out / f"{f.stem}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{f.name}: {info.duration/60:.1f}분, 구간 {len(rows)}개", flush=True)
