import {FormEvent,useEffect,useState} from 'react';
import {request} from '../api';
import '../styles/market.css';
import '../styles/evidence.css';
import {SourceResolution} from './SourceResolution';
import type {BackendSettings} from '../components/backend-panel';

type Listing={members:{instrument:string;identity:{name:string|null}}[];over_limit:boolean;background_indices:{instrument:string;name:string;basis?:string}[]};
type Gap={instrument:string;group:string;code:string;reason?:string;fields?:string[]};
type Candidate={instrument:string;group:string;assertion:string;evidence_quote:string;raw_hash:string;source_url?:string;event_time:null;available_at?:string};
type Run={run_id:string;request_id:string;status:string;evidence_kind:string;backend?:string;model?:string;resolved_model?:string;config_fingerprint?:string;sdk_runtime_version?:unknown;limits?:unknown;runtime_audit?:unknown;process?:unknown;retry_of?:string;backend_settings?:BackendSettings;question?:string;model_requests?:unknown;model_responses?:{sha256:string;http_status:number}[];error?:{code:string;message?:string};candidates?:Candidate[];started_at:string;finished_at?:string;snapshot_id?:string;gaps:Gap[];tools:{source_id:string;status:string;raw_hash?:string}[]};
type Fact=Record<string,unknown>&{instrument:string;group:string;raw_hash:string;source_url:string;received_at:string;available_at:string;revision_id:string};
type Snapshot={snapshot_id:string;request_id:string;requested_instruments:string[];requested_groups:string[];evidence_kind:string;namespace:string;facts:Fact[];observations:(Record<string,unknown>&{observation_id:string;kind:string;instrument:string;severity:string;basis_raw_hashes:string[]})[];coverage:Record<string,unknown>[];gaps:Gap[];parquet:{sha256:string};created_at:string};
const groups:{[key:string]:string}={DAILY:'日线与复权',QUOTE:'可得报价',ADJUSTMENTS:'调整事件',ANNOUNCEMENTS:'公告原文',PERFORMANCE:'业绩',MAJOR_EVENTS:'重大事项',STATUS:'证券状态',CALENDAR:'交易日历'};
const kinds:{[key:string]:string}={PENDING_ACCOUNT_RECONCILIATION:'权益到账待核',ACTION_PLAN_REFERENCE:'分派计划参考',DISCLOSED_COMPANY_EVENT:'已披露公司事项',DATA_QUALITY_ALERT:'数据口径待核',EX_RIGHTS_PRICE_CONTEXT:'除息原价变化上下文',PRICE_MOVE_OBSERVATION:'原价显著变化',STATUS_RISK_ALERT:'证券异常状态'};
const classification:{[key:string]:string}={FACT:'客观事实',DETERMINISTIC_INFERENCE:'确定性结构化推断'};
const localDate=(delta=0)=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date(Date.now()+delta*86400000));
const text=(value:unknown)=>value===null||value===undefined?'未知':typeof value==='object'?JSON.stringify(value):String(value);
const showTime=(value:unknown)=>value?new Date(String(value)).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未证实';

