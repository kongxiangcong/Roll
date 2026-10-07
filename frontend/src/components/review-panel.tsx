import {useEffect,useState} from 'react';
import {request} from '../api';
type Fact={instrument:string;group:string;last?:string;close?:string;trade_date?:string;upstream_at?:string;available_at?:string;title?:string;basis?:string;state?:string;status_basis?:string;volume_reported?:string;volume_unit?:string;raw_hash?:string};
type Snapshot={snapshot_id:string;previous_snapshot_id:string|null;change:string;calendar:{phase:string;is_trading_day:boolean|null};account_version:number;cutoff:string;knowledge_cutoff:string;knowledge_basis:string;observed_at:string;instruments:{instrument:string;role:string;name?:string;quote:Fact|null;quote_status:string;last_complete_daily:Fact|null;incomplete_daily:Fact|null;company_facts:Fact[]}[];observations:{observation_id:string;kind:string;instrument:string;title?:string;message?:string;basis?:string}[];gaps:{instrument:string;group:string;code:string}[];coverage:{unobserved_trigger_sequence:string}};
type Task={task_id:string;status:string;attempts:number;result:Snapshot|null;audit_id?:string;timing:{network_seconds:number;local_seconds:number;acquisition_seconds:number};module_errors:unknown[]};
type Audit={metrics:Record<string,{status:string;value:number|null;errors?:unknown[];state?:string}>;critical_review:unknown};
type Summary={calendar:Snapshot['calendar'];latest:Task|null;health:{worker_state:string;backlog:number;last_worker_error:unknown};coverage_gap:unknown};
const phases:Record<string,string>={AFTER_CLOSE:'盘后',CLOSED:'非交易日',CONTINUOUS:'交易时段',MORNING_CONTINUOUS:'上午交易时段',AFTERNOON_CONTINUOUS:'下午交易时段',PRE_OPEN:'开盘前',LUNCH_BREAK:'午间休市'};
const stamp=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'});
const terminal=(task:Task)=>!['QUEUED','RUNNING','RETRY_WAIT'].includes(task.status);
function SavedFacts({task}: {task:Task}){
  const [audit,setAudit]=useState<Audit|null>(null);
  const r=task.result;
  if(!r)return <p>任务状态：{task.status} · 已尝试 {task.attempts} 次{task.status==='CANCELLED'?'，未发布观察':''}</p>;
  const backgrounds=r.instruments.filter(i=>i.role==='BACKGROUND'),securities=r.instruments.filter(i=>i.role!=='BACKGROUND');
  return <section data-review-task={task.task_id}><p>观察记录已保存。</p><p>{phases[r.calendar.phase]??r.calendar.phase} · 账户版本 {r.account_version} · 事实截止 {stamp(r.cutoff)}</p><p className="muted">系统可得事实截至 {stamp(r.knowledge_cutoff)} · 实际观察 {stamp(r.observed_at)}</p>
    {r.knowledge_basis==='RETROSPECTIVE_ACTUAL_RUN'&&<p>这是实际运行时的历史事实回看，不是当时发布的预测。</p>}
    {r.change==='NO_SUBSTANTIAL_CHANGE'&&<p>与前一条观察无实质变化。</p>}
    {r.gaps.some(g=>g.code==='POST_CLOSE_DAILY_INCOMPLETE')&&<p>当日日线仍未齐，已有事实继续展示。</p>}
    {!!r.gaps.length&&<p>事实待补：{Array.from(new Set(r.gaps.map(g=>g.group))).join('、')}。缺口不转换为交易判断。</p>}
    {securities.map(i=><article key={i.instrument}><h3>{i.instrument} · {i.role==='HOLDING'?'持仓':'关注'}</h3><p>原价报价 {i.quote?.last??'未知'} · 累计量 {i.quote?.volume_reported??'未知'}（{i.quote?.volume_unit??'单位未知'}）截至 {i.quote?.upstream_at?stamp(i.quote.upstream_at):'未知'}{i.quote_status==='STALE_PREVIOUS_SESSION'?' · 先前交易日，非当前新报价':''}</p><p>最近完整日线 {i.last_complete_daily?.trade_date??'未知'} · 收盘原价 {i.last_complete_daily?.close??'未知'}</p>{i.incomplete_daily&&<p>未完整日线 {i.incomplete_daily.trade_date}，不作完整日线输入</p>}<ul>{i.company_facts.map((f,index)=><li key={`${f.raw_hash}:${index}`}>{f.title??f.group} {f.status_basis??f.basis??''}{f.state&&` · ${f.state}`}</li>)}</ul></article>)}
    {!!r.observations.length&&<ul>{r.observations.map((o,index)=><li key={`${o.observation_id}:${index}`}>{o.kind==='PENDING_ACCOUNT_RECONCILIATION'?'已归档外部权益事实，个人到账仍待确认。':o.title??o.message??o.kind} {o.basis??''}</li>)}</ul>}
    <h3>固定市场背景</h3>{backgrounds.map(i=><p key={i.instrument}>{i.name??i.instrument} · 最近完整日线 {i.last_complete_daily?.trade_date??'未知'} · 原价 {i.last_complete_daily?.close??'未知'}</p>)}
    <details onToggle={e=>{if(e.currentTarget.open&&task.audit_id&&!audit)void request<Audit>(`/reviews/audits/${task.audit_id}`).then(setAudit);}}><summary>运行审计与覆盖详情</summary><p>未观察到的触发顺序不重建；不补造盘中预测。</p><p>前一观察 {r.previous_snapshot_id??'无'}</p><p>本地处理 {task.timing.local_seconds} 秒 · 取数 {task.timing.acquisition_seconds} 秒 · 外部调用与归档 {task.timing.network_seconds} 秒</p>{audit&&<><p>重复通知：{audit.metrics.duplicate_notifications.status==='NOT_CONNECTED'?'尚未接入':audit.metrics.duplicate_notifications.value}</p><p>账户核对 {audit.metrics.account_differences.state} · 实际模块错误 {audit.metrics.module_errors.value}</p><pre>{JSON.stringify({audit,gaps:r.gaps,originals:r.instruments},null,2)}</pre></>}</details>
  </section>;
}
export function ReviewPanel(){
  const [summary,setSummary]=useState<Summary|null>(null),[task,setTask]=useState<Task|null>(null),[error,setError]=useState(''),[refresh,setRefresh]=useState(false),[historical,setHistorical]=useState(''),[submitting,setSubmitting]=useState(false);
  useEffect(()=>{request<Summary>('/reviews/summary').then(s=>{setSummary(s);setTask(current=>current??s.latest);}).catch(e=>setError(String(e)));},[]);
  useEffect(()=>{if(!task||terminal(task))return;const timer=setTimeout(()=>void request<Task>(`/reviews/tasks/${task.task_id}`).then(setTask).catch(e=>setError(String(e))),150);return()=>clearTimeout(timer);},[task]);
  async function submit(mode:string){setSubmitting(true);setTask(null);try{setError('');setTask(await request<Task>('/reviews/tasks',{mode,refresh_missing:refresh,...(mode==='HISTORICAL'?{cutoff:`${historical}:00+08:00`}:{})}));}catch(e){setError(String(e));}finally{setSubmitting(false);}}
  const busy=submitting||!!task&&!terminal(task),postClose=summary&&['AFTER_CLOSE','CLOSED'].includes(summary.calendar.phase);
  return <section><h2>今天的事实观察</h2><p>普通事实观察可用；交易判断未启用。</p>{summary&&<p>{phases[summary.calendar.phase]??summary.calendar.phase} · 单任务服务 {summary.health.worker_state} · 待处理 {summary.health.backlog}</p>}<button disabled={busy||!summary} onClick={()=>void submit('ON_DEMAND')}>按需观察</button><button disabled={busy||!postClose} onClick={()=>void submit('POST_CLOSE')}>盘后复盘</button><label><input type="checkbox" checked={refresh} onChange={e=>setRefresh(e.target.checked)}/>补查缺失事实</label>
    <details><summary>回看指定历史时点</summary><label>历史事实截止（上海时间）<input type="datetime-local" value={historical} onChange={e=>setHistorical(e.target.value)}/></label><button disabled={!historical||busy} onClick={()=>void submit('HISTORICAL')}>回看历史事实</button><p>回看不生成新的前向预测。</p></details>
    {busy&&task&&<p>任务处理中 · 第 {task.attempts} 次尝试 <button onClick={()=>void request<Task>(`/reviews/tasks/${task!.task_id}/cancel`,{}).then(setTask)}>取消观察任务</button></p>}{error&&<p role="alert">{error}</p>}{task&&<SavedFacts key={task.task_id} task={task}/>}
  </section>;
}
export function ReviewHistory(){
  const [tasks,setTasks]=useState<Task[]>([]),[selected,setSelected]=useState<Task|null>(null),[error,setError]=useState('');
  useEffect(()=>{request<Task[]>('/reviews/history').then(setTasks).catch(e=>setError(String(e)));},[]);
  return <section><h2>观察与复盘时间线</h2>{tasks.length?<ul>{tasks.map(t=><li key={t.task_id}><button onClick={()=>setSelected(t)}>查看观察 {t.result?stamp(t.result.observed_at):t.task_id}</button> · {t.status}</li>)}</ul>:<p>暂无观察记录</p>}{selected&&<SavedFacts key={selected.task_id} task={selected}/>}<p>未观察到的触发顺序不重建；不补造盘中预测。</p>{error&&<p role="alert">{error}</p>}</section>;
}
type Maintenance={schedule_id:string;kind:string;next_due_at:string|null;status:string};
type Check={check_id:string;scheduled_at:string;checked_at:string;status:string};
export function MaintenancePanel(){
  const [due,setDue]=useState(''),[kind,setKind]=useState('WEEKLY'),[schedules,setSchedules]=useState<Maintenance[]>([]),[checks,setChecks]=useState<Check[]>([]),[message,setMessage]=useState('');
  function load(){void request<Maintenance[]>('/reviews/maintenance').then(setSchedules);void request<Check[]>('/reviews/maintenance/checks').then(setChecks);}
  useEffect(load,[]);
  async function register(){try{await request('/reviews/maintenance',{kind,exchange:'SSE',first_due_at:`${due}:00+08:00`});setMessage('维护检查点已保存。');load();}catch(e){setMessage(String(e));}}
  return <section><h2>维护检查点</h2><p>程序运行时检查到期事项；停机后记录实际补查时间。统计资格检查尚未接入。</p><label>频率<select value={kind} onChange={e=>setKind(e.target.value)}><option value="ONCE">一次</option><option value="WEEKLY">每周</option><option value="MONTHLY">每月</option></select></label><label>维护检查点（上海时间）<input type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/></label><button disabled={!due} onClick={()=>void register()}>登记维护检查点</button>{message&&<p role="status">{message}</p>}<ul>{schedules.map(s=><li key={s.schedule_id}>下次检查 {s.next_due_at?stamp(s.next_due_at):'已结束或日历待适配'}</li>)}</ul><details><summary>实际维护记录</summary><ul>{checks.map(c=><li key={c.check_id}>计划 {stamp(c.scheduled_at)} · 实际检查 {stamp(c.checked_at)} · {c.status}</li>)}</ul></details></section>;
}
