"""어닝콜 음성을 받아쓰고, 대상회사 이름이 나온 구간을 찾아 확인용 음성 조각으로 자른다 (2026-11-01).

녹취록이 공개되지 않은 어닝콜(예: CJ ENM 2018~2019)의 earnings_call_note 칸을 확인하기 위한 것이다.
받아쓰기는 faster-whisper(large-v3, 한국어)로 하고, 결과는 구간마다 시작·끝 시각이 붙은 JSON으로 남긴다.
검색어가 나온 구간은 앞뒤 여유를 두고 ffmpeg로 잘라 mp3로 저장한다. 사람이 그 조각을 직접 들어 확인한다.

실행 (faster-whisper가 설치된 파이썬으로)
    받아쓰기: python transcribe_calls.py transcribe <음성 폴더> <받아쓰기 폴더>
        (카카오·NAVER 31개는 속도 때문에 large-v3-turbo 일괄 처리로 받아썼다. 같은 함수 본문에서
         모델을 BatchedInferencePipeline(WhisperModel("large-v3-turbo"))로, batch_size=16으로 바꾼 것이다.)
    반복 구간 고치기: python transcribe_calls.py repair <음성 폴더> <받아쓰기 폴더>
    검색·자르기: python transcribe_calls.py clip <받아쓰기 폴더> <음성 폴더> <조각 폴더> <검색어 JSON>
        검색어 JSON 형식: {"<라벨>": {"files": ["<음성 파일 이름>", ...], "pattern": "<정규식>"}}
"""
import json
import re
import subprocess
import sys
from pathlib import Path

MODEL = "large-v3"
PAD = 20  # 잘라 낼 때 앞뒤로 더 붙이는 초


def transcribe(src, out):
    # pip로 설치한 CUDA 라이브러리(nvidia-cublas-cu12, nvidia-cudnn-cu12)를 Windows DLL 검색 경로에 넣는다.
    import os
    import site
    for sp in site.getsitepackages():
        for sub in ("cublas", "cudnn", "cuda_nvrtc"):
            d = Path(sp) / "nvidia" / sub / "bin"
            if d.exists():
                os.add_dll_directory(str(d))
                os.environ["PATH"] = f"{d};{os.environ['PATH']}"
    from faster_whisper import WhisperModel
    out.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(MODEL, device="cuda", compute_type="float16")
    for f in sorted([*src.glob("*.mp3"), *src.glob("*.m4a")]):
        dst = out / f"{f.stem}.json"
        if dst.exists():
            continue
        segs, info = model.transcribe(load_audio(f), language="ko", vad_filter=True, beam_size=5)
        rows = [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()} for s in segs]
        dst.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
        (out / f"{f.stem}.txt").write_text(
            "\n".join(f"[{fmt(r['start'])}] {r['text']}" for r in rows), encoding="utf-8")
        print(f"{f.name}: {info.duration / 60:.1f}분, 구간 {len(rows)}개", flush=True)


LOOP = re.compile(r"(\S+)( \1){6,}")  # 같은 낱말이 일곱 번 넘게 이어지면 받아쓰기가 반복에 빠진 구간으로 본다


def repair(src, txt):
    """빠른 설정(large-v3-turbo, 일괄 처리)에서 반복에 빠진 구간만 정밀 설정(large-v3, beam 5,
    반복 n-gram 금지)으로 다시 받아쓴다. 반복 구간에 묻힌 발언을 놓치지 않기 위한 것이다."""
    import os
    import site
    for sp in site.getsitepackages():
        for sub in ("cublas", "cudnn", "cuda_nvrtc"):
            d = Path(sp) / "nvidia" / sub / "bin"
            if d.exists():
                os.add_dll_directory(str(d))
                os.environ["PATH"] = f"{d};{os.environ['PATH']}"
    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL, device="cuda", compute_type="float16")
    for p in sorted(txt.glob("*.json")):
        rows = json.loads(p.read_text(encoding="utf-8"))
        bad = [i for i, r in enumerate(rows) if LOOP.search(r["text"])]
        if not bad:
            continue
        audio = next(f for f in src.iterdir() if f.stem == p.stem)
        wav = load_audio(audio)
        for i in bad:
            r = rows[i]
            seg = wav[int(r["start"] * 16000):int(r["end"] * 16000)]
            out, _ = model.transcribe(seg, language="ko", beam_size=5, condition_on_previous_text=False,
                                      no_repeat_ngram_size=3, vad_filter=True)
            r["text"] = " ".join(s.text.strip() for s in out)
            r["repaired"] = True
        p.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
        p.with_suffix(".txt").write_text(
            "\n".join(f"[{fmt(r['start'])}] {r['text']}" for r in rows), encoding="utf-8")
        left = sum(1 for r in rows if LOOP.search(r["text"]))
        print(f"{p.stem}: 반복 구간 {len(bad)}개 다시 받아씀, 남은 반복 {left}개", flush=True)


def load_audio(f):
    """ffmpeg로 16kHz 단일 채널 float 배열을 만든다(faster-whisper의 PyAV 디코더와 av 버전이 맞지 않아 대신 씀)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(f), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def fmt(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}"


def clip(txt, src, out, queries):
    out.mkdir(parents=True, exist_ok=True)
    found = []
    for label, q in queries.items():
        pat = re.compile(q["pattern"], re.I)
        for name in q["files"]:
            p = txt / f"{Path(name).stem}.json"
            if not p.exists():
                print(f"{label}: {name} 받아쓰기 없음")
                continue
            rows = json.loads(p.read_text(encoding="utf-8"))
            hits = [r for r in rows if pat.search(r["text"])]
            print(f"{label}: {name} 일치 {len(hits)}구간")
            for i, r in enumerate(hits, 1):
                a, b = max(0, r["start"] - PAD), r["end"] + PAD
                dst = out / f"{label}_{Path(name).stem}_{i}_{fmt(r['start']).replace(':', '')}.mp3"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a), "-to", str(b),
                                "-i", str(src / name), "-c:a", "libmp3lame", "-q:a", "4", str(dst)], check=True)
                ctx = [x["text"] for x in rows if a <= x["start"] <= b]
                found.append({"label": label, "file": name, "at": fmt(r["start"]), "clip": dst.name,
                              "hit": r["text"], "context": " ".join(ctx)})
    (out / "hits.json").write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"조각 {len(found)}개 -> {out}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "transcribe":
        transcribe(Path(sys.argv[2]), Path(sys.argv[3]))
    elif cmd == "repair":
        repair(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        clip(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]),
             json.loads(Path(sys.argv[5]).read_text(encoding="utf-8")))
