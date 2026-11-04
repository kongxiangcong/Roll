import {useChartSize} from './chart-size';
export type Trade={date:string;signal_date:string;side:string;quantity:number;price:number;fee:number;cash_after:number};
export type NavPoint={date:string;nav:number;cash:number;quantity:number};
export type Simulation={return_pct:number;max_drawdown_pct:number;trades:Trade[];nav:NavPoint[];no_fills?:{date:string;side:string;reason:string}[];open_quantity?:number;final_valuation?:string};
export type ExploratoryResult={version?:string;initial_cash?:number;signal?:string;data_start?:string;start:string;end:string;warmup_rows?:number;excluded_before_action_free_tail?:string[];strategy:Simulation;buy_hold:Simulation;cash_return_pct?:number;assumptions:string[]};
const n=(value:number|undefined)=>value==null?'暂缺':new Intl.NumberFormat('zh-CN',{maximumFractionDigits:4}).format(value);
const side=(value:string)=>value==='BUY'?'买入':value==='SELL'?'卖出':value;
const reasons:Record<string,string>={SUSPENDED_OR_ZERO_VOLUME:'停牌或无成交量',LIMIT_OR_ONE_PRICE_NO_FILL:'涨跌停或单一成交价',SLIPPAGE_PRICE_OUTSIDE_BAR:'滑点后价格超出当日范围',VOLUME_PARTICIPATION_EXCEEDED:'超过成交量参与限制',INSUFFICIENT_CASH:'现金不足'};

export function BacktestDetails({value}:{value:ExploratoryResult}){
 const capital=value.initial_cash;
 const lines=[{name:'固定规则',points:value.strategy.nav??[],cls:'cw-line-strategy'},{name:'买入持有',points:value.buy_hold.nav??[],cls:'cw-line-benchmark'}];
 const points=lines.flatMap(l=>l.points).filter(p=>Number.isFinite(p.nav)&&Number.isFinite(Date.parse(p.date)));
 const dates=points.map(p=>Date.parse(p.date)),first=Math.min(...dates),last=Math.max(...dates);
 const values=capital&&capital>0?points.map(p=>p.nav/capital):[];
 const low=Math.min(...values,1),high=Math.max(...values,1),range=high-low||.01;
 const chart=values.length>1&&last>first;
 const {ref,width,height}=useChartSize(chart,{width:680,height:180});
 const chartWidth=Math.max(40,width-100),chartHeight=Math.max(40,height-50);
 return <> <h3>净值轨迹</h3><p className="cw-small">起始模拟资金归一为1。实线为固定规则，虚线为同费用与约束的买入持有；不是实际账户收益。</p>
 {chart?<figure className="cw-curve-figure"><svg ref={ref} className="cw-nav-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`回测净值：${value.start}至${value.end}，固定规则与买入持有`}><line x1="55" x2={55+chartWidth} y1={20+chartHeight} y2={20+chartHeight} className="cw-chart-axis"/>{[low,high].map((v,i)=><text key={i} x="2" y={i?24:20+chartHeight}>{n(v)}</text>)}{lines.map(l=><polyline key={l.name} className={l.cls} fill="none" points={l.points.filter(p=>Number.isFinite(p.nav)&&Number.isFinite(Date.parse(p.date))).map(p=>`${55+(Date.parse(p.date)-first)/(last-first||1)*chartWidth},${20+chartHeight-(p.nav/capital!-low)/range*chartHeight}`).join(' ')}/>)}<text x="55" y={height-4}>{new Date(first).toISOString().slice(0,10)}</text><text x={Math.max(55,width-82)} y={height-4}>{new Date(last).toISOString().slice(0,10)}</text></svg><figcaption>固定规则 ━　买入持有 ┄　现金收益 {n(value.cash_return_pct)}%</figcaption></figure>:<p>完整净值或起始资金暂缺，不生成替代曲线。</p>}
<details className="cw-history-details"><summary>查看历史表现详情</summary>
 <p>模拟起始资金 {n(capital)}元 · 规则 {value.version??'未提供版本'}</p>
 <p>数据起点 {value.data_start??'暂缺'}；热身 {value.warmup_rows??'暂缺'} 行；实际交易窗口 {value.start} — {value.end}。</p>
 <h3>模拟成交与费用</h3>{value.strategy.trades===undefined?<p>成交记录暂缺。</p>:!value.strategy.trades.length?<p>本次没有成交。</p>:<div className="cw-table-scroll" tabIndex={0} role="region" aria-label="模拟成交明细"><table><thead><tr><th>信号 / 成交日</th><th>方向</th><th>股数</th><th>成交价</th><th>费用（元）</th><th>成交后现金（元）</th></tr></thead><tbody>{(value.strategy.trades??[]).map((t,i)=><tr key={i}><td>{t.signal_date}<br/>{t.date}</td><td>{side(t.side)}</td><td>{n(t.quantity)}</td><td>{n(t.price)}</td><td>{n(t.fee)}</td><td>{n(t.cash_after)}</td></tr>)}</tbody></table></div>}
 <h3>未成交与期末状态</h3>{value.strategy.no_fills===undefined?<p>未成交记录暂缺。</p>:!value.strategy.no_fills.length?<p>没有未成交记录。</p>:<ul>{value.strategy.no_fills.map((t,i)=><li key={i}>{t.date} · {side(t.side)} · {reasons[t.reason]??t.reason}</li>)}</ul>}<p>期末持仓 {n(value.strategy.open_quantity)} 股；{value.strategy.final_valuation==='LAST_CLOSE_MARK_TO_MARKET_NO_FORCED_LIQUIDATION'?'按最后收盘价计值，未强制平仓':value.strategy.final_valuation??'期末计值口径暂缺'}。</p>
 <h3>公司行为与取样范围</h3>{value.excluded_before_action_free_tail===undefined?<p>排除窗口暂缺。</p>:value.excluded_before_action_free_tail.length?<p>因昨收与前日收盘不连续，排除 {value.excluded_before_action_free_tail.length} 行：{value.excluded_before_action_free_tail.join('、')}。只使用之后的连续窗口，不将除权缺口当作交易损失。</p>:<p>本次未因昨收与前日收盘不连续排除记录；不等于公司行为资料完整。</p>}
 <details><summary>每日净值数字</summary><div className="cw-table-scroll" tabIndex={0} role="region" aria-label="每日模拟资产"><table><thead><tr><th>日期</th><th>规则资产（元）</th><th>现金（元）</th><th>股数</th><th>买入持有资产（元）</th></tr></thead><tbody>{(value.strategy.nav??[]).map((p,i)=><tr key={i}><td>{p.date}</td><td>{n(p.nav)}</td><td>{n(p.cash)}</td><td>{n(p.quantity)}</td><td>{n((value.buy_hold.nav??[]).find(b=>b.date===p.date)?.nav)}</td></tr>)}</tbody></table></div></details>
 <h3>费用与模拟条件</h3>{(value.assumptions??[]).map((s,i)=><p key={i}>{s}</p>)}
 </details></>
}
