import {useEffect,useState} from 'react';
import {Account,Funding,request} from '../api';

type CostCommand={expected_version:number;expected_account_version:number;expected_funding_version:number;idempotency_key:string;market:'SSE';board:'MAIN';instrument_type:'STOCK';effective_from:string;effective_until:string;commission_including_regulatory_rate:string;minimum_commission_yuan:string;transfer_each_side_rate:string;source_name:string;source_text:string;confirmed:true};
type CostRecord={version:number;confirmed_at:string;contract_fingerprint:string;command:CostCommand};
type Costs={version:number;current:CostRecord|null;versions:CostRecord[];limitations:string[];current_status:string;current_reasons:string[]};
const costReasons:Record<string,string>={BROKER_COST_ACCOUNT_OR_FUNDING_VERSION_CHANGED:'账户或资金范围已变更，须重新确认适用依据。',BROKER_COST_OUTSIDE_EFFECTIVE_INTERVAL:'当前时间不在费用依据的生效区间内。',BROKER_COST_SOURCE_UNAVAILABLE_OR_CORRUPT:'费用依据原件无法核验，须检查原件。'};
const pendingKey='roll.broker-cost.confirmation';
function savedCommand():CostCommand|null{try{return JSON.parse(sessionStorage.getItem(pendingKey)??'null');}catch{return null;}}

export function BrokerCostPanel({funding}:{funding:Funding}){
  const [costs,setCosts]=useState<Costs|null>(null),[account,setAccount]=useState<Account|null>(null);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[pending,setPending]=useState<CostCommand|null>(savedCommand);
  const [from,setFrom]=useState(''),[until,setUntil]=useState(''),[commission,setCommission]=useState(''),[minimum,setMinimum]=useState(''),[transfer,setTransfer]=useState('');
  const [sourceName,setSourceName]=useState(''),[sourceText,setSourceText]=useState(''),[confirmed,setConfirmed]=useState(false),[history,setHistory]=useState<CostRecord|null>(null);
  async function refresh(){const [c,a]=await Promise.all([request<Costs>('/actions/broker-costs'),request<Account>('/account')]);setCosts(c);setAccount(a);}
  useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[funding.version]);
  async function save(){
    if(!costs||!account)return;
    setBusy(true);setError('');
    try{
      const command:CostCommand=pending??{expected_version:costs.version,expected_account_version:account.version,expected_funding_version:funding.version,idempotency_key:crypto.randomUUID(),market:'SSE',board:'MAIN',instrument_type:'STOCK',effective_from:new Date(from).toISOString(),effective_until:new Date(until).toISOString(),commission_including_regulatory_rate:commission,minimum_commission_yuan:minimum,transfer_each_side_rate:transfer,source_name:sourceName,source_text:sourceText,confirmed:true};
      setPending(command);sessionStorage.setItem(pendingKey,JSON.stringify(command));
      const response=await fetch('/api/actions/broker-costs/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command)});
      const value=await response.json();
      if(response.status>=500)throw new Error('确认结果未明，请重试原确认');
      setPending(null);sessionStorage.removeItem(pendingKey);
      if(!response.ok){setError(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));await refresh();return;}
      setHistory(value);setConfirmed(false);setSourceText('');await refresh();
    }catch(e){setError(`${String(e)}${sessionStorage.getItem(pendingKey)?'；已保留原内容，可重试找回回执。':''}`);}finally{setBusy(false);}
  }
  const ready=!!account?.version&&!!funding.version;
  return <section aria-label="券商费用"><h2>券商费用</h2>
    <p>{costs?.current?`已登记版本 ${costs.version}`:'尚未登记券商费用'}。登记后仍须通过动作政策及资格检查。</p>
    {costs?.current_reasons.map(reason=><p key={reason}>{costReasons[reason]??'当前费用依据受限，请核对适用范围与原件。'}</p>)}
    {error&&<p role="alert">{error}</p>}
    <details><summary>登记费用依据与查看历史</summary>
      {!ready&&<p>先建立账户并确认资金范围。</p>}
      {!!pending&&<p>上次确认结果未明，将重试同一份原内容。</p>}
      <form onSubmit={e=>{e.preventDefault();void save();}}>
        <fieldset disabled={busy||!!pending||!ready||!costs} className="funding-fields broker-cost-fields">
          <legend>上交所主板股票买入费用</legend>
          <label>生效时间<input type="datetime-local" required value={from} onChange={e=>setFrom(e.target.value)}/></label>
          <label>截止时间<input type="datetime-local" required value={until} onChange={e=>setUntil(e.target.value)}/></label>
          <label>佣金综合费率（小数）<input required inputMode="decimal" value={commission} onChange={e=>setCommission(e.target.value)}/></label>
          <label>最低佣金（元）<input required inputMode="decimal" value={minimum} onChange={e=>setMinimum(e.target.value)}/></label>
          <label>过户费率（小数）<input required inputMode="decimal" value={transfer} onChange={e=>setTransfer(e.target.value)}/></label>
          <label className="broker-cost-wide">依据名称<input required maxLength={200} value={sourceName} onChange={e=>setSourceName(e.target.value)}/></label>
          <label className="broker-cost-wide">费用依据原文<textarea required maxLength={20000} value={sourceText} onChange={e=>setSourceText(e.target.value)}/></label>
          <label className="broker-cost-wide"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>确认以上来自当前券商费用依据，适用于当前账户与资金范围</label>
        </fieldset>
        <button type="submit" disabled={busy||!ready||!costs||(!pending&&!confirmed)}>{pending?'重试原确认':'确认费用依据'}</button>
      </form>
      {costs&&costs.versions.length>0&&<p>历史版本：{costs.versions.map(v=><button type="button" key={v.version} onClick={()=>void request<CostRecord>(`/actions/broker-costs/versions/${v.version}`).then(setHistory).catch(e=>setError(String(e)))}>版本 {v.version}</button>)}</p>}
      {history&&<p role="status">版本 {history.version} · {history.command.source_name} · {history.command.effective_from} 至 {history.command.effective_until}</p>}
    </details>
  </section>;
}
