import {useState} from 'react';
import {request} from '../api';

type DailyFact={trade_date:string;adjustment:string;completion_state:string;source_volume_unit:string;source_amount_unit:string;
  volume_shares:string;amount_yuan:string;open:string;high:string;low:string;close:string;model_daily_input_allowed:boolean;published_at:string|null;received_at:string};
type Receipt={receipt_id:string;host_date:string;status:string;evidence_kind:string;gaps:string[];fact:DailyFact|null;
  response:{archive:{sha256:string;received_at:string};original_complete:boolean}};
type SourceGaps={instrument:string;forward_admissible:boolean;gaps:string[];source_gaps:string[];dated_daily_receipts:Receipt[]};

export function DailyEvidencePanel({planId,instrument,disabled=false}:{planId:string;instrument:string;disabled?:boolean}){
  const [value,setValue]=useState<SourceGaps|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function inspect(){
    setBusy(true);setError('');setValue(null);
    try{setValue(await request<SourceGaps>(`/research/collections/${planId}/source-gaps`));}
    catch(e){setError(String(e));}finally{setBusy(false);}
  }
  return <div className="daily-evidence">
    <p>{instrument}</p><button disabled={busy||disabled} onClick={()=>void inspect()}>查看日线与来源缺口</button>
    {error&&<p role="alert">{error}</p>}
    {value&&<>
      <p role="status">{value.forward_admissible?'当前前向输入已准入':'前向输入尚未准入'}</p>
      <p className="muted">查询已保存的原件与收据。指定日期统计不代表完整交易会话；文本和数据用途不授予正式能力。</p>
      {!value.dated_daily_receipts.length&&<p>尚无指定日期日线收据</p>}
      {value.dated_daily_receipts.map(r=><details key={r.receipt_id}><summary>{r.fact?.trade_date??r.host_date} · {r.fact?'已保存日线统计':'采集失败'} · {r.evidence_kind==='METHOD_CASE'?'工程样本':'实际来源评估'}</summary>
        {r.fact&&<>
          <p>开 {r.fact.open} · 高 {r.fact.high} · 低 {r.fact.low} · 收 {r.fact.close} 元</p>
          <p>成交 {r.fact.volume_shares} 股 · 金额 {r.fact.amount_yuan} 元</p>
          <p>上游单位：{r.fact.source_volume_unit} / {r.fact.source_amount_unit}；调整口径：{r.fact.adjustment}；会话：{r.fact.completion_state}</p>
          <p>模型日线用途：{r.fact.model_daily_input_allowed?'允许':'未获准'} · 披露时间 {r.fact.published_at??'未知'} · 实际接收 {r.fact.received_at}</p>
        </>}
        <p><a href={`/api/data/archives/${r.response.archive.sha256}`} target="_blank" rel="noreferrer">查看已保存原响应</a> · {r.response.original_complete?'响应接收完整':'响应不完整'}</p>
        <p className="muted">收据 {r.receipt_id}</p>
        {!!r.gaps.length&&<ul>{r.gaps.map(g=><li key={g}>{g}</li>)}</ul>}
      </details>)}
      {!!(value.gaps.length+value.source_gaps.length)&&<details open><summary>用途与来源缺口</summary><ul>{[...new Set([...value.gaps,...value.source_gaps])].map(g=><li key={g}>{g}</li>)}</ul></details>}
    </>}
  </div>;
}
