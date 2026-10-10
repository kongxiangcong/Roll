import {useEffect,useState} from 'react';
import {request} from '../api';

type Resolution={resolution_id:string;request_id:string;status:string;evidence_kind:string;state?:string;started_at:string;knowledge_cutoff?:string;
  dependency_status?:string;network_calls?:number;stop_reason?:string;reason?:string;command:{usage:string};
  facts:Record<string,unknown>[];attempts:{role:string;run_id:string;cached?:boolean}[];source_checks:Record<string,unknown>[];
  freshness?:Record<string,unknown>[];gaps?:Record<string,unknown>[];capabilities?:Record<string,string>;cache?:Record<string,unknown>;
  revision?:{reason:string;prior_resolution_id:string;changed_fact_keys:unknown[]}};
const time=(value:unknown)=>value?new Date(String(value)).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未知';
const text=(value:unknown)=>value===undefined||value===null?'未知':String(value);
const health:Record<string,string>={HEALTHY:'本用途必需事实可读取，仍不授予交易或模型资格',DEGRADED:'已有部分继续，缺口按字段与用途保留',
  BLOCKED_NEW_RISK:'必需条件未满足，对应新风险能力受限',MONITORING_UNAVAILABLE:'缺少适用当前交易时段的报价，不能保证当前监控'};

