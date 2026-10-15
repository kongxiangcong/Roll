import {useState} from 'react';
import {request} from '../api';
type Saved={audit_id:string;recorded_at:string;audit_status:string;G5_status:string;baseline_migration_applicability:string;lots:{lot_id:string;baseline:boolean;entry_session:number;expected_exit_session:number;overdue_observed_sessions:number[]}[];binding_errors:string[]};
export function SuccessorMigrationAuditPanel({stressId}:{stressId:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/successor-cost-stresses/'+stressId+'/migration-audit',current=records.find(r=>r.audit_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const result=await request<Saved>(base,{idempotency_key:crypto.randomUUID(),basis:'核对原迁移绑定、独立lot期限和登记范围；不证明真实迁移能力'});setRecords([...records,result]);setSelected(result.audit_id);}
  async function load(){const saved=await request<Saved[]>(base);setRecords(saved);setSelected(saved.at(-1)?.audit_id??'');}
  return <details><summary>原迁移lot与范围审计</summary><p>只读取保存的原lot迁移、各次实际新入场与登记证券范围。原期限不因退出阻塞而改写，新lot保留入场后期限；范围登记不证明跨证券、市场或时期的迁移能力。</p>
    <button disabled={busy} onClick={()=>void action(create)}>保存原lot与范围审计</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的迁移审计</button>
    {busy&&<p role="status">正在核对保存绑定和各lot期限…</p>}
    {!!records.length&&<label>迁移审计版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.audit_id} value={r.audit_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD迁移审计 · {current.audit_status} · G5 {current.G5_status} · NOT_GRANTED</p>{current.baseline_migration_applicability==='NOT_APPLICABLE_EXPLICIT_EMPTY_BASELINE'&&<p>原初始持仓为空，原lot迁移不适用；仍核对新入场lot和登记范围。</p>}<p>绑定差异 {current.binding_errors.length} 项；真实范围迁移未证明。</p><div className="reference-table"><table><thead><tr><th>lot</th><th>来源</th><th>入场会话</th><th>原截止会话</th><th>到期仍持有观察</th></tr></thead><tbody>{current.lots.map(l=><tr key={l.lot_id}><td>{l.lot_id}</td><td>{l.baseline?'原持仓':'新入场'}</td><td>{l.entry_session}</td><td>{l.expected_exit_session}</td><td>{l.overdue_observed_sessions.length}</td></tr>)}</tbody></table></div><details><summary>迁移生效、原范围及阻塞依据</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-migration-audits/'+current.audit_id+'/replay',{});setNotice(result.matches_original?'迁移审计原工件重放一致':'迁移审计重放不一致');})}>重放保存的迁移审计</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
