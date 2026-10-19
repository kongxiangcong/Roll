import {useState} from 'react';
import {request} from '../api';
type Settings={revision:number;enabled:boolean;news_postclose:boolean;news_refresh:boolean;classify:boolean;profile:string};
type Job={job_id:string;command:{kind:string};status:string;created_at:string;finished_at:string|null;observation_id:string|null;error:string|null;errors?:string[];cache_reused?:boolean;scheduled_checkpoint:string|null};
type Observation={observation_id:string;kind:string;created_at:string;known_by:string;evidence_kind:string;errors:string[];payload:Record<string,unknown>};
type Source={id:string;name:string;enabled:boolean;revision:number;health:{state?:string;consecutive_failures?:number;retry_after?:string}};
type Value={settings:Settings;jobs:Job[];observations:Observation[];sources:Source[];health:Record<string,unknown>;worker:{worker_state:string;worker_limit:number};offline_coverage:{sessions:unknown[];gaps:{start:string;end:string;reason:string}[]}};
export function ObservationUpdatesPanel({instrument}:{instrument:string}){
 const [value,setValue]=useState<Value|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[refresh,setRefresh]=useState(false);
 if(instrument!=='SSE:600362')return null;
 const base=`/observation-updates/${encodeURIComponent(instrument)}`;
 async function query(){setValue(await request<Value>(base));}
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();await query();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function configure(change:Partial<Settings>){if(!value)return;const s=value.settings;await request(base+'/settings',{enabled:s.enabled,news_postclose:s.news_postclose,news_refresh:s.news_refresh,classify:s.classify,profile:s.profile,...change,expected_revision:s.revision,basis:'用户显式配置现有worker上的受限财报新闻观察'});}
 async function enqueue(kind:string){await request(base+'/requests',{kind,refresh_sources:refresh,idempotency_key:crypto.randomUUID(),basis:'用户按需请求财报新闻观察；不启动预测、训练或交易'});}
 return <details className="status-evidence"><summary>日常财报新闻观察</summary>
  <p>复用原后台进程与租约。财报按需更新；新闻可在当前在线交易日15:05后观察，离线缺席不补造当日预测。只发站内变化摘要，外部通知渠道保持既有设置。</p>
  <button disabled={busy} onClick={()=>void action(query)}>查询日常观察状态</button>
  {value&&<section aria-label="日常观察状态">
   <p role="status">日常观察{value.settings.enabled?'已启用':'已暂停'} · 设置版本 {value.settings.revision} · 单任务上限45秒 · 账户与交易资格独立</p>
   <button disabled={busy} onClick={()=>void action(()=>configure({enabled:!value.settings.enabled}))}>{value.settings.enabled?'暂停日常观察':'启用日常观察'}</button>
   <label><input type="checkbox" disabled={busy} checked={value.settings.news_postclose} onChange={e=>void action(()=>configure({news_postclose:e.target.checked}))}/>盘后新闻观察</label>
   <label><input type="checkbox" disabled={busy} checked={value.settings.news_refresh} onChange={e=>void action(()=>configure({news_refresh:e.target.checked}))}/>盘后按原来源预算补取（来源另需启用）</label>
   <label><input type="checkbox" disabled={busy} checked={value.settings.classify} onChange={e=>void action(()=>configure({classify:e.target.checked}))}/>受限情绪分类（失败仍保留新闻事实）</label>
   <label>日常情绪版本<select aria-label="日常情绪版本" disabled={busy} value={value.settings.profile} onChange={e=>void action(()=>configure({profile:e.target.value}))}><option value="legacy">原二分类（旧质量门槛未通过）</option><option value="finbert-adaptation-01">中文FinBERT（单公司有限挑战集，非独立有效性）</option></select></label>
   {value.sources.map(source=><p key={source.id}>{source.name} · 来源{source.enabled?'已启用':'已暂停'} <button disabled={busy} onClick={()=>void action(async()=>{await request(`/research/collection-sources/${source.id}/policy`,{enabled:!source.enabled,expected_revision:source.revision,basis:'用户显式暂停或恢复受支持的财报新闻来源'});})}>{source.enabled?'暂停':'恢复'}{source.name}</button> · 连续失败 {source.health.consecutive_failures??0} 次{source.health.retry_after&&` · 可重试时点 ${source.health.retry_after}`}</p>)}
   <label><input type="checkbox" checked={refresh} onChange={e=>setRefresh(e.target.checked)}/>本次允许按原预算刷新来源；不勾选只读已保存事实</label>
   <button disabled={busy||!value.settings.enabled} onClick={()=>void action(()=>enqueue('FINANCIAL'))}>请求财务观察更新</button><button disabled={busy||!value.settings.enabled} onClick={()=>void action(()=>enqueue('NEWS'))}>请求新闻观察更新</button>
   <p>任务 {value.jobs.length} 条；观察 {value.observations.length} 个。源缓存按实际采集完成时点判断，不用包装时间刷新；同输入复用保存观察。</p>
   {value.jobs.map(job=><div key={job.job_id}><p>{job.command.kind} · {job.status} · 创建 {job.created_at} · 完成 {job.finished_at??'尚未完成'}{job.cache_reused&&' · 已复用同输入观察'}{job.error&&` · ${job.error}`}{job.errors?.length?` · 局部缺口 ${job.errors.join('；')}`:''}</p>{job.scheduled_checkpoint&&<p>登记检查点 {job.scheduled_checkpoint}；实际执行时点单列，不代表离线时在线。</p>}{['QUEUED','RUNNING'].includes(job.status)&&<button disabled={busy} onClick={()=>void action(async()=>{await request(`/observation-update-jobs/${job.job_id}/cancel`,{});})}>取消观察任务 {job.job_id.slice(0,8)}</button>}</div>)}
   {value.observations.map(observation=><details key={observation.observation_id}><summary>{observation.kind} · {observation.evidence_kind==='METHOD_CASE'?'METHOD工程样例':observation.evidence_kind==='REAL_SAVED_OBSERVATION'?'实际保存来源观察':'来源资格未验证'} · {observation.created_at}</summary><p>首次数据截止 {observation.known_by} · 观察 {observation.observation_id}</p>{observation.kind==='NEWS'?<p>已保存新闻 {String(observation.payload.saved_fact_count)} 条 / 唯一事件 {String(observation.payload.unique_event_count)} 个；{observation.payload.classification_run_id?'已有受限分类，原模型质量限制保留':'本次仅事实观察，未生成新分类'}</p>:<p>财务观察 {String(observation.payload.status)} · 原事实截止 {String(observation.payload.source_known_by)} · 版本 {String(observation.payload.financial_observation_id)}</p>}<p>缺口 {observation.errors.join('；')||'本次无局部执行错误；来源与模型有效性限制仍保留'}</p></details>)}
   <details><summary>查看原worker与离线覆盖回执</summary><p>原后台进程 {value.worker.worker_state} · 租约上限 {value.worker.worker_limit} · 实际会话 {value.offline_coverage.sessions.length} 次</p><p>离线或心跳缺席 {value.offline_coverage.gaps.length} 段；不重建历史预测、不补发过期机会。</p>{value.offline_coverage.gaps.slice(-10).map((gap,index)=><p key={index}>{gap.start} 至 {gap.end} · {gap.reason}</p>)}{Object.keys(value.health).length>0&&<pre>局部执行缺口 {JSON.stringify(value.health,null,2)}</pre>}</details>
  </section>}{error&&<p role="alert">{error}</p>}
 </details>;
}
