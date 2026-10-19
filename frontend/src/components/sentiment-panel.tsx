import {useState} from 'react';
import {request} from '../api';
type Fact={fact_id:string;title:string;media:string|null;association:string;label:string|null;confidence:number|null;reject_reason:string|null;text_sha256?:string;source_input_sha256?:string;model_input_text?:string;model_input_version?:string;event_id?:string};
type Primary={binary_macro_f1:number;three_class_macro_f1:number;total_rejection:number;irrelevant_rejection:number;per_class:Record<string,{support:number;recall:number;event_groups:number}>;confusion:Record<string,number>};
type Evaluation={metric_scope?:string;holdout?:{macro_f1:number;negative_recall:number};combined?:{macro_f1:number;positive_recall:number;negative_recall:number;non_directional_rejection_rate:number;abstain_coverage:number};primary?:Primary;primary_p95_seconds?:number;passed_frozen_gates:boolean;limitations:string[]};
type Run={run_id:string;status:string;counts:Record<string,number>;reject_counts:Record<string,number>;coverage:number;evidence_kind:string;errors:string[]};
type Value={run:Run;facts:Fact[];counts:Record<string,number>;coverage:number;model:string;license:string;weights_sha256:string;evaluation:Evaluation;reject_layer:string;network_calls:number;capability:string;labels_supported?:string[]};
const LABEL:Record<string,string>={POSITIVE:'正向',NEGATIVE:'负向',NEUTRAL:'中性'};
const REJECT:Record<string,string>={ABSTAIN_MARKET_INDEX:'市场指数/ETF类',ABSTAIN_FUND_FLOW:'资金流汇总类',ABSTAIN_NO_DIRECTIONAL_CUE:'无方向线索',ABSTAIN_RELEVANCE:'行业/不相关',ABSTAIN_NO_COMPANY_OBJECT:'无明确公司对象',ABSTAIN_IDENTITY_CONFLICT:'证券身份冲突',ABSTAIN_LOW_CONFIDENCE:'低置信度'};
export function SentimentPanel({instrument}:{instrument:string}){
 const [value,setValue]=useState<Value|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const base=`/market/sentiment/${encodeURIComponent(instrument)}`;
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function run(profile='legacy'){const response=await request<Run>(base+'/classify',{idempotency_key:crypto.randomUUID(),basis:'用户显式请求保存新闻的受限本地情绪研究分类',profile});if(response.status==='FAILED'){setError(response.errors.join('；'));return;}await query();}
 async function query(){setValue(await request<Value>(base));}
 return <details className="status-evidence"><summary>受限情绪研究</summary>
  <p>仅处理已保存新闻。原二分类模型未过冻结门槛；中文 FinBERT 研究候选支持正向、负向、中性，采用冻结对象关联与拒判规则。两者均为受限研究，不输出收益概率或买卖建议。</p>
  <button disabled={busy} onClick={()=>void action(()=>run())}>运行本地情绪分类</button>{instrument==='SSE:600362'&&<button disabled={busy} onClick={()=>void action(()=>run('finbert-adaptation-01'))}>运行中文FinBERT研究候选</button>}<button disabled={busy} onClick={()=>void action(query)}>查询已保存分类</button>
  {value&&<section aria-label="情绪分类结果">
   <p role="status">覆盖 {Math.round(value.coverage*100)}% · {value.run.evidence_kind==='METHOD_CASE'?'METHOD工程':'实际本地分类'} · 能力 {value.capability} · 网络调用 {value.network_calls}</p>
   <p>模型 {value.model}（{value.license}）· 权重 {value.weights_sha256.slice(0,16)}… · 拒判层 {value.reject_layer}</p>
   <p>实际支持标签：{(value.labels_supported??['POSITIVE','NEGATIVE']).map(label=>LABEL[label]).join('、')}；拒判独立记录。</p>
   <p>{value.evaluation.metric_scope==='ALL_LABELED_ROWS_ABSTENTION_IS_FALSE_NEGATIVE'?'评测口径：拒判计入该真实类别的漏判，跨类误判计入假阳性。':'旧评测口径：拒判未计入召回分母，不作验收依据。'}</p>
   {value.evaluation.primary?<>
    <p>冻结主留出集120条：二类 macro-F1 {value.evaluation.primary.binary_macro_f1.toFixed(3)}、三类 macro-F1 {value.evaluation.primary.three_class_macro_f1.toFixed(3)}；总拒判 {(value.evaluation.primary.total_rejection*100).toFixed(1)}%；CPU p95 {value.evaluation.primary_p95_seconds?.toFixed(3)} 秒；冻结门槛{value.evaluation.passed_frozen_gates?'通过':'未通过'}。</p>
    <p>该单公司、非独立标注的有限挑战集通过，不代表通用分类有效性或自然新闻流覆盖率。</p>
    {Object.entries(value.evaluation.primary.per_class).map(([label,metrics])=><p key={label}>评测 {LABEL[label]??'不相关'}：支持 {metrics.support} 条 / {metrics.event_groups} 事件；{label==='IRRELEVANT'?`拒判率 ${(value.evaluation.primary!.irrelevant_rejection*100).toFixed(1)}%`:`召回 ${metrics.recall.toFixed(3)}`}</p>)}
    <details><summary>查看主留出混淆计数</summary>{Object.entries(value.evaluation.primary.confusion).map(([cell,count])=><p key={cell}>{cell}：{count}</p>)}</details>
   </>:value.evaluation.combined&&<p>评测：合并二类 macro-F1 {value.evaluation.combined.macro_f1.toFixed(3)}、正向召回 {value.evaluation.combined.positive_recall.toFixed(3)}、负向召回 {value.evaluation.combined.negative_recall.toFixed(3)}、留出集负向召回 {value.evaluation.holdout?.negative_recall.toFixed(3)}、中性/不相关拒判 {value.evaluation.combined.non_directional_rejection_rate.toFixed(3)}；冻结门槛{value.evaluation.passed_frozen_gates?'通过':'未通过'}。</p>}
   {value.evaluation.primary?<><p>限制：标签由代理依据归档标题/摘要标注，缺少独立人工验证；仅覆盖江西铜业，基础模型原训练数据的交叉情况未知。更正、否定或复杂多对象语句仍可能存在覆盖缺口。研究分类不授予任何交易资格。</p><details><summary>查看评测限制原文</summary><p>{value.evaluation.limitations.join('；')}</p></details></>:<p>限制：{value.evaluation.limitations.join('；')}</p>}
   <p>计数：{Object.entries(value.counts).map(([key,count])=>`${LABEL[key]??REJECT[key]??key} ${count}`).join('；')}</p>
   {value.facts.map(fact=><div key={fact.fact_id}><p>{fact.title} · {fact.label?LABEL[fact.label]:`拒判：${REJECT[fact.reject_reason??'']??fact.reject_reason}`}{fact.confidence!==null&&` · 文本情绪置信度 ${fact.confidence.toFixed(3)}`} · 关联 {fact.association}</p>{fact.model_input_text!==undefined&&fact.model_input_text!==null&&<details><summary>查看对象输入与版本</summary><p>{fact.model_input_text||'无明确公司断言，未调用模型'}</p><p>事件 {fact.event_id} · 输入版本 {fact.model_input_version} · 输入摘要 {fact.text_sha256} · 来源摘要 {fact.source_input_sha256}</p></details>}</div>)}
   <p>拒判不是中性；未覆盖条目不进入任何情绪汇总。</p>
  </section>}
  {error&&<p role="alert">{error}</p>}
 </details>;
}
