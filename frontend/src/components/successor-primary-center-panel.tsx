import {useState} from 'react';
import {request} from '../api';
import {SuccessorModelReplayPanel} from './successor-model-replay-panel';
type Saved={binding_id:string;recorded_at:string;bound_center_count:number;validation_verdict:string};
export function SuccessorPrimaryCenterPanel({checkId}:{checkId:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
  const base='/research/successor-completion-checks/'+checkId+'/primary-center-binding',current=records.find(r=>r.binding_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const result=await request<Saved>(base,{idempotency_key:crypto.randomUUID(),basis:'仅绑定原冻结主模型中心身份，不拟合或生成邻域预测'});setRecords([...records,result]);setSelected(result.binding_id);}
  async function load(){const saved=await request<Saved[]>(base);setRecords(saved);setSelected(saved.at(-1)?.binding_id??'');}
  return <details><summary>原冻结主模型中心工件</summary><p>核对 penalty=1、lookback=20 与原模型、特征和校准归档身份。21个收盘价形成20个收益区间；另四个非中心工件仍缺，尚未对齐执行预测或授予邻域压力结论。</p>
    <button disabled={busy} onClick={()=>void action(create)}>绑定原冻结中心工件</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的中心绑定</button>
    {!!records.length&&<label>中心绑定版本<select aria-label="中心绑定版本" value={selected} disabled={busy} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.binding_id} value={r.binding_id}>{r.recorded_at}</option>)}</select></label>}
    {busy&&<p role="status">正在核对原冻结产物…</p>}
    {current&&<><p>主模型中心绑定 {current.bound_center_count}/2 · {current.validation_verdict} · 邻域压力未授予 · NOT_GRANTED</p><details><summary>中心产物与剩余缺口</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-primary-center-bindings/'+current.binding_id+'/replay',{});setNotice(result.matches_original?'中心工件原绑定重放一致':'中心工件重放不一致');})}>重放保存的中心绑定</button>
      <SuccessorModelReplayPanel key={current.binding_id} bindingId={current.binding_id}/>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
