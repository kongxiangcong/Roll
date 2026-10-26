import {useEffect,useState} from 'react';
import {request} from '../api';
type Settings={revision:number;enabled:boolean;news_postclose:boolean;financial_postclose:boolean;market_postclose:boolean;news_refresh:boolean;classify:boolean;profile:string};
type Job={result?:{source:string;status?:string;refresh?:string}[];job_id:string;command:{kind:string};status:string;created_at:string;finished_at:string|null;observation_id:string|null;error:string|null;errors?:string[];cache_reused?:boolean;scheduled_checkpoint:string|null};
type MarketFact={last?:string;close?:string;trade_date?:string;upstream_at?:string};
function MarketSummary({payload}:{payload:Record<string,unknown>}){const market=payload.market as {quote?:MarketFact|null;last_complete_daily?:MarketFact|null}|null;return <p>最近报价 {market?.quote?.last??'缺失'} 元 · 报价时点 {market?.quote?.upstream_at??'未知'}；最近完整日线 {market?.last_complete_daily?.trade_date??'缺失'} · 收盘 {market?.last_complete_daily?.close??'未知'} 元。原价变化不代表含分红总收益。</p>;}
type Observation={observation_id:string;kind:string;created_at:string;known_by:string;evidence_kind:string;errors:string[];payload:Record<string,unknown>};
type Source={id:string;name:string;enabled:boolean;revision:number;health:{state?:string;consecutive_failures?:number;retry_after?:string}};
type Value={settings:Settings;jobs:Job[];observations:Observation[];sources:Source[];health:Record<string,unknown>;worker:{worker_state:string;worker_limit:number};offline_coverage:{sessions:unknown[];gaps:{start:string;end:string;reason:string}[]}};
export function ObservationUpdatesPanel({instrument,expanded=false}:{instrument:string;expanded?:boolean}){
 const [value,setValue]=useState<Value|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[refresh,setRefresh]=useState(expanded);
 const base=`/observation-updates/${encodeURIComponent(instrument)}`;
 useEffect(()=>{
   if(!expanded)return;
   let active=true;
   const update=()=>void request<Value>(base).then(result=>{if(active){setValue(result);setError('');}}).catch(e=>{if(active)setError(String(e));});
   update();const timer=setInterval(update,5000);
   return()=>{active=false;clearInterval(timer);};
 },[base,expanded,instrument]);

 async function query(){setValue(await request<Value>(base));}
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();await query();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function configure(change:Partial<Settings>){if(!value)return;const s=value.settings;await request(base+'/settings',{enabled:s.enabled,news_postclose:s.news_postclose,financial_postclose:s.financial_postclose??false,market_postclose:s.market_postclose??false,news_refresh:s.news_refresh,classify:s.classify,profile:s.profile,...change,expected_revision:s.revision,basis:'用户显式配置现有worker上的所选证券日常观察'});}
 async function enqueue(kind:string){await request(base+'/requests',{kind,refresh_sources:refresh,idempotency_key:crypto.randomUUID(),basis:'用户按需请求财报新闻观察；不启动预测、训练或交易'});}
 return <details className="status-evidence" open={expanded||undefined}><summary>日常财报新闻观察</summary>
  <p>程序运行时可在交易日15:05后更新行情、财报与新闻；也可随时手动刷新。关闭网页后后台继续运行，关机期间不会采集；重启后记录实际更新时点。行情只取近90天，财务复用当日缓存。只发站内变化摘要。</p>
  <button disabled={busy} onClick={()=>void action(query)}>查询日常观察状态</button>
  {value&&<section aria-label="日常观察状态">
   <p role="status">日常观察{value.settings.enabled?'已启用':'已暂停'} · 设置版本 {value.settings.revision} · 单任务上限45秒 · 账户与交易资格独立</p>
   {expanded&&<div className="daily-latest"><h3>最近更新</h3>{(['MARKET','FINANCIAL','NEWS'] as const).map(kind=>{const observation=value.observations.find(o=>o.kind===kind);const latest=value.jobs.find(j=>j.command.kind===kind);const sourcePartial=value.jobs.filter(j=>j.command.kind===kind).flatMap(j=>j.result??[]).find(r=>r.status)?.status==='PARTIAL';return <div key={kind}><strong>{{MARKET:'行情',FINANCIAL:'财报',NEWS:'新闻'}[kind]}</strong>{latest&&<p>最近任务：{({COMPLETE:'已完成',PARTIAL:'部分完成',FAILED:'失败',RUNNING:'更新中',QUEUED:'排队中',CANCELLED:'已取消',INTERRUPTED:'运行中断'} as Record<string,string>)[latest.status]??latest.status}{sourcePartial?' · 来源内容不完整':''}{latest.error&&` · ${latest.error}`}</p>}{!observation?<p>尚无保存记录</p>:<><p>{new Date(observation.created_at).toLocaleString('zh-CN')} · {observation.errors.length?'存在来源缺口':'已有观察记录'}</p>{kind==='MARKET'?<MarketSummary payload={observation.payload}/>:kind==='NEWS'?<p>已保存 {String(observation.payload.saved_fact_count)} 条新闻，归并为 {String(observation.payload.unique_event_count)} 个事件</p>:<p>财务状态 {String(observation.payload.status)}，详见下方财务分析</p>}</>}</div>;})}</div>}
   <button disabled={busy} onClick={()=>void action(()=>configure({enabled:!value.settings.enabled}))}>{value.settings.enabled?'暂停日常观察':'启用日常观察'}</button>
   <details open={!expanded||undefined}><summary>更新设置与来源</summary>
   <label><input type="checkbox" disabled={busy} checked={value.settings.news_postclose} onChange={e=>void action(()=>configure({news_postclose:e.target.checked}))}/>盘后新闻观察</label>
   <label><input type="checkbox" disabled={busy} checked={value.settings.financial_postclose??false} onChange={e=>void action(()=>configure({financial_postclose:e.target.checked}))}/>盘后财务观察</label>
   <label><input type="checkbox" disabled={busy} checked={value.settings.market_postclose??false} onChange={e=>void action(()=>configure({market_postclose:e.target.checked}))}/>盘后行情观察</label>
   <label><input type="checkbox" disabled={busy} checked={value.settings.news_refresh} onChange={e=>void action(()=>configure({news_refresh:e.target.checked}))}/>盘后刷新行情、新闻与财务来源（来源另需启用）</label>
   <label><input type="checkbox" disabled={busy} checked={value.settings.classify} onChange={e=>void action(()=>configure({classify:e.target.checked}))}/>受限情绪分类（失败仍保留新闻事实）</label>
   <label>日常情绪版本<select aria-label="日常情绪版本" disabled={busy} value={value.settings.profile} onChange={e=>void action(()=>configure({profile:e.target.value}))}><option value="legacy">原二分类（旧质量门槛未通过）</option><option value="finbert-adaptation-01">中文FinBERT（单公司有限挑战集，非独立有效性）</option></select></label>
   {value.sources.map(source=><p key={source.id}>{source.name} · 来源{source.enabled?'已启用':'已暂停'} <button disabled={busy} onClick={()=>void action(async()=>{await request(`/research/collection-sources/${source.id}/policy`,{enabled:!source.enabled,expected_revision:source.revision,basis:'用户显式暂停或恢复受支持的财报新闻来源'});})}>{source.enabled?'暂停':'恢复'}{source.name}</button> · 连续失败 {source.health.consecutive_failures??0} 次{source.health.retry_after&&` · 可重试时点 ${source.health.retry_after}`}</p>)}
   </details>
   <label><input type="checkbox" checked={refresh} onChange={e=>setRefresh(e.target.checked)}/>本次允许按原预算刷新来源；不勾选只读已保存事实</label>
   <button disabled={busy||!value.settings.enabled} onClick={()=>void action(()=>enqueue('FINANCIAL'))}>请求财务观察更新</button><button disabled={busy||!value.settings.enabled} onClick={()=>void action(()=>enqueue('NEWS'))}>请求新闻观察更新</button>
   <button disabled={busy||!value.settings.enabled} onClick={()=>void action(()=>enqueue('MARKET'))}>请求行情更新</button>
   <p>任务 {value.jobs.length} 条；观察 {value.observations.length} 个。源缓存按实际采集完成时点判断，不用包装时间刷新；同输入复用保存观察。</p>
   <details open={!expanded||undefined}><summary>任务与来源回执</summary>{value.jobs.map(job=><div key={job.job_id}><p>{job.command.kind} · {job.status} · 创建 {job.created_at} · 完成 {job.finished_at??'尚未完成'}{job.cache_reused&&' · 已复用同输入观察'}{job.error&&` · ${job.error}`}{job.errors?.length?` · 局部缺口 ${job.errors.join('；')}`:''}</p>{job.result?.map((source,index)=><p key={index}>{source.source} · {source.status??source.refresh}</p>)}{job.scheduled_checkpoint&&<p>登记检查点 {job.scheduled_checkpoint}；实际执行时点单列，不代表离线时在线。</p>}{['QUEUED','RUNNING'].includes(job.status)&&<button disabled={busy} onClick={()=>void action(async()=>{await request(`/observation-update-jobs/${job.job_id}/cancel`,{});})}>取消观察任务 {job.job_id.slice(0,8)}</button>}</div>)}
   {value.observations.map(observation=><details key={observation.observation_id}><summary>{observation.kind} · {observation.evidence_kind==='METHOD_CASE'?'METHOD工程样例':observation.evidence_kind==='REAL_SAVED_OBSERVATION'?'实际保存来源观察':'来源资格未验证'} · {observation.created_at}</summary><p>首次数据截止 {observation.known_by} · 观察 {observation.observation_id}</p>{observation.kind==='NEWS'?<p>已保存新闻 {String(observation.payload.saved_fact_count)} 条 / 唯一事件 {String(observation.payload.unique_event_count)} 个；{observation.payload.classification_run_id?'已有受限分类，原模型质量限制保留':'本次仅事实观察，未生成新分类'}</p>:observation.kind==='MARKET'?<MarketSummary payload={observation.payload}/>:<p>财务观察 {String(observation.payload.status)} · 原事实截止 {String(observation.payload.source_known_by)} · 版本 {String(observation.payload.financial_observation_id)}</p>}<p>缺口 {observation.errors.join('；')||'本次无局部执行错误；来源与模型有效性限制仍保留'}</p></details>)}
   </details>
   <details><summary>查看原worker与离线覆盖回执</summary><p>原后台进程 {value.worker.worker_state} · 租约上限 {value.worker.worker_limit} · 实际会话 {value.offline_coverage.sessions.length} 次</p><p>离线或心跳缺席 {value.offline_coverage.gaps.length} 段；不重建历史预测、不补发过期机会。</p>{value.offline_coverage.gaps.slice(-10).map((gap,index)=><p key={index}>{gap.start} 至 {gap.end} · {gap.reason}</p>)}{Object.keys(value.health).length>0&&<pre>局部执行缺口 {JSON.stringify(value.health,null,2)}</pre>}</details>
  </section>}{error&&<p role="alert">{error}</p>}
 </details>;
}
