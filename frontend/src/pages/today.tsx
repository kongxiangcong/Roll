import {useEffect,useState} from 'react';
import {Account,request} from '../api';
type TodayResult={account:Account;formal_judgment:string;pending_items:string[]};
const money=(value:string|null)=>value===null?'未知':`${value} 元`;
export function Today(){
  const [data,setData]=useState<TodayResult|null>(null),[error,setError]=useState('');
  useEffect(()=>{request<TodayResult>('/today').then(setData).catch(e=>setError(String(e)));},[]);
  if(error)return <p role="alert">{error}</p>;
  if(!data)return <p>正在读取今天…</p>;
  const a=data.account;
  return <><h1>今天</h1><div className="capability">交易判断未启用</div><p className="muted">账户版本 {a.version} · {a.confirmed_at?`确认于 ${new Date(a.confirmed_at).toLocaleString('zh-CN')}`:'尚未建立账户，请前往同步账户'}</p>
    {a.effective_at&&<p>账户事实截至 {new Date(a.effective_at).toLocaleString('zh-CN')}</p>}
    <section className="summary">{[['账面现金',a.cash_balance],['券商可用资金',a.broker_available],['冻结资金',a.broker_frozen],['可取资金',a.withdrawable]].map(([label,value])=><div key={label}><span>{label}</span><strong>{money(value)}</strong></div>)}</section>
    <section><h2>持仓</h2>{a.positions.length?<table><thead><tr><th>证券</th><th>持仓数量</th><th>可卖数量</th><th>参考成本</th></tr></thead><tbody>{a.positions.map(p=><tr key={p.instrument}><td>{p.instrument}</td><td>{p.quantity} 股</td><td>{p.sellable_quantity??'未知'}</td><td>{p.reference_cost??'未知'}</td></tr>)}</tbody></table>:<p>尚无已确认持仓</p>}<p className="muted">历史收益未知 · 不推定买入时间或历史费用</p></section>
    <section><h2>待核事项</h2>{data.pending_items.length?<ul>{data.pending_items.map(p=><li key={p}>{p}</li>)}</ul>:<p>当前已记录字段无未知待核项。其他账户变化仍需由用户确认。</p>}</section></>;
}
