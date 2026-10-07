import {FormEvent,useEffect,useState} from 'react';
import {request} from '../api';

type Basis={baseline_account_version:number;origin_at:string;as_of:string;scope_kind:string;scope_id:string;funding_version:number};
type Quote={upstream_at:string;available_at:string;source_id:string;raw_hash:string;evidence_kind:string};
type Value={valuation_id:string;method_version:string;account_version:number;known_by:string;origin_at:string;as_of:string;cash_plus_holdings:string|null;cash_estimated:boolean;asynchronous_quotes:boolean;
  account:{confirmed_at:string;effective_at:string;cash_balance:string;cash_balance_basis:string;broker_available:string|null;broker_available_as_of:string|null;broker_frozen:string|null;broker_frozen_as_of:string|null;withdrawable:string|null;withdrawable_as_of:string|null;fees_pending:string[]|null;rights_fee_breakdown_pending:string[]|null};
  positions:{instrument:string;quantity:string;price:string|null;market_value:string|null;acquisition_cost_including_fees:string|null;broker_reference_cost:string|null;quote_status:string;quote:Quote|null}[];
  pending_income:string;pending_expenses:string;pending_items:{record_id:string;item_type:string;outstanding_amount:string;settled_amount:string;status:string;basis:string;settlement_ids:string[]}[];
  facts:{baseline_assets:string|null;net_assets:string|null;realized_pnl:string|null;unrealized_pnl:string|null;income:string|null;fees:string|null;external_in:string|null;external_out:string|null;pending_income_delta:string|null;pending_expense_delta:string|null;valuation_status:string};
  performance:{total_pnl:string|null;nav_adjusted_pnl:string|null;conservation:string;return_percent:string|null;weighted_capital:string|null;estimated:boolean}};
const amount=(value:string|null|undefined)=>value===null||value===undefined?'未知':`${value} 元`;
const statusNames:Record<string,string>={MISSING:'报价或必要事实缺失',STALE:'陈旧／非同步估值',COMPLETE:'所选日原价估值',SAME_DAY_INDICATIVE:'同日参考价'};

