import {useState} from 'react';
import {request} from '../api';
type Fact={fact_id:string;title:string;excerpt:string|null;url:string;media:string|null;reported_published_at:string|null;first_received_at:string;available_at:string;body_received_at:string|null;list_sha256:string;body_sha256:string|null;body_status:string;body_text:string|null;evidence_kind:string;extractor_version:string|null;extracted_metadata:unknown;errors:string[]};
type Run={run_id:string;status:string;errors:string[];coverage?:{returned:number;body_extracted:number};originals?:{sha256:string;role:string;original_complete?:boolean;integrity_verified?:boolean}[]};
type News={facts:Fact[];runs:Run[];active_run_ids:string[]};
export function NewsPanel({instrument}:{instrument:string}){
 const [value,setValue]=useState<News|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[cutoff,setCutoff]=useState('');const base=`/market/news/${encodeURIComponent(instrument)}`;
 async function read(){return request<News>(base+(cutoff?`?known_by=${encodeURIComponent(new Date(cutoff).toISOString())}`:''));}
 async function inspect(){setValue(await read());}
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function collect(){const run=await request<Run>(base+'/collect',{idempotency_key:crypto.randomUUID(),basis:'用户显式请求单股近期新闻列表、最多三篇正文原件和离线抽取'});await inspect();if(run.status==='FAILED')setError(run.errors.join('；'));}
 async function cancel(){const current=await request<News>(base);if(current.active_run_ids.length)await request('/market/news/runs/'+current.active_run_ids[0]+'/cancel',{});else setError('当前没有运行中的新闻采集');}
 return <details className="status-evidence"><summary>查看近期新闻</summary>
  <p>上游文档最多近期100条，当前锁定SDK只取默认排序的第一页10条；最多取其中3篇正文。不代表完整历史或已核实证券关联。来源默认关闭，请在来源配置显式启用。</p>
  <label>新闻系统已知截至（留空查询当前）<input type="datetime-local" value={cutoff} disabled={busy} onChange={e=>{setCutoff(e.target.value);setValue(null);}}/></label>
  <button disabled={busy} onClick={()=>void action(inspect)}>查询保存的新闻</button><button disabled={busy||!!cutoff} onClick={()=>void action(collect)}>有限采集近期新闻</button>{busy&&<button onClick={()=>void action(cancel)}>取消新闻采集</button>}
  {value&&!value.facts.length&&<p>当前截止没有已保存新闻；未查到不等于没有新闻。</p>}
  {value?.facts.map(f=><section key={f.fact_id} aria-label={`新闻 ${f.title}`}><h3>{f.title}</h3><p>{f.evidence_kind==='METHOD_CASE'?'METHOD工程证据':'实际收到的近期观察'}</p>
   <p>媒体 {f.media??'未知'} · 来源时间 {f.reported_published_at??'未知'}（上游未声明时区）<br/>列表首次接收 {f.first_received_at}<br/>本观察可用 {f.available_at}{f.body_received_at&&<><br/>正文原件接收 {f.body_received_at}</>}</p>
   <details><summary>列表摘要（非全文）</summary><p>{f.excerpt??'未提供'}</p></details>
   {f.body_text?<><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{f.body_text}</p><p>离线正文提取 Trafilatura {f.extractor_version} · 请与原件核对</p></>:<p>正文缺口：{f.body_status}</p>}
   <p><a href={`/api/data/archives/${f.list_sha256}`} target="_blank" rel="noreferrer">新闻列表原响应</a>{f.body_sha256&&<> · <a href={`/api/data/archives/${f.body_sha256}`} target="_blank" rel="noreferrer">正文HTML原件</a></>}</p>
   <details><summary>来源链接、提取元数据与缺口</summary><p style={{overflowWrap:'anywhere'}}>来源记录 {f.url}</p><pre>{JSON.stringify(f.extracted_metadata,null,2)}</pre><p>提取日期不作为首次披露或首次接收时间。</p><p>{f.errors.join('；')}</p></details>
  </section>)}
  {value?.runs.map(r=><section key={r.run_id}><p>新闻采集 {r.status}{r.coverage?` · 列表${r.coverage.returned}条／全文${r.coverage.body_extracted}篇`:''} {r.errors.join('；')}</p>{!!r.originals?.length&&<details><summary>本次采集原件</summary>{r.originals.map((o,i)=><p key={i}><a href={`/api/data/archives/${o.sha256}`} target="_blank" rel="noreferrer">{o.role==='LIST'?'列表':'正文'}接收原件{i+1}</a>{!o.original_complete&&' · 不完整接收，仅保留收到的字节'}{o.integrity_verified===false&&' · 完整性核验失败，不能用于全文'}</p>)}</details>}</section>)}
  {error&&<p role="alert">{error}</p>}
 </details>;
}
