import {useState} from 'react';
import {request} from '../api';

type Curve={status:string;window:[string,string]|null;coverage:{original_points:number;missing_sessions:string[];unknown_nav_dates:string[]};benchmark_status:string;
  total_return?:number;maximum_drawdown?:number;annualized_return:number|null;monthly_returns:{month:string;value:number;coverage:string}[];benchmarks?:Record<string,Curve>;interval_return_difference?:number};
type Saved={performance_report_id:string;source_revision:number;created_at:string;source_evidence_kind:string;library:{version:string};namespaces:Record<string,Curve>;figures:Record<string,{sha256:string}>;renderer_fingerprint:string};
const percent=(value:number)=>`${(100*value).toFixed(2)}%`;

export function PerformanceReportPanel({freezeId,revision,options}:{freezeId:string;revision:number;options:Record<string,string>}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const current=records.find(r=>r.performance_report_id===selected);
  const base='/research/reports/'+freezeId+'/performance';
  async function load(){setBusy(true);setError('');try{const values=await request<Saved[]>(base);setRecords(values);setSelected(values[0]?.performance_report_id??'');}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function generate(){setBusy(true);setError('');try{
    const saved=await request<Saved>(base,{...options,expected_shadow_revision:revision,idempotency_key:crypto.randomUUID(),basis:'用户按保存研究报告生成只读绩效图；不产生研究或交易资格'});
    setRecords([saved,...records]);setSelected(saved.performance_report_id);
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  return <details className="performance-report"><summary>QuantStats绩效图与离线报告</summary>
    <p>只读保存的收盘净值。首个时点作为区间起点，其前收益未知；缺失不补零、不裁切。真实账户、历史预测和单次条件结果分别保留。</p>
    <button disabled={busy} onClick={()=>void generate()}>生成保存版本的绩效图</button><button disabled={busy} onClick={()=>void load()}>查看保存的绩效图</button>
    {busy&&<p role="status">正在生成或读取保存工件…</p>}
    {!!records.length&&<label>保存图表版本<select disabled={busy} value={selected} onChange={e=>setSelected(e.target.value)}>{records.map(r=><option key={r.performance_report_id} value={r.performance_report_id}>{r.created_at} · 影子版本{r.source_revision} · {r.source_evidence_kind}</option>)}</select></label>}
    {current&&<><p>QuantStats {current.library.version} · {current.source_evidence_kind} · NOT_GRANTED</p>
      {Object.entries(current.namespaces).map(([name,c])=><article key={name}>
        <h4>{name}{c.status==='DESCRIPTIVE_SAVED_CLOSE_INTERVAL'?' · 首个保存收盘至末次收盘':''}</h4>
        {c.status==='DESCRIPTIVE_SAVED_CLOSE_INTERVAL'?<>
          <p>{c.coverage.original_points}个保存时点 · {c.window![0]} 至 {c.window![1]}</p>
          <p>区间收益 {percent(c.total_return!)} · 最大回撤 {percent(c.maximum_drawdown!)}</p>
          <p>{c.annualized_return===null?'年化收益：窗口不足，未计算':`252期年化收益 ${percent(c.annualized_return)}`}</p>
          <p>无风险率假设0，年化252期；不改变冻结研究口径。保存的基准仅作收盘区间描述，不授风险匹配资格。</p>
          {c.benchmarks&&Object.keys(c.benchmarks).length?<div className="reference-table"><table><thead><tr><th>已保存影子基准</th><th>覆盖</th><th>区间收益</th><th>最大回撤</th><th>策略减基准</th></tr></thead><tbody>{Object.entries(c.benchmarks).map(([label,b])=><tr key={label}><td>{label}</td><td>{b.status==='DESCRIPTIVE_SAVED_CLOSE_INTERVAL'?'同一完整收盘窗口':'日期或净值缺失，未对比'}</td><td>{b.total_return===undefined?'不足':percent(b.total_return)}</td><td>{b.maximum_drawdown===undefined?'不足':percent(b.maximum_drawdown)}</td><td>{b.interval_return_difference===undefined?'不足':percent(b.interval_return_difference)}</td></tr>)}</tbody></table></div>:<p>该保存版本未包含匹配连续基准序列，未计算相对收益。</p>}
          {current.figures[name]&&<img alt={name+'累计收益、回撤与观察月度收益'} src={`/api/research/performance-reports/${current.performance_report_id}/figures/${name}`}/>}
          <details><summary>观察月度区间（边界月份不是完整月收益）</summary>{c.monthly_returns.map(m=><p key={m.month}>{m.month} · {percent(m.value)}</p>)}</details>
        </>:<p>{c.status==='NOT_A_CONTINUOUS_RETURN_SERIES'?'没有连续收益序列，未串成策略绩效':`固定窗口不完整或支持不足；缺日${c.coverage.missing_sessions.length}，未知净值${c.coverage.unknown_nav_dates.length}，未计算完整期指标`}</p>}
      </article>)}
      <a href={`/api/research/performance-reports/${current.performance_report_id}/export`} download>导出离线绩效报告</a>
      <details><summary>方法、覆盖与工件指纹</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
    </>}{error&&<p role="alert">{error}</p>}
  </details>;
}
