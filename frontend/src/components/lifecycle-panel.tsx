import {useEffect,useState} from 'react';
import {Capability,Lifecycle,LifecycleScope,request} from '../api';
type Event={event_id:string;scope?:LifecycleScope;grant_id?:string;state?:string;reason?:string;version?:number;effective_at?:string};
type Monitor={check_id:string;grant_id:string;status:string;checked_at:string;reasons:string[];recovery_conditions:string;maturity:{review_status:string};system_usable:boolean};
type Recovery={state:string;journal_fingerprint:string;recovery_conditions?:string;permission_history_known:boolean;pending_permission_events:unknown[]};
const labels:Record<LifecycleScope,string>={NEW_RISK:'新增风险',MODEL:'模型建议',ALL_MONITOR:'全部监控'};
const states:Record<string,string>={ACTIVE:'运行中',SUSPENDED:'已暂停',REVOKED:'已撤回',EXPIRED:'已到期'};
const time=(value:string)=>new Date(value).toLocaleString('zh-CN');
const reasonLabels:Record<string,string>={FEATURE_OUTSIDE_DEV_REFERENCE_AT_LEAST20_PERCENT:'最近20次输入至少20%超出冻结开发参考范围',REQUIRED_FEATURE_COVERAGE_BELOW80_PERCENT:'最近20次输入完整覆盖低于80%',REQUIRED_MONITORING_SOURCE_UNVERIFIED:'必需监测来源尚无法核实',FROZEN_DEV_REFERENCE_EMPTY:'缺少冻结开发参考范围',MONITORING_SCOPE_OR_FREEZE_MISMATCH:'监测范围或冻结材料不一致',ACTUAL_EXECUTION_ASSUMPTIONS_UNKNOWN:'实际执行假设仍有未知字段',ACTUAL_FILL_ASSOCIATION_UNVERIFIED:'成交关联尚未核实',PRICE_OUTSIDE_FROZEN_WINDOW:'实际成交价格超出冻结窗口',DELAY_OUTSIDE_FROZEN_SCENARIOS:'操作延迟超出冻结场景',MATURE_RISK_CONSTRAINT_MAXIMUM_EXPOSURE_EXCEEDED:'登记检查点的暴露超出冻结上限',MATURE_RISK_CONSTRAINT_MAXIMUM_DRAWDOWN_EXCEEDED:'登记检查点的回撤超出冻结上限'};
const explain=(reason:string)=>reason.split('；').map(r=>reasonLabels[r]??r).join('；');
const monitorStates:Record<string,string>={CHECKED:'已按冻结方法核对',PENDING:'正常积累中，尚待检查',RESTRICTED:'当前用途受限'};

