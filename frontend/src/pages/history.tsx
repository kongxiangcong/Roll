import {ReviewHistory} from '../components/review-panel';
import {FinancialObservationReview} from '../components/financial-observation-panel';
import {useEffect,useState} from 'react';
import {Account,Receipt,request} from '../api';
import {Research} from './research';
import {VerificationReview} from './verification';
import {ResearchReport} from '../components/research-report';
type Audit={audit_id:string;account_version:number;receipt_id:string;recorded_at:string;source:string};
const status:Record<string,string>={OPEN:'已开通',NOT_OPEN:'未开通',UNKNOWN:'未知'};
export function History({researchFreezeId}:{researchFreezeId?:string}){
  const [research,setResearch]=useState(Boolean(researchFreezeId));
  useEffect(()=>{if(researchFreezeId)setResearch(true);},[researchFreezeId]);
  const [verification,setVerification]=useState(false);
  const [entries,setEntries]=useState<Audit[]>([]),[snapshot,setSnapshot]=useState<Account|null>(null),[receipt,setReceipt]=useState<Receipt|null>(null),[error,setError]=useState('');
  const [known,setKnown]=useState(''),[effective,setEffective]=useState(''),[asOf,setAsOf]=useState<Account|null>(null);
  const [current,setCurrent]=useState<Account|null>(null);
  useEffect(()=>{request<Account>('/account').then(setCurrent).catch(e=>setError(String(e)));},[]);
  useEffect(()=>{request<Audit[]>('/account/audit').then(setEntries).catch(e=>setError(String(e)));},[]);
  async function inspect(entry:Audit){try{setSnapshot(await request<Account>(`/account/versions/${entry.account_version}`));setReceipt(await request<Receipt>(`/account/receipts/${entry.receipt_id}`));}catch(e){setError(String(e));}}
  return <><h1>历史记录</h1><ReviewHistory/><button onClick={()=>setResearch(!research)} aria-expanded={research}>研究登记</button>{research&&(researchFreezeId?<ResearchReport freezeId={researchFreezeId}/>:<Research/>)}<button onClick={()=>setVerification(!verification)} aria-expanded={verification}>关键复盘</button>{verification&&<VerificationReview/>}<FinancialObservationReview/><section><h2>查回当时已知的账户事实</h2><label>系统当时已知截至<input type="datetime-local" value={known} onChange={e=>setKnown(e.target.value)}/></label><label>实际发生截至<input type="datetime-local" value={effective} onChange={e=>setEffective(e.target.value)}/></label><button disabled={!known||!effective} onClick={async()=>{try{const p=new URLSearchParams({known_by:new Date(known).toISOString(),effective_at:new Date(effective).toISOString()});setAsOf((await request<{account:Account}>(`/account/as-of?${p}`)).account);}catch(e){setError(String(e));}}}>查询双时间账户</button>{asOf&&<p role="status">当时现金 {asOf.cash_balance??'未知'} 元 · 当时持仓 {asOf.positions.map(p=>`${p.instrument} ${p.quantity}股`).join('；')||'无'}。下方已发布版本保留原确认快照。</p>}</section>{entries.length?<ul>{entries.map(e=><li key={e.audit_id}><button onClick={()=>void inspect(e)}>查看账户版本 {e.account_version}</button> · {new Date(e.recorded_at).toLocaleString('zh-CN')} · {e.source}</li>)}</ul>:<p>暂无已确认记录</p>}
    {!!current?.fills?.length&&<section><h2>已确认实际成交</h2><ul>{current.fills.map(f=><li key={f.record_id}>{f.fill_id??f.record_id} · {f.instrument} · {f.direction==='BUY'?'买入':'卖出'} {f.quantity} 股 · {f.price} 元/股 · {current.fee_resolutions?.[f.record_id]?`费用已补充 ${current.fee_resolutions[f.record_id].actual_fee_amount} 元`:f.fee.status==='PROVISIONAL'?`费用暂估 ${f.fee.reserve_amount} 元`:`实际费用 ${f.fee.amount} 元`} · 建议关联未知</li>)}</ul></section>}
    {!!current?.cash_records?.length&&<section><h2>已确认资金与权益</h2><ul>{current.cash_records.map(r=><li key={r.record_id}>{r.record_id} · {r.kind==='PENDING_ITEM'?'原确认待结算':r.kind==='SETTLEMENT'?'实际关联结算':r.kind==='CASH_CORRECTION'?'追加金额更正':r.flow_category==='EXTERNAL_IN'?'外部转入':r.flow_category==='EXTERNAL_OUT'?'外部转出':r.flow_category==='INVESTMENT_INCOME'?'投资收入到账':'税费扣款'} · {r.corrected_amount??r.amount} 元{r.target_record_id&&` · 关联 ${r.target_record_id}`} · {r.basis} · 实际时点 {r.effective_at} · 确认于 {r.confirmed_at}</li>)}</ul></section>}
    {!!current?.pending_items?.length&&<section><h2>应收/应付余额</h2><ul>{current.pending_items.map(r=><li key={r.record_id}>{r.record_id} · 原确认 {r.amount} 元 · 当前总额 {r.resolved_amount} 元 · 已结 {r.settled_amount} 元 · 未结 {r.outstanding_amount} 元 · {r.status}</li>)}</ul></section>}
    {!!current?.share_records?.length&&<section><h2>实际股份变动</h2><ul>{current.share_records.map(r=><li key={r.record_id}>{r.record_id} · {r.instrument} · {r.quantity_before} → {r.new_quantity} 股 · 取得成本 {r.cost_after??'未知'} 元{r.kind==='RIGHTS_SUBSCRIPTION'&&` · 配股实际支付总额 ${r.amount} 元 · 其中费用 ${current.fee_resolutions?.[r.record_id]?.actual_fee_amount??r.fee_amount??'分拆未知'} 元`} · {r.basis}</li>)}</ul></section>}
    {!!current?.corrections?.length&&<section><h2>追加冲正与替代链</h2><ul>{current.corrections.map(c=><li key={c.record_id}>{c.record_id} · {c.reason} · 原事实 {c.root_event_id} · 上一链节点 {c.target_event_id} · 系统获知 {c.recorded_at} · 回执 {c.receipt_id}</li>)}</ul></section>}
    {snapshot&&<section><h2>账户版本 {snapshot.version}</h2><p>现金 {snapshot.cash_balance} 元 · 事实截至 {snapshot.effective_at}</p><h3>该版本账户交易权限</h3><ul>{snapshot.permission_profile.map(p=><li key={`${p.market}:${p.board}`}>{p.market}/{p.board} · {status[p.status]} · {p.basis} · 确认于 {p.confirmed_at}</li>)}</ul><p>回执 {receipt?.receipt_id}</p></section>}{error&&<p role="alert">{error}</p>}</>;
}
