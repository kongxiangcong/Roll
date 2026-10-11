import {useEffect,useState} from 'react';
import {Capability,request} from '../api';

export function CapabilityPanel(){
  const [value,setValue]=useState<Capability|null>(null),[material,setMaterial]=useState(''),[review,setReview]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function reload(){setValue(await request<Capability>('/capabilities'));}
  useEffect(()=>{void reload().catch(e=>setError(String(e)));},[]);
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
  return <section><h2>技术资格与适用范围</h2>{value&&<><p>{value.state==='METHOD_GRANTED'?'隔离工程资格已登记':value.state==='GRANTED'?'技术资格已授予':value.state==='RESTRICTED'?'已登记资格当前受限':'技术资格未授予'}</p><p>{value.reason}</p><p className="muted">{value.human_review_label}</p>{(value.grant_statuses??[]).map(status=><div key={status.grant.grant_id}><p>{status.grant.scope.instruments.join('、')} · {status.grant.scope.frequency} · {status.grant.scope.horizon} 交易日期限 · {status.grant.allowed_actions.join('、')}</p><p>资格到期：{new Date(status.grant.expires_at).toLocaleString('zh-CN')}</p>{status.state==='RESTRICTED'&&<p>此范围当前受限：{status.reason}</p>}{status.grant.evidence_kind==='METHOD_ENGINEERING'&&<p>METHOD 工程凭证，仅隔离验收，不能用于真实正式建议。</p>}</div>)}</>}
    <form onSubmit={e=>{e.preventDefault();void check();}}><label>冻结审阅材料编号<input required value={material} onChange={e=>setMaterial(e.target.value)}/></label><label>Codex 审阅记录编号<input required value={review} onChange={e=>setReview(e.target.value)}/></label><button disabled={busy} type="submit">核验并登记资格</button></form>{error&&<p role="alert">{error}</p>}
  </section>;
}
