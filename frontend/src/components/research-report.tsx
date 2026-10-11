import {useEffect,useState} from 'react';
import {request} from '../api';
type Point={date?:string;as_of?:string;nav_yuan?:string|null;net_assets?:string|null;cash_yuan?:string;origin_at?:string};
type Curve={continuous_performance:boolean;points:Point[];reason?:string};
type Valuation={valuation_id:string;as_of:string;account_version:number};
type Intent={intent_id:string;decision_id:string;evaluation_id:string;instrument:string;status:string};
type Check={check_id:string;status:string;reasons:string[]};
type Report={freeze_id:string;protocol_id:string;model_run_id:string;evidence_kind:string;
  complete_protocol_fingerprint:string;original_fingerprints:Record<string,string>;
  qualification:{capability:string;calibrator_fit_status:string;validation_gaps:string[]};
  platform:{baseline:unknown;execution:unknown;costs:unknown;state:{revision:number;through_date:string;cash_yuan:string;nav_yuan:string|null;positions:{instrument:string;quantity:string}[]}};
  actual:{account_version:number;net_assets:string|null;status:string;valuation:unknown};
  comparison:{status:string;reasons:string[];window:unknown;conditions:unknown};
  execution:{status:string;response_seconds:number|null;notification_chain:unknown;unlinked_fills:unknown[]};
  execution_deviations:{intent_id:string;status:string;remaining_quantity:string;synced_quantity:string;same_strategy:boolean;proposal:unknown;allocations:unknown[];allocation_diagnostics:unknown[];time_chain:unknown}[];
  monitoring:{checks:Check[];corrections:unknown[];same_strategy:boolean|null};
  namespaces:{ACCOUNT_CONDITIONAL:unknown[];HISTORICAL:unknown};curves:Record<string,Curve>};
