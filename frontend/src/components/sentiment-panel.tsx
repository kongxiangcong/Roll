import {useState} from 'react';
import {request} from '../api';
type Fact={fact_id:string;title:string;media:string|null;association:string;label:string|null;confidence:number|null;reject_reason:string|null};
type Evaluation={design:{macro_f1:number;negative_recall:number};holdout:{macro_f1:number;negative_recall:number};combined:{macro_f1:number;positive_recall:number;negative_recall:number;non_directional_rejection_rate:number;abstain_coverage:number};passed_frozen_gates:boolean;limitations:string[]};
type Run={run_id:string;status:string;counts:Record<string,number>;reject_counts:Record<string,number>;coverage:number;evidence_kind:string;errors:string[]};
type Value={run:Run;facts:Fact[];counts:Record<string,number>;coverage:number;model:string;license:string;weights_sha256:string;evaluation:Evaluation;reject_layer:string;network_calls:number;capability:string};
const LABEL:Record<string,string>={POSITIVE:'正向',NEGATIVE:'负向'};
const REJECT:Record<string,string>={ABSTAIN_MARKET_INDEX:'市场指数/ETF类',ABSTAIN_FUND_FLOW:'资金流汇总类',ABSTAIN_NO_DIRECTIONAL_CUE:'无方向线索',ABSTAIN_RELEVANCE:'行业/不相关',ABSTAIN_LOW_CONFIDENCE:'低置信度'};
export function SentimentPanel({instrument}:{instrument:string}){
 const [value,setValue]=useState<Value|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const base=`/market/sentiment/${encodeURIComponent(instrument)}`;
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function run(){const response=await request<Run>(base+'/classify',{idempotency_key:crypto.randomUUID(),basis:'用户显式请求保存新闻的受限本地情绪研究分类'});if(response.status==='FAILED')setError(response.errors.join('；'));await query();}
 async function query(){setValue(await request<Value>(base));}
 return <details className="status-evidence"><summary>受限情绪研究</summary>
  <p>本地二分类模型 + 冻结拒判层，只处理已保存新闻标题/摘要；非独立人工标签，未过冻结门槛，不输出中性概率、收益概率或买卖建议。</p>
  <button disabled={busy} onClick={()=>void action(run)}>运行本地情绪分类</button><button disabled={busy} onClick={()=>void action(query)}>查询已保存分类</button>
  {value&&<section aria-label="情绪分类结果">
   <p role="status">覆盖 {Math.round(value.coverage*100)}% · {value.run.evidence_kind==='METHOD_CASE'?'METHOD工程':'实际本地分类'} · 能力 {value.capability} · 网络调用 {value.network_calls}</p>
   <p>模型 {value.model}（{value.license}）· 权重 {value.weights_sha256.slice(0,16)}… · 拒判层 {value.reject_layer}</p>
   <p>评测：合并 macro-F1 {value.evaluation.combined.macro_f1.toFixed(3)}、正向召回 {value.evaluation.combined.positive_recall.toFixed(3)}、负向召回 {value.evaluation.combined.negative_recall.toFixed(3)}、留出集负向召回 {value.evaluation.holdout.negative_recall.toFixed(3)}、中性/不相关拒判 {value.evaluation.combined.non_directional_rejection_rate.toFixed(3)}；冻结门槛{value.evaluation.passed_frozen_gates?'通过':'未通过'}。</p>
   <p>限制：{value.evaluation.limitations.join('；')}</p>
   <p>计数：{Object.entries(value.counts).map(([key,count])=>`${LABEL[key]??REJECT[key]??key} ${count}`).join('；')}</p>
   {value.facts.map(fact=><p key={fact.fact_id}>{fact.title} · {fact.label?LABEL[fact.label]:`拒判：${REJECT[fact.reject_reason??'']??fact.reject_reason}`}{fact.confidence!==null&&` · 置信度 ${fact.confidence.toFixed(3)}`} · 关联 {fact.association}</p>)}
   <p>拒判不是中性；未覆盖条目不进入任何情绪汇总。</p>
  </section>}
  {error&&<p role="alert">{error}</p>}
 </details>;
}
