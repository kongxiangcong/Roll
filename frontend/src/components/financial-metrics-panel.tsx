import {useState} from 'react';
import {request} from '../api';
type Metric={status:string;value:string|null;formula:string;reason:string|null;unit:string;source_fact_ids:string[];absolute_change?:string|null};
type View={known_by:string;calculation_version:string;periods:{report_period:string;metrics:Record<string,Metric>}[];source_versions:Record<string,{report_period:string;statement:string;version:number;raw_sha256:string}>};
const names:Record<string,string>={operating_revenue:'营业收入累计',revenue:'营业总收入累计',parent_net_profit:'归母净利累计',net_profit:'集团净利累计',operating_cash_flow:'经营现金累计',gross_margin:'毛利率',net_margin:'集团净利率',cash_profit_ratio:'集团经营现金／集团净利',debt_ratio:'负债率',revenue_yoy:'营收同比',parent_net_profit_yoy:'归母净利同比'};
const reasons:Record<string,string>={OPERATING_REVENUE_CONFLICT:'营业收入与已核验原表金额冲突，待核',PRIOR_YTD_MISSING_OR_INCOMPARABLE:'前一累计期缺失或不可比',CURRENT_FACT_UNKNOWN:'当前金额或口径未知',FOUR_COMPARABLE_QUARTERS_REQUIRED:'缺少四个连续可比单季',NON_POSITIVE_BASE:'同比基期为零或负，仅显示绝对变化',NON_POSITIVE_DENOMINATOR:'分母为零或负，不计算比率',PRIOR_YEAR_MISSING_OR_INCOMPARABLE:'上年同口径期间缺失或不可比',MISSING_OR_INCOMPARABLE_INPUT:'金额缺失或主体、期间、更新口径不可比',FINANCIAL_OR_UNKNOWN_INDUSTRY_NOT_APPLICABLE:'金融企业或行业未核对，通用毛利率不适用',NON_QUARTER_PERIOD:'非标准季末期间'};
function label(key:string){return key.startsWith('quarter_')?'单季'+(names[key.slice(8)]??key).replace('累计',''):key.startsWith('ttm_')?'TTM '+(names[key.slice(4)]??key).replace('累计',''):names[key]??key;}
export function FinancialMetricsPanel({instrument}:{instrument:string}){
 const [value,setValue]=useState<View|null>(null),[cutoff,setCutoff]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function read(){setBusy(true);setValue(null);setError('');try{setValue(await request<View>(`/market/financial/${encodeURIComponent(instrument)}/metrics`+(cutoff?`?known_by=${encodeURIComponent(new Date(cutoff).toISOString())}`:'')));}catch(e){setError(String(e));}finally{setBusy(false);}}
 return <details className="status-evidence"><summary>确定性财务指标</summary>
  <p>仅使用已保存的当时可知事实。单季为同口径累计差分，TTM为四个连续单季；负或零同比基期仅显示绝对变化。集团现金流只与集团净利比较，指标不构成买卖评分。</p>
  <label>指标系统已知截至<input type="datetime-local" value={cutoff} disabled={busy} onChange={e=>{setCutoff(e.target.value);setValue(null);}}/></label>
  <button disabled={busy} onClick={()=>void read()}>查询财务指标</button>
  {value&&<p>观察截止{value.known_by} · {value.calculation_version} · 当前观察非历史PIT</p>}
  {value&&!value.periods.length&&<p>该截止尚无保存的财务事实</p>}
  {value?.periods.map(p=><details key={p.report_period}><summary>指标 {p.report_period} · 营收{p.metrics.revenue.value??'未知'} · 归母净利{p.metrics.parent_net_profit.value??'未知'}</summary>
   {Object.entries(p.metrics).map(([key,m])=><details key={key}><summary>{label(key)}：{m.value??'未知'}{m.value!==null&&(m.unit==='PERCENT'?'%':m.unit==='YUAN'?'元':'倍')}</summary>
    <p>公式：{m.formula}</p>{m.reason&&<p>{reasons[m.reason]??m.reason}</p>}{m.absolute_change!==undefined&&<p>绝对变化：{m.absolute_change??'未知'}元</p>}
    {m.source_fact_ids.map(id=>{const source=value.source_versions[id];return source&&<p key={id}>{source.statement} · {source.report_period} · 版本{source.version} · <a href={`/api/data/archives/${source.raw_sha256}`} target="_blank" rel="noreferrer">指标输入原件</a></p>;})}
   </details>)}
  </details>)}
  {error&&<p role="alert">{error}</p>}
 </details>;
}
