import {FormEvent, useEffect, useState} from 'react';
import {request, Position, Permission} from '../api';
import '../styles/market.css';
import {Evidence} from './evidence';
import {Valuation} from './valuation';
import {ActionPanel} from '../components/action-panel';
import {StatusEvidencePanel} from '../components/status-evidence-panel';
import {ActionEvidencePanel} from '../components/action-evidence-panel';

type Source = {id:string;url:string;sha256:string;fetched_at:string};
type Rule = {implementation_status:string;reason?:string;effective_from?:string;adapted_date_range?:string[];buy_minimum?:string;buy_increment?:string;price_tick_yuan?:string;normal_price_limit_percent?:string;source:Source|null;fees?:{state:string;reason:string}};
type Member = {instrument:string;holding:Position|null;watched:boolean;watch_added_at:string|null;identity:{exchange:string;board:string;instrument_type:string;name:string|null;source:{kind:string;basis?:string}|null};rule:Rule;account_permission:Permission;current_status:{state:string;reason:string};limitations:string[]};
type Listing = {version:number;recorded_at:string;account_version:number;members:Member[];limit:number;over_limit:boolean;background_indices:{instrument:string;name:string}[]};
type Calendar = {exchange:string;date:string;is_trading_day:boolean|null;phase:string;reason:string|null;next_trading_day:string|null;coverage:string;source:Source|null};
const status:{[key:string]:string} = {OPEN:'已开通',NOT_OPEN:'未开通',UNKNOWN:'未知'};
const boardNames:{[key:string]:string} = {MAIN:'主板',STAR:'科创板',CHINEXT:'创业板',BSE:'北交所',UNKNOWN:'未核对',OTHER:'其他'};
const localNow=()=>new Date(Date.now()+8*60*60*1000).toISOString().slice(0,16);

