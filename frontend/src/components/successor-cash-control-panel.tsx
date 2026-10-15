import {useState} from 'react';
import {request} from '../api';
type Control={control_id:string;recorded_at:string;G4_status:string;candidate:{economics:{net_return:number|null};unknown_nav_sessions:number[];maximum_observed_gross_exposure_fraction:string|null};cash:{economics:{net_return:number|null};gross_exposure_fraction:string};interval_return_difference:number|null};
const percent=(value:number|null)=>value===null?'未知':(value*100).toFixed(2)+'%';
export function SuccessorCashControlPanel({stressId}:{stressId:string}){
  const [records,setRecords]=useState<Control[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const current=records.find(r=>r.control_id===selected),base='/research/successor-cost-stresses/'+stressId+'/cash-control';
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const saved=await request<Control>(base,{idempotency_key:crypto.randomUUID(),basis:'同一空初始持仓和现金的CASH控制；零暴露差异仅描述，不授风险匹配'});setRecords([...records,saved]);setSelected(saved.control_id);}
  async function load(){const saved=await request<Control[]>(base);setRecords(saved);setSelected(saved.at(-1)?.control_id??'');}
  return <details><summary>同窗口CASH控制</summary><p>只接受明确空初始持仓，保留原初始现金，不假定清仓、利息或成交。CASH零暴露与持仓候选风险不同，差值不能授风险匹配或G4通过。</p>
    <button disabled={busy} onClick={()=>void action(create)}>保存原窗口CASH控制</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的CASH控制</button>
    {busy&&<p role="status">正在读取原轨迹…</p>}
    {!!records.length&&<label>CASH控制版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.control_id} value={r.control_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD CASH控制 · G4 {current.G4_status} · 风险未匹配 · NOT_GRANTED</p><p>候选区间收益 {percent(current.candidate.economics.net_return)} · CASH区间收益 {percent(current.cash.economics.net_return)} · 描述性差值 {percent(current.interval_return_difference)}</p><p>CASH暴露0% · 候选已观察最大暴露 {current.candidate.maximum_observed_gross_exposure_fraction===null?'未知':percent(Number(current.candidate.maximum_observed_gross_exposure_fraction))} · 候选未知净值 {current.candidate.unknown_nav_sessions.length}</p>
      <details><summary>完整会话、缺失与方法原件</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-cash-controls/'+current.control_id+'/replay',{});setNotice(result.matches_original?'CASH控制原工件重放一致':'CASH控制重放不一致');})}>重放保存的CASH控制</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
