"""Archive six already located official rules; independent from runtime stores."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
import httpx
from html import unescape
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent/'.roll-data'/'rights-public'
SOURCES=[
('2015-fee-change','2015-07-01','2015-08-01','https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988866.shtml'),
('2018-closing-mechanism','2018-08-06','2018-08-20','https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml'),
('2018-rules-notice','2018-08-06','2018-08-20','https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20210531_5478087.shtml'),
('2023-fee-change','2023-08-18','2023-08-28','https://www.sse.com.cn/home/component/news/c/c_20230818_5725376.shtml'),
('CSDC-milestones',None,None,'https://m.chinaclear.cn/zdjs/dsj/about_dsj.shtml'),
('SSE2013-factbook',None,None,'https://www.sse.com.cn/aboutus/publication/factbook/documents/c/10170569/files/cdccf6c0b46a4c0cadc0a531ecc3aad7.pdf')]
def now():return datetime.now(timezone.utc).isoformat()
rows=[];total=0
with httpx.Client(timeout=30,follow_redirects=False,headers={'User-Agent':'Mozilla/5.0'}) as c:
 for key,pub,effective,url in SOURCES:
  row={'id':key,'publication_date':pub,'publication_precision':'DATE' if pub else 'UNKNOWN','effective_date':effective,'url':url,'requested_at':now()}
  try:
   with c.stream('GET',url) as r:
    row['http_status']=r.status_code;r.raise_for_status();chunks=[];size=0
    for chunk in r.iter_bytes():
     size+=len(chunk)
     if size>64*1024**2 or total+size>256*1024**2:raise RuntimeError('BYTE_BOUND')
     chunks.append(chunk)
   data=b''.join(chunks);total+=size;sha=hashlib.sha256(data).hexdigest();ext='pdf' if data.startswith(b'%PDF') else 'html';p=ROOT/'raw'/f'{sha}.{ext}';p.write_bytes(data)
   row.update({'received_at':now(),'sha256':sha,'bytes':size,'path':str(p),'status':'OFFICIAL_ORIGINAL_ARCHIVED'})
   if ext=='pdf':
    reader=PdfReader(p);selected=[]
    for i,page in enumerate(reader.pages):
     txt=page.extract_text() or ''
     if '0.0696' in txt or '过户费' in txt:selected.append({'pdf_page':i+1,'text':txt})
    tp=ROOT/f'{sha}.pages.json';tp.write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n','utf8');row['text_path']=str(tp)
   else:
    match=re.search(rb'charset=[\s"\x27]*([\w-]+)',data,re.I);encoding=match.group(1).decode() if match else 'utf8';html=data.decode(encoding,errors='replace');html=re.sub(r'<(script|style)\b[^>]*>.*?</\1>','',html,flags=re.I|re.S);text=unescape(re.sub(r'<[^>]+>','\n',html));text=re.sub(r'\n\s*\n','\n',text);tp=ROOT/f'{sha}.txt';tp.write_text(text,'utf8');row.update({'text_path':str(tp),'html_locator':'article body; native HTML has no PDF page'})
  except Exception as e:row.update({'status':'FAILED','error':type(e).__name__})
  rows.append(row)
(ROOT/'rules-manifest.json').write_text(json.dumps({'sources':rows,'new_bytes':total},ensure_ascii=False,indent=2)+'\n','utf8')
print(json.dumps({'successful':sum(x['status']=='OFFICIAL_ORIGINAL_ARCHIVED' for x in rows),'new_bytes':total}))