function IdentityForm({member,onDone}:{member:Member;onDone:(v:Listing)=>void}) {
  const [board,setBoard]=useState(member.identity.board);
  const [name,setName]=useState(member.identity.name??'');
  const [instrumentType,setInstrumentType]=useState(member.identity.instrument_type==='UNKNOWN'?'':member.identity.instrument_type);
  const [basis,setBasis]=useState('');
  const [at,setAt]=useState(localNow());
  const [error,setError]=useState('');
  async function save(e:FormEvent){e.preventDefault();try{
    onDone(await request<Listing>('/market/identities',{instrument:member.instrument,exchange:member.identity.exchange,board,instrument_type:instrumentType,name,basis,effective_at:`${at}+08:00`}));setError('');
  }catch(e){setError(String(e));}}
  return <details><summary>核对证券身份与依据</summary><form onSubmit={save}>
    <p className="muted">按券商证券详情确认板块与普通 A 股身份，未核对时保留未知。确认身份后仍会分别核对账户权限、当前状态与模型资格。</p>
    <label>证券名称<input value={name} onChange={e=>setName(e.target.value)} required maxLength={80}/></label>
    <label>已核对板块<select value={board} onChange={e=>setBoard(e.target.value)}>{Object.entries(boardNames).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    <label>证券类型<select aria-label="证券类型" value={instrumentType} onChange={e=>setInstrumentType(e.target.value)} required><option value="">未核对</option><option value="STOCK">普通 A 股</option><option value="OTHER">其他证券（基本规则未适配）</option></select></label>
    <label>身份确认依据<input value={basis} onChange={e=>setBasis(e.target.value)} required maxLength={1000}/></label>
    <label>身份事实截至时点（上海时间）<input type="datetime-local" value={at} onChange={e=>setAt(e.target.value)} required/></label>
    {error&&<p role="alert">{error}</p>}<button>保存已核对身份</button>
  </form></details>;
}

export function Market() {
  const [showValuation,setShowValuation]=useState(false);
  const [showEvidence,setShowEvidence]=useState(false);
  const [listing,setListing]=useState<Listing|null>(null);
  const [error,setError]=useState('');
  const [exchange,setExchange]=useState('SSE');
  const [code,setCode]=useState('');
  const [calendarExchange,setCalendarExchange]=useState('SSE');
  const [date,setDate]=useState(localNow().slice(0,10));
  const [calendar,setCalendar]=useState<Calendar|null>(null);
  const [history,setHistory]=useState<Listing[]>([]);
  const [membership,setMembership]=useState<{account_version:number;confirmed_at:string;materialized_at:string;members:{instrument:string;held:boolean;watched:boolean;identity:Member['identity']|null}[]}[]>([]);
  const [past,setPast]=useState<Listing|null>(null);
  const [busy,setBusy]=useState(false);
  async function calendarQuery(){try{setCalendar(await request<Calendar>(`/market/calendar?exchange=${calendarExchange}&date=${date}`));setError('');}catch(e){setError(String(e));}}
  useEffect(()=>{void request<Listing>('/market/list').then(setListing).catch(e=>setError(String(e)));void calendarQuery();},[]);
  async function edit(operation:string,instrument:string){if(!listing)return;setBusy(true);try{
    setListing(await request<Listing>('/market/watch',{operation,instrument,expected_list_version:listing.version}));setError('');if(operation==='ADD')setCode('');
  }catch(e){setError(String(e));setListing(await request<Listing>('/market/list'));}finally{setBusy(false);}}
  async function loadHistory(){try{const response=await request<{versions:Listing[];account_membership_history:typeof membership}>('/market/history');setHistory(response.versions);setMembership(response.account_membership_history);setPast(null);}catch(e){setError(String(e));}}
  if(showEvidence)return <><button onClick={()=>setShowEvidence(false)}>返回持仓与关注</button><Evidence/></>;
  if(showValuation)return <><button onClick={()=>setShowValuation(false)}>返回持仓与关注</button><Valuation/></>;
  return <><button onClick={()=>setShowEvidence(true)}>市场事实</button><button onClick={()=>setShowValuation(true)}>账户估值与绩效</button><section><h1>持仓与关注</h1><p>真实持仓自动纳入。关注只用于有限名单内观察，交易判断尚未启用。</p>
    {error&&<p role="alert">{error}</p>}
    {!listing?<p>正在读取名单…</p>:<><p className="muted">名单版本 {listing.version} · 账户版本 {listing.account_version} · 共 {listing.members.length} 只</p>
      {listing.over_limit&&<p role="alert">名单超过 {listing.limit} 只，全部真实资产继续展示；新增关注暂受限。</p>}
      <form className="watch-form" onSubmit={e=>{e.preventDefault();void edit('ADD',`${exchange}:${code}`);}}>
        <label>关注交易所<select value={exchange} onChange={e=>setExchange(e.target.value)}><option value="SSE">上交所</option><option value="SZSE">深交所</option><option value="BSE">北交所</option></select></label>
        <label>关注代码<input value={code} onChange={e=>setCode(e.target.value)} pattern="[0-9]{6}" maxLength={6} required placeholder="六位代码"/></label>
        <button disabled={busy}>添加关注</button>
      </form>
      {!listing.members.length&&<p>尚无持仓与关注，可同步账户或添加关注。</p>}
      {listing.members.map(m=><article className="market-member" key={m.instrument} aria-label={m.instrument}>
        <div className="member-heading"><h2>{m.identity.name??m.instrument}{m.identity.name&&<span className="muted"> · {m.instrument}</span>}</h2><button disabled={busy} onClick={()=>void edit(m.watched?'REMOVE':'ADD',m.instrument)}>{m.watched?'取消关注':'加入关注'}</button></div>
        <p>{m.holding?`实际持仓 ${m.holding.quantity} 股 · 可卖 ${m.holding.sellable_quantity??'未知'}`:'关注证券'}</p>
        <p>身份：{m.identity.exchange} / {boardNames[m.identity.board]??m.identity.board} / {m.identity.instrument_type==='STOCK'?'普通 A 股':m.identity.instrument_type==='OTHER'?'其他证券':'类型未核对'}</p>
        <p>规则：{m.rule.implementation_status==='ADAPTED'?'基本规则已适配':'未适配'} · 账户权限：{status[m.account_permission.status]}</p>
        <p className="muted">当前证券状态未知，依赖该状态的交易用途受限。账户权限{status[m.account_permission.status]} · 模型资格未授予。</p>
        <details><summary>查看规则、状态与依据</summary>
          <p>{m.current_status.reason}</p><p>账户权限依据：{m.account_permission.basis}</p>
          {m.rule.implementation_status==='ADAPTED'?<><p>买入至少 {m.rule.buy_minimum} 股，按 {m.rule.buy_increment} 股递增；价格最小变动 {m.rule.price_tick_yuan} 元。普通状态涨跌幅 {m.rule.normal_price_limit_percent}%。数量、价格限制仍需核对当日特殊状态。</p><p>规则自 {m.rule.effective_from} 生效，本次适配日期 {m.rule.adapted_date_range?.join(' 至 ')}。买入后最早下一交易日可卖，实际可卖数量按账户事实核对。</p><p>费用：{m.rule.fees?.reason}</p></>:<p>{m.rule.reason}</p>}
          {m.rule.source&&<p><a href={m.rule.source.url} target="_blank" rel="noreferrer">交易所原规则</a> · <a href={`/api/market/sources/${m.rule.source.id}/raw`}>已归档原件</a> · 取得于 {m.rule.source.fetched_at}</p>}
          {m.identity.source&&<p>身份来源：用户核对 · {m.identity.source.basis}</p>}
        </details><StatusEvidencePanel instrument={m.instrument}/><ActionEvidencePanel instrument={m.instrument}/><IdentityForm member={m} onDone={setListing}/><details><summary>查看单股当前动作</summary><ActionPanel instrument={m.instrument}/></details>
      </article>)}
      <p className="muted">背景指数：{listing.background_indices.map(i=>`${i.name}（${i.instrument}）`).join('、')}。仅作市场背景/基准，无指数交易能力。</p>
    </>}
  </section><section><h2>交易日与规则范围</h2><form className="watch-form" onSubmit={e=>{e.preventDefault();void calendarQuery();}}>
    <label>日历交易所<select value={calendarExchange} onChange={e=>setCalendarExchange(e.target.value)}><option value="SSE">上交所</option><option value="SZSE">深交所</option><option value="BSE">北交所</option></select></label>
    <label>查询日期（上海时间）<input type="date" value={date} onChange={e=>setDate(e.target.value)} required/></label><button>查询交易日</button>
  </form>{calendar&&<><p>{calendar.date} · {calendar.exchange} · {calendar.is_trading_day===null?'日历未取得，交易日未知':calendar.is_trading_day?'交易日':'休市'}</p><p>下一个已知交易日：{calendar.next_trading_day??'未知'}</p>{calendar.source&&<p className="muted"><a href={calendar.source.url} target="_blank" rel="noreferrer">交易所休市安排</a> · <a href={`/api/market/sources/${calendar.source.id}/raw`}>已归档原件</a></p>}</>}
    <p className="muted">已取得上交所 2013—2026 年及深交所 2026 年日历；历史交易阶段及未适配规则保持未知。基本规则适配沪市主板、科创板与深市主板、创业板的普通 A 股，日期限 2026-07-06 至 2026-12-31。北交所原页本次访问受限，规则/日历范围未适配；全部真实持仓仍可查看。盘中临时停市与证券停牌另需当前证据。</p>
  </section><section><h2>名单历史</h2><button onClick={()=>void loadHistory()}>查询名单历史</button>{history.map(v=><button key={v.version} onClick={()=>setPast(v)}>查看名单版本 {v.version}</button>)}
    {past&&<div><p>名单版本 {past.version} · 记录于 {past.recorded_at} · 账户版本 {past.account_version}</p><ul>{past.members.map(m=><li key={m.instrument}>{m.instrument} · {m.holding?'实际持仓':'关注'}{m.watched?' · 已关注':''} · {boardNames[m.identity.board]??m.identity.board} · 权限{status[m.account_permission.status]}</li>)}</ul></div>}
    {!!membership.length&&<details><summary>每次账户确认时的成员变化</summary><p className="muted">包括当时未打开页面的账户版本；身份仅使用当时已确认的知识，不补写为历史市场观察。</p>{membership.map(v=><p key={v.account_version}>账户版本 {v.account_version} · 确认于 {v.confirmed_at} · 成员历史整理于 {v.materialized_at}：{v.members.map(m=>`${m.instrument}（${m.held?'持仓':'关注'}，${m.identity?.board??'身份未知'}）`).join('、')||'空名单'}</p>)}</details>}
  </section></>;
}
