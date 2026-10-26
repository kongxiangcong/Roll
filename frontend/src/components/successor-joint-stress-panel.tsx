import {useState} from 'react';
import {request} from '../api';
type Saved={joint_id:string;recorded_at:string;G5_status:string;scenarios:{scenario_id:string;candidate:{economics:{net_return:number|null}};controls:Record<string,{interval_return_difference:number|null}>}[]};
const percent=(v:number|null)=>v===null?'不足或未准入':(v*100).toFixed(2)+'%';
export function SuccessorJointStressPanel({stressId}:{stressId:string}){
  const [controls,setControls]=useState<{comparison_id:string;recorded_at:string}[]>([]),[entries,setEntries]=useState<{diagnostic_id:string;recorded_at:string}[]>([]),[control,setControl]=useState(''),[entry,setEntry]=useState('');
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/successor-cost-stresses/'+stressId,current=records.find(r=>r.joint_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function choices(){const [c,e]=await Promise.all([request<typeof controls>(base+'/registered-controls'),request<typeof entries>(base+'/entry-stress')]);setControls(c);setEntries(e);}
  async function create(){const result=await request<Saved>(base+'/joint-stress',{controls_id:control,entry_id:entry,idempotency_key:crypto.randomUUID(),basis:'同一保存前缀的十二固定候选/原基准场景；保留期限与缺口，不授风险匹配'});setRecords([...records,result]);setSelected(result.joint_id);}
  async function load(){const saved=await request<Saved[]>(base+'/joint-stress');setRecords(saved);setSelected(saved.at(-1)?.joint_id??'');}
  return <details><summary>同场景候选与原基准压力</summary><p>同一费用和入场场景下同时报告候选、CASH、START_HOLD和MA5_MA20。原持有期限差异保留，MA前置历史不足不裁窗；只显示可计算的描述差值，风险匹配和独立区间未授予。</p>
    <button disabled={busy} onClick={()=>void action(choices)}>读取同前缀对照工件</button>
    <label>联合压力原基准<select aria-label="联合压力原基准" disabled={busy} value={control} onChange={e=>setControl(e.target.value)}><option value="">选择保存的原基准</option>{controls.map(c=><option key={c.comparison_id} value={c.comparison_id}>{c.recorded_at}</option>)}</select></label>
    <label>联合压力入场版本<select aria-label="联合压力入场版本" disabled={busy} value={entry} onChange={e=>setEntry(e.target.value)}><option value="">选择保存的入场压力</option>{entries.map(e=><option key={e.diagnostic_id} value={e.diagnostic_id}>{e.recorded_at}</option>)}</select></label>
    <button disabled={busy||!control||!entry} onClick={()=>void action(create)}>运行同场景候选基准压力</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的联合压力</button>
    {busy&&<p role="status">正在校验同源工件并运行固定基准场景…</p>}
    {!!records.length&&<label>联合压力版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.joint_id} value={r.joint_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD联合压力 {current.scenarios.length}项 · G5 {current.G5_status} · NOT_GRANTED</p><div className="reference-table"><table><thead><tr><th>固定场景</th><th>候选收益</th><th>候选减CASH</th><th>候选减START_HOLD</th><th>候选减MA</th></tr></thead><tbody>{current.scenarios.map(s=><tr key={s.scenario_id}><td>{s.scenario_id}</td><td>{percent(s.candidate.economics.net_return)}</td>{['CASH','START_HOLD','MA5_MA20'].map(name=><td key={name}>{percent(s.controls[name].interval_return_difference)}</td>)}</tr>)}</tbody></table></div>
      <details><summary>联合场景原件、基准成交与不可比依据</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-joint-stresses/'+current.joint_id+'/replay',{});setNotice(result.matches_original?'联合压力原工件重放一致':'联合压力重放不一致');})}>重放保存的联合压力</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
