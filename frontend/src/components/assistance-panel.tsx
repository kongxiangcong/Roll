import {useEffect,useState} from 'react';
import {request} from '../api';

type Trade={date:string;signal_date:string;side:string;quantity:number;price:number;fee:number};
type Result={return_pct:number;max_drawdown_pct:number;trades:Trade[];nav:{date:string;nav:number}[];open_quantity:number};
type Run={run_id:string;status:string;phase:string;started_at:string;as_of:string;error?:{code:string};
  sources?:{source_id:string;provider:string;first_date:string;last_date:string;row_count:number;price_unit:string;adjustment:string;received_at:string;sha256:string}[];
  gaps?:{source_id?:string;code:string}[];
  assessment?:{bias:string;summary:string;valid_until:string;basis_as_of:string;evidence:{source_id:string;reason:string}[];counterevidence:string[];change_conditions:string[];limitations:string[]};
  backtest?:{start:string;end:string;data_start:string;signal:string;assumptions:string[];strategy:Result;buy_hold:Result;excluded_before_action_free_tail:string[]};
  reflections?:{id:string;text:string;created_at:string}[]};
const names:Record<string,string>={'sh.600362':'江西铜业','sh.000001':'上证指数','sh.000300':'沪深300','sz.399006':'创业板指'};

