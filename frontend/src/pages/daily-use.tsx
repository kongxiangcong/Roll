import {useEffect,useState} from 'react';
import {Account,request} from '../api';
import {ObservationUpdatesPanel} from '../components/observation-updates-panel';
import {FinancialObservationPanel} from '../components/financial-observation-panel';
import {NewsPanel} from '../components/news-panel';
import {ReviewPanel} from '../components/review-panel';
import {DailyReportPanel} from '../components/daily-report-panel';
import '../styles/daily-report.css';
import {SyncFill} from './sync-fill';

export function DailyUse({account,onRefresh,onNavigate}:{account:Account;onRefresh:()=>void;onNavigate:(page:string)=>void}){
  const [recording,setRecording]=useState(false);
  const [members,setMembers]=useState<{instrument:string;identity:{name:string|null};holding:unknown}[]>([]);
  const [selected,setSelected]=useState(''),[error,setError]=useState('');
  useEffect(()=>{let active=true;request<{members:typeof members}>('/market/list').then(v=>{if(active){setMembers(v.members);setSelected(old=>v.members.some(m=>m.instrument===old)?old:v.members[0]?.instrument??'');}}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[account.version]);
  const member=members.find(m=>m.instrument===selected);
  const supported=/^(SSE:(60|68)|SZSE:(00|30))\d{4}$/.test(selected);
  return <section className="daily-use" aria-label="持仓与自选日常使用">
    <h1>持仓与自选 · 日常使用</h1>
    <label>观察证券<select aria-label="观察证券" value={selected} onChange={e=>{setSelected(e.target.value);setRecording(false);}}>{members.map(m=><option key={m.instrument} value={m.instrument}>{m.identity.name??m.instrument} · {m.holding?'持仓':'自选'}</option>)}</select></label>
    {error&&<p role="alert">{error}</p>}
    {!members.length&&<p>暂无持仓与自选，请先建立账户或在「持仓与关注」添加证券。</p>}
    <p>{selected} · {member?.identity.name} · 跟踪公开事实、分析变化、记录实际买卖。模型研究独立保留，未取得交易资格不影响这些功能。</p>
    <div className="actions">
      <button onClick={()=>onNavigate('同步账户')}>{account.version===0?'建立账户起点':'核对现金与持仓'}</button>
      <button disabled={account.version===0||!selected} onClick={()=>setRecording(!recording)}>{recording?'收起成交录入':'记录实际买卖'}</button>
      <button onClick={()=>onNavigate('历史记录')}>查看成交与复盘记录</button>
      <button onClick={()=>onNavigate('持仓与关注')}>行情与持仓详情</button>
    </div>
    {account.version===0&&<p>先填写你确认的当前现金与持仓；无需补齐过去全部交易。</p>}
    {recording&&<SyncFill account={account} mode="FILL" key={selected} defaultCode={selected.split(':')[1]} onDone={()=>{onRefresh();setRecording(false);}}/>}
    {supported&&<ObservationUpdatesPanel key={selected} instrument={selected} expanded/>}
    {selected&&!supported&&<p>该证券采集器尚未适配；账户与历史仍可查看。</p>}
    <DailyReportPanel/>
    <ReviewPanel/>
    {supported&&<FinancialObservationPanel key={selected} instrument={selected}/>}
    {supported&&<NewsPanel key={selected} instrument={selected}/>}
  </section>;
}
