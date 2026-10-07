import {FormEvent,useEffect,useState} from 'react';
import {request} from '../api';
type Snapshot={snapshot_id:string;evidence_kind:string;facts:Record<string,unknown>[]};
type Evidence={value:string|null;field_unit:string;source_id:string;raw_hash:string;document_hash:string|null;available_at:string;context:Record<string,unknown>;provenance:Record<string,unknown>};
type Fact={fact_id:string;field:string;result:string;attribution_status:string;independent_basis_count:number;gaps:string[];limitations:string[];evidence:Evidence[];comparisons:unknown[]};
type Verification={verification_id:string;created_at:string;result:string;current_result:string;dependency_status:string;evidence_kind:string;reuse_of:string|null;knowledge_cutoff:string;command:{trigger:string;reason:string};facts:Fact[];review_origin:{request_id:string;task_id:string;audit_id:string}|null};
const fields:Record<string,string>={last:'报价价格',close:'日线收盘',open:'开盘',high:'最高价',low:'最低价',previous_close:'前收盘',reported_limit_up:'所报涨停价',reported_limit_down:'所报跌停价',volume_shares:'成交股数',volume_reported:'原报成交量',amount_yuan:'成交额',trade_date:'交易日期',report_period:'报告期',disclosure_date:'披露日期',record_date:'权益登记日',ex_date:'除权除息日',dividend_yuan_per_share:'每股税前分派',total_operating_income_yuan:'营业总收入',net_profit_yuan:'净利润',eps_yuan_per_share:'每股收益',published_at:'实际发布时点',upstream_at:'上游所报时点'};
const results:Record<string,string>={VERIFIED:'已核验',CONFLICT:'存在冲突',INSUFFICIENT:'证据不足'};
const gaps:Record<string,string>={SOURCE_BASIC_CHECK_FAILED:'源数据未通过基本校验',INDEPENDENCE_UNPROVEN:'原始依据独立性未证明',SAME_ORIGINAL_BASIS:'同一原始依据只计一次',TWO_INDEPENDENT_ORIGINAL_BASES_NOT_ESTABLISHED:'不足两条独立原始依据',ACQUIRED_AFTER_REVIEW_KNOWLEDGE_CUTOFF:'材料取得晚于本次复盘知识截止',UPSTREAM_AT_NOT_COMPARABLE:'上游时点不可比',UNIT_NOT_ESTABLISHED:'单位尚无依据',FIELD_UNIT_NOT_COMPARABLE:'字段单位不可比',ADJUSTMENT_NOT_COMPARABLE:'原价或复权口径不可比',ADJUSTMENT_VERSION_NOT_COMPARABLE:'复权版本不可比',TRADE_DATE_NOT_COMPARABLE:'交易日期不可比',MISSING_VALUE:'字段缺失',CURRENCY_NOT_COMPARABLE:'币种口径不可比',INSTRUMENT_NOT_COMPARABLE:'证券对象不可比',GROUP_NOT_COMPARABLE:'事实类型不可比',TIME_PRECISION_NOT_COMPARABLE:'时点精度不可比',REPORT_PERIOD_NOT_COMPARABLE:'报告期不可比',EX_DATE_NOT_COMPARABLE:'权益事件日不可比',VOLUME_UNIT_NOT_COMPARABLE:'成交量单位不可比',NONFINITE_VALUE:'字段不是有效有限数值'};
const text=(v:unknown)=>v===null||v===undefined?'未知':String(v);

