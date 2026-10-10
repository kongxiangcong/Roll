import {useEffect,useState} from 'react';
import {Account,Draft,Receipt,request} from '../api';

const dateInput=()=>new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16);
const blankToNull=(value:string)=>value.trim()===''?null:value.trim();
const diffLabels:Record<string,string>={cash_balance:'账面现金',positions:'持仓与取得成本',conservative_available:'估计保守可用资金',broker_available:'已核对券商可用资金',net_result_state:'费用与结果状态'};
export function SyncFill({account,mode,onDone}:{account:Account;mode:'FILL'|'FEE_ADJUSTMENT';onDone:()=>void}){
  const [effective,setEffective]=useState(dateInput),[source,setSource]=useState('用户核对成交回报');
  const [market,setMarket]=useState('SSE'),[code,setCode]=useState(''),[direction,setDirection]=useState('BUY');
  const [quantity,setQuantity]=useState(''),[price,setPrice]=useState(''),[fillId,setFillId]=useState(''),[orderId,setOrderId]=useState('');
  const [behavior,setBehavior]=useState('NO_RECOMMENDATION'),[feeStatus,setFeeStatus]=useState('KNOWN');
  const [fee,setFee]=useState(''),[reserve,setReserve]=useState(''),[basis,setBasis]=useState(''),[available,setAvailable]=useState('');
  const [target,setTarget]=useState(()=>account.fills?.find(f=>f.fee.status==='PROVISIONAL'&&!account.fee_resolutions?.[f.record_id])?.record_id??account.share_records?.find(r=>r.kind==='RIGHTS_SUBSCRIPTION'&&r.fee_amount===null&&!account.fee_resolutions?.[r.record_id])?.record_id??account.fills?.at(-1)?.record_id??account.share_records?.filter(r=>r.kind==='RIGHTS_SUBSCRIPTION').at(-1)?.record_id??'');
  const [draft,setDraft]=useState<Draft|null>(null),[key,setKey]=useState(''),[receipt,setReceipt]=useState<Receipt|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[queried,setQueried]=useState(false);
  const storageKey=`roll.pending-${mode}`;
  useEffect(()=>{const pending=sessionStorage.getItem(storageKey);if(pending){const saved=JSON.parse(pending);request<Draft>(`/account/drafts/${saved.draft_id}`).then(d=>{setDraft(d);setKey(saved.key);}).catch(()=>sessionStorage.removeItem(storageKey));}},[storageKey]);
  async function preview(){
    setBusy(true);setError('');
    try{
      const common={effective_at:new Date(effective).toISOString(),source};
      const payload=mode==='FILL'?{...common,instrument:`${market}:${code}`,direction,quantity,price,record_id:crypto.randomUUID(),fill_id:blankToNull(fillId),order_id:blankToNull(orderId),behavior_context:behavior,
        fee:{status:feeStatus,amount:feeStatus==='KNOWN'?fee:null,reserve_amount:feeStatus==='PROVISIONAL'?reserve:null,basis},broker_available_after:blankToNull(available)}:
        {...common,target_record_id:target,actual_fee_amount:fee,basis};
      const d=await request<Draft>('/account/drafts',{kind:mode,expected_account_version:account.version,payload});
      const k=crypto.randomUUID();setDraft(d);setKey(k);sessionStorage.setItem(storageKey,JSON.stringify({draft_id:d.draft_id,key:k}));
    }catch(e){setError(String(e));}finally{setBusy(false);}
  }
  async function confirm(){setBusy(true);setError('');try{setReceipt(await request<Receipt>('/account/confirm',{draft_id:draft!.draft_id,idempotency_key:key}));sessionStorage.removeItem(storageKey);}catch(e){setError(String(e));}finally{setBusy(false);}}
  if(receipt)return <section><h2>{mode==='FILL'?'实际成交':'费用调整'}已确认，回执已保存</h2><p>账户版本 {receipt.account_version} · 确认于 {new Date(receipt.confirmed_at).toLocaleString('zh-CN')}</p><p>回执 {receipt.receipt_id}</p><button onClick={async()=>{try{await request<Receipt>(`/account/receipts/${receipt.receipt_id}`);setQueried(true);}catch(e){setError(String(e));}}}>查询成交回执</button>{queried&&<p role="status">回执查询成功</p>}<button className="primary" onClick={onDone}>回到今天</button></section>;
  return <section><h2>{mode==='FILL'?'同步实际成交':'补充实际费用'}</h2><p>仅同步券商已发生的事实。没有建议或没有按建议执行也可记录；建议关联保持未知。</p>
    {!draft?<form onSubmit={e=>{e.preventDefault();void preview();}}><label>实际发生时点<input type="datetime-local" required value={effective} onChange={e=>setEffective(e.target.value)}/></label><label>成交依据与来源<input required value={source} onChange={e=>setSource(e.target.value)}/></label>
      {mode==='FILL'?<><div className="position-form"><label>成交交易所<select value={market} onChange={e=>setMarket(e.target.value)}><option>SSE</option><option>SZSE</option><option>BSE</option></select></label><label>成交证券代码<input required value={code} onChange={e=>setCode(e.target.value)}/></label><label>成交方向<select value={direction} onChange={e=>setDirection(e.target.value)}><option value="BUY">实际买入</option><option value="SELL">实际卖出</option></select></label><label>实际成交数量<input required value={quantity} onChange={e=>setQuantity(e.target.value)}/></label><label>原始成交价格（元）<input required value={price} onChange={e=>setPrice(e.target.value)}/></label></div>
      <label>分笔成交标识<input value={fillId} onChange={e=>setFillId(e.target.value)}/></label><label>券商委托标识（可选）<input value={orderId} onChange={e=>setOrderId(e.target.value)}/></label><p className="muted">同一委托的不同分笔分别录入；缺少分笔标识时保留歧义，不按价量自动合并。</p>
      <label>实际行为备注<select value={behavior} onChange={e=>setBehavior(e.target.value)}><option value="NO_RECOMMENDATION">没有对应建议</option><option value="CONTRARY">与建议相反</option><option value="EXCESS_QUANTITY">超出建议数量</option><option value="OFFLINE">离线时发生</option><option value="UNSPECIFIED">未说明</option></select></label>
      <label>费用状态<select value={feeStatus} onChange={e=>setFeeStatus(e.target.value)}><option value="KNOWN">实际费用已知</option><option value="PROVISIONAL">成交已确认，费用暂估</option></select></label>
      {feeStatus==='KNOWN'?<label>实际费用（元）<input required value={fee} onChange={e=>setFee(e.target.value)}/></label>:<label>保守预留费用（元）<input required value={reserve} onChange={e=>setReserve(e.target.value)}/></label>}<label>费用依据<input required value={basis} onChange={e=>setBasis(e.target.value)}/></label>
      <label>成交后已核对券商可用资金（元，可空）<input value={available} onChange={e=>setAvailable(e.target.value)}/></label><p className="muted">没有当前快照时保持未知；估计可用资金单独列示。暂估不会成为已知零费用或正式净收益。</p></>:
      <><label>费用对应成交<select value={target} onChange={e=>setTarget(e.target.value)}>{account.fills?.map(f=><option key={f.record_id} value={f.record_id}>{f.fill_id??f.record_id} · {f.instrument} · {f.quantity} 股</option>)}{account.share_records?.filter(r=>r.kind==='RIGHTS_SUBSCRIPTION').map(r=><option key={r.record_id} value={r.record_id}>{r.record_id} · {r.instrument} · 配股支付 {r.amount} 元</option>)}</select></label><label>补充实际费用（元）<input required value={fee} onChange={e=>setFee(e.target.value)}/></label><label>费用调整依据<input required value={basis} onChange={e=>setBasis(e.target.value)}/></label><p>调整追加保存，原记录保持可查。配股填写已支付总额中实际费用的分拆金额，现金与取得总成本保持不变。</p></>}
      <button className="primary" disabled={busy||mode==='FEE_ADJUSTMENT'&&!target}>{mode==='FILL'?'预览成交差异':'预览费用调整'}</button></form>:
      <><h3>{draft.status==='QUARANTINED'?'输入已保存，需核对':'确认前的资金与持仓差异'}</h3>{draft.issues?.map((issue,i)=><p key={i} role="status">{issue}</p>)}{draft.command?.kind==='FILL'&&(draft.command.payload.fee as {status:string})?.status==='PROVISIONAL'&&<p>费用暂估，实际费用仍未知</p>}
      <dl>{Object.entries(draft.preview).filter(([field])=>field in diffLabels).map(([field,value])=><div key={field}><dt>{diffLabels[field]}</dt><dd>之前：{display(field,value.before)}<br/>之后：{display(field,value.after)}</dd></div>)}</dl>
      <button className="primary" disabled={busy||draft.status==='QUARANTINED'} onClick={()=>void confirm()}>{mode==='FILL'?'确认实际成交':'确认费用调整'}</button><button disabled={busy} onClick={()=>{setDraft(null);sessionStorage.removeItem(storageKey);}}>返回修改</button></>}
    {error&&<p role="alert">{error}</p>}</section>;
}
function display(field:string,value:unknown):string{
  if(value===null||value===undefined)return '未知';
  if(field==='positions')return (value as Account['positions']).map(p=>`${p.instrument} ${p.quantity}股，取得成本${p.acquisition_cost??'未知'}元`).join('；')||'无持仓';
  const states:Record<string,string>={FEE_PENDING:'费用待核，净收益未确定',KNOWN_FEES:'费用已知',COST_UNKNOWN:'历史成本未知',FEE_BREAKDOWN_PENDING:'配股总支付已确认，费用分拆及费用前损益未知'};
  return states[String(value)]??String(value);
}