export function Evidence(){
  const [listing,setListing]=useState<Listing|null>(null);
  const [instruments,setInstruments]=useState<string[]>([]);
  const [purpose,setPurpose]=useState('OBSERVATION');
  const [selectedGroups,setSelectedGroups]=useState(Object.keys(groups).filter(g=>g!=='CALENDAR'));
  const [start,setStart]=useState(localDate(-90));const [end,setEnd]=useState(localDate());
  const [source,setSource]=useState('TENCENT');const [maxCalls,setMaxCalls]=useState(30);
  const [backend,setBackend]=useState('DIRECT_HTTP');const [settings,setSettings]=useState<BackendSettings|null>(null);const [question,setQuestion]=useState('请核对所请求事实的来源与时点，补充有依据的缺失事实并明确缺口。');
  const [baoAuth,setBaoAuth]=useState('API_KEY');
  const [statusSource,setStatusSource]=useState('QUOTE');
  const [quoteSource,setQuoteSource]=useState('TENCENT');const [adjustmentSource,setAdjustmentSource]=useState('EASTMONEY');const [needShares,setNeedShares]=useState(false);
  const [runs,setRuns]=useState<Run[]>([]);const [run,setRun]=useState<Run|null>(null);const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [registry,setRegistry]=useState<Record<string,unknown>[]>([]);
  const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [replay,setReplay]=useState('');
  async function view(value:Run){setRun(value);setReplay('');setSnapshot(value.snapshot_id?await request<Snapshot>('/data/snapshots/'+value.snapshot_id):null);}
  useEffect(()=>{void Promise.all([request<Listing>('/market/list'),request<Run[]>('/data/runs'),request<Record<string,unknown>[]>('/data/sources')]).then(async ([list,history,sources])=>{
    void request<BackendSettings>('/agents/settings').then(setSettings).catch(e=>setError(String(e)));
    setListing(list);setInstruments(list.members.map(m=>m.instrument));setRuns(history);setRegistry(sources);if(history[0])await view(history[0]);
  }).catch(e=>setError(String(e)));},[]);
  useEffect(()=>{if(run?.status!=='RUNNING'||!['CODEX','DEEPSEEK'].includes(run.backend??''))return;
    const timer=setInterval(()=>void request<Run>('/data/runs/'+run.run_id).then(async value=>{await view(value);setRuns(await request<Run[]>('/data/runs'));}).catch(e=>setError(String(e))),1000);
    return ()=>clearInterval(timer);
  },[run?.run_id,run?.status]);
  function changePurpose(value:string){setPurpose(value);if(value==='BACKGROUND')setSource('TENCENT');setInstruments(value==='BACKGROUND'?listing?.background_indices.map(i=>i.instrument)??[]:listing?.members.map(m=>m.instrument)??[]);setSelectedGroups(value==='BACKGROUND'?['DAILY','QUOTE']:Object.keys(groups).filter(g=>g!=='CALENDAR'));}
  async function retrieve(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{
    const command=await request<{request_id:string}>('/data/requests',{instruments,groups:selectedGroups,purpose,start_date:start,end_date:end,daily_source:source,
      quote_source:quoteSource,adjustment_source:adjustmentSource,status_source:statusSource,calendar_source:'BAOSTOCK',baostock_auth_mode:baoAuth,required_fields:needShares&&selectedGroups.includes('QUOTE')?['QUOTE.volume_shares']:[],max_calls:maxCalls,timeout_seconds:60});
    const value=await request<Run>('/data/requests/'+command.request_id+(backend==='AGENT'?'/agent':backend==='CODEX'?'/codex':backend==='DEEPSEEK'?'/deepseek':'/retrieve'),backend==='DIRECT_HTTP'?{}:{question});await view(value);setRuns(await request<Run[]>('/data/runs'));
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  const objects=purpose==='BACKGROUND'?listing?.background_indices:listing?.members.map(m=>({instrument:m.instrument,name:m.identity.name??m.instrument}));
  return <><section><h1>市场事实</h1><p>为持仓、关注和预定背景取得原始依据。来源缺口与未知状态分别保留，正式交易判断未启用。</p>
    {error&&<p role="alert">{error}</p>}{listing?.over_limit&&<p role="status">全部 {listing.members.length} 只真实资产可请求；调用预算不足会逐对象列出缺口。</p>}
    <form onSubmit={retrieve}>
      <label>取证方式<select value={backend} onChange={e=>setBackend(e.target.value)}><option value="DIRECT_HTTP">固定来源获取</option><option value="AGENT">设置后端补充取证（{settings?.backend==='DEEPSEEK'?'DeepSeek':'Codex'}）</option><option value="CODEX">Codex 补充取证</option><option value="DEEPSEEK">DeepSeek 补充取证</option></select></label>
      {backend!=='DIRECT_HTTP'&&<label>需要补充核对的问题<textarea required maxLength={2000} value={question} onChange={e=>setQuestion(e.target.value)}/></label>}
      <label>取证用途<select value={purpose} onChange={e=>changePurpose(e.target.value)}><option value="OBSERVATION">名单观察</option><option value="RESEARCH">历史研究输入归档</option><option value="BACKGROUND">预定市场背景</option></select></label>
      <fieldset className="evidence-choices"><legend>请求对象（已选 {instruments.length} 只）</legend>{objects?.map(o=><label key={o.instrument}><input type="checkbox" checked={instruments.includes(o.instrument)} onChange={e=>setInstruments(e.target.checked?[...instruments,o.instrument]:instruments.filter(i=>i!==o.instrument))}/>{o.name} · {o.instrument}</label>)}</fieldset>
      <fieldset className="evidence-choices"><legend>事实组</legend>{Object.entries(groups).filter(([g])=>purpose!=='BACKGROUND'||['DAILY','QUOTE'].includes(g)).map(([g,label])=><label key={g}><input type="checkbox" checked={selectedGroups.includes(g)} onChange={e=>setSelectedGroups(e.target.checked?[...selectedGroups,g]:selectedGroups.filter(v=>v!==g))}/>{label}</label>)}</fieldset>
      <label>开始日期（上海交易/披露日期）<input type="date" required value={start} onChange={e=>setStart(e.target.value)}/></label>
      <label>截止日期<input type="date" required value={end} max={localDate()} onChange={e=>setEnd(e.target.value)}/></label>
      <label>日线来源<select value={source} onChange={e=>setSource(e.target.value)}><option value="TENCENT">腾讯：历史成交额通常缺失</option>{purpose!=='BACKGROUND'&&<option value="EASTMONEY">东方财富：保留实际失败</option>}<option value="FUYAO">扶摇：同花顺日线</option>{purpose!=='BACKGROUND'&&<option value="BAOSTOCK">BaoStock：不复权日线及量额</option>}</select></label>
      <label>报价来源<select value={quoteSource} onChange={e=>setQuoteSource(e.target.value)}><option value="TENCENT">腾讯</option><option value="SINA">新浪：已实证主板股票股数口径</option><option value="FUYAO">扶摇：逐证券时间未知</option></select></label>
      {purpose!=='BACKGROUND'&&selectedGroups.includes('ADJUSTMENTS')&&<label>除权事项来源<select value={adjustmentSource} onChange={e=>setAdjustmentSource(e.target.value)}><option value="EASTMONEY">东方财富公告及分派</option><option value="FUYAO">扶摇：原始除权事件</option><option value="BAOSTOCK">BaoStock：分红实施日期</option></select></label>}
      {purpose!=='BACKGROUND'&&selectedGroups.includes('STATUS')&&<label>证券状态来源<select value={statusSource} onChange={e=>setStatusSource(e.target.value)}><option value="QUOTE">报价附带状态：可能未知</option><option value="BAOSTOCK">BaoStock：逐日交易与 ST 标记</option></select></label>}
      {purpose!=='BACKGROUND'&&(source==='BAOSTOCK'||adjustmentSource==='BAOSTOCK'||statusSource==='BAOSTOCK'||selectedGroups.includes('CALENDAR'))&&<label>BaoStock 访问方式<select value={baoAuth} onChange={e=>setBaoAuth(e.target.value)}><option value="API_KEY">已配置 API Key</option><option value="PUBLIC">公共匿名接口</option></select></label>}
      <label><input type="checkbox" checked={needShares} onChange={e=>setNeedShares(e.target.checked)}/>报价需要已核对的股数，缺失时限制此用途</label>
      {backend==='DIRECT_HTTP'&&<label>本次最多调用<input type="number" value={maxCalls} min={1} max={30} onChange={e=>setMaxCalls(Number(e.target.value))}/></label>}
      <p className="muted">日线原价与当前前复权版本分开。历史取得时间为实际本次时间，不能证明过去已经可得；背景指数不取得个股研究或交易能力。</p>
      <button disabled={busy||run?.status==='RUNNING'||!instruments.length||!selectedGroups.length}>{busy?'正在创建取证记录…':backend==='AGENT'?'启动设置后端取证':backend==='CODEX'?'启动 Codex 取证':backend==='DEEPSEEK'?'启动 DeepSeek 取证':'取得并归档事实'}</button>
    </form></section>
    <section><h2>取证记录</h2>{!runs.length?<p>尚无归档记录。</p>:<label>选择归档运行<select aria-label="选择归档运行" value={run?.run_id??''} onChange={e=>{const found=runs.find(r=>r.run_id===e.target.value);if(found)void view(found).catch(e=>setError(String(e)));}}>{runs.map(r=><option key={r.run_id} value={r.run_id}>{showTime(r.started_at)} · {r.status} · {r.evidence_kind}</option>)}</select></label>}
      {run&&<><p>获取状态：{run.status} · 来源种类：{run.evidence_kind} · 上海时间 {showTime(run.started_at)}</p><p className="muted">获取完成只表示请求已处理；必需字段、单位、当前状态和模型资格仍分别检查。</p>
      {['CODEX','DEEPSEEK'].includes(run.backend??'')&&run.status==='RUNNING'&&<button onClick={()=>void request('/data/runs/'+run.run_id+'/cancel',{}).catch(e=>setError(String(e)))}>取消本次取证</button>}
      {run.error&&<p role="alert">{run.error.code}{run.error.message&&` · ${run.error.message}`}</p>}
      {['CODEX','DEEPSEEK'].includes(run.backend??'')&&<details><summary>后端与运行配置</summary><p>{run.backend==='CODEX'?'Codex':'DeepSeek'} · 模型 {run.resolved_model??run.model} · 配置 {run.config_fingerprint} · 设置版本 {run.backend_settings?.version??'历史记录'}</p><pre>{JSON.stringify({versions:run.sdk_runtime_version,limits:run.limits,runtime:run.runtime_audit,cleanup:run.process,model_requests:run.model_requests},null,2)}</pre>{run.model_responses?.map((r,i)=><p key={i}>模型响应 HTTP {r.http_status} · <a href={'/api/data/archives/'+r.sha256}>本地脱敏记录</a></p>)}</details>}
      {['CODEX','DEEPSEEK'].includes(run.backend??'')&&run.status!=='RUNNING'&&<button disabled={busy} onClick={()=>{setBusy(true);void request<Run>('/data/requests/'+run.request_id+'/agent',{question:run.question??question,retry_of:run.run_id}).then(async value=>{await view(value);setRuns(await request<Run[]>('/data/runs'));}).catch(e=>setError(String(e))).finally(()=>setBusy(false));}}>重新尝试本次请求</button>}
      {run.retry_of&&<p className="muted">关联原运行：{run.retry_of}；原记录保留。</p>}
      {run.candidates&&run.candidates.length>0&&<><h3>补充证据候选</h3><p>原文字面引用已核对；模型表述与事项发生时间待核，不能直接作为历史事实或正式判断。</p>{run.candidates.map((c,i)=><article key={i}><h4>{c.instrument} · {c.assertion}</h4><blockquote>{c.evidence_quote}</blockquote><p>事项时间：未知 · 实际获取 {showTime(c.available_at)} · <a href={'/api/data/archives/'+c.raw_hash}>原始依据</a>{c.source_url&&<> · <a href={c.source_url} target="_blank" rel="noreferrer">来源页面</a></>}</p></article>)}</>}
      {run.evidence_kind.startsWith('METHOD_CASE')&&<p role="status">固定方法样本：模拟状态时间，仅用于验收，不是实际当前市场状态。</p>}
      {run.gaps.length>0&&<details open><summary>未取得或受限：{run.gaps.length} 项</summary><ul>{run.gaps.map((g,i)=><li key={i}>{g.instrument} · {groups[g.group]??g.group}：{g.code}{g.reason&&` · ${g.reason}`}{g.fields&&` · ${g.fields.join('、')}`}</li>)}</ul></details>}
      <details><summary>来源与工具记录</summary><ul>{run.tools.map((t,i)=><li key={i}>{t.source_id} · {t.status}{t.raw_hash&&<> · <a href={'/api/data/archives/'+t.raw_hash}>原始响应</a></>}</li>)}</ul></details></>}
    </section>
    <SourceResolution requestId={run?.request_id} runId={run?.run_id}/>
    {snapshot&&<section><h2>归档事实与客观观察</h2><p>{snapshot.namespace} · {snapshot.requested_instruments.length} 只对象 · {snapshot.facts.length} 条事实 · 归档于 {showTime(snapshot.created_at)}</p>
      <p><a href={'/api/data/archives/'+snapshot.parquet.sha256}>下载规范化 Parquet</a> · <button onClick={()=>void request<{network_calls:number}>('/data/runs/'+run?.run_id+'/replay',{}).then(r=>setReplay(`同版本归档回放完成，网络调用 ${r.network_calls} 次`)).catch(e=>setError(String(e)))}>只读归档回放</button></p>{replay&&<p role="status">{replay}</p>}
      {snapshot.observations.map(o=><article className="market-member" key={o.observation_id}><h3>{o.instrument} · {text(o.title??kinds[o.kind]??o.kind)}</h3><p>{text(o.message??classification[String(o.classification)]??o.classification)} · {o.severity==='ATTENTION'?'需关注':'提示'}</p><p className="muted">{classification[String(o.classification)]??text(o.classification)} · 事件日期 {text(o.event_date)} · 精度 {text(o.time_precision)} · 实际观察 {showTime(o.observed_at)}</p><details><summary>原始依据与未知项</summary>{o.basis_raw_hashes.map((h,i)=><p key={i}><a href={'/api/data/archives/'+h}>依据 {h.slice(0,12)}</a></p>)}<p>未知项：{text(o.unknown_items)} · 正式判断未启用</p></details></article>)}
      <details><summary>覆盖与限制（{snapshot.coverage.length} 组记录）</summary>{snapshot.coverage.map((c,i)=><pre key={i}>{JSON.stringify(c,null,2)}</pre>)}</details>
      {snapshot.requested_groups.map(group=><details key={group}><summary>{groups[group]}：{snapshot.facts.filter(f=>f.group===group).length} 条归档事实</summary>{snapshot.facts.filter(f=>f.group===group).map((f,i)=><article className="market-member" key={i}>
        <h3>{f.instrument} · {text(f.title??f.trade_date??f.disclosure_date??f.state)}</h3>
        <p>{f.group==='DAILY'?`原价/复权 ${text(f.adjustment)} · 收盘 ${text(f.close)} · 成交量 ${text(f.volume_reported)} (${text(f.source_volume_unit)}) · 股 ${text(f.volume_shares)} · 成交额元 ${text(f.amount_yuan)} · ${text(f.completion_state)}`:f.group==='QUOTE'?`可得报价 ${text(f.last)} · 上游 ${showTime(f.upstream_at)} · 距获取 ${text(f.age_seconds)} 秒`:`状态/报告期 ${text(f.state??f.report_period)} · 披露日期 ${text(f.disclosure_date)}`}</p>
        <p className="muted">获取 {showTime(f.received_at)} · 本机首次可得 {showTime(f.available_at)} · 事件精度 {text(f.time_precision)}</p>
        <p><a href={'/api/data/archives/'+f.raw_hash}>原始响应</a>{Boolean(f.document_hash)&&<> · <a href={'/api/data/archives/'+String(f.document_hash)}>原始 PDF</a></>}</p>
        <details><summary>转换、质量与来源详情</summary><p><a href={f.source_url} target="_blank" rel="noreferrer">来源地址</a></p><pre>{JSON.stringify(f,null,2)}</pre></details>
      </article>)}</details>)}
    </section>}
    <section><details><summary>实际来源登记与权限、深度限制</summary>{registry.map(s=><article key={String(s.id)}><h3>{text(s.id)}</h3><p>{text(s.depth)}</p><p>{text(s.unit_scope)}</p><p>{text(s.permission_basis)}</p></article>)}</details></section>
  </>;
}