export function Valuation(){
  const [basis,setBasis]=useState<Basis|null>(null);
  const [value,setValue]=useState<Value|null>(null);
  const [history,setHistory]=useState<Value[]>([]);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  useEffect(()=>{void request<Basis>('/account/valuation-basis').then(setBasis).catch(e=>setError(String(e)));void request<Value[]>('/account/valuations').then(v=>{setHistory(v);setValue(v[0]??null);}).catch(e=>setError(String(e)));},[]);
  async function publish(e:FormEvent){e.preventDefault();if(!basis)return;setBusy(true);try{const v=await request<Value>('/account/valuations',{baseline_account_version:basis.baseline_account_version,origin_at:basis.origin_at,as_of:basis.as_of,scope_kind:basis.scope_kind,scope_id:basis.scope_id});setValue(v);setHistory([v,...history]);setError('');setMessage('估值版本已保存，可按原输入重放。');}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function replay(){if(!value)return;setBusy(true);try{setValue(await request<Value>(`/account/valuations/${value.valuation_id}/replay`,{}));setMessage('原账户与报价输入重放一致。');setError('');}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <section><h1>账户估值与绩效</h1><p>现金账面余额加各持仓原始报价，已确认应收与应付另列。冻结款仍属于现金资产。基线前历史不完整，不推算全历史收益。</p>
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {basis&&<form onSubmit={publish}>
      <label>基线账户版本<input type="number" min="1" value={basis.baseline_account_version} readOnly={basis.funding_version>0} onChange={e=>setBasis({...basis,baseline_account_version:Number(e.target.value)})} required/></label>
      <label>计算起点（含时区）<input value={basis.origin_at} readOnly={basis.funding_version>0} onChange={e=>setBasis({...basis,origin_at:e.target.value})} required/></label>
      <label>估值截止（含时区）<input value={basis.as_of} onChange={e=>setBasis({...basis,as_of:e.target.value})} required/></label>
      {basis.funding_version>0&&<p className="muted">沿已确认资金范围保留原基线与损失起点。</p>}
      <button disabled={busy}>计算并保存估值</button>
    </form>}
    {history.length>0&&<label>查看已保存估值<select aria-label="查看已保存估值" value={value?.valuation_id??''} onChange={e=>{setValue(history.find(v=>v.valuation_id===e.target.value)??null);setMessage('');}}>{history.map(v=><option key={v.valuation_id} value={v.valuation_id}>{v.as_of} · 账户 {v.account_version} · {v.valuation_id.slice(0,8)}</option>)}</select></label>}
    {value&&<><h2>{statusNames[value.facts.valuation_status]}</h2><p>账户版本 {value.account_version} · 确认于 {value.account.confirmed_at} · 事实截至 {value.account.effective_at}</p><p className="muted">估值截止 {value.as_of} · 已知输入截止 {value.known_by}</p>
      {value.performance.estimated&&<p role="note">使用原时点的陈旧价格，仅为显式估算。报价新鲜度不代表交易资格。</p>}
      {value.asynchronous_quotes&&<p role="note">证券报价时点不同，本次估值非同步。</p>}
      <dl><dt>现金与持仓市值{value.cash_estimated?'（含暂估费用扣款）':''}</dt><dd data-testid="valuation-assets">{amount(value.cash_plus_holdings)}</dd><dt>含确认待结算项净资产</dt><dd data-testid="valuation-net">{amount(value.facts.net_assets)}</dd><dt>基线净资产</dt><dd>{amount(value.facts.baseline_assets)}</dd>
        <dt>已实现价格损益（费用前）</dt><dd>{amount(value.facts.realized_pnl)}</dd><dt>未实现价格损益（费用前）</dt><dd>{amount(value.facts.unrealized_pnl)}</dd><dt>实际收入</dt><dd>{amount(value.facts.income)}</dd><dt>实际费用及税</dt><dd>{amount(value.facts.fees)}</dd><dt>外部转入／转出</dt><dd>{amount(value.facts.external_in)} ／ {amount(value.facts.external_out)}</dd>
        <dt>已知范围总盈亏</dt><dd data-testid="valuation-pnl">{amount(value.performance.total_pnl)}</dd><dt>现金流调整收益率</dt><dd>{value.performance.return_percent===null?'未知':`${value.performance.return_percent}%`}</dd></dl>
      <p className="muted">收益率采用修正 Dietz：总盈亏除以基线净资产与按实际发生时间加权的外部净投入。分红、利息属于收入；确认未结收入／费用按余额变化计入一次，结算只转为现金。费用前批次按 FIFO 分摊，费用独立扣除；报价陈旧时金额与比例均为估算。</p>
      <h2>现金资金口径</h2><p>账面现金 {amount(value.account.cash_balance)} · 券商可用 {amount(value.account.broker_available)} · 冻结 {amount(value.account.broker_frozen)} · 可取 {amount(value.account.withdrawable)}</p>
      <p className="muted">券商可用截至 {value.account.broker_available_as_of??'未知'} · 冻结截至 {value.account.broker_frozen_as_of??'未知'} · 可取截至 {value.account.withdrawable_as_of??'未知'}。冻结金额未重复扣减。</p>
      {(value.account.fees_pending?.length||value.account.rights_fee_breakdown_pending?.length)?<p role="note">费用或配股本金分拆待核，损益与现金口径保留未知；暂估费用不当作已结算费用。</p>:null}
      <h2>持仓原价估值</h2>{!value.positions.length&&<p>所选时点无持仓。</p>}{value.positions.map(p=><article key={p.instrument} aria-label={`估值 ${p.instrument}`}><h3>{p.instrument}</h3><p>数量 {p.quantity??'未知'} · 原始报价 {amount(p.price)} · 市值 {amount(p.market_value)} · {statusNames[p.quote_status]}</p><p>实际含费剩余成本 {amount(p.acquisition_cost_including_fees)} · 券商参考单位成本 {amount(p.broker_reference_cost)}</p>{p.quote?<p className="muted">报价截至 {p.quote.upstream_at} · 取得于 {p.quote.available_at} · {p.quote.source_id} · {p.quote.evidence_kind==='METHOD_CASE'?'方法案例':'实际原件'} · <a href={`/api/data/archives/${p.quote.raw_hash}`}>报价原件</a></p>:<p>未取得可用于该时点的原价报价，未填零市值。</p>}</article>)}
      <h2>确认待结算项</h2><p>应收 {amount(value.pending_income)} · 应付 {amount(value.pending_expenses)}，计入净资产，尚未计入现金或券商可用。</p>{value.pending_items.map(p=><article key={p.record_id}><p>{p.record_id} · {p.item_type} · {p.status} · 已结 {amount(p.settled_amount)} · 未结 {amount(p.outstanding_amount)}</p><p className="muted">{p.basis} · 关联结算 {p.settlement_ids.join('、')||'暂无'}</p></article>)}
      <details><summary>查看计算与重放依据</summary><p>口径 {value.method_version} · 估值版本 {value.valuation_id} · 分项与净资产核对 {value.performance.conservation}</p><p>净资产减基线与外部净投入：{amount(value.performance.nav_adjusted_pnl)} · 时间加权资本：{amount(value.performance.weighted_capital)}</p><p>本页仅发布账户事实，资金剩余额度及正式动作未授予。</p><button disabled={busy} onClick={()=>void replay()}>重放原输入</button></details>
    </>}
  </section>;
}
