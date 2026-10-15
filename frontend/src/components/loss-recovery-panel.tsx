import {useState} from 'react';
import {request,Funding,Lifecycle,Capability} from '../api';
type Check={check_id:string;status:string;gaps:string[];snapshot:{current_loss:{peak_loss:string}|null}};
type Receipt={recovery_id:string;check_id:string;recorded_at:string;preserved_peak_loss:string;evidence_kind:string;old_grant_revived:boolean};
type Pending={checkId:string;command:{acknowledge_preserved_peak:true;idempotency_key:string;basis:string}};
const storage='roll.loss-recovery.confirmation';
export function LossRecoveryPanel(){
  const [funding,setFunding]=useState<Funding|null>(null),[account,setAccount]=useState(0),[control,setControl]=useState<Lifecycle|null>(null),[caps,setCaps]=useState<Capability|null>(null),[receipts,setReceipts]=useState<Receipt[]>([]);
  const [grant,setGrant]=useState(''),[basis,setBasis]=useState(''),[ack,setAck]=useState(false),[check,setCheck]=useState<Check|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [pending,setPending]=useState<Pending|null>(()=>JSON.parse(sessionStorage.getItem(storage)??'null'));
  async function reload(){const [f,a,l,c,r]=await Promise.all([request<Funding>('/funding'),request<{version:number}>('/account'),request<Lifecycle>('/capabilities/lifecycle'),request<Capability>('/capabilities'),request<Receipt[]>('/funding/loss-recovery/receipts')]);setFunding(f);setAccount(a.version);setControl(l);setCaps(c);setReceipts(r);}
  async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function inspect(){const result=await request<Check>('/funding/loss-recovery/checks',{pause_event_id:control!.scopes.NEW_RISK.event_id,successor_grant_id:grant,expected_account_version:account,expected_funding_version:funding!.version,expected_lifecycle_version:control!.version,idempotency_key:crypto.randomUUID(),basis});setCheck(result);setAck(false);}
  function clearPending(){setPending(null);sessionStorage.removeItem(storage);setCheck(null);setAck(false);}
  async function activate(){const saved=pending??{checkId:check!.check_id,command:{acknowledge_preserved_peak:true as const,idempotency_key:crypto.randomUUID(),basis}};setPending(saved);sessionStorage.setItem(storage,JSON.stringify(saved));
    let response:Response;
    try{response=await fetch('/api/funding/loss-recovery/checks/'+saved.checkId+'/activate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(saved.command)});}
    catch{throw new Error('确认结果尚不确定，请保留原确认并重试核对。');}
    const value=await response.json();
    if(!response.ok){
      const detail=value.detail;const code=typeof detail==='string'?detail:detail?.code;
      // Only this refusal is guaranteed to precede a commit for the original key.
      if(response.status===409&&code==='LOSS_RECOVERY_CURRENT_CONDITIONS_CHANGED'){
        clearPending();await reload();throw new Error('当前条件已变化，本次确认未提交；请重新核验LOSS恢复条件。');
      }
      // Another key may have committed this check. Read verified receipts before releasing it.
      const verified=await request<Receipt[]>('/funding/loss-recovery/receipts');
      if(!verified.some(r=>r.check_id===saved.checkId))throw new Error(typeof detail==='string'?detail:JSON.stringify(detail));
    }
    clearPending();await reload();window.dispatchEvent(new Event('roll-capability-changed'));
  }
  const paused=control?.scopes.NEW_RISK.reason_code==='LOSS_BOUNDARY'&&control.scopes.NEW_RISK.state==='SUSPENDED';
  return <details><summary>LOSS原因绑定恢复</summary><p>先重新确认自己的损失边界，再在模型维护中关联已关闭的原记录登记后继资格，最后核对本次LOSS暂停。保留原损失起点、峰值及暂停记录，旧撤回或到期资格不会复活；反弹、扩资、重启均不自动恢复。</p>
    <button disabled={busy} onClick={()=>void action(reload)}>读取LOSS恢复条件</button>
    {funding&&<p>资金版本{funding.version} · 当前损失阈值{funding.loss_threshold??'未知'}元 · {paused?'LOSS限制生效':'当前没有可恢复的LOSS暂停'}</p>}
    <fieldset disabled={busy||!!pending}>
      <label>LOSS后继资格<select aria-label="LOSS后继资格" value={grant} onChange={e=>{setGrant(e.target.value);setCheck(null);}}><option value="">选择当前后继资格</option>{caps?.grant_statuses?.map(s=><option key={s.grant.grant_id} value={s.grant.grant_id}>{s.grant.grant_id} · {s.state}</option>)}</select></label>
      <label>LOSS恢复依据<input value={basis} onChange={e=>{setBasis(e.target.value);setCheck(null);}}/></label>
      <button disabled={!paused||!grant||!basis.trim()} onClick={()=>void action(inspect)}>核验当前LOSS恢复条件</button>
      {check&&<><p>LOSS恢复核验 · {check.status} · 保留峰值{check.snapshot.current_loss?.peak_loss??'未知'}元</p><p>{check.gaps.join(' / ')}</p></>}
      {check?.status==='READY'&&<label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>确认保留原损失起点、峰值和暂停历史</label>}
    </fieldset>
    <button disabled={busy||(!pending&&(!ack||check?.status!=='READY'))} onClick={()=>void action(activate)}>{pending?'重试原LOSS恢复确认':'确认按后继资格恢复LOSS限制'}</button>
    {pending&&<p>保留原确认内容与幂等键；可重试核对结果。</p>}
    {receipts.map(r=><p key={r.recovery_id}>{r.evidence_kind==='METHOD_ENGINEERING'?'METHOD恢复回执':'LOSS恢复回执'} · 保留峰值{r.preserved_peak_loss}元 · 旧资格未复活</p>)}
    {error&&<p role="alert">{error}</p>}
  </details>;
}
