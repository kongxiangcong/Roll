import {useState} from 'react';
import {request} from '../api';

type Reference={role:string;url:string;received_at:string;archive_sha256:string};
type Daily={trade_date:string;close:string;volume_shares:string;amount_yuan:string;successor_use:{provider_daily_allowed:boolean;rejections:string[];revision_state:string}};
type Notice={notice_number:string;period:string;record_date:string;ex_date:string;scheduled_payment_date:string;cash_cny_per_share:string};
type Saved={assessment_id:string;kind:string;created_at:string;evidence_kind:string;references:Reference[];details:{rows?:Daily[];gaps:string[];source_reported_date?:string;fp_phase_original?:string;fp_phase_display?:string;source_current_for_host_date?:boolean;returned_count?:number;source_total?:number;missing_reported_rows?:number;announcement_count?:number;notices?:Notice[];sse_reported_comparison?:{TX_DATE:string;TRADE_VOL:string;TRADE_AMT:string}}};
type Snapshot={snapshot_id:string;created_at:string;evidence_kind:string};
const TITLES:Record<string,string>={DAILY:'日线用途核验',STATUS_PHASE:'盘后阶段显示依据',ACTION_DOCUMENTS:'公司行动公告链'};
const ROLES:Record<string,string>={bao_home:'BaoStock入库时间契约',bao_daily:'BaoStock日K字段契约',bao_factors:'BaoStock因子说明',phase_client:'交易所盘后阶段脚本',phase_snap:'实际行情响应',company_client:'交易所公司客户端',company_page:'交易所公司页',dividend_1:'分红第1页',dividend_2:'分红第2页',send_share_1:'送股查询页',announcements_1:'公告窗口第1页',announcements_2:'公告窗口第2页',interim_notice:'2025半年度实施公告',annual_notice:'2025年度实施公告',annual_report:'2025年报摘要计划及实施报告',sse_daily_comparison:'交易所日统计对照'};
export function SourceAuthorityPanel({instrument}:{instrument:string}){
 const [saved,setSaved]=useState<Saved[]>([]),[snapshots,setSnapshots]=useState<Snapshot[]>([]),[snapshot,setSnapshot]=useState(''),[cutoff,setCutoff]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 if(instrument!=='SSE:600362')return null;
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function load(){setSaved([]);const suffix=cutoff?'&known_by='+encodeURIComponent(cutoff+'+08:00'):'';setSaved(await request<Saved[]>('/market/source-authority?instrument='+instrument+suffix));setSnapshots(await request<Snapshot[]>('/market/source-authority/daily-options'));}
 async function capture(kind:string){const value=await request<Saved>('/market/source-authority',{kind,instrument,idempotency_key:crypto.randomUUID(),snapshot_id:kind==='DAILY'?snapshot:null});setSaved(rows=>[...rows,value]);}
 return <details className="status-evidence"><summary>来源契约与新补充原件</summary>
  <p>只消费已保存原件。供应商日线、交易所阶段显示和发行人公告分别核验；这些观察不授予完整状态、全部义务、历史时点或交易资格。</p>
  <label>补充依据系统已知截至（上海时间）<input type="datetime-local" disabled={busy} value={cutoff} onChange={e=>{setCutoff(e.target.value);setSaved([]);}}/></label>
  <button disabled={busy} onClick={()=>void action(load)}>查询来源契约补充</button>
  <label>保存日线版本<select aria-label="契约核验日线版本" disabled={busy} value={snapshot} onChange={e=>setSnapshot(e.target.value)}><option value="">选择已保存日线</option>{snapshots.map(s=><option key={s.snapshot_id} value={s.snapshot_id}>{s.created_at} · {s.evidence_kind}</option>)}</select></label>
  <button disabled={busy||!snapshot||!!cutoff} onClick={()=>void action(()=>capture('DAILY'))}>核验保存日线用途</button>
  <button disabled={busy||!!cutoff} onClick={()=>void action(()=>capture('STATUS_PHASE'))}>保存阶段显示依据</button>
  <button disabled={busy||!!cutoff} onClick={()=>void action(()=>capture('ACTION_DOCUMENTS'))}>保存公司行动公告链</button>
  {saved.map(s=><section key={s.assessment_id} aria-label={TITLES[s.kind]}><h3>{TITLES[s.kind]}</h3><p>{s.evidence_kind==='METHOD_CASE'?'METHOD工程样例':'实际保存来源观察'} · 系统记录 {s.created_at}</p>
   {s.details.rows?.map((r,i)=><div key={i}><p>{r.trade_date} · 收盘 {r.close}元 · {r.volume_shares}股 · {r.amount_yuan}元</p><p>供应商已完成日原价用途：{r.successor_use.provider_daily_allowed?'成立':'拒绝'}；联合模型输入未准入，历史修订未知。</p>{r.successor_use.rejections.map(g=><p key={g}>{g}</p>)}</div>)}
   {s.details.sse_reported_comparison&&<p>交易所对照日期 {s.details.sse_reported_comparison.TX_DATE}：{s.details.sse_reported_comparison.TRADE_VOL}万股 / {s.details.sse_reported_comparison.TRADE_AMT}万元。与供应商原值分别保留，差异未解决，不择源或平均，不当作独立验证。</p>}
   {s.kind==='STATUS_PHASE'&&<p>来源报告日期 {s.details.source_reported_date} · 盘后阶段 {s.details.fp_phase_display}（原值 {s.details.fp_phase_original}）；{s.details.source_current_for_host_date?'报告日期与记录日相同':'报告日期与记录日不同，不代表记录日当前状态'}。仅首位显示，全状态、生效时点和否定覆盖未知。</p>}
   {s.kind==='ACTION_DOCUMENTS'&&<><p>分红查询 {s.details.returned_count}/{s.details.source_total}条 · 缺行 {s.details.missing_reported_rows}；固定2025-01-01至2026-10-20公告索引 {s.details.announcement_count}条。列表日期范围及全部行动覆盖仍未知。</p>{s.details.notices?.map(n=><p key={n.notice_number}>公告 {n.notice_number} · {n.period} · 每股{n.cash_cny_per_share}元 · 登记{n.record_date} · 除息{n.ex_date} · 约定发放{n.scheduled_payment_date}，实际到账未确认。</p>)}<p>2025末期计划与实施按同一发行人及期间关联；年报报告2025半年度已实施，属于发行人陈述。更正/取消及全部旧义务仍未知。</p></>}
   <details><summary>原件与契约</summary>{s.references.map(r=><p key={r.role}>{ROLES[r.role]??r.role} · 实际接收 {r.received_at} · <a href={'/api/data/archives/'+r.archive_sha256} target="_blank" rel="noreferrer">保存原件</a> · <a href={r.url} target="_blank" rel="noreferrer">公开来源</a></p>)}</details>
   <details><summary>仍缺条件</summary>{s.details.gaps.map(g=><p key={g}>{g}</p>)}</details>
  </section>)}
  {error&&<p role="alert">{error}</p>}
 </details>;
}
