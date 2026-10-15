import {useState} from 'react';
import {request} from '../api';
import {SuccessorTimeSegmentsPanel} from './successor-time-segments-panel';
type Scenario={component:string;fees_yuan:string;economics:{net_return:number|null;maximum_drawdown:number|null};input_gaps:unknown[]};
type Saved={stress_id:string;shadow_revision:number;recorded_at:string;scenarios:Scenario[];remaining_components:string[];G5_status:string};
const percent=(v:number|null)=>v===null?'未知':(v*100).toFixed(2)+'%';
export function SuccessorCostStressPanel({freezeId,fingerprint}:{freezeId:string;fingerprint:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const current=records.find(r=>r.stress_id===selected),base='/research/policy-successor-freezes/'+freezeId;
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const state=await request<{revision:number}>(base+'/shadow');const result=await request<Saved>(base+'/cost-stress',{
    expected_complete_protocol_fingerprint:fingerprint,expected_revision:state.revision,idempotency_key:crypto.randomUUID(),basis:'用户查看既定费用网格下同一METHOD保存前缀的敏感性，不选择赢家或授予G5'});
    setRecords([...records,result]);setSelected(result.stress_id);}
  async function load(){const saved=await request<Saved[]>(base+'/cost-stress');setRecords(saved);setSelected(saved.at(-1)?.stress_id??'');}
  return <details><summary>已登记费用压力诊断</summary><p>固定三档佣金与三档滑点，逐项改变，其余政策、帧和各lot期限保持原冻结值。最多200帧，30秒；仅METHOD敏感性，不是实际费用或G5通过。</p>
    <button disabled={busy} onClick={()=>void action(create)}>诊断保存前缀的费用压力</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的费用诊断</button>
    {busy&&<p role="status">正在核对保存前缀或读取原件…</p>}
    {!!records.length&&<label>费用诊断版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.stress_id} value={r.stress_id}>{r.recorded_at} · 前缀{r.shadow_revision}</option>)}</select></label>}
    {current&&<><p>METHOD费用场景 {current.scenarios.length}项 · 前缀{current.shadow_revision} · G5 {current.G5_status} · NOT_GRANTED</p>
      <div className="reference-table"><table><thead><tr><th>已冻结费用场景</th><th>成交费用（元）</th><th>净值收益率</th><th>最大回撤</th><th>输入缺口</th></tr></thead><tbody>{current.scenarios.map(s=><tr key={s.component}><td>{s.component}</td><td>{s.fees_yuan}</td><td>{percent(s.economics.net_return)}</td><td>{percent(s.economics.maximum_drawdown)}</td><td>{s.input_gaps.length}</td></tr>)}</tbody></table></div>
      <details><summary>结果原件、输入指纹与剩余G5条件</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-cost-stresses/'+current.stress_id+'/replay',{});setNotice(result.matches_original?'费用诊断原前缀重放一致':'费用诊断重放不一致');})}>重放保存的费用诊断</button>
      <SuccessorTimeSegmentsPanel key={current.stress_id} stressId={current.stress_id}/>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
