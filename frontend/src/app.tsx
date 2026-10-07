import {useEffect,useState} from 'react';
import {Account,request} from './api';
import {SyncAccount} from './pages/sync-account';
import {Today} from './pages/today';
import {History} from './pages/history';
import {Market} from './pages/market';
const pages = ['今天','持仓与关注','同步账户','历史记录','设置'] as const;
export default function App() {
  const [page,setPage]=useState<string>('今天');
  const [account,setAccount]=useState<Account|null>(null);
  const [error,setError]=useState('');
  async function refresh(){try{setAccount(await request<Account>('/account'));setError('');}catch(e){setError(String(e));}}
  useEffect(()=>{void refresh();},[]);
  return <><header><div className="brand">Roll <span>账户镜像</span></div><nav aria-label="主导航">{pages.map(p=><button key={p} aria-current={p===page?'page':undefined} onClick={()=>{setPage(p);void refresh();}}>{p}</button>)}</nav></header>
    <main>{error&&<p role="alert">无法连接账户服务：{error}</p>}{!account?<p>正在读取账户…</p>:page==='同步账户'?<SyncAccount account={account} onDone={()=>{void refresh();setPage('今天');}}/>:page==='历史记录'?<History/>:page==='今天'?<Today/>:page==='持仓与关注'?<Market/>:<section><h1>设置</h1><p>本机普通人民币现金账户。交易判断未启用。</p><p>建立账户无需配置取证后端。</p></section>}</main></>;
}