export function SourceResolution({requestId,runId}:{requestId?:string;runId?:string}){
  const [usage,setUsage]=useState('PRE_MARKET_RECORD');const [useCache,setUseCache]=useState(true);
  const [result,setResult]=useState<Resolution|null>(null);const [history,setHistory]=useState<Resolution[]>([]);
  const [error,setError]=useState('');const [replay,setReplay]=useState('');
  const busy=result?.status==='RUNNING';
  const summaryFacts=result?Object.values(result.facts.reduce<Record<string,Record<string,unknown>>>((rows,f)=>{
    if(f.group!=='QUOTE'&&!(f.group==='DAILY'&&f.adjustment==='RAW'))return rows;
    const instrument=String(f.instrument);const previous=rows[instrument];
    if(!previous||f.group==='QUOTE'||previous.group!=='QUOTE'&&String(f.trade_date)>String(previous.trade_date))rows[instrument]=f;
    return rows;
  },{})):[];
  async function load(){const rows=await request<Resolution[]>('/data/resolutions');setHistory(rows.filter(r=>r.request_id===requestId));}
  useEffect(()=>{setResult(null);setReplay('');void load().catch(e=>setError(String(e)));},[requestId]);
  useEffect(()=>{
    if(!result||result.status!=='RUNNING')return;
    let active=true;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{const value=await request<Resolution>('/data/resolutions/'+result.resolution_id);if(active){setResult(value);
      if(value.status==='RUNNING')timer=setTimeout(()=>void poll(),300);else await load();}}
      catch(e){if(active)setError(String(e));}};
    timer=setTimeout(()=>void poll(),200);return()=>{active=false;clearTimeout(timer);};
  },[result?.resolution_id,result?.status]);
  async function resolve(refresh=false){if(!requestId)return;setError('');setReplay('');try{
    const value=await request<Resolution>('/data/requests/'+requestId+'/resolve',{usage,use_cache:refresh?false:useCache,
      basis_run_id:refresh?undefined:runId,revision_of:refresh?result?.resolution_id:undefined});setResult(value);
    if(value.status!=='RUNNING')await load();
  }catch(e){setError(String(e));}}
  return <section><h2>用途与换源</h2><p>读取当前选择的归档请求。补查最多尝试一条适配备源，共用原请求的调用与时间预算；等待期间可同步账户。</p>
    {!requestId&&<p>先取得事实，再按用途检查原档案。</p>}{error&&<p role="alert">{error}</p>}
    <label>本次读取用途<select value={usage} onChange={e=>setUsage(e.target.value)}>
      <option value="PRE_MARKET_RECORD">盘前读取上一交易日</option><option value="POST_MARKET_RECORD">盘后记录</option>
      <option value="CURRENT_MONITORING">当前市场观察</option><option value="HISTORICAL_RESEARCH">历史材料读取</option><option value="NEW_RISK">新风险输入条件检查</option>
    </select></label><label><input type="checkbox" checked={useCache} onChange={e=>setUseCache(e.target.checked)}/>优先复用仍适用的归档，不刷新原采集时点</label>
    <button disabled={!requestId||busy} onClick={()=>void resolve()}>{busy?'正在有界补查…':'按用途检查并补查'}</button>
    {history.length>0&&<label>选择用途记录<select aria-label="选择用途记录" value={result?.resolution_id??''} onChange={e=>{void request<Resolution>('/data/resolutions/'+e.target.value).then(value=>{setResult(value);setReplay('');}).catch(e=>setError(String(e)));}}>
      <option value="" disabled>选择记录</option>{history.map(r=><option key={r.resolution_id} value={r.resolution_id}>{time(r.started_at)} · {r.state??r.status} · {r.command.usage}</option>)}
    </select></label>}
    {result&&result.status!=='RUNNING'&&<><h3>用途与换源结果</h3><p>本次用途：{result.state??result.status}</p><p>{health[result.state??'']??result.reason}</p>
      {result.evidence_kind==='METHOD_CASE'&&<p>固定方法样本，仅证明受控错误/修订/等待路径。</p>}
      <p>消费知识截止 {time(result.knowledge_cutoff)} · 本次网络调用 {result.network_calls??'未知'} 次</p>
      {result.cache&&<p>沿用原采集时点，本次网络调用 0 次</p>}
      {result.dependency_status==='INVALIDATED'&&<p role="status">该旧派生依据已失效；原输入与当时状态继续保留。</p>}
      {result.revision&&<p>后继依据：{result.revision.reason} · 改变 {result.revision.changed_fact_keys.length} 项原事实</p>}
      {summaryFacts.map((f,i)=><article className="market-member" key={i}><p>{text(f.instrument)} · {text(f.source_id)} · 报价 {text(f.last??f.close)} · 股数 {text(f.volume_shares)} · 成交额元 {text(f.amount_yuan)}</p>
        <p className="muted">报告交易日 {text(f.trade_date)} · 上游 {time(f.upstream_at)} · 实际采集 {time(f.received_at)} · 首次可得 {time(f.available_at)}</p>
        <a href={'/api/data/archives/'+text(f.raw_hash)}>对应原件</a></article>)}
      <details><summary>本次全部事实（{result.facts.length} 项，概览每对象最新报价或原价日线）</summary><pre>{JSON.stringify(result.facts,null,2)}</pre></details>
      <button disabled={busy||result.status!=='COMPLETED'} onClick={()=>void resolve(true)}>重新取数形成后继记录</button>{' '}
      <button disabled={result.status!=='COMPLETED'} onClick={()=>void request<{original_state:string;network_calls:number}>('/data/resolutions/'+result.resolution_id+'/replay',{}).then(r=>setReplay(`原用途状态 ${r.original_state}，网络调用 ${r.network_calls} 次`)).catch(e=>setError(String(e)))}>重放原输入</button>
      {replay&&<p role="status">{replay}</p>}
      <details><summary>字段、用途与停止原因</summary><pre>{JSON.stringify({capabilities:result.capabilities,freshness:result.freshness,gaps:result.gaps,stop_reason:result.stop_reason},null,2)}</pre></details>
      <details><summary>逐字段换源比较与原运行</summary><pre>{JSON.stringify(result.source_checks,null,2)}</pre><ul>{result.attempts.map((a,i)=><li key={i}>{a.role} · {a.cached?'复用原档案':'实际取得'} · {a.run_id}</li>)}</ul></details>
    </>}
  </section>;
}
