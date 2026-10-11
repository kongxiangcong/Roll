import {useEffect,useState} from 'react';
import {request} from '../api';

export type Intent={intent_id:string;instrument:string;action:string;status:string;remaining_quantity:string;synced_quantity:string;provisional_reservation_yuan:string;broker_reflection:string;external_order_id:string|null;resolution:string|null;time_chain:{prepared_at:string;occurred_at:string|null;reported_at:string|null;read_at:string|null}};
export type IntentList={intents:Intent[];unreflected_reservation_yuan:string;pending_attribution:boolean};
const labels:Record<string,string>={PREPARED:'准备操作',OPERATION_PENDING:'已操作待同步',NOT_EXECUTED:'未执行',RESOLVED:'外部结果已明确'};
export function ExecutionIntents({instrument,revision}:{instrument?:string;revision:number}){
  const [data,setData]=useState<IntentList|null>(null),[error,setError]=useState('');
  async function refresh(){setData(await request<IntentList>('/intents'));}
  useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[revision]);
  return <section aria-label="执行意向"><h3>执行意向</h3>{error&&<p role="alert">{error}</p>}{data?.pending_attribution&&<p role="status">外部委托占用归属待核，限制新增风险</p>}{data?.intents.filter(i=>!instrument||i.instrument===instrument).map(i=><IntentCard key={i.intent_id} intent={i} onDone={refresh}/>)}{data&&!data.intents.length&&<p>暂无执行意向</p>}</section>;
}
function IntentCard({intent:i,onDone}:{intent:Intent;onDone:()=>Promise<void>}){
  const [order,setOrder]=useState(i.external_order_id??''),[reflection,setReflection]=useState(i.broker_reflection),[occurred,setOccurred]=useState(''),[reason,setReason]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function declare(state:string){setBusy(true);try{await request('/intents/'+i.intent_id+'/declare',{state,external_order_id:order.trim()||null,broker_reflection:reflection,occurred_at:occurred?new Date(occurred).toISOString():null,reason:reason.trim()||null,idempotency_key:crypto.randomUUID()});await onDone();setError('');}catch(e){setError(String(e));}finally{setBusy(false);}}
  const active=!['NOT_EXECUTED','RESOLVED'].includes(i.status);
  return <article aria-label={`执行意向 ${i.instrument}`}><h4>{i.instrument} · {labels[i.status]}</h4><p>已同步 {i.synced_quantity} 股 · 剩余待核 {i.remaining_quantity} 股 · 临时占用 {i.provisional_reservation_yuan} 元</p><p className="muted">准备于 {new Date(i.time_chain.prepared_at).toLocaleString('zh-CN')} · 送达与已读未知</p>{i.external_order_id&&<p>外部委托 {i.external_order_id}</p>}{i.resolution&&<p>结果说明：{i.resolution}</p>}{active&&<details><summary>记录自行操作结果</summary><label>外部委托标识<input value={order} onChange={e=>setOrder(e.target.value)}/></label><label>券商可用资金中的占用<select value={reflection} onChange={e=>setReflection(e.target.value)}><option value="UNKNOWN">归属未知</option><option value="NOT_REFLECTED">确认尚未反映</option><option value="CONFIRMED_REFLECTED">确认同一委托已反映</option></select></label><label>实际操作时点（未知可留空）<input type="datetime-local" value={occurred} onChange={e=>setOccurred(e.target.value)}/></label><label>未执行或外部结果说明<input value={reason} onChange={e=>setReason(e.target.value)}/></label><button disabled={busy} onClick={()=>void declare('OPERATION_PENDING')}>已自行操作，待同步</button>{i.status==='PREPARED'?<button disabled={busy} onClick={()=>void declare('NOT_EXECUTED')}>记录未执行</button>:<button disabled={busy} onClick={()=>void declare('RESOLVED')}>确认外部结果已明确</button>}<p>实际成交请到“同步账户”确认。动作失效或到期不会取消外部委托。</p></details>}{error&&<p role="alert">{error}</p>}</article>;
}