export function LifecyclePanel(){
  const [control,setControl]=useState<Lifecycle|null>(null),[capability,setCapability]=useState<Capability|null>(null),[events,setEvents]=useState<Event[]>([]),[monitors,setMonitors]=useState<Monitor[]>([]),[recovery,setRecovery]=useState<Recovery|null>(null);
  const [scope,setScope]=useState<LifecycleScope>('NEW_RISK'),[grant,setGrant]=useState(''),[reason,setReason]=useState(''),[checkId,setCheckId]=useState(''),[proof,setProof]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [category,setCategory]=useState('DATA_REPAIR'),[correction,setCorrection]=useState({error_source:'',expected_improvement:'',affected_modules:'',validation_plan:'',successor_protocol_id:'',successor_version_fingerprint:''}),[changesFrozen,setChangesFrozen]=useState(false);
  async function reload(){
    const [l,c,e,m,r]=await Promise.all([request<Lifecycle>('/capabilities/lifecycle'),request<Capability>('/capabilities'),request<Event[]>('/capabilities/events'),request<Monitor[]>('/capabilities/monitoring'),request<Recovery>('/capabilities/recovery')]);
    setControl(l);setCapability(c);setEvents(e.filter(value=>value.scope));setMonitors(m);setRecovery(r);
  }
  useEffect(()=>{const refresh=()=>void reload().catch(e=>setError(String(e)));refresh();window.addEventListener('focus',refresh);return()=>window.removeEventListener('focus',refresh);},[]);
  const selected=grant?capability?.grant_statuses?.find(s=>s.grant.grant_id===grant)?.lifecycle:control;
  const latest=monitors.filter(m=>m.grant_id===grant).at(-1);
  async function operate(action:()=>Promise<unknown>){setBusy(true);setError('');try{await action();await reload();window.dispatchEvent(new Event('roll-capability-changed'));}catch(e){setError(String(e));await reload().catch(()=>{});}finally{setBusy(false);}}
  async function change(state:'ACTIVE'|'SUSPENDED'|'REVOKED'){
    const previous=selected?.scopes[scope];
    await request('/capabilities/lifecycle',{scope,state,reason_code:state==='ACTIVE'?previous?.reason_code:state==='REVOKED'?'USER_REVOKE':'USER_PAUSE',reason,expected_version:control!.version,idempotency_key:crypto.randomUUID(),...(grant?{grant_id:grant}:{}),...(state==='ACTIVE'?{resume_event_id:previous?.event_id,...(checkId?{recovery_check_id:checkId}:{})}:{})});
  }
  async function recover(){
    const [account,funding]=await Promise.all([request<{version:number}>('/account'),request<{version:number}>('/funding')]);
    await request('/capabilities/recovery',{proof_id:proof,expected_account_version:account.version,expected_funding_version:funding.version,expected_journal_fingerprint:recovery!.journal_fingerprint,basis:reason,idempotency_key:crypto.randomUUID()});
  }
  return <section aria-label="暂停与恢复"><h2>暂停与恢复</h2>
    <p>新增风险暂停只停止买入、加仓及新增风险准备；模型建议暂停保留客观观察及独立风险规则。全部监控暂停仍允许同步事实、对账、审计和备份。</p>
    <p>暂停不会撤单、清仓或解除已存在的风险。恢复后需要重新核验并生成动作。</p>
    {selected&&<>{(Object.keys(labels) as LifecycleScope[]).map(key=><div key={key}><p>{labels[key]}：{states[selected.scopes[key].state]??selected.scopes[key].state}</p>{selected.scopes[key].reason&&<p>{explain(selected.scopes[key].reason!)} · {selected.scopes[key].effective_at&&time(selected.scopes[key].effective_at!)}</p>}</div>)}<p className="muted">权限版本 {control?.version}</p></>}
    <form onSubmit={e=>e.preventDefault()}><fieldset disabled={busy||!control}>
      <label>资格范围<select aria-label="资格范围" value={grant} onChange={e=>{setGrant(e.target.value);setCheckId('');}}><option value="">当前全局范围</option>{capability?.grant_statuses?.map(s=><option key={s.grant.grant_id} value={s.grant.grant_id}>{s.grant.scope.instruments.join('、')} · {s.grant.grant_id}</option>)}</select></label>
      <label>暂停范围<select aria-label="暂停范围" value={scope} onChange={e=>setScope(e.target.value as LifecycleScope)}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>操作原因<input value={reason} onChange={e=>setReason(e.target.value)} required maxLength={2000}/></label>
      <button disabled={!reason.trim()} onClick={()=>void operate(()=>change('SUSPENDED'))}>暂停所选范围</button>
      <button disabled={!reason.trim()||selected?.scopes[scope].state!=='SUSPENDED'} onClick={()=>void operate(()=>change('ACTIVE'))}>核对原因并恢复所选范围</button>
      <button disabled={!grant||!reason.trim()} onClick={()=>void operate(()=>change('REVOKED'))}>撤回所选资格</button>
    </fieldset></form>
    <p>主动暂停须核对原原因；自动暂停须较晚的健康监测、同一冻结材料和当前账户、资金、部署及范围。损失暂停不会因反弹或扩容自动解除。撤回和到期须新资格与后继授权。</p>
    {grant&&<details open><summary>冻结监测与复核</summary><button disabled={busy} onClick={()=>void operate(()=>request('/capabilities/monitoring/check',{grant_id:grant,basis:reason||'用户请求按原冻结方法核对当前支持'}))}>核对冻结监测</button>
      {latest&&<><p>最近检查：{time(latest.checked_at)} · {monitorStates[latest.status]??latest.status}</p><p>{latest.maturity.review_status==='NOT_AT_REGISTERED_CHECKPOINT'?'尚未到登记统计检查点':latest.maturity.review_status==='REGISTERED_CHECKPOINT_ALREADY_CONSUMED'?'本登记检查点已经处理，不重复判定':'登记点仅核对已成熟记录，未知或不足保持待核'}；未新增统计通过结论。</p>{latest.reasons.map(r=><p key={r}>{explain(r)}</p>)}<p>恢复条件：核对当前来源支持与执行假设，绑定原暂停事件；工程样例不用于真实正式建议。</p></>}
      <label>恢复监测依据<select aria-label="恢复监测依据" value={checkId} onChange={e=>setCheckId(e.target.value)}><option value="">选择较晚的健康检查</option>{monitors.filter(m=>m.grant_id===grant&&m.status==='CHECKED').map(m=><option key={m.check_id} value={m.check_id}>{time(m.checked_at)} · {m.check_id}</option>)}</select></label>
      {latest&&<details><summary>记录修正与验证方案</summary><form onSubmit={e=>{e.preventDefault();void operate(()=>request('/capabilities/corrections',{monitoring_check_id:latest.check_id,category,...correction,affected_modules:correction.affected_modules.split(',').map(s=>s.trim()).filter(Boolean),changes_frozen:changesFrozen,successor_protocol_id:changesFrozen?correction.successor_protocol_id:null,successor_version_fingerprint:changesFrozen?correction.successor_version_fingerprint:null,idempotency_key:crypto.randomUUID()}));}}><fieldset disabled={busy}>
        <label>修正类别<select value={category} onChange={e=>setCategory(e.target.value)}><option value="DATA_REPAIR">数据修复回归</option><option value="EXECUTION_ASSUMPTION">执行与费用假设</option><option value="USER_DELAY">已核实的用户延迟</option><option value="MODEL_RESEARCH">模型失效研究</option></select></label>
        {Object.entries({error_source:'错误来源',expected_improvement:'预期改善',affected_modules:'受影响模块（逗号分隔）',validation_plan:'验证方案'}).map(([key,label])=><label key={key}>{label}<input required value={correction[key as keyof typeof correction]} onChange={e=>setCorrection({...correction,[key]:e.target.value})}/></label>)}
        <label><input type="checkbox" checked={changesFrozen} onChange={e=>setChangesFrozen(e.target.checked)}/>涉及冻结模型、政策或假设变更</label>
        {changesFrozen&&<><label>后继协议编号<input required value={correction.successor_protocol_id} onChange={e=>setCorrection({...correction,successor_protocol_id:e.target.value})}/></label><label>后继版本指纹<input required pattern="[0-9a-f]{64}" value={correction.successor_version_fingerprint} onChange={e=>setCorrection({...correction,successor_version_fingerprint:e.target.value})}/></label><p>仅记录后继计划，仍须重新登记与验证；不重写原结论。</p></>}
        <button type="submit">保存修正方案</button></fieldset></form></details>}
    </details>}
    {recovery?.state==='RECOVERY_LOCK'&&<details open><summary>恢复锁与当前核对</summary><p>最新权限历史：{recovery.permission_history_known?'本机日志可核':'尚无法核实'} · 未确认事件 {recovery.pending_permission_events.length}</p><p>须恢复后的券商核对、当前完整验证与 Codex 审阅材料、部署及资金范围；未知时保持观察。</p><label>当前主机核验凭证编号<input value={proof} onChange={e=>setProof(e.target.value)}/></label><button disabled={busy||!proof||!reason.trim()} onClick={()=>void operate(recover)}>核对恢复依据</button></details>}
    {error&&<p role="alert">{error}</p>}
    <details><summary>查看权限历史</summary>{events.filter(e=>!grant||!e.grant_id||e.grant_id===grant).map(e=><p key={e.event_id}>{labels[e.scope!]} · {states[e.state!]??e.state} · {e.reason&&explain(e.reason)} · 版本 {e.version} · {e.effective_at&&time(e.effective_at)}</p>)}</details>
  </section>;
}
