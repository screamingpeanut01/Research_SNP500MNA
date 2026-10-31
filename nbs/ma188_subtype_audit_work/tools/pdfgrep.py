import sys,io,re
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
try:
  import fitz
  d=fitz.open(sys.argv[1]); t=''.join(p.get_text() for p in d)
except ImportError:
  from pypdf import PdfReader; t=''.join(p.extract_text() or '' for p in PdfReader(sys.argv[1]).pages)
w=int(sys.argv[3]) if len(sys.argv)>3 else 150
seen=-10**9
for m in re.finditer(sys.argv[2],t):
  if m.start()-seen<w: continue
  seen=m.start()
  print(t[max(0,m.start()-w):m.start()+w].replace('\n',' ')); print('---')
