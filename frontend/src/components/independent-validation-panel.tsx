import {useEffect, useState} from 'react';
import {request} from '../api';

type Admission = {admitted:boolean; gaps:string[]; excluded_through_date:string;
  feasibility:{status:string; required_blocks:number; mature_block_upper_bounds:Record<string,number>}};
type Plan = {registered_at:string; admission:Admission};
type Result = {validation_verdict:string; evidence_kind:string; final_look_count:number; gates:Record<string,{status:string;reasons:string[]}>;
  maturity:{mature:unknown[];unmatured:unknown[];unscorable:unknown[]}; archive:{sha256:string}};

export function IndependentValidationPanel({freezeId,fingerprint,forwardStatus,samples}: {
  freezeId:string; fingerprint:string; forwardStatus?:string; samples:number}) {
  const path=`/research/complete-freezes/${freezeId}/independent-validation`;
  const [admission,setAdmission]=useState<Admission|null>(null),[plan,setPlan]=useState<Plan|null>(null);
  const [result,setResult]=useState<Result|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  async function optional<T>(suffix:string,missing:string):Promise<T|null>{
    try{return await request<T>(path+suffix);}catch(e){if(String(e).includes(missing))return null;throw e;}
  }
  async function refresh(){
    const [a,p,r]=await Promise.all([request<Admission>(path+'/admission'),
      optional<Plan>('/plan','INDEPENDENT_PREREGISTRATION_NOT_FOUND'),optional<Result>('','INDEPENDENT_RESULT_NOT_FOUND')]);
    setAdmission(a);setPlan(p);setResult(r);
  }
  useEffect(()=>{setAdmission(null);setPlan(null);setResult(null);setError('');void refresh().catch(e=>setError(String(e)));},[freezeId,forwardStatus,samples]);
  async function run(action:()=>Promise<void>){setBusy(true);setError('');try{await action();await refresh();}catch(e){setError(String(e));}finally{setBusy(false);}}
  const feasibility=plan?.admission.feasibility??admission?.feasibility;
  return <section aria-label="独立验证"><h4>独立验证</h4>
    <p>先登记盘后归档，再在第一条预测前预登记验证。仅使用此后保存的预测与成熟结果；终点关闭后生成一次最终结论。</p>
    {feasibility&&<p>{feasibility.status==='INFEASIBLE_FOR_PASS_UNDER_FROZEN_LIMITS'
      ?`当前冻结期限的样本上限不足：需要 ${feasibility.required_blocks} 个有效时间块。可完成证据归档与验证交付，不能据此取得统计 PASS。`
      :'统计支持与抽样假设仍需验证。'}</p>}
    {!plan&&<><button disabled={busy||!admission?.admitted} onClick={()=>void run(async()=>{
      await request(path+'/plan',{expected_complete_protocol_fingerprint:fingerprint,basis:'在第一条预测前预登记；保持冻结门槛与单次终点评估'});
    })}>预登记独立验证</button>{admission?.gaps.length? <p>{admission.gaps.join('、')}</p>:null}</>}
    {plan&&<p>预登记时间：{plan.registered_at} · 不读取封存历史样本</p>}
    {plan&&!result&&<button disabled={busy||forwardStatus!=='CLOSED'} onClick={()=>void run(async()=>{await request(path,{});})}>生成最终验证结论</button>}
    {result&&<><p role="status">{result.evidence_kind} · 结论 {result.validation_verdict} · 最终检验 {result.final_look_count} 次 · 正式能力未授权 · 未经人工独立复核</p>
      <p>成熟可评分 {result.maturity.mature.length} · 未成熟 {result.maturity.unmatured.length} · 无法评分 {result.maturity.unscorable.length}</p>
      <table><caption>冻结协议验证门</caption><thead><tr><th>验证门</th><th>结论</th><th>待解决事项</th></tr></thead>
        <tbody>{Object.entries(result.gates).map(([name,g])=><tr key={name}><td>{name}</td><td>{g.status}</td><td>{g.reasons.join('、')||'本项已核验'}</td></tr>)}</tbody></table>
      <button disabled={busy} onClick={()=>void run(async()=>{const value=await request<{matches_original:boolean}>(path+'/replay',{});setNotice(value.matches_original?'原输入离线重放一致，未增加检验次数':'重放不一致');})}>离线重放验证</button>
      <a href={`/api/data/archives/${result.archive.sha256}`} download>下载完整验证结果</a>
    </>}
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </section>;
}