export function AssistancePanel(){
  const [loading,setLoading]=useState(true);
  const [history,setHistory]=useState<Run[]>([]),[run,setRun]=useState<Run|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[note,setNote]=useState('');
  const loadHistory=()=>request<Run[]>('/assistance/runs').then(setHistory);
  const select=(id:string)=>request<Run>('/assistance/runs/'+id).then(setRun).catch(e=>setError(String(e)));
  useEffect(()=>{request<Run[]>('/assistance/runs').then(items=>{setHistory(items);return items[0]?select(items[0].run_id):undefined;}).catch(e=>setError(String(e))).finally(()=>setLoading(false));},[]);
  useEffect(()=>{if(run?.status!=='RUNNING')return;const timer=setInterval(()=>{void select(run.run_id);void loadHistory().catch(e=>setError(String(e)));},2000);return()=>clearInterval(timer);},[run?.run_id,run?.status]);
  async function start(){setBusy(true);setError('');try{setRun(await request<Run>('/assistance/runs',{}));await loadHistory();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function save(){if(!run||!note.trim())return;const submittedNote=note;setBusy(true);setError('');try{await request('/assistance/runs/'+run.run_id+'/reflections',{text:submittedNote.trim()});setNote(current=>current===submittedNote?'':current);await select(run.run_id);}catch(e){setError(String(e));}finally{setBusy(false);}}
  const a=run?.assessment,b=run?.backtest;
  return <section aria-label="研究辅助与探索回测" className="panel">
    <div className="assistance-lead"><div><p className="wb-eyebrow">观点 · 反证 · 条件</p><h2>研究辅助与探索回测</h2><p>江西铜业与三大指数，基于真实日线形成辅助观点，比较固定规则的历史表现。</p></div><button className="assistance-start" onClick={start} disabled={loading||busy||run?.status==='RUNNING'}>{busy?'正在提交…':run?.status==='RUNNING'?'研究进行中':'开始研究与回测'}</button></div>
    <p className="assistance-meta">辅助观点不具备正式交易资格；账户未知时只分析证券。结果自动保存，关闭页面不取消任务。</p>
    <details className="assistance-details"><summary>本次研究范围与数据时点</summary><p>18:00后请求当日已收盘数据，此前截至昨日；最多读取120个自然日，实际最新日期见来源覆盖。预计需要数分钟。探索回测采用固定均线规则，不是模型历史预测业绩。</p></details>
    {error&&<p role="alert">{error}</p>}
    {loading&&<p role="status">正在读取已保存的研究…</p>}
    {!loading&&!run&&!busy&&!error&&<div className="assistance-empty"><h3>开始这次研究</h3><p>运行后在这里查看辅助观点、反证和探索回测。尚未取得的结果不会用示例数字填充。</p></div>}
    {history.length>0&&<label>已保存的研究 <select aria-label="已保存的研究" value={run?.run_id??''} onChange={e=>void select(e.target.value)}>{history.map(r=><option key={r.run_id} value={r.run_id}>{r.as_of} · {r.status} · {r.run_id.slice(0,8)}</option>)}</select></label>}
    {run&&<><p className="assistance-status" role="status">状态：{run.status} · 阶段：{run.phase} · 请求截至 {run.as_of}</p>
      {run.error&&<p role="alert">{run.error.code}；已获得的结果保留。</p>}
      {!!run.gaps?.length&&<ul>{run.gaps.map((g,i)=><li key={i}>{g.source_id}：{g.code}</li>)}</ul>}
      {a?<><div className="assistance-verdict"><h3>辅助观点：{a.bias}</h3><p>{a.summary}</p><p>证据截至 {a.basis_as_of}；有效至 {new Date(a.valid_until).toLocaleString('zh-CN')} · {Date.now()>Date.parse(a.valid_until)?'已过期，请更新后再判断':'有效期内，新事实可使观点提前失效'}</p></div>
        <h4>依据</h4><ul>{a.evidence.map((e,i)=><li key={i}>[{names[e.source_id]??e.source_id}] {e.reason}</li>)}</ul>
        <h4>反证</h4><ul>{a.counterevidence.map((s,i)=><li key={i}>{s}</li>)}</ul>
        <h4>改变观点的条件</h4><ul>{a.change_conditions.map((s,i)=><li key={i}>{s}</li>)}</ul>
        <h4>缺口与限制</h4><ul>{a.limitations.map((s,i)=><li key={i}>{s}</li>)}</ul></>:<p>尚无模型辅助观点；不会用固定模板冒充模型运行。</p>}
      {b&&<><h3>探索回测：{b.start} 至 {b.end}</h3><p>5/20日均线，前日信号、次日开盘；模拟初始资金10万元。热身从 {b.data_start} 开始；因公司行为调整排除 {b.excluded_before_action_free_tail.length} 行。结果不是模型历史预测业绩。</p>
        <table><thead><tr><th>方案</th><th>收益</th><th>最大回撤</th><th>成交笔数</th></tr></thead><tbody>{([['固定策略',b.strategy],['买入持有',b.buy_hold]] as const).map(([name,r])=><tr key={name}><td>{name}</td><td>{r.return_pct.toFixed(2)}%</td><td>{r.max_drawdown_pct.toFixed(2)}%</td><td>{r.trades.length}</td></tr>)}<tr><td>现金</td><td>0%</td><td>0%</td><td>0</td></tr></tbody></table>
        <details><summary>费用与成交假设</summary><ul>{b.assumptions.map(s=><li key={s}>{s}</li>)}</ul></details>
        <details><summary>策略成交明细</summary><table><thead><tr><th>日期 / 信号日</th><th>方向</th><th>股数</th><th>价格</th><th>费用</th></tr></thead><tbody>{b.strategy.trades.map((t,i)=><tr key={i}><td>{t.date} / {t.signal_date}</td><td>{t.side}</td><td>{t.quantity}</td><td>{t.price}</td><td>{t.fee}</td></tr>)}</tbody></table></details>
        <details><summary>每日净值</summary><table><thead><tr><th>日期</th><th>策略</th><th>买入持有</th><th>现金</th></tr></thead><tbody>{b.strategy.nav.map((n,i)=><tr key={n.date}><td>{n.date}</td><td>{n.nav}</td><td>{b.buy_hold.nav[i]?.nav}</td><td>100000</td></tr>)}</tbody></table></details></>}
      <details className="assistance-details"><summary>真实来源与覆盖</summary><ul>{run.sources?.map(s=><li key={s.source_id}>{names[s.source_id]??s.source_id}：{s.first_date} 至 {s.last_date}，{s.row_count} 行，{s.adjustment} / {s.price_unit}；{s.provider}，读取于 {new Date(s.received_at).toLocaleString('zh-CN')}<details><summary>原始证据指纹</summary><code style={{overflowWrap:'anywhere'}}>{s.sha256}</code></details></li>)}</ul></details>
      <h3>保存复盘</h3><textarea aria-label="复盘内容" value={note} onChange={e=>setNote(e.target.value)} maxLength={4000} placeholder="记录实际观察、是否采用观点及后续变化；不会写入真实账户。"/><button disabled={busy||!note.trim()} onClick={save}>保存这次复盘</button>
      <ul>{run.reflections?.map(n=><li key={n.id}>{new Date(n.created_at).toLocaleString('zh-CN')}：{n.text}</li>)}</ul>
      <a href={'/api/assistance/runs/'+run.run_id} target="_blank" rel="noreferrer">查看完整保存结果 JSON</a>
    </>}
  </section>;
}

