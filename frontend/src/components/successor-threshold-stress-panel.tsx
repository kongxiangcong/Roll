import {useState} from 'react';
import {request} from '../api';
type Saved={diagnostic_id:string;recorded_at:string;status:string;G5_status?:string;scenarios?:{entry_threshold:string;support_threshold:string;economics:{net_return:number|null;maximum_drawdown:number|null};hard_failures:string[]}[];method_attempt_manifest?:{attempts:unknown[]};research_attempt_manifest:{attempts:unknown[]}};
const percent=(v:number|null)=>v===null?'未知':(100*v).toFixed(2)+'%';
export function SuccessorThresholdStressPanel({stressId}:{stressId:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/successor-cost-stresses/'+stressId+'/threshold-stress',current=records.find(r=>r.diagnostic_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const result=await request<Saved>(base,{idempotency_key:crypto.randomUUID(),basis:'原登记三档入场阈值复用保存概率，支持阈值固定，METHOD逐档登记，不拟合或选赢家'});setRecords([...records,result]);setSelected(result.diagnostic_id);}
  async function load(){const saved=await request<Saved[]>(base);setRecords(saved);setSelected(saved.at(-1)?.diagnostic_id??'');}
  return <details><summary>已登记入场阈值邻域</summary><p>固定0.55、0.60、0.65三档入场阈值，支持阈值保持原值，复用同一前缀的保存概率。三档全报，不选择赢家，不拟合新模型。</p><p>逐档METHOD尝试与原训练尝试分列，失败/中断不抹掉；整数会话不被登记为训练分区，拟合、校准及SEALED额度不变。</p>
    <button disabled={busy} onClick={()=>void action(create)}>运行已登记入场阈值邻域</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的阈值邻域</button>
    {busy&&<p role="status">正在登记METHOD尝试并核对三档保存概率…</p>}
    {!!records.length&&<label>阈值邻域版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.diagnostic_id} value={r.diagnostic_id}>{r.recorded_at} · {r.status}</option>)}</select></label>}
    {current&&<>{current.status==='SUCCEEDED'?<><p>METHOD入场阈值 {current.scenarios?.length}项 · G5 {current.G5_status} · NOT_GRANTED</p><div className="reference-table"><table><thead><tr><th>入场阈值</th><th>固定支持阈值</th><th>完整窗口收益</th><th>最大回撤</th><th>硬失败</th></tr></thead><tbody>{current.scenarios?.map(s=><tr key={s.entry_threshold}><td>{s.entry_threshold}</td><td>{s.support_threshold}</td><td>{percent(s.economics.net_return)}</td><td>{percent(s.economics.maximum_drawdown)}</td><td>{s.hard_failures.length}</td></tr>)}</tbody></table></div></>:<p>METHOD阈值运行 {current.status} · 结果未准入 · NOT_GRANTED</p>}
      <p>保存时METHOD尝试 {current.method_attempt_manifest?.attempts.length??0} 项；原训练家族尝试 {current.research_attempt_manifest.attempts.length} 项，未新增拟合。</p>
      <details><summary>阈值结果、METHOD尝试与原训练清单</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy||current.status!=='SUCCEEDED'} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-threshold-stresses/'+current.diagnostic_id+'/replay',{});setNotice(result.matches_original?'阈值邻域原前缀重放一致':'阈值邻域重放不一致');})}>重放保存的阈值邻域</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
