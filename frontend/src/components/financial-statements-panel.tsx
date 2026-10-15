import {useState} from 'react';
import {request} from '../api';

type Fact={fact_id:string;statement:string;report_period:string;version:number;period_basis:string;values:Record<string,string|null>;raw_sha256:string;semantic_document:{sha256:string;page:number}|null;original_fields:Record<string,unknown>;gaps:string[];evidence_kind:string;available_at:string};
type Group={report_period:string;statement_scope:string;currency:string|null;unit:string;status:string;missing:string[];facts:Record<string,Fact>;versions:Record<string,string>;balance_check:{status:string;difference:string|null;tolerance:string|null}};
type View={groups:Group[];active_run_ids:string[];runs:{run_id:string;status:string;errors:string[]}[]};
const labels:Record<string,string>={INCOME:'利润表',BALANCE:'资产负债表',CASH_FLOW:'现金流量表',MATCHED:'三表口径匹配',MISSING_STATEMENTS:'缺少报表',UNVERIFIED_SCOPE:'口径尚未证明',INCOMPLETE_VALUES:'金额缺失',WITHIN_ROUNDING:'差异在来源舍入范围内',REQUIRES_REVIEW:'平衡差异待核',UNKNOWN:'来源精度或金额未知'};
const fields:Record<string,string>={revenue:'营业收入',net_profit:'净利润',parent_net_profit:'归母净利润',assets:'资产总计',liabilities:'负债合计',equity:'股东权益合计',operating_cash_flow:'经营现金流净额',investing_cash_flow:'投资现金流净额',financing_cash_flow:'筹资现金流净额',net_cash_change:'现金净增加额'};
export function FinancialStatementsPanel({instrument}:{instrument:string}){
  const [value,setValue]=useState<View|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[cutoff,setCutoff]=useState('');
  const base=`/market/financial/${encodeURIComponent(instrument)}/statements`;
  async function read(){return request<View>(base+(cutoff?`?known_by=${encodeURIComponent(new Date(cutoff).toISOString())}`:''));}
  async function run(collect=false){setBusy(true);setError('');setValue(null);try{
    if(collect){const result=await request<{status:string;errors:string[]}>(base+'/collect',{idempotency_key:crypto.randomUUID(),basis:'用户显式请求有限资产负债与现金流观察'});if(result.status!=='COMPLETE')setError(`采集${result.status}：${result.errors.join('；')}`);}
    setValue(await read());
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  async function cancel(){try{const current=await request<View>(base);if(!current.active_run_ids.length){setError('当前没有可取消的三表采集');return;}await request(`/market/financial/runs/${current.active_run_ids[0]}/cancel`,{});}catch(e){setError(String(e));}}
  return <details className="status-evidence"><summary>三表联读</summary>
    <p>同证券、报告期、主体、币种、单位及来源更新版本关联；资产负债为时点数，利润与现金流为年初累计。未知口径分别显示，当前观察不构成历史PIT或模型资格。</p>
    <label>三表系统已知截至<input type="datetime-local" disabled={busy} value={cutoff} onChange={e=>{setCutoff(e.target.value);setValue(null);}}/></label>
    <button disabled={busy} onClick={()=>void run()}>查询保存的三表</button><button disabled={busy||!!cutoff} onClick={()=>void run(true)}>有限采集资产负债与现金流</button>
    {busy&&<button onClick={()=>void cancel()}>取消三表采集</button>}
    {value&&!value.groups.length&&<p>尚无已保存三表事实</p>}
    {value?.groups.map(g=><section key={Object.values(g.versions).join(':')} aria-label={`三表 ${g.report_period} ${g.status}`}>
      <h3>{g.report_period} · {g.statement_scope==='CONSOLIDATED'?'合并':'主体未知'} · {g.currency??'币种未知'} · {g.unit==='YUAN'?'元':'单位未知'}</h3>
      <p>{labels[g.status]??g.status}{g.missing.length>0&&`：${g.missing.map(s=>labels[s]).join('、')}`}</p>
      {g.facts.BALANCE&&<p>资产−负债−权益：{g.balance_check.difference??'未知'}；来源舍入容差：{g.balance_check.tolerance??'未知'}；{labels[g.balance_check.status]}</p>}
      {Object.entries(g.facts).map(([statement,f])=><details key={f.fact_id}><summary>{labels[statement]} · 版本{f.version} · {f.period_basis==='POINT_IN_TIME'?'报告期末时点':f.period_basis==='YEAR_TO_DATE'?'年初累计':'期间未知'}</summary>
        <p>{f.evidence_kind==='METHOD_CASE'?'METHOD工程证据':'当前来源观察'} · 可知时间{f.available_at}</p>
        <dl>{Object.entries(f.values).map(([key,amount])=><div key={key}><dt>{fields[key]??key}</dt><dd>{amount??'未知'}</dd></div>)}</dl>
        <p><a href={`/api/data/archives/${f.raw_sha256}`} target="_blank" rel="noreferrer">{labels[statement]}原响应</a>{f.semantic_document&&<> · <a href={`/api/data/archives/${f.semantic_document.sha256}#page=${f.semantic_document.page}`} target="_blank" rel="noreferrer">口径PDF第{f.semantic_document.page}页</a></>}</p>
        <details><summary>原始字段与缺口</summary><pre>{JSON.stringify(f.original_fields,null,2)}</pre><p>{f.gaps.join('；')}</p></details>
      </details>)}
    </section>)}
    {value?.runs.filter(r=>r.status!=='COMPLETE').map(r=><p key={r.run_id}>采集{r.status}：{r.errors.join('；')}</p>)}
    {error&&<p role="alert">{error}</p>}
  </details>;
}
