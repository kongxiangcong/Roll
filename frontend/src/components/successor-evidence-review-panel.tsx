import {useState} from 'react';
import {request} from '../api';
import {SuccessorJointReviewPanel} from './successor-joint-review-panel';
const names=['segments','cash','controls','entry','probability'] as const;
type Name=typeof names[number];
const labels:Record<Name,string>={segments:'时间分段',cash:'CASH控制',controls:'原登记基准',entry:'入场压力',probability:'CAL概率'};
type Saved={review_id:string;recorded_at:string;validation_verdict:string;shadow_revision:number;bound_components:string[];gates:Record<string,{status:string;reasons:string[]}>};
type Option={id:string;date:string};
export function SuccessorEvidenceReviewPanel({stressId,freezeId}:{stressId:string;freezeId:string}){
  const [options,setOptions]=useState<Partial<Record<Name,Option[]>>>({}),[chosen,setChosen]=useState<Partial<Record<Name,string>>>({});
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/successor-cost-stresses/'+stressId,current=records.find(r=>r.review_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function choices(){
    const paths={segments:[base+'/time-segments','segmentation_id'],cash:[base+'/cash-control','control_id'],controls:[base+'/registered-controls','comparison_id'],entry:[base+'/entry-stress','diagnostic_id'],probability:['/research/policy-successor-freezes/'+freezeId+'/probability-evidence','binding_id']};
    const values=await Promise.all(names.map(async name=>{const [url,key]=paths[name];const rows=await request<Record<string,string>[]>(url);return {name,items:rows.map(r=>({id:r[key],date:r.recorded_at}))};}));
    const next:Partial<Record<Name,Option[]>>={};for(const v of values)next[v.name]=v.items;setOptions(next);
  }
  async function create(){const command:Record<string,string|null>={idempotency_key:crypto.randomUUID(),basis:'显式绑定同一前缀的保存证据；CAL单列、保留硬失败与未知，不授资格'};for(const name of names)command[name+'_id']=chosen[name]||null;
    const result=await request<Saved>(base+'/evidence-review',command);setRecords([...records,result]);setSelected(result.review_id);}
  async function load(){const saved=await request<Saved[]>(base+'/evidence-review');setRecords(saved);setSelected(saved.at(-1)?.review_id??'');}
  return <details><summary>当前保存证据与验证缺口</summary><p>选择同一前缀已保存的分段、控制与压力结果；未选择项明确列缺。CAL概率单独报告，不拼成同窗口独立支持。汇总保留已知硬失败，其余INCONCLUSIVE，不授完整冻结或资格。</p>
    <button disabled={busy} onClick={()=>void action(choices)}>读取可绑定证据</button>
    {names.map(name=><label key={name}>汇总{labels[name]}证据<select aria-label={'汇总'+labels[name]+'证据'} disabled={busy} value={chosen[name]??''} onChange={e=>setChosen({...chosen,[name]:e.target.value})}><option value="">未绑定</option>{(options[name]??[]).map(o=><option key={o.id} value={o.id}>{o.date}</option>)}</select></label>)}
    <button disabled={busy} onClick={()=>void action(create)}>保存选定证据的验证汇总</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的验证汇总</button>
    {busy&&<p role="status">正在校验保存证据的来源和绑定…</p>}
    {!!records.length&&<label>证据汇总版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.review_id} value={r.review_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD证据汇总 · 前缀{current.shadow_revision} · {current.validation_verdict} · NOT_GRANTED</p><p>已绑定 {current.bound_components.length} 类保存证据；完整实验未冻结，真实前向未启动。</p><ul>{Object.entries(current.gates).map(([name,g])=><li key={name}>{name} · {g.status}<details><summary>{name}依据与缺口</summary>{g.reasons.join('、')}</details></li>)}</ul>
      <details><summary>证据原件、支持要求与绑定详情</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-evidence-reviews/'+current.review_id+'/replay',{});setNotice(result.matches_original?'证据汇总原工件重放一致':'证据汇总重放不一致');})}>重放保存的证据汇总</button>
      <SuccessorJointReviewPanel key={current.review_id} reviewId={current.review_id} stressId={stressId}/>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