function CurveView({name,curve}:{name:string;curve:Curve}){
  const valid=curve.points.flatMap((p,i)=>{const raw=p.nav_yuan??p.net_assets;return raw==null?[]:[{i,value:Number(raw)}];});
  const low=Math.min(...valid.map(p=>p.value)),high=Math.max(...valid.map(p=>p.value));
  const line=valid.map((p,j)=>`${j&&p.i===valid[j-1].i+1?'L':'M'}${20+p.i*280/Math.max(1,curve.points.length-1)},${100-(p.value-low)*80/Math.max(1,high-low)}`).join(' ');
  return <article><h4>{name}</h4><p>{curve.continuous_performance?'连续资金约束策略':'独立保存结果，不是连续策略收益'}</p>
    {valid.length>1&&<svg role="img" aria-label={name+' 分列净资产曲线'} viewBox="0 0 320 120"><path d={line} fill="none" stroke="currentColor" strokeWidth="2"/></svg>}
    {curve.points.length?<details><summary>{curve.points.length} 个原保存时点</summary><table><thead><tr><th>时点</th><th>净资产（元）</th></tr></thead><tbody>{curve.points.map((p,i)=><tr key={i}><td>{p.date??p.as_of}</td><td>{p.nav_yuan??p.net_assets??'未知'}</td></tr>)}</tbody></table></details>:<p>{name==='HISTORICAL'?'逐机会预测与成熟反事实只作诊断，不叠加为策略收益':name==='ACCOUNT_CONDITIONAL'?'一次账户快照诊断不连接为净值曲线':'尚未选定已保存估值'}</p>}</article>;
}
export function ResearchReport({freezeId}:{freezeId:string}){
  const [report,setReport]=useState<Report|null>(null),[valuations,setValuations]=useState<Valuation[]>([]),[intents,setIntents]=useState<Intent[]>([]),[checks,setChecks]=useState<Check[]>([]);
  const [valuationId,setValuationId]=useState(''),[intentId,setIntentId]=useState(''),[checkId,setCheckId]=useState(''),[error,setError]=useState('');
  const params=new URLSearchParams();if(valuationId)params.set('valuation_id',valuationId);if(checkId)params.set('monitoring_check_id',checkId);
  const intent=intents.find(i=>i.intent_id===intentId);if(intent){params.set('decision_id',intent.decision_id);params.set('evaluation_id',intent.evaluation_id);params.set('intent_id',intent.intent_id);}
  const query=params.toString(),url='/research/reports/'+freezeId+(query?'?'+query:'');
  useEffect(()=>{let active=true;request<Report>(url).then(v=>{if(active){setReport(v);setError('');}}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[url]);
  useEffect(()=>{Promise.all([request<Valuation[]>('/account/valuations'),request<{intents:Intent[]}>('/intents'),request<Check[]>('/capabilities/monitoring')]).then(([v,i,c])=>{setValuations(v);setIntents(i.intents);setChecks(c);}).catch(e=>setError(String(e)));},[freezeId]);
  return <section aria-label="保存的研究报告"><h3>保存的研究报告</h3><p>RESEARCH · 原保存版本，未用当前代码重算 · 没有正式执行或行动推送入口。</p>
    <label>已保存实际估值<select aria-label="已保存实际估值" value={valuationId} onChange={e=>setValuationId(e.target.value)}><option value="">不选定（净资产未知）</option>{valuations.map(v=><option key={v.valuation_id} value={v.valuation_id}>账户 {v.account_version} · {v.as_of}</option>)}</select></label>
    <label>已保存动作与成交<select aria-label="已保存动作与成交" value={intentId} onChange={e=>setIntentId(e.target.value)}><option value="">未选定动作</option>{intents.map(i=><option key={i.intent_id} value={i.intent_id}>{i.instrument} · {i.status} · {i.intent_id.slice(0,8)}</option>)}</select></label>
    <label>已保存监测检查<select aria-label="已保存监测检查" value={checkId} onChange={e=>setCheckId(e.target.value)}><option value="">未选定检查</option>{checks.map(c=><option key={c.check_id} value={c.check_id}>{c.status} · {c.check_id.slice(0,8)}</option>)}</select></label>
    {report&&<><p>{report.evidence_kind} · {report.qualification.capability} · 校准 {report.qualification.calibrator_fit_status} · 未经人工独立复核</p>
      <h4>平台策略结果</h4><p>原版本 {report.platform.state.revision} · 截止 {report.platform.state.through_date} · 现金 {report.platform.state.cash_yuan} · 净资产 {report.platform.state.nav_yuan??'未知'}</p><p>持仓 {report.platform.state.positions.map(p=>`${p.instrument} ${p.quantity}股`).join('、')||'无'}</p>
      <h4>实际用户结果</h4><p>账户版本 {report.actual.account_version} · 已保存净资产 {report.actual.net_assets??'未知'} · {report.actual.status}</p>
      <h4>执行偏差</h4><p>送达与响应时间未知；实际收益减影子收益不能直接归因为执行损益。</p>
      {report.execution_deviations.length?report.execution_deviations.map(d=><article key={d.intent_id}><p>{d.status} · 已关联 {d.synced_quantity} 股 · 剩余 {d.remaining_quantity} 股 · {d.same_strategy?'相同冻结策略':'不同来源策略，不能归为本影子执行'}</p><details><summary>原动作、成交、费用及时间起止依据</summary><pre>{JSON.stringify(d,null,2)}</pre></details></article>):<p>未选定已登记动作；成交关联与未执行原因保持未知。</p>}
      {!!report.execution.unlinked_fills.length&&<p>另有 {report.execution.unlinked_fills.length} 项实际成交关联未知，不能追认研究建议。</p>}
      <p><strong>{report.comparison.status}</strong> · {report.comparison.reasons.join('、')}</p><details><summary>比较窗口与资金、持仓、范围、执行条件</summary><pre>{JSON.stringify({window:report.comparison.window,conditions:report.comparison.conditions},null,2)}</pre></details>
      <div className="research-results">{Object.entries(report.curves).map(([name,curve])=><CurveView key={name} name={name} curve={curve}/>)}</div>
      <p>ACCOUNT_CONDITIONAL 保存 {report.namespaces.ACCOUNT_CONDITIONAL.length} 项；被拒机会的反事实评分只进入 HISTORICAL 预测诊断。</p>
      {report.monitoring.checks.map(c=><article key={c.check_id}><h4>原保存监测 · {c.status}</h4><p>{c.reasons.join('、')} · {report.monitoring.same_strategy?'相同策略':'不同冻结来源'}</p></article>)}
      <details><summary>保存的监测方法、检查点与修正计划</summary><pre>{JSON.stringify(report.monitoring,null,2)}</pre></details>
      <details><summary>原通知与成交时间链（外部送达与已读不推定）</summary><pre>{JSON.stringify(report.execution.notification_chain,null,2)}</pre></details>
      <details><summary>实验、运行、原指纹及验证缺口</summary><p>实验 {report.freeze_id} · 协议 {report.protocol_id} · 运行 {report.model_run_id}</p><pre>{JSON.stringify(report.original_fingerprints,null,2)}</pre><ul>{report.qualification.validation_gaps.map(g=><li key={g}>{g}</li>)}</ul></details>
      <a href={'/api/research/reports/'+freezeId+'/export?'+params.toString()} download>导出 JSON</a> · <a href={'/api/research/reports/'+freezeId+'/export?'+new URLSearchParams({...Object.fromEntries(params),format:'text'})} download>导出文字</a>
    </>}{error&&<p role="alert">{error}</p>}</section>;
}
