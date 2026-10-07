import {useEffect,useState} from 'react';
import {Account,Receipt,request} from '../api';
type Audit={audit_id:string;account_version:number;receipt_id:string;recorded_at:string;source:string};
const status:Record<string,string>={OPEN:'已开通',NOT_OPEN:'未开通',UNKNOWN:'未知'};
export function History(){
  const [entries,setEntries]=useState<Audit[]>([]),[snapshot,setSnapshot]=useState<Account|null>(null),[receipt,setReceipt]=useState<Receipt|null>(null),[error,setError]=useState('');
  const [current,setCurrent]=useState<Account|null>(null);
  useEffect(()=>{request<Account>('/account').then(setCurrent).catch(e=>setError(String(e)));},[]);
  useEffect(()=>{request<Audit[]>('/account/audit').then(setEntries).catch(e=>setError(String(e)));},[]);
  async function inspect(entry:Audit){try{setSnapshot(await request<Account>(`/account/versions/${entry.account_version}`));setReceipt(await request<Receipt>(`/account/receipts/${entry.receipt_id}`));}catch(e){setError(String(e));}}
  return <><h1>历史记录</h1>{entries.length?<ul>{entries.map(e=><li key={e.audit_id}><button onClick={()=>void inspect(e)}>查看账户版本 {e.account_version}</button> · {new Date(e.recorded_at).toLocaleString('zh-CN')} · {e.source}</li>)}</ul>:<p>暂无已确认记录</p>}
    {!!current?.fills?.length&&<section><h2>已确认实际成交</h2><ul>{current.fills.map(f=><li key={f.record_id}>{f.fill_id??f.record_id} · {f.instrument} · {f.direction==='BUY'?'买入':'卖出'} {f.quantity} 股 · {f.price} 元/股 · {current.fee_resolutions?.[f.record_id]?`费用已补充 ${current.fee_resolutions[f.record_id].actual_fee_amount} 元`:f.fee.status==='PROVISIONAL'?`费用暂估 ${f.fee.reserve_amount} 元`:`实际费用 ${f.fee.amount} 元`} · 建议关联未知</li>)}</ul></section>}
    {snapshot&&<section><h2>账户版本 {snapshot.version}</h2><p>现金 {snapshot.cash_balance} 元 · 事实截至 {snapshot.effective_at}</p><h3>该版本账户交易权限</h3><ul>{snapshot.permission_profile.map(p=><li key={`${p.market}:${p.board}`}>{p.market}/{p.board} · {status[p.status]} · {p.basis} · 确认于 {p.confirmed_at}</li>)}</ul><p>回执 {receipt?.receipt_id}</p></section>}{error&&<p role="alert">{error}</p>}</>;
}
