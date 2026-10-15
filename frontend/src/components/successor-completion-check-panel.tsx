import {useState} from 'react';
import {request} from '../api';
import {SuccessorPrimaryCenterPanel} from './successor-primary-center-panel';
type Saved={check_id:string;recorded_at:string;bound_diagnostic_count:number;required_diagnostic_count:number;diagnostic_package_complete:boolean;diagnostic_binding_gaps:string[];complete_freeze_admission:{status:string;reasons:string[]};validation_verdict:string};
export function SuccessorCompletionCheckPanel({jointReviewId,stressId}:{jointReviewId:string;stressId:string}){
  const [thresholds,setThresholds]=useState<{diagnostic_id:string;recorded_at:string;status:string}[]>([]),[migrations,setMigrations]=useState<{audit_id:string;recorded_at:string}[]>([]),[threshold,setThreshold]=useState(''),[migration,setMigration]=useState('');
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/successor-joint-reviews/'+jointReviewId+'/completion-check',current=records.find(r=>r.check_id===selected),source='/research/successor-cost-stresses/'+stressId;
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function choices(){const [t,m]=await Promise.all([request<typeof thresholds>(source+'/threshold-stress'),request<typeof migrations>(source+'/migration-audit')]);setThresholds(t.filter(r=>r.status!=='RUNNING'));setMigrations(m);}
  async function create(){const result=await request<Saved>(base,{threshold_id:threshold,migration_id:migration,idempotency_key:crypto.randomUUID(),basis:'核对同源诊断绑定及工程/真实缺口；不授完整冻结、资格或真实启运'});setRecords([...records,result]);setSelected(result.check_id);}
  async function load(){const saved=await request<Saved[]>(base);setRecords(saved);setSelected(saved.at(-1)?.check_id??'');}
  return <details><summary>诊断绑定与完整冻结剩余条件</summary><p>核对九类保存诊断和家族运行状态。诊断绑定齐全仍不等于工程全部完成或完整实验冻结；真实输入、拟合邻域工件与独立支持需另验，G6/G7在启运后积累。</p>
    <button disabled={busy} onClick={()=>void action(choices)}>读取工程检查依据</button>
    <label>工程检查阈值版本<select aria-label="工程检查阈值版本" disabled={busy} value={threshold} onChange={e=>setThreshold(e.target.value)}><option value="">选择已终态阈值记录</option>{thresholds.map(t=><option key={t.diagnostic_id} value={t.diagnostic_id}>{t.recorded_at} · {t.status}</option>)}</select></label>
    <label>工程检查迁移版本<select aria-label="工程检查迁移版本" disabled={busy} value={migration} onChange={e=>setMigration(e.target.value)}><option value="">选择保存迁移审计</option>{migrations.map(m=><option key={m.audit_id} value={m.audit_id}>{m.recorded_at}</option>)}</select></label>
    <button disabled={busy||!threshold||!migration} onClick={()=>void action(create)}>保存诊断绑定与工程检查</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的工程检查</button>
    {busy&&<p role="status">正在核对不可变来源和家族尝试…</p>}
    {!!records.length&&<label>工程检查版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.check_id} value={r.check_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD诊断绑定 {current.bound_diagnostic_count}/{current.required_diagnostic_count} · {current.validation_verdict} · 完整冻结未授予 · NOT_GRANTED</p><p>{current.diagnostic_package_complete?'所选诊断绑定一致；工程、真实及资格条件仍未全部满足。':'所选诊断或运行状态仍有缺口。'}</p><details><summary>工程/冻结与启运后资格缺口</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-completion-checks/'+current.check_id+'/replay',{});setNotice(result.matches_original?'工程检查原工件重放一致':'工程检查重放不一致');})}>重放保存的工程检查</button>
      <SuccessorPrimaryCenterPanel key={current.check_id} checkId={current.check_id}/>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
