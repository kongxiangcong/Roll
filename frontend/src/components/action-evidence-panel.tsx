import {useState} from 'react';
import {savedEvidence} from '../saved-evidence';

type Candidate={candidate_id:string;raw_hash:string;record_date_reported:string;dividend_date_reported:string;cash_before_tax_exact:string;cash_per_share_unit:string};
type Assessment={assessment_id:string;normalized_known_at:string;candidates:Candidate[];role_audits:Record<string,{returned_count:number;total_reported:number;missing_reported_rows:number}>};
type Notice={announcement_id:string;record_date:string;scheduled_payment_date:string;pdf_raw_hash:string};
type Audit={audit_id:string;protocol_id:string;known_notice_count:number;resolution_unknown_count:number;notices:Notice[]};
type Evidence={known_by:string;assessments:Assessment[];known_obligation_audits:Audit[];gaps:string[]};

export function ActionEvidencePanel({instrument}:{instrument:string}){
  const [cutoff,setCutoff]=useState(''),[rows,setRows]=useState<Evidence[]>([]),[queried,setQueried]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function inspect(){
    setBusy(true);setError('');setRows([]);setQueried(false);
    try{
      setRows(await savedEvidence<Evidence>(instrument,'action-evidence',cutoff));
      setQueried(true);
    }catch(e){setError(String(e));}finally{setBusy(false);}
  }
  return <details className="status-evidence"><summary>查看公司行动与旧义务</summary>
    <label>行动系统已知截至（留空查询当前）<input type="datetime-local" disabled={busy} value={cutoff} onChange={e=>{setCutoff(e.target.value);setRows([]);setQueried(false);}}/></label>
    <button disabled={busy} onClick={()=>void inspect()}>查询保存的行动依据</button>
    {queried&&!rows.length&&<p>尚无该证券的行动采集计划，覆盖未知。</p>}
    {rows.map((r,i)=><div key={i}><p>已知截至 {r.known_by} · 完整行动及旧义务覆盖未知</p>
      <p className="muted">公告计划、履行及实际到账分别记录；计划付款不改变真实账户。</p>
      {!r.assessments.length&&<p>尚无已解析行动版本</p>}
      {r.assessments.map(a=><details key={a.assessment_id}><summary>行动观察版本 {a.assessment_id.slice(0,8)} · {a.normalized_known_at}</summary>
        <p>{Object.entries(a.role_audits).map(([role,v])=>`${role==='dividend'?'现金分派':'送股'}：返回${v.returned_count}/${v.total_reported}条，缺${v.missing_reported_rows}条`).join('；')} · 查询区间与完整性未证明</p>
        {a.candidates.map(c=><p key={c.candidate_id}>报告登记日 {c.record_date_reported} · 报告分派日 {c.dividend_date_reported} · 上游税前现金字段 {c.cash_before_tax_exact}（单位未验证） · 修订/取消/履行未知 · <a href={`/api/data/archives/${c.raw_hash}`} target="_blank" rel="noreferrer">行动原件</a></p>)}
      </details>)}
      {r.known_obligation_audits.map(a=><details key={a.audit_id}><summary>已知义务审计 · 协议 {a.protocol_id.slice(0,8)} · {a.known_notice_count}份公告</summary>
        <p>履行未知 {a.resolution_unknown_count} 项；不是全部旧义务清单。</p>
        {a.notices.map(n=><p key={n.announcement_id}>公告 {n.announcement_id} · 登记日 {n.record_date} · 计划付款 {n.scheduled_payment_date} · 权益、履行及实际到账未知 · <a href={`/api/data/archives/${n.pdf_raw_hash}`} target="_blank" rel="noreferrer">公告PDF原件</a></p>)}
      </details>)}
      <details><summary>行动来源缺口</summary><ul>{r.gaps.map(g=><li key={g}>{g}</li>)}</ul></details>
    </div>)}
    {error&&<p role="alert">{error}</p>}
  </details>;
}
