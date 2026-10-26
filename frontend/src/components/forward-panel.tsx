import {useEffect,useState} from 'react';
import {request} from '../api';
import {IndependentValidationPanel} from './independent-validation-panel';
type Result={sample_id:string;label:number|null};
type State={namespace:string;status:string;forward_started_at:string|null;forward_deadline:string|null;method_deadline:string|null;
  samples:{sample_id:string;trading_date:string;action:{action:string;reasons:string[]}}[];
  missing_checkpoints:{trading_date:string;reason:string}[];checks:{gaps:string[]}[];
  endpoint?:{cutoff:string;preliminary_verdict:string;validation_status:string;review_status:string;mature:Result[];unmatured:Result[];unscorable:Result[]};
  latest_assessment?:{mature:Result[];unmatured:Result[];unscorable:Result[]}};
export function ForwardPanel({freezeId,evidenceKind,fingerprint}:{freezeId:string;evidenceKind:string;fingerprint:string}){
  const [state,setState]=useState<State|null>(null),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
  const path=`/research/complete-freezes/${freezeId}/forward`;
  async function refresh(){try{setState(await request<State>(path));}catch(e){if(!String(e).includes('尚未登记前向归档'))throw e;}}
  useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[freezeId]);
  async function run(action:()=>Promise<void>){setBusy(true);setError('');try{await action();}catch(e){setError(String(e));}finally{setBusy(false);}}
  const outcome=state?.endpoint??state?.latest_assessment;
  return <section aria-label="盘后前向归档"><h3>盘后前向归档</h3>
    <p>程序运行且当前完整输入可用时，按冻结检查点保存一次。缺日保留缺口，期限不因重试或缺席延长。</p>
    {!state&&<button disabled={busy} onClick={()=>void run(async()=>{await request(path,{purpose:evidenceKind==='METHOD_CASE'?'METHOD_VALIDATION':'RESEARCH',basis:'登记固定盘后检查点；无正式能力授权'});await refresh();})}>登记盘后归档</button>}
    {state&&<><p>{state.namespace} · {state.status} · 正式能力未授权 · 未经人工独立复核</p>
      <p>实际前向起点：{state.forward_started_at??'尚未启动'}</p>
      {state.forward_deadline&&<p>实际最迟终点：{state.forward_deadline}</p>}
      {state.method_deadline&&<p>METHOD 工程期限：{state.method_deadline} · 不能作为真实前向证据</p>}
      <p>唯一归档：{state.samples.length} 项</p>
      <button disabled={busy||state.status==='CLOSED'} onClick={()=>void run(async()=>{await request(path+'/check',{basis:'手动检查当前盘后归档，不补预测'});await refresh();})}>检查当前盘后归档</button>
      <button disabled={busy||!state.samples.length} onClick={()=>void run(async()=>{await request(path+'/settle',{basis:'仅结算已归档机会'});await refresh();})}>检查已归档机会成熟结果</button>
      <button disabled={busy||!state.samples.length} onClick={()=>void run(async()=>{const r=await request<{matches_original:boolean;network_calls:number}>(path+'/replay',{});setNotice(`前向归档重放${r.matches_original?'一致':'不一致'} · 联网 ${r.network_calls} 次`);})}>重放前向归档</button>
      <button disabled={busy||state.status==='CLOSED'} onClick={()=>void run(async()=>{await request(path+'/stop',{kind:'USER_STOP',basis:'用户停止本轮采样；统计结论另行保留'});await refresh();})}>停止本轮采样</button>
      {state.endpoint&&<p>终点 {state.endpoint.cutoff} · 初步结论 {state.endpoint.preliminary_verdict} · 验证 {state.endpoint.validation_status} · 技术审阅 {state.endpoint.review_status}</p>}
      {outcome&&<p>成熟可评分 {outcome.mature.length} · 未成熟 {outcome.unmatured.length} · 无法评分 {outcome.unscorable.length}</p>}
      <details><summary>归档与覆盖缺口</summary><ul>{state.samples.map(s=><li key={s.sample_id}>{s.trading_date} · {s.action.action} · {s.action.reasons.join('、')||'符合冻结政策'}</li>)}{state.missing_checkpoints.map(g=><li key={g.trading_date}>{g.trading_date} · 漏日未补预测</li>)}</ul><p style={{overflowWrap:'anywhere'}}>{state.checks.at(-1)?.gaps.join('、')}</p></details>
    </>}
    <IndependentValidationPanel key={freezeId} freezeId={freezeId} fingerprint={fingerprint} forwardStatus={state?.status} samples={state?.samples.length??0}/>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </section>;
}
