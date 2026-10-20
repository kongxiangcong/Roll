import {useState} from 'react';
import {Account} from '../api';
import {ObservationUpdatesPanel} from '../components/observation-updates-panel';
import {FinancialObservationPanel} from '../components/financial-observation-panel';
import {NewsPanel} from '../components/news-panel';
import {ReviewPanel} from '../components/review-panel';
import {SyncFill} from './sync-fill';

export function DailyUse({account,onRefresh,onNavigate}:{account:Account;onRefresh:()=>void;onNavigate:(page:string)=>void}){
  const [recording,setRecording]=useState(false);
  return <section className="daily-use" aria-label="江西铜业日常使用">
    <h1>江西铜业 · 日常使用</h1>
    <p>SSE:600362 · 跟踪公开事实、分析变化、记录实际买卖。模型研究独立保留，未取得交易资格不影响这些功能。</p>
    <div className="actions">
      <button onClick={()=>onNavigate('同步账户')}>{account.version===0?'建立账户起点':'核对现金与持仓'}</button>
      <button disabled={account.version===0} onClick={()=>setRecording(!recording)}>{recording?'收起成交录入':'记录实际买卖'}</button>
      <button onClick={()=>onNavigate('历史记录')}>查看成交与复盘记录</button>
      <button onClick={()=>onNavigate('持仓与关注')}>行情与持仓详情</button>
    </div>
    {account.version===0&&<p>先填写你确认的当前现金与持仓；无需补齐过去全部交易。</p>}
    {recording&&<SyncFill account={account} mode="FILL" defaultCode="600362" onDone={()=>{onRefresh();setRecording(false);}}/>}
    <ObservationUpdatesPanel instrument="SSE:600362" expanded/>
    <ReviewPanel/>
    <FinancialObservationPanel instrument="SSE:600362"/>
    <NewsPanel instrument="SSE:600362"/>
  </section>;
}
