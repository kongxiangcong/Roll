import {useEffect,useState} from 'react';
import {request} from '../api';
import {DailyEvidencePanel} from '../components/daily-evidence-panel';

type Plan={plan_id:string;instrument:string;started_at:string};
type Readiness={state:string;real_recorded_sessions:number;real_context_sessions:number;batches:number;system_usable:boolean;readiness_basis:string};
type Development={status:string;evidence_kind:string;system_usable:boolean;model_run_id?:string;statistical_support?:{development_total:number;calibration_total:number};replay?:{matches_original:boolean}};
type Source={id:string;name:string;upstream:string;enabled:boolean;revision:number;health:{state:string;retry_after?:string;last_success_at?:string}};
type Cleaning={accepted_rows:number;quarantined_rows:unknown[]};
type Integrity={consistent:boolean;archives_checked:number;facts_checked:number};

export function Collections(){
  const [plans,setPlans]=useState<Plan[]>([]),[states,setStates]=useState<Record<string,Readiness>>({}),[runs,setRuns]=useState<Development[]>([]);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const [sources,setSources]=useState<Source[]>([]),[cleaning,setCleaning]=useState<Cleaning[]>([]),[integrity,setIntegrity]=useState<Integrity|null>(null);
  async function refresh(){
    const found=await request<Plan[]>('/research/collections');setPlans(found);
    const values=await Promise.all(found.map(async p=>[p.plan_id,await request<Readiness>(`/research/collections/${p.plan_id}/readiness`)] as const));
    setStates(Object.fromEntries(values));setRuns(await request<Development[]>('/research/development-runs'));
    setSources(await request<Source[]>('/research/collection-sources'));setCleaning(await request<Cleaning[]>('/research/collection-cleaning'));
  }
  useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[]);
  async function act(action:()=>Promise<unknown>){setBusy(true);setError('');try{await action();await refresh();}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <section aria-label="前向数据积累"><h3>从现在开始积累数据</h3><p>系统尚不可用。数据取得时点与修订版本持续保存，资料和验证满足后才能启用。</p>
    {plans.map(p=><div key={p.plan_id}><p>{p.instrument} · 起点 {new Date(p.started_at).toLocaleString('zh-CN')}</p>
      {states[p.plan_id]&&<p>真实记录 {states[p.plan_id].real_recorded_sessions} 个交易日 · 当前已知回看 {states[p.plan_id].real_context_sessions} 日 · {states[p.plan_id].batches} 次采集</p>}
      <button disabled={busy} onClick={()=>void act(()=>request(`/research/collections/${p.plan_id}/collect`,{}))}>采集当前数据</button></div>)}
    {!plans.length&&<button disabled={busy} onClick={()=>void act(()=>request('/research/collections',{instrument:'SSE:600362',basis:'从现在开始记录江西铜业PIT数据；旧数据只保留，不再搜旧PIT'}))}>开始记录江西铜业</button>}
    {runs.map((r,i)=><p key={i}>虚拟框架 · {r.status==='ENGINEERING_COMPLETE'?'构建完成':r.status} · 开发样本 {r.statistical_support?.development_total??0} / 校准样本 {r.statistical_support?.calibration_total??0} · 重放 {r.replay?.matches_original?'一致':'尚未完成'} · 不具备真实使用资格</p>)}
    <details><summary>数据源与清洗</summary>
      {plans.map(p=><DailyEvidencePanel key={p.plan_id} planId={p.plan_id} instrument={p.instrument}/>)}
      <table><thead><tr><th>来源</th><th>最近访问</th><th>采集</th></tr></thead><tbody>{sources.map(s=><tr key={s.id}>
        <td>{s.name}</td><td>{s.health.retry_after&&new Date(s.health.retry_after)>new Date()?'失败退避中':s.health.state==='ACQUIRED'?'已取得':s.health.state==='FAILED'?'访问失败':'尚未采集'}</td>
        <td><button disabled={busy} aria-pressed={s.enabled} onClick={()=>void act(()=>request(`/research/collection-sources/${s.id}/policy`,{enabled:!s.enabled,expected_revision:s.revision,basis:s.enabled?'用户暂停该采集来源':'用户启用该采集来源'}))}>{s.enabled?'已启用 · 暂停':'已暂停 · 启用'}</button></td>
      </tr>)}</tbody></table>
      <p>最近 {cleaning.length} 份清洗报告 · 接收 {cleaning.reduce((n,c)=>n+c.accepted_rows,0)} 条 · 隔离 {cleaning.reduce((n,c)=>n+c.quarantined_rows.length,0)} 条。异常记录保留原件，未知值保持未知。</p>
      <button disabled={busy} onClick={()=>void act(async()=>setIntegrity(await request<Integrity>('/research/collection-integrity',{})))}>检查数据库与归档</button>
      {integrity&&<p role="status">{integrity.consistent?'完整性检查通过':'完整性检查未通过'} · {integrity.archives_checked} 份归档 · {integrity.facts_checked} 条事实版本</p>}
    </details>
    {error&&<p role="alert">{error}</p>}
  </section>;
}
