import {useEffect,useState} from 'react';
import {request} from '../api';

type Notice={notification_id:string;category:string;severity:string;title:string;message:string;evidence_kind:string;read_at:string|null;external_status:string;delivered_at:string|null;known_at:string;expires_at:string};
type Current={notification:Notice;current_state:string;read_at:string|null;external_status:string;prepare_allowed:boolean;attempts:{attempt_id:string;result:{status:string}|null}[]};
const categories:Record<string,string>={NEED_ACTION:'需要行动',NEED_SYNC_RECOVERY:'需要同步/恢复',STAGE_SUMMARY:'阶段摘要'};
const states:Record<string,string>={CURRENT:'当前有效',EXPIRED:'已到期，仅作历史记录',SUPERSEDED:'已被后续状态替代',INVALIDATED:'已失效，请核对当前条件',RESOLVED:'事实已确认或已处理，仅作历史记录'};
const channel:Record<string,string>={CHANNEL_DISABLED:'未配置外部渠道，需打开查看',QUEUED:'等待渠道处理',OUTBOUND_CLOSED:'已失效或到期，仅保留站内记录',INFLIGHT:'正在尝试发送',CHANNEL_ACCEPTED:'渠道已受理',RESULT_UNKNOWN:'发送结果未知，可能已经受理',NOT_DISPATCHED:'本地尚未发送',NOT_SENT:'本次未发送',FAILED:'渠道拒绝本次请求'};

export function NotificationPanel({selectedId}:{selectedId?:string}){
  const [notices,setNotices]=useState<Notice[]>([]),[current,setCurrent]=useState<Current|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function reload(){
    const result=await request<{notifications:Notice[]}>('/notifications');setNotices(result.notifications);
    setCurrent(selectedId?await request<Current>('/notifications/'+encodeURIComponent(selectedId)+'/current'):null);
  }
  useEffect(()=>{const refresh=()=>void reload().catch(()=>setError('通知暂时无法读取，请重新打开查看。'));refresh();window.addEventListener('focus',refresh);window.addEventListener('roll-capability-changed',refresh);return()=>{window.removeEventListener('focus',refresh);window.removeEventListener('roll-capability-changed',refresh);};},[selectedId]);
  async function read(id:string){setBusy(true);try{await request('/notifications/'+id+'/read',{idempotency_key:crypto.randomUUID()});await reload();setError('');}catch{setError('已读记录未明确，请重新查看。');}finally{setBusy(false);}}
  async function retry(id:string){setBusy(true);try{await request('/notifications/'+id+'/retry',{idempotency_key:crypto.randomUUID()});await reload();setError('');}catch{setError('当前条件不允许重试，请核对状态、期限与渠道配置。');}finally{setBusy(false);}}
  return <section aria-label="通知"><h2>通知</h2>
    <p className="muted">站内查看不会自动标为已读；渠道受理不代表送达或已读。</p>
    {error&&<p role="alert">{error}</p>}
    {current&&<div role="status"><h3>旧消息的当前状态</h3><p>{states[current.current_state]??'当前状态待核'}</p><p>{current.notification.message}</p><p>旧消息只作记录，请以当前状态为准；打开消息不能创建操作意向。</p></div>}
    {!notices.length&&<p>暂无需要查看的通知</p>}
    {notices.map(n=><article key={n.notification_id} aria-label={n.title}><p>{categories[n.category]??'通知'}{n.severity==='CRITICAL'?' · 重要状态变化':''}</p><h3>{n.title}</h3><p>{n.message}</p>
      {n.evidence_kind==='METHOD_ENGINEERING'&&<p>工程样例，不用于真实资格或交易建议</p>}
      <p><span>{channel[n.external_status]??'渠道状态待核'}</span> · <span>外部送达与已读未知</span></p>
      <p>{n.read_at?'站内已读':'站内未读'}</p><p className="muted">记录于 {new Date(n.known_at).toLocaleString('zh-CN')} · 有效至 {new Date(n.expires_at).toLocaleString('zh-CN')}</p>
      <button onClick={()=>{window.location.hash='notification='+n.notification_id;}}>打开当前状态</button>
      {!n.read_at&&<button disabled={busy} onClick={()=>void read(n.notification_id)}>标为已读</button>}
      {['RESULT_UNKNOWN','FAILED','NOT_SENT','NOT_DISPATCHED'].includes(n.external_status)&&<><p>重试可能重复发送；仅允许一次显式重试，仍须核对当前条件。</p><button disabled={busy} onClick={()=>void retry(n.notification_id)}>重试本条通知</button></>}
    </article>)}
    {current?.attempts.length? <details><summary>查看本地发送尝试</summary>{current.attempts.map(a=><p key={a.attempt_id}>{channel[a.result?.status??'INFLIGHT']??'结果待核'}；不推定用户收到。</p>)}</details>:null}
  </section>;
}
