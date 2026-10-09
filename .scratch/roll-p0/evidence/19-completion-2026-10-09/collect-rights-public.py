"""Bounded official-only disclosure audit; no account/research databases."""
from __future__ import annotations
import hashlib, json, re, time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from pypdf import PdfReader

BASE=Path(__file__).resolve().parent
OUT=BASE/'.roll-data'/'rights-public'
PREVIOUS=BASE.parent/'continuation-2026-10-09'/'.roll-data'/'official-disclosures-v6'
def now(): return datetime.now(timezone.utc).isoformat()
def save(body,ext):
    sha=hashlib.sha256(body).hexdigest(); p=OUT/'raw'/f'{sha}.{ext}';p.write_bytes(body)
    return {'path':str(p),'sha256':sha,'bytes':len(body)}
def main():
    (OUT/'raw').mkdir(parents=True,exist_ok=True)
    old=json.loads((PREVIOUS/'manifest.json').read_text('utf8'))
    known={d['url']:d for d in old['documents']}
    result={'started_at':now(),'instrument':'SSE:600362','bounds':{'queries':40,'new_downloads':25,'one_file':64*1024**2,'total_new_bytes':256*1024**2},'queries':[],'documents':[],'complete_actions_certification':False,'sealed_read':False,'models_fitted':False,'labels_computed':False}
    found={}; new_bytes=0; downloads=0
    with httpx.Client(timeout=25,follow_redirects=False,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}) as c:
        for keyword in ['停牌','复牌','回购','注销','权益分派','利润分配方案实施','送股','配股']:
            form={'stock':'600362,gssh0600362','column':'sse','tabName':'fulltext','seDate':'2013-01-01~2025-12-31','searchkey':keyword,'sortName':'time','sortType':'asc','pageNum':'1','pageSize':'30'}
            pages=1
            for page in range(1,5):
                if page>pages:break
                if len(result['queries'])>=40:raise RuntimeError('QUERY_BOUND')
                form['pageNum']=str(page);row={'request_form':dict(form),'requested_at':now(),'url':'https://www.cninfo.com.cn/new/hisAnnouncement/query'}
                try:
                    r=c.post(row['url'],data=form);body=r.content;row.update(save(body,'json'));row.update({'http_status':r.status_code,'received_at':now()});r.raise_for_status();data=r.json()
                    total=data.get('totalAnnouncement',0);pages=min(4,(total+29)//30);row.update({'total_reported':total,'all_reported_pages_bounded':total<=120,'announcements':data.get('announcements',[])})
                    for d in data.get('announcements',[]) or []:found[str(d['announcementId'])]=d
                except Exception as e:row['error']=type(e).__name__
                result['queries'].append(row)
        for d in sorted(found.values(),key=lambda x:x['announcementTime']):
            title=re.sub('<[^>]+>','',d['announcementTitle']);pub=datetime.fromtimestamp(d['announcementTime']/1000,timezone.utc).astimezone(timezone.utc).strftime('%Y-%m-%d')
            # CNINFO dates are DATE precision. Adjunct URL carries the actual release date.
            url='https://static.cninfo.com.cn/'+d['adjunctUrl'];date_match=re.search(r'finalpage/(\d{4}-\d{2}-\d{2})/',url)
            if date_match:pub=date_match.group(1)
            row={'title':title,'url':url,'publication_date':pub,'publication_precision':'DATE','announcement_id':str(d['announcementId'])}
            if url in known:
                k=known[url];p=PREVIOUS/k['path'];sha=hashlib.sha256(p.read_bytes()).hexdigest()
                assert sha==k['sha256'];row.update({'status':'REUSED_OFFICIAL_ORIGINAL','received_at':k['received_at'],'sha256':sha,'path':str(p),'bytes':p.stat().st_size,'text_path':str(PREVIOUS/k['text_path'])});result['documents'].append(row);continue
            # Only operational actions and trading state, no proposals or holders' unrelated transactions.
            if not (any(k in title for k in ['停牌','复牌','权益分派实施','利润分配方案实施','回购','注销']) and '恒邦' not in title):continue
            if downloads>=25:row['status']='DOWNLOAD_BOUND';result['documents'].append(row);continue
            downloads+=1;row['requested_at']=now()
            try:
                with c.stream('GET',url) as r:
                    row['http_status']=r.status_code;r.raise_for_status();chunks=[];size=0
                    for chunk in r.iter_bytes():
                        size+=len(chunk)
                        if size>64*1024**2 or new_bytes+size>256*1024**2:raise RuntimeError('BYTE_BOUND')
                        chunks.append(chunk)
                body=b''.join(chunks);row['received_at']=now();row.update(save(body,'pdf'));new_bytes+=size
                if not body.startswith(b'%PDF'):raise RuntimeError('NOT_PDF')
                reader=PdfReader(row['path']);texts=[]
                for i,p in enumerate(reader.pages):texts.append({'pdf_page':i+1,'text':p.extract_text() or ''})
                tp=OUT/f"{row['sha256']}.pages.json";tp.write_text(json.dumps(texts,ensure_ascii=False,indent=2)+'\n','utf8');row.update({'text_path':str(tp),'pdf_pages':len(reader.pages),'status':'NEW_OFFICIAL_ORIGINAL'})
            except Exception as e:row.update({'status':'FAILED','error':type(e).__name__})
            result['documents'].append(row)
    result.update({'finished_at':now(),'new_download_attempts':downloads,'new_bytes':new_bytes,'unique_matching_announcements':len(found)})
    (OUT/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({k:result[k] for k in ['new_download_attempts','new_bytes','unique_matching_announcements']}))
if __name__=='__main__':main()
