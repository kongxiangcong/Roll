import {useState} from 'react';
import {request} from '../api';
type Saved={diagnostic_id:string;recorded_at:string;G5_status:string;scenarios:{scenario_id:string;fees_yuan:string;economics:{net_return:number|null;maximum_drawdown:number|null};entry_attempts:unknown[]}[]};
const percent=(v:number|null)=>v===null?'未知':(v*100).toFixed(2)+'%';
export function SuccessorEntryStressPanel({stressId}:{stressId:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/successor-cost-stresses/'+stressId+'/entry-stress',current=records.find(r=>r.diagnostic_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const result=await request<Saved>(base,{idempotency_key:crypto.randomUUID(),basis:'已登记入场延迟与0/50/100%成交压力；只作METHOD诊断'});setRecords([...records,result]);setSelected(result.diagnostic_id);}
  async function load(){const values=await request<Saved[]>(base);setRecords(values);setSelected(values.at(-1)?.diagnostic_id??'');}
  return <details><summary>入场延迟与部分成交压力</summary><p>六个固定场景只改变BUY/ADD入场。早退和到期退出保持原规则；每笔实际新入场仍保留原lot期限。默认场景核对旧保存状态，漏会话不借用远期行情。</p><p>部分成交剩余预留在单次尝试后释放，不自动重报；原政策后续ADD仍可能发生。尚无基准联合压力或独立支持，不授G5通过。</p>
    <button disabled={busy} onClick={()=>void action(create)}>运行保存前缀的入场压力</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的入场压力</button>
    {busy&&<p role="status">正在核对原状态并计算固定入场场景…</p>}
    {!!records.length&&<label>入场压力版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.diagnostic_id} value={r.diagnostic_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD入场压力 {current.scenarios.length}项 · G5 {current.G5_status} · NOT_GRANTED</p><div className="reference-table"><table><thead><tr><th>固定场景</th><th>成交费用（元）</th><th>完整窗口收益</th><th>最大回撤</th></tr></thead><tbody>{current.scenarios.map(s=><tr key={s.scenario_id}><td>{s.scenario_id}</td><td>{s.fees_yuan}</td><td>{percent(s.economics.net_return)}</td><td>{percent(s.economics.maximum_drawdown)}</td></tr>)}</tbody></table></div>
      <details><summary>委托数量、剩余释放、各lot与未知依据</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-entry-stresses/'+current.diagnostic_id+'/replay',{});setNotice(result.matches_original?'入场压力原前缀重放一致':'入场压力重放不一致');})}>重放保存的入场压力</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
