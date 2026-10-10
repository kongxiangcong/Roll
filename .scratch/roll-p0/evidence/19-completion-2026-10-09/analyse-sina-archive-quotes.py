"""Offline byte-level analysis; never follows archive links or imports databases."""
import base64,collections,gzip,hashlib,io,json,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
HERE=Path(__file__).parent
rows=[];failures=[];mismatches=[]
for name in ['sina-archive-payload-receipts.json','sina-archive-payload-retry-receipts.json']:
 receipt=json.loads((HERE/name).read_text(encoding='utf8'))
 for item in receipt['captures']:
  if 'path' not in item or item.get('http_status')!=200:
   failures.append({'receipt':name,'capture':item['cdx'],'error':item.get('error'),'http_status':item.get('http_status')});continue
  raw=Path(item['path']).read_bytes()
  if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:mismatches.append(item['url']);continue
  decoded=raw;encoding='IDENTITY'
  if raw[:2]==b'\x1f\x8b':
   with gzip.GzipFile(fileobj=io.BytesIO(raw)) as z:decoded=z.read(2097153)
   if len(decoded)>2097152:raise ValueError('DECODED_2MiB_CAP')
   encoding='GZIP_WIRE_BODY_DECODED_OFFLINE'
  text=decoded.decode('gb18030',errors='strict');match=re.search(r'var\s+hq_str_sh600362\s*=\s*"([^"]*)"\s*;',text)
  if not match:failures.append({'receipt':name,'capture':item['cdx'],'error':'NO_EXPECTED_QUOTE'});continue
  f=match.group(1).split(',');assert len(f)>=32
  quote={'security_name':f[0],'open':f[1],'previous_close':f[2],'last_price':f[3],'high':f[4],'low':f[5],'raw_volume':f[8],'raw_amount':f[9],'business_date':f[30],'business_time':f[31],'trailing_fields':f[32:],'raw_fields':f}
  clock=datetime.fromisoformat(f[30]+'T'+f[31]).replace(tzinfo=timezone(timedelta(hours=8)))
  capture=datetime.fromisoformat(item['capture_time'])
  quote['completion_class']='AFTER_NOMINAL_CLOSE_NOT_CALENDAR_QUALIFIED' if f[31]>='15:00:00' else 'INTRADAY_OR_PREOPEN'
  quote['zero_open_or_volume']=float(f[1])==0 or float(f[8])==0
  row={'receipt':name,'url':item['url'],'original':item['cdx']['original'],'capture_time':item['capture_time'],'original_publication_at':None,'received_at':item['received_at'],'wire_bytes':len(raw),'wire_sha256':item['sha256'],'wire_path':item['path'],'decode':encoding,'decoded_bytes':len(decoded),'decoded_sha256':hashlib.sha256(decoded).hexdigest(),'cdx_sha1_matches_wire_body':item['cdx_digest_matches_body'],'cdx_sha1_matches_decoded_body':base64.b32encode(hashlib.sha1(decoded).digest()).decode().rstrip('=')==item['cdx']['digest'],'capture_lag_from_business_seconds':(capture-clock).total_seconds(),'quote':quote,'risk_warning_state':'UNQUALIFIED','calendar_qualified':False,'source_independence':'UNPROVEN'}
  rows.append(row)
unique={r['capture_time']:r for r in rows};rows=sorted(unique.values(),key=lambda r:r['capture_time'])
result={'quotes':rows,'unresolved_attempts':failures,'wire_hash_length_mismatches':mismatches,'summary':{'actual_unique_quote_captures':len(rows),'business_dates':len(set(r['quote']['business_date'] for r in rows)),'post_nominal_close':sum(r['quote']['completion_class'].startswith('AFTER') for r in rows),'intraday_or_preopen':sum(r['quote']['completion_class'].startswith('INTRADAY') for r in rows),'gzip_resolved_offline':sum(r['decode'].startswith('GZIP') for r in rows),'decoded_cdx_digest_matches':sum(r['cdx_sha1_matches_decoded_body'] for r in rows),'negative_capture_lags':sum(r['capture_lag_from_business_seconds']<0 for r in rows)},'unit_schema_evidence':'Current first-party Sina sf_sdk.js CN parser takes field 8 divided by 100 as totalVolume; datas/k.js applies CN multiplier 100 when merging current quote to daily K. Historical schema version and corporate-action raw convention are not proven by current SDK alone.','qualification':'NONE','labels_computed':False,'models_fitted':False,'sealed_read':False}
(HERE/'sina-archive-quote-analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result['summary']));print('wire_mismatches',mismatches)
for r in rows:print(r['capture_time'],r['quote']['business_date'],r['quote']['business_time'],r['quote']['open'],r['quote']['raw_volume'],r['quote']['trailing_fields'])
