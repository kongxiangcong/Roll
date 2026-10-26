import {useState} from 'react';
import {request} from '../api';
type Metric={status:string;value:string|null;reason:string|null;formula:string;source_fact_ids:string[]};
type Period={report_period:string;metrics:Record<string,Metric>};
type Document={sha256:string;source_url:string|null;report_period:string;page:number|null;parses:{parse_id:string;status:string;first_page:number;last_page:number;artifact_sha256:string}[]};
type Observation={observation_id:string;observation_version:number;known_by:string;status:string;freshness_days:number|null;latest_period:string|null;times:Record<string,string|null>;industry:{organization_type:string|null;support:string};analysis:{kind:string;text:string}[];conclusions:{kind:string;text:string}[];trend:Record<string,string>[];gaps:{metric:string;reason:string;description:string}[];documents:Document[];periods:Period[];source_versions:Record<string,unknown>;limitations:string[];revision:{revised:boolean;fact_ids:string[];latest_update:string|null};network_calls:number;system_usable:boolean;capability:string};
type Versions={observation_id:string;version:number;known_by:string;status:string;created_at:string};
type Response={current:Observation;versions:Versions[]};
const SUPPORT:Record<string,string>={GENERAL_SUPPORTED:'一般非金融企业口径',FINANCIAL_OR_SPECIAL_NOT_SUPPORTED:'金融/特殊行业专用口径未支持',UNKNOWN_INDUSTRY_NOT_SUPPORTED:'行业未知，专用口径未支持'};
const STATE:Record<string,string>={FRESH:'新鲜',STALE:'过期',MISSING:'缺失'};
const METRICS:[string,string][]=[['revenue','营业收入'],['revenue_yoy','营收同比'],['parent_net_profit','归母净利润'],['parent_net_profit_yoy','归母同比'],['gross_margin','毛利率%'],['net_margin','净利率%'],['cash_profit_ratio','经营现金/净利润'],['debt_ratio','资产负债率%']];
export function FinancialObservationPanel({instrument,replay=false}:{instrument:string;replay?:boolean}){
 const [cutoff,setCutoff]=useState(''),[value,setValue]=useState<Response|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function inspect(){setBusy(true);setError('');try{const suffix=cutoff?`?known_by=${encodeURIComponent(new Date(cutoff).toISOString())}`:'';setValue(await request<Response>(`/market/financial/${encodeURIComponent(instrument)}/observations${suffix}`));}catch(e){setError(String(e));}finally{setBusy(false);}}
 const current=value?.current;
 return <details className="status-evidence"><summary>财务观察</summary>
  <p>只读取已保存合并口径事实、确定性指标和已核实PDF派生；事实、限制与描述性结论分开，不补数、不排名、不给目标价。</p>
  {replay&&<label>复盘已知截至<input type="datetime-local" value={cutoff} disabled={busy} onChange={e=>{setCutoff(e.target.value);setValue(null);}}/></label>}
  <button disabled={busy} onClick={()=>void inspect()}>查看财务观察</button>
  {current&&<section aria-label="财务观察内容">
   <p role="status">{STATE[current.status]??current.status} · 最新报告期 {current.latest_period??'无'} · {SUPPORT[current.industry.support]??current.industry.support} · 观察版本 {current.observation_version} · 数据截至 {current.known_by}</p>
   {current.status==='MISSING'?<p>该截止时点没有已保存财务事实；不补造默认值。</p>:<>
    <p>披露/更新 {current.times.reported_publication_date??'未知'} / {current.times.reported_update_date??'未知'} · 首次接收 {current.times.first_received_at??'未知'} · 可用 {current.times.available_at??'未知'}{current.revision.revised?' · 含修订版本':''}</p>
    {current.analysis.map((item,index)=><p key={index}>{item.text}</p>)}
    {current.conclusions.map((item,index)=><p key={'c'+index}><strong>{item.text}</strong></p>)}
    <details><summary>指标趋势与缺失</summary>
     <table><thead><tr><th>报告期</th>{METRICS.map(([key,label])=><th key={key}>{label}</th>)}</tr></thead><tbody>
      {current.trend.map(row=><tr key={row.report_period}><td>{row.report_period}</td>{METRICS.map(([key])=><td key={key}>{row[key]??'未知'}</td>)}</tr>)}
     </tbody></table>
     {!!current.gaps.length&&<ul>{current.gaps.map((gap,index)=><li key={index}>{gap.metric}：{gap.description}</li>)}</ul>}
     <p>未知或不可比不补零；跨报告期只按同口径比较。</p>
    </details>
    <details><summary>原件与解析依据</summary>
     {current.documents.map(doc=><p key={doc.sha256}><a href={`/api/data/archives/${doc.sha256}`} target="_blank" rel="noreferrer">PDF原件 {doc.report_period}{doc.page?` 第${doc.page}页`:''}</a>{doc.parses.length?<>{' · '}{doc.parses.map(p=><a key={p.parse_id} href={`/api/data/archives/${p.artifact_sha256}`} target="_blank" rel="noreferrer">派生 {p.status} {p.first_page}—{p.last_page}页</a>)}</>:<>{' · '}尚无表格/页码派生，仅原件</>}</p>)}
     <p>结构化事实与PDF并列核对；解析不自动改写财务事实。</p>
    </details>
    <details><summary>观察版本、限制与依据</summary>
     <ul>{value?.versions.map(v=><li key={v.observation_id}>{v.version} · {v.known_by} · {STATE[v.status]??v.status} · {v.created_at}</li>)}</ul>
     <ul>{current.limitations.map((item,index)=><li key={index}>{item}</li>)}</ul>
     <p>来源事实 {Object.keys(current.source_versions).length} 个 · 网络调用 {current.network_calls} · 系统可用 {current.system_usable?'是':'否'} · 能力 {current.capability}</p>
    </details>
   </>}
  </section>}
  {error&&<p role="alert">{error}</p>}
 </details>;
}
export function FinancialObservationReview(){
 const [instrument,setInstrument]=useState('SSE:600362');
 return <section><h2>财务观察复盘</h2><label>复盘证券<input value={instrument} disabled={false} onChange={e=>setInstrument(e.target.value)}/></label><FinancialObservationPanel key={instrument} instrument={instrument} replay/></section>;
}
