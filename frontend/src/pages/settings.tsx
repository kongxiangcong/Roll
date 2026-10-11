import {BackupPanel} from '../components/backup-panel';
import {MaintenancePanel} from '../components/review-panel';
import {useEffect,useState} from 'react';
import {Funding,request} from '../api';
import {FundingStatus} from '../components/funding-status';
import {BackendPanel} from '../components/backend-panel';
import {CapabilityPanel} from '../components/capability-panel';
import {LifecyclePanel} from '../components/lifecycle-panel';

export function Settings(){
  const [funding,setFunding]=useState<Funding|null>(null),[error,setError]=useState(''),[history,setHistory]=useState<Funding|null>(null);
  const [scope,setScope]=useState<'ACCOUNT'|'TRIAL_ACTUAL'>('ACCOUNT'),[scopeId,setScopeId]=useState('account-1');
  const [purpose,setPurpose]=useState(''),[basis,setBasis]=useState(''),[enabled,setEnabled]=useState(false),[pause,setPause]=useState(false);
  const [amounts,setAmounts]=useState<Record<string,string>>({capital_amount:'',total_exposure:'',single_exposure:'',cash_reserve:'',loss_threshold:''});
  function populate(value:Funding){setFunding(value);if(value.version){setScope(value.scope_kind!);setScopeId(value.scope_id!);setPurpose(value.purpose!);setBasis(value.basis!);setEnabled(value.enabled!);setPause(value.pause_latched!);setAmounts({capital_amount:value.capital_amount!,total_exposure:value.total_exposure!,single_exposure:value.single_exposure!,cash_reserve:value.cash_reserve!,loss_threshold:value.loss_threshold!});}}
  useEffect(()=>{request<Funding>('/funding').then(populate).catch(e=>setError(String(e)));},[]);
  const [pending,setPending]=useState<unknown>(()=>JSON.parse(sessionStorage.getItem('roll.funding.confirmation')??'null'));
  const [busy,setBusy]=useState(false);
  async function confirm(){
    const command=pending??{expected_version:funding!.version,idempotency_key:crypto.randomUUID(),authorization:{scope_kind:scope,scope_id:scopeId,purpose,basis,...amounts,enabled,pause,effective_at:new Date().toISOString()}};
    setPending(command);sessionStorage.setItem('roll.funding.confirmation',JSON.stringify(command));setBusy(true);
    try{const response=await fetch('/api/funding/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command)});const next=await response.json();
      if(response.ok){populate(next);setError('');}
      else{if(response.status>=500)throw new Error('确认结果未明，请重试同一确认');if(next.detail?.current)populate(next.detail.current);setError(typeof next.detail==='string'?next.detail:JSON.stringify(next.detail));}
      setPending(null);sessionStorage.removeItem('roll.funding.confirmation');
    }catch(e){setError(`${String(e)}；保留原确认内容与幂等键，可重试找回结果。`);}finally{setBusy(false);}
  }
  if(!funding)return <p role={error?'alert':undefined}>{error||'正在读取资金边界…'}</p>;
  return <><h1>设置</h1><p>建立账户无需配置取证后端。资金确认不产生技术资格；交易判断未启用。</p><BackendPanel/><BackupPanel/><MaintenancePanel/><CapabilityPanel/><LifecyclePanel/><FundingStatus funding={funding}/><section><h2>确认资金用途与边界</h2><p>填写自己的金额。损失口径从首次授权起保留，跨日、反弹或扩大金额不清除暂停历史。恢复须核对暂停原因和实际事实。</p>
    {error&&<p role="alert">{error}</p>}{!!pending&&<p>正在保留未明确认，可重试原内容。</p>}<form onSubmit={e=>{e.preventDefault();void confirm();}}><fieldset className="funding-fields" disabled={busy||!!pending}>
    <label>资金范围<select aria-label="资金范围" value={scope} disabled={funding.version>0} onChange={e=>{setScope(e.target.value as 'ACCOUNT'|'TRIAL_ACTUAL');setScopeId(e.target.value==='ACCOUNT'?'account-1':'');}}><option value="ACCOUNT">整个真实账户</option><option value="TRIAL_ACTUAL">已界定的真实试验资金</option></select></label>
    {scope==='TRIAL_ACTUAL'&&<label>真实资金范围标识<input required value={scopeId} disabled={funding.version>0} onChange={e=>setScopeId(e.target.value)}/></label>}
    <label>资金用途<input required value={purpose} onChange={e=>setPurpose(e.target.value)}/></label>
    {Object.entries({capital_amount:'资金金额（元）',total_exposure:'总暴露上限（元）',single_exposure:'单票暴露上限（元）',cash_reserve:'现金保留额（元）',loss_threshold:'损失暂停阈值（元）'}).map(([key,label])=><label key={key}>{label}<input required inputMode="decimal" value={amounts[key]} onChange={e=>setAmounts({...amounts,[key]:e.target.value})}/></label>)}
    <label>确认依据<input required value={basis} onChange={e=>setBasis(e.target.value)}/></label>
    <label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>允许在此资金边界内使用</label>
    <label><input type="checkbox" checked={pause} disabled={!!funding.pause_latched} onChange={e=>setPause(e.target.checked)}/>暂停此资金用途</label>
    </fieldset><button type="submit" disabled={busy}>确认资金边界</button></form></section>
    {funding.version>0&&<section><h2>资金授权历史</h2>{Array.from({length:funding.version},(_,i)=>i+1).map(version=><button key={version} onClick={()=>request<Funding>(`/funding/versions/${version}`).then(setHistory).catch(e=>setError(String(e)))}>查看资金授权版本 {version}</button>)}{history&&<p>历史资金用途：{history.purpose} · {history.capital_amount} 元 · {history.state}</p>}</section>}</>;
}
