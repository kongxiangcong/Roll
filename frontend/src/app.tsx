import {useEffect,useState} from 'react';
import {Account,request} from './api';
import {SyncAccount} from './pages/sync-account';
import {Today} from './pages/today';
import {History} from './pages/history';
import {Market} from './pages/market';
import {Settings} from './pages/settings';
const pages = ['今天','持仓与关注','同步账户','历史记录','设置'] as const;
export default function App() {
  const [page,setPage]=useState<string>('今天');
  const [researchFreezeId,setResearchFreezeId]=useState<string|undefined>();
  const [notificationId,setNotificationId]=useState<string|undefined>();
  const [account,setAccount]=useState<Account|null>(null);
  const [error,setError]=useState('');
  async function refresh(){try{setAccount(await request<Account>('/account'));setError('');}catch(e){setError(String(e));}}
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{const open=()=>{const research=new URLSearchParams(window.location.hash.slice(1)).get('research');if(research&&/^[0-9a-f-]{36}$/i.test(research)){setResearchFreezeId(research);setPage('历史记录');setNotificationId(undefined);return;}setResearchFreezeId(undefined);const id=new URLSearchParams(window.location.hash.slice(1)).get('notification');if(id&&/^[0-9a-f-]{36}$/i.test(id)){setNotificationId(id);setPage('今天');}else setNotificationId(undefined);};open();window.addEventListener('hashchange',open);return()=>window.removeEventListener('hashchange',open);},[]);
  return <><header><div className="brand">Roll <span>账户镜像</span></div><nav aria-label="主导航">{pages.map(p=><button key={p} aria-current={p===page?'page':undefined} onClick={()=>{setPage(p);void refresh();}}>{p}</button>)}</nav></header>
    <main>{error&&<p role="alert">无法连接账户服务：{error}</p>}{!account?<p>正在读取账户…</p>:page==='同步账户'?<SyncAccount account={account} onDone={()=>{void refresh();setPage('今天');}}/>:page==='历史记录'?<History researchFreezeId={researchFreezeId}/>:page==='今天'?<Today notificationId={notificationId}/>:page==='持仓与关注'?<Market/>:<Settings/>}</main></>;
}
