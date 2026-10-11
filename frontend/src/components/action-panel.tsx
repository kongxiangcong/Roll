import {useEffect,useState} from 'react';
import {request} from '../api';
type Decision={decision_id:string;instrument:string;action:string;basis_type:string;quantity:string;current_quantity:string;target_quantity:string;price_lower_yuan:string;price_upper_yuan:string;expires_at:string;data_cutoff:string;forecast_cutoff?:string;forecast_horizon?:number;quote_at?:string;cumulative_volume?:string;uncertainty:string};
type Evaluation={namespace:string;registered_at:string;limitations:string[];refusals:{instrument:string;reasons:string[]}[];holding_risks:{instrument:string;sellable_quantity:string|null;reasons:string[]}[];joint_budget:{loss:{status:string;remaining_loss_allowance:string|null}|null}|null};
type Current={evaluation:Evaluation|null;decisions:Decision[];invalidated:{decision:Decision;reasons:string[]}[]};
const time=(s:string)=>new Date(s).toLocaleString('zh-CN');
export function ActionPanel({instrument}:{instrument?:string}){
  const [data,setData]=useState<Current|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const path='/actions/current'+(instrument?'?instrument='+encodeURIComponent(instrument):'');
  useEffect(()=>{request<Current>(path).then(setData).catch(e=>setError(String(e)));},[path]);
  async function evaluate(){setBusy(true);try{await request('/actions/evaluate',{});setData(await request<Current>(path));setError('');}catch(e){setError(String(e));}finally{setBusy(false);}}
  const e=data?.evaluation;
  return <section aria-label={instrument?'单股当前动作':'当前动作'}><h2>当前动作</h2>{!instrument&&<button onClick={()=>void evaluate()} disabled={busy}>{busy?'正在核验…':'核验当前动作'}</button>}
    {error&&<p role="alert">{error}</p>}{e?.namespace==='METHOD_ENGINEERING'&&<p role="status">METHOD 工程样例，不能用于真实正式建议。</p>}
    {data&&!data.decisions.length&&<p>当前没有有效正式动作</p>}
    {data?.decisions.map(d=><article key={d.decision_id}><h3>{d.instrument} · {({BUY:'买入',REDUCE:'减仓',EXIT:'退出'} as Record<string,string>)[d.action]??d.action}</h3><p>{d.basis_type==='RISK_POLICY'?'独立风险回退政策':'冻结收益模型政策'} · 本次 {d.quantity} 股</p><p>当前 {d.current_quantity} 股 → 目标 {d.target_quantity} 股</p><p>价格条件 {d.price_lower_yuan}—{d.price_upper_yuan} 元 · 期限至 {time(d.expires_at)}</p><p>当前报价截至 {time(d.quote_at??d.data_cutoff)}{d.cumulative_volume!==undefined&&` · 累计成交量 ${d.cumulative_volume}`}</p>{d.forecast_cutoff&&<p>最近完整日线预测截至 {time(d.forecast_cutoff)} · {d.forecast_horizon} 个交易日</p>}<p className="muted">生成于 {time(e!.registered_at)} · 账户、资金、数据、资格变化或到期需重新核验</p><p>{d.uncertainty}</p></article>)}
    {data?.invalidated.map(i=><p key={i.decision.decision_id} role="status">{i.decision.instrument} 原动作已失效：{i.reasons.join('；')}</p>)}
    {!!e?.limitations.length&&<p>当前限制：{e.limitations.join('；')}</p>}
    {e?.joint_budget?.loss&&<p>损失额度：{e.joint_budget.loss.remaining_loss_allowance??'未知，限制新增风险'} · {e.joint_budget.loss.status}</p>}
    {!!e?.refusals.length&&<details><summary>查看机会限制</summary>{e.refusals.filter(r=>!instrument||r.instrument===instrument).map(r=><p key={r.instrument}>{r.instrument}：{r.reasons.join('；')}</p>)}</details>}
    {!!e?.holding_risks.length&&<details open><summary>持仓风险与待核</summary>{e.holding_risks.filter(r=>!instrument||r.instrument===instrument).map(r=><p key={r.instrument}>{r.instrument} · 可卖 {r.sellable_quantity??'未知'} · {r.reasons.join('；')}</p>)}</details>}
  </section>;
}
