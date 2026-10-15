import {useState} from 'react';
import {request} from '../api';
import {SuccessorCompletionCheckPanel} from './successor-completion-check-panel';
type Saved={joint_review_id:string;recorded_at:string;validation_verdict:string;bound_components:string[];gates:Record<string,{status:string;reasons:string[]}>};
export function SuccessorJointReviewPanel({reviewId,stressId}:{reviewId:string;stressId:string}){
  const [choices,setChoices]=useState<{joint_id:string;recorded_at:string}[]>([]),[joint,setJoint]=useState(''),[records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/successor-evidence-reviews/'+reviewId+'/joint-review',current=records.find(r=>r.joint_review_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const result=await request<Saved>(base,{joint_id:joint,idempotency_key:crypto.randomUUID(),basis:'新版本绑定同源联合压力，原汇总和重放保持不变，不授资格'});setRecords([...records,result]);setSelected(result.joint_review_id);}
  async function load(){const saved=await request<Saved[]>(base);setRecords(saved);setSelected(saved.at(-1)?.joint_review_id??'');}
  return <details><summary>将联合压力绑定至此汇总</summary><p>创建包含联合场景的新版本。原汇总及其重放保留；相同前缀和协议才可绑定，仍不授风险匹配或资格。</p>
    <button disabled={busy} onClick={()=>void action(async()=>setChoices(await request<typeof choices>('/research/successor-cost-stresses/'+stressId+'/joint-stress')))}>读取可绑定联合压力</button>
    <label>汇总扩展联合压力<select aria-label="汇总扩展联合压力" disabled={busy} value={joint} onChange={e=>setJoint(e.target.value)}><option value="">选择已保存联合压力</option>{choices.map(c=><option key={c.joint_id} value={c.joint_id}>{c.recorded_at}</option>)}</select></label>
    <button disabled={busy||!joint} onClick={()=>void action(create)}>保存联合证据汇总新版本</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的联合汇总版本</button>
    {busy&&<p role="status">正在核对原汇总与联合压力来源…</p>}
    {!!records.length&&<label>联合汇总版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.joint_review_id} value={r.joint_review_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD联合证据汇总 · {current.validation_verdict} · NOT_GRANTED</p><p>已绑定 {current.bound_components.length} 类证据；原汇总不变，完整冻结未授予。</p><ul>{Object.entries(current.gates).map(([name,g])=><li key={name}>{name} · {g.status}</li>)}</ul><details><summary>新版本来源与门槛缺口</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-joint-reviews/'+current.joint_review_id+'/replay',{});setNotice(result.matches_original?'联合汇总新版本重放一致':'联合汇总重放不一致');})}>重放联合证据汇总新版本</button>
      <SuccessorCompletionCheckPanel key={current.joint_review_id} jointReviewId={current.joint_review_id} stressId={stressId}/>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
