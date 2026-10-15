import {useState} from 'react';
import {request} from '../api';

type Bin={bin:number;count:number;mean_probability:number|null;observed_positive_rate:number|null};
type Phase={status:string;error?:string;mature_unique?:number;excluded?:unknown[];duplicate_keys?:string[];unique_observation_dates?:number;absolute_tolerance?:number;
  library_aligned?:Record<string,number>;library_default?:unknown;saved_metrics?:Record<string,unknown>;differences?:Record<string,number|null>;aligned_bins?:Bin[];accepted_rows?:unknown[];boundary_convention_differs?:boolean};
type Reference={reference_id:string;recorded_at:string;library:{version:string};cutoff:string;source_evidence_kind:string;source_scope:string;phases:Record<string,Phase>};
const names:Record<string,string>={NUMERICALLY_CONSISTENT:'数值一致',CONVENTION_DIFFERENCE_SAMPLE_SELECTION:'口径不同：样本去重',IMPLEMENTATION_DIFFERENCE:'实现差异，需核查',SUPPORT_INSUFFICIENT:'支持不足',SOURCE_INPUT_ERROR:'原始输入错误'};
const number=(value:unknown)=>typeof value==='number'?value.toPrecision(12):'未知';

export function ProbabilityReferencePanel({freezeId,fingerprint}:{freezeId:string;fingerprint:string}){
  const [records,setRecords]=useState<Reference[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  const current=records.find(r=>r.reference_id===selected);
  const base='/research/complete-freezes/'+freezeId+'/probability-reference';
  async function load(){setBusy(true);setError('');setMessage('');try{const saved=await request<Reference[]>(base);setRecords(saved);setSelected(saved.at(-1)?.reference_id??'');}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function compare(){setBusy(true);setError('');setMessage('');try{
    const value=await request<Reference>(base,{expected_complete_protocol_fingerprint:fingerprint,idempotency_key:crypto.randomUUID(),basis:'用户核对旧CAL归档向量；只评分，不拟合、不读SEALED、不改变旧结果'});
    setRecords([...records,value]);setSelected(value.reference_id);
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  async function replay(){if(!current)return;setBusy(true);setError('');try{
    const value=await request<{matches_original:boolean}>('/research/probability-references/'+current.reference_id+'/replay',{});
    setMessage(value.matches_original?'原工件校验一致 · 未重新评分':'原工件校验失败');
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  return <details className="probability-reference"><summary>概率计算独立库核验</summary>
    <p>CAL原窗口诊断 · 未验证独立校准有效性</p><p>等权按事件去重，标签需在原截止前成熟。先固定1e-12绝对容差，再对齐旧方法的1e-15逐类别概率下限与左闭分箱；库默认结果另列。没有交叉验证或新校准拟合。</p>
    <button disabled={busy} onClick={()=>void compare()}>核对已保存CAL概率</button><button disabled={busy} onClick={()=>void load()}>查看保存的概率核验</button>
    {busy&&<p role="status">正在评分或读取归档…</p>}
    {!!records.length&&<label>保存的数值核验<select value={selected} disabled={busy} onChange={e=>{setSelected(e.target.value);setMessage('');}}>{records.map(r=><option key={r.reference_id} value={r.reference_id}>{r.recorded_at} · {r.source_evidence_kind}</option>)}</select></label>}
    {current&&<><p>scikit-learn {current.library.version} · NOT_GRANTED</p><p>{current.source_evidence_kind} · 原标签可知截至 {current.cutoff}</p>
      {Object.entries(current.phases).map(([name,p])=><article key={name}><h4>{name==='BEFORE_CALIBRATION'?'校准前':'校准后'} · {names[p.status]??p.status}</h4>
        <p>成熟唯一 {p.mature_unique??0} · 观察日期 {p.unique_observation_dates??0} · 去重 {p.duplicate_keys?.length??0} · 未成熟/未知排除 {p.excluded?.length??0}</p>
        {p.library_aligned&&<div className="reference-table"><table><thead><tr><th>指标</th><th>原保存值</th><th>库对齐值</th><th>差值</th></tr></thead><tbody>{[['brier','Brier'],['base_rate_brier','基率Brier'],['log_loss','Log-loss（自然对数）']].map(([key,label])=><tr key={key}><td>{label}</td><td>{number(p.saved_metrics?.[key])}</td><td>{number(p.library_aligned?.[key])}</td><td>{number(p.differences?.[key])}</td></tr>)}</tbody></table></div>}
        {p.aligned_bins&&<details><summary>对齐分箱与样本数（不是独立支持）</summary><div className="reference-table"><table><thead><tr><th>概率分箱</th><th>计数</th><th>平均概率</th><th>正例频率</th></tr></thead><tbody>{p.aligned_bins.map(b=><tr key={b.bin}><td>{b.bin/5}—{(b.bin+1)/5}{b.bin===4?'（含1）':'（右端不含）'}</td><td>{b.count}</td><td>{b.mean_probability===null?'未知':(100*b.mean_probability).toFixed(2)+'%'}</td><td>{b.observed_positive_rate===null?'未知':(100*b.observed_positive_rate).toFixed(2)+'%'}</td></tr>)}</tbody></table></div></details>}
        {p.boundary_convention_differs&&<p>库默认分箱边界口径不同；上表为对齐结果。</p>}
        <details><summary>库默认口径与成熟、去重、排除明细</summary><pre>{JSON.stringify({library_default:p.library_default,accepted_rows:p.accepted_rows,excluded:p.excluded,duplicate_keys:p.duplicate_keys},null,2)}</pre></details>
        {p.error&&<p role="alert">{p.error}</p>}
      </article>)}
      <button disabled={busy} onClick={()=>void replay()}>校验保存的概率核验工件</button>
      <p>仅验证数值实现，不改变FITTED_UNVALIDATED、统计假设或G1—G7门槛。</p>
    </>}{message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
