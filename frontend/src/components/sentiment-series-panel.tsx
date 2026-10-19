import {useEffect,useState} from 'react';
import {request} from '../api';

type SourceRun={run_id:string;model:string;finished_at:string;profile:string;quality_gate_passed:boolean};
type Saved={series_id:string;created_at:string;known_by:string;model:string;source_run_id:string};
type Day={trade_date:string;status:string;unique_events:number;source_fact_count:number;counts:Record<string,number|null>;proportions:Record<string,number|null>;reject_count:number;coverage:number|null;revision_event_count:number};
type Series={series_id:string;model:string;known_by:string;created_at:string;labels_supported:string[];quality_gate_passed:boolean;days:Day[];deferred_events:{event_id:string;checkpoint_at:string|null;gap:string|null}[];source_coverage:{archived_facts:number;unique_recorded_events:number;source_ids:string[]};source_run_ids:string[];semantics:{reference_sha256:string;news_grouping_version:number};membership_boundary:string|null;evidence_kind:string;limitations:string[]};
const STATUS:Record<string,string>={OBSERVED:'已观察',NO_OBSERVATIONS:'无可消费归档观察',CLOSED:'休市',NOT_REACHED:'检查点未到',CALENDAR_UNKNOWN:'日历覆盖未知',VERSION_NOT_AVAILABLE:'此版本当时尚无分类'};
function shanghai(value:string){return new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});}
function today(){return new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'});}
function weekStart(){const date=new Date(today()+'T00:00:00+08:00');date.setUTCDate(date.getUTCDate()-6);return date.toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'});}

export function SentimentSeriesPanel({instrument,initialRunId}:{instrument:string;initialRunId?:string}){
 const base=`/market/sentiment-series/${encodeURIComponent(instrument)}`;
 const [runs,setRuns]=useState<SourceRun[]>([]),[selected,setSelected]=useState(initialRunId??''),[start,setStart]=useState(weekStart),[end,setEnd]=useState(today),[cutoff,setCutoff]=useState('');
 const [saved,setSaved]=useState<Saved[]>([]),[value,setValue]=useState<Series|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{if(initialRunId)setSelected(initialRunId);},[initialRunId]);
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function versions(){const rows=await request<SourceRun[]>(base+'/source-runs');setRuns(rows);if(!selected&&rows.length)setSelected(rows[0].run_id);}
 async function history(){const rows=await request<Saved[]>(base+'/snapshots');setSaved(rows);if(rows.length)setValue(await request<Series>(`/market/sentiment-series/runs/${rows[0].series_id}`));else setError('尚无保存的事件序列。');}
 async function build(){const result=await request<Series>(base,{idempotency_key:crypto.randomUUID(),basis:'用户显式重建已保存分类的事件观察；不是历史预测归档',source_run_id:selected,start_date:start,end_date:end,...(cutoff?{known_by:cutoff+'+08:00'}:{})});setValue(result);setSaved(await request<Saved[]>(base+'/snapshots'));}
 return <details><summary>事件情绪序列</summary>
  <p>按已保存版本重建观察。检查点为上海时间 15:05；盘后或休市内容顺延，不倒填新闻的历史发布日期。新事件按唯一事件计数，修订更新单列，转载不增加权重。</p>
  <button disabled={busy} onClick={()=>void action(versions)}>查询分类版本</button>
  <label>分类版本<select aria-label="情绪序列分类版本" value={selected} onChange={e=>setSelected(e.target.value)}><option value="">请选择已完成的分类</option>{runs.map(run=><option key={run.run_id} value={run.run_id}>{shanghai(run.finished_at)} · {run.profile} · {run.quality_gate_passed?'有限门槛通过':'原质量限制保留'}</option>)}</select></label>
  <label>开始日期<input aria-label="情绪序列开始日期" type="date" value={start} onChange={e=>setStart(e.target.value)}/></label>
  <label>结束日期<input aria-label="情绪序列结束日期" type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label>
  <label>数据可得截止（上海时间，可留空使用当前时点）<input aria-label="情绪序列数据截止" type="datetime-local" step="1" value={cutoff} onChange={e=>setCutoff(e.target.value)}/></label>
  <button disabled={busy||!selected} onClick={()=>void action(build)}>保存事件序列</button><button disabled={busy} onClick={()=>void action(history)}>查询已保存序列</button>
  {saved.length>0&&<label>最近保存的版本<select aria-label="已保存情绪序列版本" value={value?.series_id??''} onChange={e=>void action(async()=>setValue(await request<Series>(`/market/sentiment-series/runs/${e.target.value}`)))}>{saved.map(row=><option key={row.series_id} value={row.series_id}>{shanghai(row.created_at)} · {row.model}</option>)}</select></label>}
  {value&&<section aria-label="事件情绪序列结果">
   <p role="status">{value.evidence_kind==='METHOD_CASE'?'METHOD工程样例':value.evidence_kind==='REAL_SAVED_OBSERVATION_RECONSTRUCTION'?'实际归档观察重建':'来源资格未验证'} · 模型 {value.model} · 数据截至 {shanghai(value.known_by)} · 实际创建 {shanghai(value.created_at)}</p>
   <p>已归档 {value.source_coverage.archived_facts} 条来源记录 / {value.source_coverage.unique_recorded_events} 个已记录事件；不代表完整新闻覆盖。分类质量限制{value.quality_gate_passed?'：有限挑战集通过，仍非独立有效性验证':'：原未通过结论保留'}。</p>
   <p>待消费事件 {value.deferred_events.length}；未到检查点或日历未知时不输出未来情绪计数。无观察与中性不同。</p>
   {value.membership_boundary&&<p>事件关联发生变化，本版本开启后继序列；先前序列保持原样。</p>}
   {value.days.map(day=><div key={day.trade_date}><p><strong>{day.trade_date} · {STATUS[day.status]??day.status}</strong></p><p>唯一新事件 {day.unique_events} · 来源 {day.source_fact_count} 条 · 正向 {day.counts.POSITIVE??'—'} · 负向 {day.counts.NEGATIVE??'—'} · 中性 {value.labels_supported.includes('NEUTRAL')?(day.counts.NEUTRAL??'—'):'未支持'} · 拒判 {day.reject_count} · 覆盖 {day.coverage===null?'—':`${Math.round(day.coverage*100)}%`} · 修订更新 {day.revision_event_count}</p><p>各类占唯一新事件比例（含拒判分母）：{['POSITIVE','NEGATIVE','NEUTRAL'].map((label,index)=>`${['正向','负向','中性'][index]} ${day.proportions?.[label]===null||day.proportions?.[label]===undefined?'—':`${Math.round(day.proportions[label]!*100)}%`}`).join(' · ')}</p></div>)}
   {value.deferred_events.length>0&&<details><summary>查看待消费与覆盖缺口</summary>{value.deferred_events.map((row,index)=><p key={row.event_id+index}>{row.event_id} · {row.checkpoint_at?shanghai(row.checkpoint_at):'消费日历未知'}{row.gap&&` · ${row.gap}`}</p>)}</details>}
   <details><summary>查看序列版本与限制</summary><p>序列 {value.series_id} · 模型版本 {value.semantics.reference_sha256} · 去重版本 {value.semantics.news_grouping_version} · 分类回执 {value.source_run_ids.join('、')}</p><p>{value.limitations.join('；')}</p></details>
  </section>}
  {error&&<p role="alert">{error}</p>}
 </details>;
}
