import {useState} from 'react';
import {request} from '../api';

type Fact={fact_id:string;report_period:string;version:number;supersedes_id:string|null;statement_scope:string;period_basis:string;currency:string|null;unit:string;
  values:Record<string,string|null>;reported_publication_date:string|null;reported_update_date:string|null;first_received_at:string;available_at:string;raw_sha256:string;evidence_kind:string;
  semantic_document:{sha256:string;page:number}|null;original_fields:Record<string,unknown>;gaps:string[];comparable_with_superseded:boolean};
type Income={known_by:string;facts:Fact[];active_run_ids:string[];runs:{run_id:string;status:string;errors:string[]}[]};

export function FinancialIncomePanel({instrument}:{instrument:string}){
  const [value,setValue]=useState<Income|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[cutoff,setCutoff]=useState('');
  const base=`/market/financial/${encodeURIComponent(instrument)}/income`;
  async function read(){return request<Income>(base+(cutoff?`?known_by=${encodeURIComponent(new Date(cutoff).toISOString())}`:''));}
  async function inspect(){setBusy(true);setError('');setValue(null);try{setValue(await read());}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function collect(){
    setBusy(true);setError('');setValue(null);
    try{
      const result=await request<{status:string;errors:string[]}>(base+'/collect',{idempotency_key:crypto.randomUUID(),basis:'用户从单股页面显式请求有界利润表观察'});
      if(result.status!=='COMPLETE')setError(`采集${result.status}：${result.errors.join('；')}`);
      setValue(await read());
    }catch(e){setError(String(e));}finally{setBusy(false);}
  }
  async function cancel(){try{
    const current=await request<Income>(base);
    if(!current.active_run_ids.length){setError('当前没有可取消的利润表采集');return;}
    await request(`/market/financial/runs/${current.active_run_ids[0]}/cancel`,{});
  }catch(e){setError(String(e));}}
  return <details className="status-evidence financial-income"><summary>查看利润表</summary>
    <p className="muted">AKShare 1.19.1 · 东财来源 · 最近五个报告期。默认关闭，请在来源配置显式启用；范围外或未配置独立运行环境时显示原因。</p>
    <label>财报系统已知截至（留空查询当前）<input type="datetime-local" disabled={busy} value={cutoff} onChange={e=>{setCutoff(e.target.value);setValue(null);}}/></label>
    <button disabled={busy} onClick={()=>void inspect()}>查询保存的利润表</button>
    <button disabled={busy||!!cutoff} onClick={()=>void collect()}>有限采集利润表</button>
    {busy&&<button onClick={()=>void cancel()}>取消利润表采集</button>}
    {value&&!value.facts.length&&<p>尚无已保存利润表</p>}
    {value?.facts.map(f=><section key={f.fact_id} aria-label={`利润表 ${f.report_period} 版本${f.version}`}>
      <h3>{f.report_period} · {f.statement_scope==='CONSOLIDATED'?'合并':'口径未知'} · {f.period_basis==='YEAR_TO_DATE'?'年初累计':'期间口径未知'} · {f.currency??'币种未知'} {f.unit==='YUAN'?'元':'单位未知'} · 版本{f.version}</h3>
      <p>{f.evidence_kind==='METHOD_CASE'?'METHOD工程证据':'当前收到的来源观察'} · 非历史PIT</p>
      <dl>{[['revenue','营业收入'],['net_profit','净利润'],['parent_net_profit','归母净利润']].map(([key,label])=><div key={key}><dt>{label}</dt><dd>{f.values[key]??'未知'}</dd></div>)}</dl>
      <p>来源披露日 {f.reported_publication_date??'未知'}（日期精度） · 来源更新 {f.reported_update_date??'未知'}<br/>首次接收 {f.first_received_at}<br/>本规范事实可知 {f.available_at}</p>
      <p><a href={`/api/data/archives/${f.raw_sha256}`} target="_blank" rel="noreferrer">利润表原响应</a>{f.semantic_document&&<> · <a href={`/api/data/archives/${f.semantic_document.sha256}#page=${f.semantic_document.page}`} target="_blank" rel="noreferrer">口径PDF第{f.semantic_document.page}页</a></>}</p>
      {f.supersedes_id&&<p>同来源修订前版本 {f.supersedes_id} · {f.comparable_with_superseded?'已验证口径一致':'可比口径未证明'}</p>}
      <details><summary>来源字段与缺口</summary><pre>{JSON.stringify(f.original_fields,null,2)}</pre><p>{f.gaps.join('；')}</p></details>
    </section>)}
    {value?.runs.filter(r=>r.status!=='COMPLETE').map(r=><p key={r.run_id}>采集记录 {r.status}：{r.errors.join('；')}</p>)}
    {error&&<p role="alert">{error}</p>}
  </details>;
}
