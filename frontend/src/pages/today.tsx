import {ReviewPanel} from '../components/review-panel';
import {useEffect,useState} from 'react';
import {Account,Funding,Capability,RuntimeHealth,request} from '../api';
import {stateLabels} from './sync-reconcile';
import {FundingStatus} from '../components/funding-status';
type TodayResult={account:Account;formal_judgment:string;pending_items:string[];funding:Funding;technical_capability:Capability;runtime_health:RuntimeHealth;recovery:{state:string;restore_point?:{account_version:number}}};
const money=(value:string|null)=>value===null?'未知':`${value} 元`;
export function Today(){
  const [data,setData]=useState<TodayResult|null>(null),[error,setError]=useState('');
  useEffect(()=>{request<TodayResult>('/today').then(setData).catch(e=>setError(String(e)));},[]);
  if(error)return <p role="alert">{error}</p>;
  if(!data)return <p>正在读取今天…</p>;
  const a=data.account;
  return <><h1>今天</h1><div className="capability">交易判断未启用</div>{data.recovery?.state==='RECOVERY_LOCK'&&<p role="status">恢复锁生效：恢复到账户版本 {data.recovery.restore_point?.account_version}。请核对当前账户；旧授权、旧通知保持关闭，可以继续观察。未运行期间没有新的分析覆盖。</p>}<p>账户核对状态：{stateLabels[a.state]??a.state}</p><p className="muted">账户版本 {a.version} · {a.confirmed_at?`确认于 ${new Date(a.confirmed_at).toLocaleString('zh-CN')}`:'尚未建立账户，请前往同步账户'}</p>
    {a.effective_at&&<p>最新有效账户事实截至 {new Date(a.effective_at).toLocaleString('zh-CN')}</p>}
    {a.latest_confirmed_input_at&&<p className="muted">最近确认输入的实际时点 {new Date(a.latest_confirmed_input_at).toLocaleString('zh-CN')} · 系统获知于 {new Date(a.system_known_at??a.confirmed_at!).toLocaleString('zh-CN')}</p>}
    {!!a.declarations?.length&&<p>本次声明：{a.declarations.at(-1)!.scope.map(s=>({TRADES:'成交',ORDERS:'委托',CASH:'资金',EQUITY:'权益'}[s])).join('、')}截至 {new Date(a.declarations.at(-1)!.confirmed_as_of).toLocaleString('zh-CN')} · {a.declarations.at(-1)!.changes==='NONE'?'无未记录变化':'账户变化待同步'}</p>}
    {a.cash_balance_basis==='PROVISIONAL_FEES'&&<p>账面现金含费用暂估，净收益仍待核</p>}
    {a.conservative_available!==undefined&&<p className="muted">保守可用资金：{money(a.conservative_available??null)} · {a.conservative_available_basis==='USER_CONFIRMED'?'用户核对的券商快照':a.conservative_available===null?'当前可用资金未知，尚未重新核对':'基于最近已核对资金推算，非当前券商快照'}</p>}
    {a.broker_available_as_of&&<p className="muted">券商可用资金截至 {new Date(a.broker_available_as_of).toLocaleString('zh-CN')}</p>}
    {a.broker_frozen_as_of&&<p className="muted">冻结资金核对时点 {new Date(a.broker_frozen_as_of).toLocaleString('zh-CN')}</p>}
    {a.withdrawable_as_of&&<p className="muted">可取资金核对时点 {new Date(a.withdrawable_as_of).toLocaleString('zh-CN')}</p>}
<ReviewPanel/>    <div className="status-grid"><FundingStatus funding={data.funding} compact/><section><h2>技术资格</h2><p>{data.technical_capability.state==='METHOD_GRANTED'?'隔离工程资格已登记':data.technical_capability.state==='GRANTED'?'技术资格已授予':data.technical_capability.state==='RESTRICTED'?'已登记资格当前受限':'技术资格未授予'}</p><p>{data.technical_capability.reason}</p>{data.technical_capability.grant&&<p>范围：{data.technical_capability.grant.scope.instruments.join('、')} · 到期 {new Date(data.technical_capability.grant.expires_at).toLocaleString('zh-CN')}</p>}</section><section><h2>运行健康</h2><p>账户服务在线</p><p>{data.runtime_health.reason}</p></section></div>
    <section className="summary">{[['账面现金',a.cash_balance],['券商可用资金',a.broker_available],['冻结资金',a.broker_frozen],['可取资金',a.withdrawable]].map(([label,value])=><div key={label}><span>{label}</span><strong>{money(value)}</strong></div>)}</section>
    <section><h2>持仓</h2>{a.positions.length?<table><thead><tr><th>证券</th><th>持仓数量</th><th>可卖数量</th><th>参考成本</th></tr></thead><tbody>{a.positions.map(p=><tr key={p.instrument}><td>{p.instrument}</td><td>{p.quantity} 股</td><td>{p.sellable_quantity??'未知'}</td><td>{p.reference_cost??'未知'}</td></tr>)}</tbody></table>:<p>尚无已确认持仓</p>}<p className="muted">历史收益未知 · 不推定买入时间或历史费用</p></section>
    {a.investment_income!==undefined&&<section><h2>已确认现金流</h2><p>实际到账投资收入 {a.investment_income} 元 · 实际扣款税费 {a.investment_expenses} 元</p><p>外部转入 {a.external_cash_in} 元 · 外部转出 {a.external_cash_out} 元</p><p>未结应收 {a.pending_income} 元 · 未结应付 {a.pending_expenses} 元</p><p className="muted">外部转入不计投资收益；未结事项不进入实际现金或券商可用。此处税费是独立现金税费，不含成交费用。</p></section>}
    <section><h2>待核事项</h2>{data.pending_items.length?<ul>{data.pending_items.map(p=><li key={p}>{p}</li>)}</ul>:<p>当前已记录字段无未知待核项。其他账户变化仍需由用户确认。</p>}</section></>;
}