export function VerificationReview({reviewTask}:{reviewTask?:{task_id:string;data_versions:string[];knowledge_cutoff:string}}){
  const [snapshots,setSnapshots]=useState<Snapshot[]>([]),[history,setHistory]=useState<Verification[]>([]),[value,setValue]=useState<Verification|null>(null);
  const [selected,setSelected]=useState<string[]>([]),[field,setField]=useState('last'),[trigger,setTrigger]=useState('USER_SELECTED'),[reason,setReason]=useState(''),[cutoff,setCutoff]=useState('');
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[replay,setReplay]=useState('');
  async function load(){try{setSnapshots(await request<Snapshot[]>('/data/snapshots'));const records=await request<Verification[]>('/data/verifications');setHistory(records);if(value)setValue(records.find(v=>v.verification_id===value.verification_id)??value);}catch(e){setError(String(e));}}
  useEffect(()=>{void load();},[]);
  const available=snapshots.filter(s=>!reviewTask||reviewTask.data_versions.includes(s.snapshot_id)).flatMap(s=>s.facts.map((f,i)=>({key:s.snapshot_id+':'+i,ref:{snapshot_id:s.snapshot_id,fact_index:i},f,kind:s.evidence_kind}))).filter(r=>Object.hasOwn(r.f,field));
  async function verify(e:FormEvent){e.preventDefault();setBusy(true);setError('');setReplay('');try{
    const references=available.filter(r=>selected.includes(r.key)).map(r=>r.ref);
    const command={trigger,reason,facts:[{fact_id:'decisive-'+field,field,references}],...(reviewTask?{knowledge_cutoff:reviewTask.knowledge_cutoff}:cutoff?{knowledge_cutoff:new Date(cutoff).toISOString()}:{} )};
    const frozen=reviewTask?await request<{request_id:string}>(`/reviews/tasks/${reviewTask.task_id}/verification-request`,command):null;
    const result=frozen?await request<Verification>(`/reviews/verification-requests/${frozen.request_id}/verify`,{}):await request<Verification>('/data/verifications',command);
    setValue(result);setHistory(await request<Verification[]>('/data/verifications'));
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  async function view(id:string){if(!id){setValue(null);return;}try{setValue(await request<Verification>('/data/verifications/'+id));setReplay('');setError('');}catch(e){setValue(history.find(v=>v.verification_id===id)??null);setError(String(e));}}
  return <section aria-label="关键复盘" className="verification-review"><h2>关键复盘</h2><p>普通记录可用单源基本检查；只核对足以改变结论的疑点。来源域名或多个模型重述不增加独立依据。</p>{error&&<p role="alert">{error}</p>}
    <form onSubmit={verify}><label>关键复盘触发<select value={trigger} onChange={e=>setTrigger(e.target.value)}><option value="USER_SELECTED">用户指定重点复盘</option><option value="MATERIAL_DOUBT">疑点影响重大盈亏、失效或规则归因</option><option value="CRITICAL_CONFLICT">影响结论的关键字段冲突</option></select></label>
      <label>疑点及其如何影响结论<textarea required maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <label>决定性字段<select value={field} onChange={e=>{setField(e.target.value);setSelected([]);}}>{Object.entries(fields).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      {reviewTask?<p>保持原观察知识截止 {reviewTask.knowledge_cutoff}；仅选择原观察实际保存的事实。</p>:<label>复盘当时已知截至（留空按当前已取得材料）<input type="datetime-local" value={cutoff} onChange={e=>setCutoff(e.target.value)}/></label>}
      <fieldset className="evidence-choices"><legend>选择决定性事实的已有依据（最多6项）</legend>{available.length?available.map(r=><label key={r.key}><input type="checkbox" checked={selected.includes(r.key)} disabled={!selected.includes(r.key)&&selected.length>=6} onChange={e=>setSelected(e.target.checked?[...selected,r.key]:selected.filter(k=>k!==r.key))}/>{text(r.f.instrument)} · {text(r.f.trade_date??r.f.report_period??r.f.disclosure_date)} · {text(r.f.source_id)} · 原值 {text(r.f[field])} · {r.ref.snapshot_id.slice(0,8)} #{r.ref.fact_index}{r.kind.startsWith('METHOD_CASE')?' · 固定方法材料':''}</label>):<p>此字段尚无归档事实，请先从市场事实取得依据。</p>}</fieldset><button disabled={busy||!selected.length}>核验决定性事实</button>
    </form>
    <label>选择已存核验<select value={value?.verification_id??''} onChange={e=>void view(e.target.value)}><option value="">请选择</option>{history.map(v=><option key={v.verification_id} value={v.verification_id}>{new Date(v.created_at).toLocaleString('zh-CN')} · {results[v.current_result]} · {v.command.reason}</option>)}</select></label><button type="button" onClick={()=>void load()}>刷新证据与核验</button>
    {value&&<article className="market-member"><h3>当前核验：{results[value.current_result]}</h3><p>{value.command.reason} · 知识截止 {value.knowledge_cutoff}</p>
      {value.review_origin&&<p role="status">已关联原观察 {value.review_origin.task_id} 与审计 {value.review_origin.audit_id} · 核验 {value.verification_id}</p>}
      {value.evidence_kind.startsWith('METHOD_CASE')&&<p role="status">固定方法核验：独立依据为合成测试材料，不表示真实市场多源核验通过。</p>}
      {value.dependency_status!=='CURRENT'&&<p role="status">该核验依据已失效或无法读取，相关归因暂缓；原结论“{results[value.result]}”仅作历史记录。</p>}{value.reuse_of&&<p role="status">复用同证据版本核验 {value.reuse_of}</p>}
      {value.facts.map(f=><section key={f.fact_id}><h4>{fields[f.field]??f.field}：{value.dependency_status==='CURRENT'?results[f.result]:'当前证据不足'}</h4><p>可证明的独立原始依据 {f.independent_basis_count} 条 · {value.dependency_status==='CURRENT'&&f.attribution_status==='READY'?'此项可形成事实归因':'此项归因暂缓，其他已知部分继续'}</p>{f.gaps.length>0&&<ul>{[...new Set(f.gaps)].map(g=><li key={g}>{gaps[g]??g}</li>)}</ul>}
        <ul>{f.evidence.map((e,i)=><li key={i}>{e.source_id} · 原值 {text(e.value)} · 单位 {e.field_unit} · 交易/事件 {text(e.context.trade_date??e.context.ex_date??e.context.report_period)} · 上游 {text(e.context.upstream_at)} · 本机可得 {e.available_at} · <a href={'/api/data/archives/'+e.raw_hash}>原始依据 {i+1}</a>{e.document_hash&&<> · <a href={'/api/data/archives/'+e.document_hash}>原始文件</a></>}<details><summary>原始链与比较详情</summary><p>{text(e.provenance.reason)}</p><pre>{JSON.stringify({provenance:e.provenance,context:e.context},null,2)}</pre></details></li>)}</ul>
        <details><summary>时点、口径与逐对原值比较</summary><pre>{JSON.stringify(f.comparisons,null,2)}</pre><p>{f.limitations.map(g=>gaps[g]??g).join('；')}</p></details>
      </section>)}
      <button onClick={async()=>{try{const r=await request<{network_calls:number;original_result:string}>('/data/verifications/'+value.verification_id+'/replay',{});setReplay(`原记录${results[r.original_result]}，网络调用 ${r.network_calls} 次`);}catch(e){setError(String(e));}}}>重放原核验</button>{replay&&<p role="status">{replay}</p>}
      <details><summary>核验版本与修订</summary><pre>{JSON.stringify(value,null,2)}</pre></details><p className="muted">核验不签发模型资格；成交、现金与权益到账仍由用户确认。</p>
    </article>}
  </section>;
}
