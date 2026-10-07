import {useEffect,useState} from 'react';
import {Account,Draft,Receipt,request} from '../api';

const names:Record<string,string>={CASH_IN:'现金转入',CASH_OUT:'现金转出',DIVIDEND:'分红到账',INTEREST:'利息到账',TAX:'税款扣除',FEE:'费用扣除',PENDING_ITEM:'确认应收/应付',SETTLEMENT:'关联实际结算',CASH_CORRECTION:'追加金额更正',SHARE_CHANGE:'实际股份变动'};
const labels:Record<string,string>={cash_balance:'实际账面现金',positions:'实际持仓与成本',broker_available:'券商可用资金',investment_income:'累计实际到账投资收入',investment_expenses:'累计实际扣款税费',external_cash_in:'累计外部转入',external_cash_out:'累计外部转出',pending_income:'未结应收',pending_expenses:'未结应付',pending_items:'应收/应付状态'};
const optional=(value:string)=>value.trim()||null;
const display=(value:unknown)=>value===null||value===undefined?'未知':typeof value==='object'?JSON.stringify(value,null,2):String(value);

export function SyncCash({account,onDone}:{account:Account;onDone:()=>void}){
  const [kind,setKind]=useState('CASH_IN'),[record,setRecord]=useState<string>(()=>crypto.randomUUID()),[amount,setAmount]=useState(''),[target,setTarget]=useState('');
  const [security,setSecurity]=useState(''),[quantity,setQuantity]=useState(''),[itemType,setItemType]=useState('DIVIDEND'),[available,setAvailable]=useState('');
  const [effective,setEffective]=useState(()=>new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16));
  const [source,setSource]=useState('用户核对账户流水'),[basis,setBasis]=useState(''),[draft,setDraft]=useState<Draft|null>(null),[key,setKey]=useState('');
  const [receipt,setReceipt]=useState<Receipt|null>(null),[queried,setQueried]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [hintSource,setHintSource]=useState(''),[declared,setDeclared]=useState(''),[content,setContent]=useState(''),[hintStatus,setHintStatus]=useState('');
  useEffect(()=>{const raw=sessionStorage.getItem('roll.pending-CASH_EVENT');if(raw){const saved=JSON.parse(raw);request<Draft>(`/account/drafts/${saved.draft_id}`).then(d=>{setDraft(d);setKey(saved.key);}).catch(()=>sessionStorage.removeItem('roll.pending-CASH_EVENT'));}},[]);
  async function preview(){setBusy(true);setError('');try{
    const common={effective_at:effective?new Date(effective).toISOString():null,source,record_id:record,basis};
    const payload=kind==='SHARE_CHANGE'?{...common,instrument:optional(security),new_quantity:optional(quantity)}
      :kind==='PENDING_ITEM'?{...common,instrument:optional(security),item_type:itemType,amount:optional(amount)}
      :kind==='SETTLEMENT'?{...common,target_record_id:target,amount:optional(amount),broker_available_after:optional(available)}
      :kind==='CASH_CORRECTION'?{...common,target_record_id:target,corrected_amount:optional(amount),broker_available_after:optional(available)}
      :{...common,instrument:optional(security),amount:optional(amount),broker_available_after:optional(available)};
    const value=await request<Draft>('/account/drafts',{kind,expected_account_version:account.version,payload});const k=crypto.randomUUID();setDraft(value);setKey(k);sessionStorage.setItem('roll.pending-CASH_EVENT',JSON.stringify({draft_id:value.draft_id,key:k}));
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  async function confirm(){setBusy(true);setError('');try{setReceipt(await request<Receipt>('/account/confirm',{draft_id:draft!.draft_id,idempotency_key:key}));sessionStorage.removeItem('roll.pending-CASH_EVENT');}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function saveHint(){setError('');try{const saved=await request<{learned_at:string}>('/account/equity-hints',{source:hintSource,declared_at:optional(declared),instrument:optional(security),content});setHintStatus(`待核材料已保存，获知于 ${saved.learned_at}；实际现金与持仓未变化。`);}catch(e){setError(String(e));}}
  if(receipt)return <section><h2>已确认，回执已保存</h2><p>账户版本 {receipt.account_version} · 回执 {receipt.receipt_id}</p><button onClick={async()=>{try{setReceipt(await request<Receipt>(`/account/receipts/${receipt.receipt_id}`));setQueried(true);}catch(e){setError(String(e));}}}>查询回执</button>{queried&&<p role="status">回执查询成功</p>}<button onClick={onDone}>回到今天</button>{error&&<p role="alert">{error}</p>}</section>;
  return <section><h2>资金与权益</h2><p>仅确认个人账户实际事实。未到账应收/应付单列；公告和网页说法保存为待核材料。</p>
    {!draft?<form onSubmit={e=>{e.preventDefault();void preview();}}>
      <label>变动类别<select aria-label="变动类别" value={kind} onChange={e=>setKind(e.target.value)}>{Object.entries(names).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      <label>实际发生时点<input type="datetime-local" value={effective} onChange={e=>setEffective(e.target.value)}/></label><p className="muted">时点或个人金额未知可保存待核草稿，不能确认入账。</p>
      <label>来源<input value={source} required onChange={e=>setSource(e.target.value)}/></label><label>依据<input value={basis} required onChange={e=>setBasis(e.target.value)}/></label><label>流水标识<input value={record} required onChange={e=>setRecord(e.target.value)}/></label>
      {kind==='PENDING_ITEM'&&<label>应收/应付类别<select value={itemType} onChange={e=>setItemType(e.target.value)}><option value="DIVIDEND">应收分红</option><option value="INTEREST">应收利息</option><option value="TAX">应付税款</option><option value="FEE">应付费用</option></select></label>}
      {['SETTLEMENT','CASH_CORRECTION'].includes(kind)&&<label>关联原流水标识<input value={target} required onChange={e=>setTarget(e.target.value)}/></label>}
      {kind==='SHARE_CHANGE'?<label>变动后持仓数量<input value={quantity} inputMode="decimal" onChange={e=>setQuantity(e.target.value)}/></label>:<label>{kind==='CASH_CORRECTION'?'更正后原总金额（元）':'金额（元）'}<input value={amount} inputMode="decimal" onChange={e=>setAmount(e.target.value)}/></label>}
      {!['SETTLEMENT','CASH_CORRECTION'].includes(kind)&&<label>证券（交易所:代码，现金事项可空）<input value={security} onChange={e=>setSecurity(e.target.value)}/></label>}
      {!['PENDING_ITEM','SHARE_CHANGE'].includes(kind)&&<label>核对后的当前券商可用资金（元，可空）<input value={available} inputMode="decimal" onChange={e=>setAvailable(e.target.value)}/></label>}
      {kind==='CASH_CORRECTION'&&<p>填写原事项更正后的总金额，系统只追加差额；更正应收/应付时请保持券商可用资金空白。</p>}
      <button className="primary" disabled={busy}>预览差异</button>
    </form>:<section><h3>确认前的差异</h3><p>{names[draft.command?.kind??kind]} · 仍为草稿，尚未入账。</p>{draft.issues?.map((issue,i)=><p role="alert" key={i}>{issue}</p>)}{draft.status==='QUARANTINED'?<p>原输入已保存待核，现金与数量保持原值。</p>:<dl className="difference">{Object.entries(draft.preview).filter(([field])=>field in labels).map(([field,value])=><div key={field}><dt>{labels[field]}</dt><dd><span>之前：{display(value.before)}</span><strong>之后：{display(value.after)}</strong></dd></div>)}</dl>}
      <button className="primary" disabled={busy||draft.status==='QUARANTINED'} onClick={()=>void confirm()}>确认入账</button><button disabled={busy} onClick={()=>{setDraft(null);sessionStorage.removeItem('roll.pending-CASH_EVENT');}}>返回修改</button></section>}
    <details><summary>保存待核权益线索</summary><p>宣告内容不证明个人到账；保存后不改变实际账户。</p><label>线索来源<input value={hintSource} onChange={e=>setHintSource(e.target.value)}/></label><label>宣告日期或时点（按原文，可空）<input value={declared} onChange={e=>setDeclared(e.target.value)}/></label><label>宣告内容<textarea value={content} onChange={e=>setContent(e.target.value)}/></label><button disabled={!hintSource.trim()||!content.trim()} onClick={()=>void saveHint()}>保存待核材料</button>{hintStatus&&<p role="status">{hintStatus}</p>}</details>
    {error&&<p role="alert">{error}</p>}</section>;
}
