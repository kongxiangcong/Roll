import {useState} from 'react';
import {request} from '../api';

type Company={company_state_reported:string;listing_date_reported:string|null;effective_at:string|null;raw_hash:string;received_at:string};
type Suspension={reported_start_date:string;reported_end_date:string|null;resume_date:null;reason?:string;stop_reason_reported?:string;raw_hash:string;received_at:string};
type Evidence={state:string;known_by:string;negative_coverage_verified:boolean;company_observations:Company[];suspension_observations:Suspension[];gaps:string[]};

export function StatusEvidencePanel({instrument}:{instrument:string}){
  const [cutoff,setCutoff]=useState(''),[rows,setRows]=useState<Evidence[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [queried,setQueried]=useState(false);
  async function inspect(){
    setBusy(true);setError('');setRows([]);setQueried(false);
    try{
      const plans=await request<{plan_id:string;instrument:string}[]>('/research/collections');
      const knownBy=cutoff?new Date(cutoff).toISOString():new Date().toISOString();
      const results=await Promise.all(plans.filter(p=>p.instrument===instrument).map(p=>request<Evidence>(`/research/collections/${p.plan_id}/status-evidence?known_by=${encodeURIComponent(knownBy)}`)));
      setRows(results);setQueried(true);
    }catch(e){setError(String(e));}finally{setBusy(false);}
  }
  return <details className="status-evidence"><summary>查看证券状态来源</summary>
    <label>系统已知截至（留空查询当前）<input type="datetime-local" disabled={busy} value={cutoff} onChange={e=>{setCutoff(e.target.value);setRows([]);setQueried(false);}}/></label>
    <button disabled={busy} onClick={()=>void inspect()}>查询保存的状态依据</button>
    {queried&&!rows.length&&<p>尚无该证券的状态采集计划，交易状态未知。</p>}
    {rows.map((r,i)=><div key={i}>
      <p role="status">完整交易状态未知 · 已知截至 {r.known_by}</p>
      <p className="muted">上市描述和计划停牌区间不证明当前正常或实际复牌。</p>
      {r.company_observations.map((c,j)=><p key={j}>来源报告：{c.company_state_reported} · 上市日期 {c.listing_date_reported??'未知'} · 状态生效时点 {c.effective_at??'未知'} · 接收 {c.received_at} · <a href={`/api/data/archives/${c.raw_hash}`} target="_blank" rel="noreferrer">公司信息原件</a></p>)}
      {r.suspension_observations.map((s,j)=><p key={j}>来源报告停牌区间 {s.reported_start_date} 至 {s.reported_end_date??'未知'} · 实际复牌未知 · {s.reason??s.stop_reason_reported??'原因未提供'} · <a href={`/api/data/archives/${s.raw_hash}`} target="_blank" rel="noreferrer">停牌原件</a></p>)}
      <details><summary>状态来源缺口</summary><ul>{r.gaps.map(g=><li key={g}>{g}</li>)}</ul></details>
    </div>)}
    {error&&<p role="alert">{error}</p>}
  </details>;
}
