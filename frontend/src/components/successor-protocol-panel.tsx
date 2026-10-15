import {useEffect,useState} from 'react';
import {request} from '../api';

type Freeze={successor_freeze_id:string;successor_fingerprint:string;policy:{version:string}};
type Protocol={protocol_id:string;predecessor_id:string|null;protocol_fingerprint:string};
type Complete={protocol_id:string;complete_protocol_fingerprint:string;complete_experiment_frozen:boolean;evidence_kind:string;complete_freeze_gaps:string[];
  design:{primary_objective:{minimum_improvement_nav_return:string};statistics:{minimum_effective_time_blocks:number};stopping:{maximum_natural_months:number}}};
type Validation={validation_id:string;shadow_revision:number;validation_verdict:string;gates:Record<string,{status:string;reasons:string[]}>;
  economics:{net_return:number|null;maximum_drawdown:number|null};evidence_kind:string};
const percent=(value:number|null)=>value===null?'未知':`${(value*100).toFixed(2)}%`;

export function SuccessorProtocolPanel({parentFreezeId,parentProtocolId}:{parentFreezeId:string;parentProtocolId:string}){
  const [freezes,setFreezes]=useState<Freeze[]>([]),[protocols,setProtocols]=useState<Protocol[]>([]),[selected,setSelected]=useState(''),[child,setChild]=useState('');
  const [complete,setComplete]=useState<Complete|null>(null),[results,setResults]=useState<Validation[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const current=freezes.find(f=>f.successor_freeze_id===selected),registered=protocols.find(p=>p.protocol_id===child);
  const base=`/research/policy-successor-freezes/${selected}`;
  useEffect(()=>{setSelected('');setComplete(null);setResults([]);setError('');void Promise.all([
    request<Freeze[]>(`/research/complete-freezes/${parentFreezeId}/policy-successor-freezes`),request<Protocol[]>('/research/protocols')
  ]).then(([f,p])=>{setFreezes(f);setProtocols(p.filter(v=>v.predecessor_id===parentProtocolId));}).catch(e=>setError(String(e)));},[parentFreezeId,parentProtocolId]);
  async function inspect(id:string){setSelected(id);setComplete(null);setResults([]);setError('');setNotice('');if(!id)return;
    try{setComplete(await request<Complete>(`/research/policy-successor-freezes/${id}/complete-protocol`));setResults(await request<Validation[]>(`/research/policy-successor-freezes/${id}/validations`));}
    catch(e){if(!String(e).includes('SUCCESSOR_COMPLETE_PROTOCOL_NOT_FOUND'))setError(String(e));}}
  async function act(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function freeze(){if(!current||!registered)return;await request(base+'/complete-protocol',{
    protocol_id:registered.protocol_id,expected_protocol_fingerprint:registered.protocol_fingerprint,expected_successor_fingerprint:current.successor_fingerprint,
    idempotency_key:`complete-${selected}`,basis:'冻结已登记同家族后继经济/统计设计；仅METHOD研究，不授真实能力'});await inspect(selected);}
  async function validate(){if(!complete)return;const state=await request<{revision:number}>(base+'/shadow');await request(base+'/validations',{
    expected_complete_protocol_fingerprint:complete.complete_protocol_fingerprint,expected_revision:state.revision,idempotency_key:`diagnostic-${selected}-${state.revision}`,
    basis:'当前已保存METHOD前缀验证；不读取SEALED或补造真实前向'});await inspect(selected);}
  return <details className="successor-protocol"><summary>后继政策完整设计与验证</summary>
    <p>沿用已登记目标、费用、期限、风险与统计门槛。工程设计冻结和METHOD诊断不授正式能力。</p>
    {!freezes.length&&<p>尚无已登记后继影子冻结版本。</p>}
    {!!freezes.length&&<label>后继影子版本<select disabled={busy} value={selected} onChange={e=>void act(()=>inspect(e.target.value))}><option value="">选择已保存版本</option>{freezes.map(f=><option key={f.successor_freeze_id} value={f.successor_freeze_id}>{f.policy.version}</option>)}</select></label>}
    {current&&!complete&&<><label>关联后继实验<select disabled={busy} value={child} onChange={e=>setChild(e.target.value)}><option value="">选择同家族后继实验</option>{protocols.map(p=><option key={p.protocol_id} value={p.protocol_id}>{p.protocol_id.slice(0,8)}</option>)}</select></label><button disabled={busy||!registered} onClick={()=>void act(freeze)}>冻结后继完整设计</button>{!protocols.length&&<p>先在研究登记中保存关联后继版本。</p>}</>}
    {complete&&<><p role="status">后继设计参数已冻结 · 完整实验未冻结 · METHOD工程研究 · 正式能力未授予</p><p>净值改善目标 {percent(Number(complete.design.primary_objective.minimum_improvement_nav_return))} · 最少有效时间块 {complete.design.statistics.minimum_effective_time_blocks} · 首次真实归档后最长 {complete.design.stopping.maximum_natural_months} 自然月，当前未启运。</p><details><summary>完整冻结剩余条件</summary><ul>{complete.complete_freeze_gaps.map(g=><li key={g}>{g}</li>)}</ul></details><button disabled={busy} onClick={()=>void act(validate)}>验证已保存后继影子</button></>}
    {results.map(v=><div key={v.validation_id}><p>METHOD前缀 {v.shadow_revision} · {v.validation_verdict} · 无正式能力</p><p>工程模拟净值收益率 {percent(v.economics.net_return)} · 最大回撤 {percent(v.economics.maximum_drawdown)}</p><details><summary>验证门槛与缺口</summary><ul>{Object.entries(v.gates).map(([g,s])=><li key={g}>{g} · {s.status} · {s.reasons.join('、')}</li>)}</ul></details><button disabled={busy} onClick={()=>void act(async()=>{const r=await request<{matches_original:boolean;shadow_revision:number}>(`/research/successor-validations/${v.validation_id}/replay`,{});setNotice(`前缀${r.shadow_revision}重放${r.matches_original?'一致':'不一致'}`);})}>重放后继验证前缀 {v.shadow_revision}</button></div>)}
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
