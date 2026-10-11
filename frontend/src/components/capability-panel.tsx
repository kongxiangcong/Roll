import {useEffect,useState} from 'react';
import {Capability,request} from '../api';

export const capabilityLabel=(state:string)=>({METHOD_GRANTED:'隔离工程资格已登记',GRANTED:'技术资格已授予',RESTRICTED:'已登记资格当前受限',SUSPENDED:'当前资格已暂停',REVOKED:'原资格已撤回',EXPIRED:'原资格已到期'} as Record<string,string>)[state]??'技术资格未授予';
export const capabilityReason=(reason:string)=>reason.replaceAll('CAPABILITY_REVOKED','原资格已撤回，须当前新资格及后继授权').replaceAll('CAPABILITY_EXPIRED','原资格已到期，须当前新资格').replaceAll('ALL_MONITOR_SUSPENDED','全部监控已暂停').replaceAll('MODEL_SUSPENDED','模型建议已暂停').replaceAll('RECOVERY_LOCK','恢复锁生效，最新权限及当前依据仍待核');
type Material={material_id:string;protocol_id:string;candidate_kind:string;evidence_kind:string;created_at:string;basis_manifest:{validation_verdict:string;experiment_status:string;preliminary:boolean}};
type Review={run_id:string;backend:string;status:string;finished_at?:string;review_record?:{blocking_issues_resolved:boolean}};

export function CapabilityPanel(){
  const [value,setValue]=useState<Capability|null>(null),[material,setMaterial]=useState(''),[review,setReview]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [materials,setMaterials]=useState<Material[]>([]),[reviews,setReviews]=useState<Review[]>([]),[revision,setRevision]=useState(0);
  async function reload(){setValue(await request<Capability>('/capabilities'));}
  useEffect(()=>{const refresh=()=>void reload().catch(e=>setError(String(e)));refresh();window.addEventListener('roll-capability-changed',refresh);window.addEventListener('focus',refresh);return()=>{window.removeEventListener('roll-capability-changed',refresh);window.removeEventListener('focus',refresh);};},[]);
  useEffect(()=>{let current=true;void request<Material[]>('/research/review-materials').then(saved=>{if(current){setMaterials(saved);setMaterial(previous=>saved.some(m=>m.material_id===previous)?previous:'');}}).catch(e=>{if(current){setMaterials([]);setMaterial('');setError(String(e));}});return()=>{current=false;};},[revision]);
  useEffect(()=>{let current=true;setReviews([]);setReview('');if(material)void request<Review[]>(`/research/review-materials/${encodeURIComponent(material)}/reviews`).then(saved=>{if(current)setReviews(saved.filter(r=>r.backend==='CODEX'));}).catch(e=>{if(current)setError(String(e));});return()=>{current=false;};},[material,revision]);
  const selected=materials.find(m=>m.material_id===material);
  async function check(){
    setBusy(true);setError('');
    try{
      const proposal=await request<Record<string,unknown>>(`/capabilities/proposal?material_id=${encodeURIComponent(material)}&review_run_id=${encodeURIComponent(review)}`);
      const response=await fetch('/api/capabilities/grants',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...proposal,idempotency_key:crypto.randomUUID(),basis:'用户请求按冻结证据核验能力资格'})});
      const result=await response.json();
      if(!response.ok)setError(result.detail?.reasons?.join('；')??(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail)));
      await reload();
    }catch(e){setError(String(e));}finally{setBusy(false);}
  }
  return <section><h2>技术资格与适用范围</h2>{value&&<><p>{capabilityLabel(value.state)}</p><p>{capabilityReason(value.reason)}</p><p className="muted">{value.human_review_label}</p>{(value.grant_statuses??[]).map(status=><div key={status.grant.grant_id}><p>{status.grant.scope.instruments.join('、')} · {status.grant.scope.frequency} · {status.grant.scope.horizon} 交易日期限 · 原登记动作 {status.grant.allowed_actions.join('、')}</p><p>当前可用动作：{status.allowed_actions?.join('、')||'暂无'}</p><p>资格到期：{new Date(status.grant.expires_at).toLocaleString('zh-CN')}</p>{!['METHOD_GRANTED','GRANTED'].includes(status.state)&&<p>{capabilityLabel(status.state)}：{capabilityReason(status.reason)}</p>}{status.grant.evidence_kind==='METHOD_ENGINEERING'&&<p>METHOD 工程凭证，仅隔离验收，不能用于真实正式建议。</p>}</div>)}</>}
    <button onClick={()=>setRevision(r=>r+1)}>刷新已保存材料与审阅</button>
    {!materials.length&&<p>暂无可读取的已保存审阅材料。请先在研究页完成对应材料；资格仍须宿主核验。</p>}
    <form onSubmit={e=>{e.preventDefault();void check();}}><label>已保存的冻结审阅材料<select required value={material} onChange={e=>setMaterial(e.target.value)}><option value="">选择已保存材料</option>{materials.map(m=><option key={m.material_id} value={m.material_id}>{m.protocol_id} · {m.candidate_kind} · {m.basis_manifest.validation_verdict} · {new Date(m.created_at).toLocaleString('zh-CN')}</option>)}</select></label>
    {selected&&<p>材料结论：{selected.basis_manifest.validation_verdict} · 实验状态 {selected.basis_manifest.experiment_status} · {selected.evidence_kind}{selected.basis_manifest.preliminary?' · 仍为初步材料':''}。选择材料不表示资格已授予。</p>}
    <label>已保存的 Codex 审阅记录<select required value={review} disabled={!material||!reviews.length} onChange={e=>setReview(e.target.value)}><option value="">选择已保存审阅</option>{reviews.map(r=><option key={r.run_id} value={r.run_id}>{r.status} · {r.finished_at?new Date(r.finished_at).toLocaleString('zh-CN'):'尚未结束'} · {r.review_record?.blocking_issues_resolved?'阻断项已解决':'资格仍待核验'}</option>)}</select></label>
    {material&&!reviews.length&&<p>此材料尚无已保存的 Codex 审阅记录。</p>}<button disabled={busy||!material||!review} type="submit">核验并登记资格</button></form>{error&&<p role="alert">{error}</p>}
  </section>;
}
