import {useEffect,useRef,useState} from 'react';
import {Account,request} from '../api';
import {ObservationUpdatesPanel} from '../components/observation-updates-panel';
import {FinancialObservationPanel} from '../components/financial-observation-panel';
import {NewsPanel} from '../components/news-panel';
import {ReviewPanel} from '../components/review-panel';
import {DailyReportPanel} from '../components/daily-report-panel';
import '../styles/daily-report.css';
import {SyncFill} from './sync-fill';
import {AssistancePanel} from '../components/assistance-panel';
import '../styles/workbench.css';

const views=['研究判断','事实与来源','观察复盘'] as const;
const stamp=(value:string|null)=>value?new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}):'尚未确认';
export function DailyUse({account,onRefresh,onNavigate}:{account:Account;onRefresh:()=>void;onNavigate:(page:string)=>void}){
  const [members,setMembers]=useState<{instrument:string;identity:{name:string|null};watched:boolean}[]>([]),[instrument,setInstrument]=useState(''),[scopeError,setScopeError]=useState('');
  useEffect(()=>{let active=true;request<{members:{instrument:string;identity:{name:string|null};watched:boolean}[]}>('/market/list').then(v=>{if(active){setMembers(v.members??[]);setInstrument(current=>(v.members??[]).some(m=>m.instrument===current)?current:v.members?.[0]?.instrument??'');}}).catch(e=>{if(active)setScopeError(String(e));});return()=>{active=false;};},[account.version]);
  const companyName=members.find(m=>m.instrument===instrument)?.identity.name??instrument;
  const [recording,setRecording]=useState(false);
  const [view,setView]=useState(0);
  const accountPanel=useRef<HTMLElement|null>(null);
  const entry=useRef<HTMLDivElement|null>(null);
  useEffect(()=>{if(recording)entry.current?.focus();},[recording]);
  const tabs=useRef<(HTMLButtonElement|null)[]>([]);
  const supported=/^(SSE:(60|68)|SZSE:(00|30))\d{4}$/.test(instrument);
  const position=account.positions.find(p=>p.instrument===instrument);
  return <section className="daily-use workbench" aria-label="公司日常使用">
    <div className="wb-heading"><div><p className="wb-eyebrow">研究工作台 <span>/ {instrument||'请选择持仓或关注证券'}</span></p><h1>{companyName||'公司研究'} <span>日常使用</span></h1><p className="wb-intro">看清变化，形成判断，留下复盘。</p><label>研究对象 <select aria-label="研究对象" value={instrument} onChange={e=>{setInstrument(e.target.value);setRecording(false);}}>{members.map(m=><option key={m.instrument} value={m.instrument}>{m.identity.name??'身份名称待核'} · {m.instrument}{m.watched?' · 关注':''}</option>)}</select></label>{scopeError&&<p role="alert">{scopeError}</p>}{!members.length&&<p>先在「持仓与关注」选择有限证券；无需确认账户即可研究关注公司。</p>}</div><div className="wb-heading-tools"><span className="wb-label">按需分析 · 非实时覆盖</span><button className="wb-account-jump" onClick={()=>accountPanel.current?.focus()}>账户与成交 ↓</button></div></div>
    <div className="wb-layout">
      <div className="wb-main">
        <div className="wb-tabs" role="tablist" aria-label="工作台视图">{views.map((name,i)=><button key={name} ref={node=>{tabs.current[i]=node;}} id={`wb-tab-${i}`} role="tab" aria-selected={view===i} aria-controls={`wb-panel-${i}`} tabIndex={view===i?0:-1} onClick={()=>setView(i)} onKeyDown={event=>{let next=i;if(event.key==='ArrowRight')next=(i+1)%views.length;else if(event.key==='ArrowLeft')next=(i+views.length-1)%views.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=views.length-1;else return;event.preventDefault();setView(next);tabs.current[next]?.focus();}}><span className="wb-tab-number">0{i+1}</span>{name}</button>)}</div>
        <div id="wb-panel-0" role="tabpanel" aria-labelledby="wb-tab-0" hidden={view!==0} tabIndex={0}>{instrument&&<AssistancePanel key={instrument} instrument={instrument} companyName={companyName}/>}</div>
        <div id="wb-panel-1" role="tabpanel" aria-labelledby="wb-tab-1" hidden={view!==1} tabIndex={0} className="wb-facts"><div className="wb-section-intro"><p className="wb-eyebrow">证据底稿</p><h2>先核对事实，再理解变化</h2><p>行情、财报和新闻各自保留更新时间与来源缺口。更新请求不会生成交易动作。</p></div>{supported?<><ObservationUpdatesPanel instrument={instrument} expanded/><FinancialObservationPanel instrument={instrument}/><NewsPanel instrument={instrument}/></>:<p>旧财报/新闻采集器尚未支持此证券范围；请阅读共享研究的真实原件和缺口，不套用其他公司资料。</p>}</div>
        <div id="wb-panel-2" role="tabpanel" aria-labelledby="wb-tab-2" hidden={view!==2} tabIndex={0}><div className="wb-section-intro"><p className="wb-eyebrow">观察档案</p><h2>把当时知道的事实留下来</h2><p>按需观察与盘后回看保留各自的实际时点；研究笔记在「研究判断」中保存。</p></div><DailyReportPanel/><ReviewPanel/></div>
      </div>
      <aside ref={accountPanel} tabIndex={-1} className="wb-account" aria-label="账户与实际操作"><p className="wb-eyebrow">我的账户镜像</p><h2>{account.version===0?'先建立账户起点':'已确认的账户事实'}</h2><p className="wb-account-time">确认于 {stamp(account.confirmed_at)}<br/>不代表实时券商状态</p>
        {account.version===0?<p>填写你确认的当前现金与持仓，无需补齐过去全部交易。证券研究可先使用。</p>:<dl><div><dt>现金余额</dt><dd>{account.cash_balance===null?'未知':`${Number(account.cash_balance).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})} 元`}</dd></div><div><dt>{companyName}持仓</dt><dd>{position?`${position.quantity} 股`:'无已记录持仓'}</dd></div>{position&&<div><dt>可卖数量</dt><dd>{position.sellable_quantity===null?'未知':`${position.sellable_quantity} 股`}</dd></div>}</dl>}
        <button className="wb-account-primary" onClick={()=>onNavigate('同步账户')}>{account.version===0?'建立账户起点':'核对现金与持仓'}</button>
        <button disabled={account.version===0} aria-expanded={recording} aria-controls="wb-trade-entry" onClick={()=>setRecording(!recording)}>{recording?'收起成交录入':'记录实际买卖'}</button>
        <p className="wb-account-note">仅记录你在券商端实际发生的成交，提交前仍需预览并确认。</p>
        <div className="wb-links"><button onClick={()=>onNavigate('历史记录')}>查看成交与复盘记录 <span aria-hidden="true">↗</span></button><button onClick={()=>onNavigate('持仓与关注')}>行情与持仓详情 <span aria-hidden="true">↗</span></button></div>
      </aside>
      <div id="wb-trade-entry" ref={entry} tabIndex={-1} className="wb-trade-entry" hidden={!recording}>{recording&&<SyncFill account={account} mode="FILL" defaultCode={instrument.split(':')[1]??''} onDone={()=>{onRefresh();setRecording(false);}}/>}</div>
    </div>
  </section>;
}
