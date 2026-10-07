import {useEffect,useState} from 'react';
import {Account,Receipt,request} from '../api';
type Audit={audit_id:string;account_version:number;receipt_id:string;recorded_at:string;source:string};
const status:Record<string,string>={OPEN:'已开通',NOT_OPEN:'未开通',UNKNOWN:'未知'};
export function History(){
  const [entries,setEntries]=useState<Audit[]>([]),[snapshot,setSnapshot]=useState<Account|null>(null),[receipt,setReceipt]=useState<Receipt|null>(null),[error,setError]=useState('');
  useEffect(()=>{request<Audit[]>('/account/audit').then(setEntries).catch(e=>setError(String(e)));},[]);
  async function inspect(entry:Audit){try{setSnapshot(await request<Account>(`/account/versions/${entry.account_version}`));setReceipt(await request<Receipt>(`/account/receipts/${entry.receipt_id}`));}catch(e){setError(String(e));}}
  return <><h1>历史记录</h1>{entries.length?<ul>{entries.map(e=><li key={e.audit_id}><button onClick={()=>void inspect(e)}>查看账户版本 {e.account_version}</button> · {new Date(e.recorded_at).toLocaleString('zh-CN')} · {e.source}</li>)}</ul>:<p>暂无已确认记录</p>}{snapshot&&<section><h2>账户版本 {snapshot.version}</h2><p>现金 {snapshot.cash_balance} 元 · 事实截至 {snapshot.effective_at}</p><h3>该版本账户交易权限</h3><ul>{snapshot.permission_profile.map(p=><li key={`${p.market}:${p.board}`}>{p.market}/{p.board} · {status[p.status]} · {p.basis} · 确认于 {p.confirmed_at}</li>)}</ul><p>回执 {receipt?.receipt_id}</p></section>}{error&&<p role="alert">{error}</p>}</>;
}
