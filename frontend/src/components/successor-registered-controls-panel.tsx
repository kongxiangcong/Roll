import {useState} from 'react';
import {request} from '../api';
type Saved={comparison_id:string;recorded_at:string;G4_status:string;timing_contrast:Record<string,string>;controls:Record<string,{economics:{net_return:number|null;maximum_drawdown:number|null};interval_return_difference:number|null;eligibility_gaps:string[];events:unknown[]}>};
const percent=(value:number|null)=>value===null?'不足或未准入':(100*value).toFixed(2)+'%';
export function SuccessorRegisteredControlsPanel({stressId}:{stressId:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/successor-cost-stresses/'+stressId+'/registered-controls',current=records.find(r=>r.comparison_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const result=await request<Saved>(base,{idempotency_key:crypto.randomUUID(),basis:'原登记基准保留退出与热身规则；同一METHOD窗口、现金、费用和暴露上限，不授风险匹配'});setRecords([...records,result]);setSelected(result.comparison_id);}
  async function load(){const values=await request<Saved[]>(base);setRecords(values);setSelected(values.at(-1)?.comparison_id??'');}
  return <details><summary>原登记基准与期限差异</summary><p>空初始持仓下沿用原CASH、START_HOLD、MA5_MA20算法。START_HOLD不自动退出，MA期限从观察算起；v2新lot期限从入场算起。只作METHOD描述，不授风险匹配。</p><p>缺失位置不压缩；MA运行前历史和执行支持不足时，不裁掉热身段来计算完整窗口差值。</p>
    <button disabled={busy} onClick={()=>void action(create)}>运行原登记基准参照</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的原基准参照</button>
    {busy&&<p role="status">正在核对原算法和保存前缀…</p>}
    {!!records.length&&<label>原基准参照版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.comparison_id} value={r.comparison_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD原登记基准 · G4 {current.G4_status} · 风险匹配未授予 · NOT_GRANTED</p><div className="reference-table"><table><thead><tr><th>原基准</th><th>保存区间收益</th><th>最大回撤</th><th>候选减基准</th><th>支持缺口</th></tr></thead><tbody>{Object.entries(current.controls).map(([name,c])=><tr key={name}><td>{name}</td><td>{percent(c.economics.net_return)}</td><td>{percent(c.economics.maximum_drawdown)}</td><td>{percent(c.interval_return_difference)}</td><td>{c.eligibility_gaps.length}</td></tr>)}</tbody></table></div>
      <details><summary>期限对照、实际算法成交与未准入依据</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-registered-controls/'+current.comparison_id+'/replay',{});setNotice(result.matches_original?'原登记基准归档重放一致':'原基准重放不一致');})}>重放保存的原基准参照</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
