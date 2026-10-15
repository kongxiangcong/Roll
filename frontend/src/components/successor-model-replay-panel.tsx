import {useState} from 'react';
import {request} from '../api';
type Saved={replay_id:string;recorded_at:string;calendar_session_count:number;prediction_count:number;validation_verdict:string};
export function SuccessorModelReplayPanel({bindingId}:{bindingId:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
  const base='/research/successor-primary-center-bindings/'+bindingId+'/model-execution-replay',current=records.find(r=>r.replay_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const result=await request<Saved>(base,{idempotency_key:crypto.randomUUID(),basis:'原CAL校准后预测与完整日历的独立METHOD执行回放；保留人工轨迹'});setRecords([...records,result]);setSelected(result.replay_id);}
  async function load(){const saved=await request<Saved[]>(base);setRecords(saved);setSelected(saved.at(-1)?.replay_id??'');}
  return <details><summary>原CAL模型预测的独立执行回放</summary><p>使用已保存的完整CAL日历和校准后预测；无预测日期保持无预测。此处复用校准拟合窗口，不能证明独立有效性或真实来源准入；原人工轨迹保留。</p>
    <button disabled={busy} onClick={()=>void action(create)}>运行原CAL预测执行回放</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的模型执行回放</button>
    {!!records.length&&<label>模型执行回放版本<select aria-label="模型执行回放版本" value={selected} disabled={busy} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.replay_id} value={r.replay_id}>{r.recorded_at}</option>)}</select></label>}
    {busy&&<p role="status">正在按原日历执行已保存预测…</p>}
    {current&&<><p>METHOD模型执行 · 日历{current.calendar_session_count} · 预测{current.prediction_count} · {current.validation_verdict} · NOT_GRANTED</p><details><summary>日历、逐日输入与执行结果</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-model-execution-replays/'+current.replay_id+'/replay',{});setNotice(result.matches_original?'模型执行原日历重放一致':'模型执行重放不一致');})}>重放保存的模型执行</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
