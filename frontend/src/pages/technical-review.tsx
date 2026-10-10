import {useEffect,useState} from 'react';
import {request} from '../api';
type Material={material_id:string;material_fingerprint:string};
type Issue={issue_id:string;severity:string;blocking:boolean;description:string;resolution:{basis:string}|null};
type Run={run_id:string;status:string;backend:string;model:string;resolved_model:string|null;retry_of:string|null;started_at:string;finished_at:string|null;error?:{code:string};review_record?:{method:string;issues:Issue[];limitations:string[];blocking_issues_resolved:boolean;host_unresolved_gate_evidence:Record<string,unknown>}};
type Delivery={delivery_status:string;preliminary:boolean;validation_verdict:string;experiment_status:string;review_status:string;capability_status:string;human_review_label:string;gaps:string[]};
export function TechnicalReview({basisId,kind='validations'}:{basisId:string;kind?:'validations'|'risk-evaluations'}){
  const [material,setMaterial]=useState<Material|null>(null),[runs,setRuns]=useState<Run[]>([]),[delivery,setDelivery]=useState<Delivery|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[download,setDownload]=useState('');
  async function inspect(m:Material){setMaterial(m);setRuns(await request<Run[]>(`/research/review-materials/${m.material_id}/reviews`));setDelivery(await request<Delivery>(`/research/review-materials/${m.material_id}/delivery`));}
  useEffect(()=>{let active=true;void request<Material[]>(`/research/${kind}/${basisId}/review-materials`).then(async items=>{if(active&&items.length)await inspect(items[0]);}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[basisId,kind]);
  const latest=runs.at(-1),running=latest?.status==='RUNNING';
  useEffect(()=>{if(!running||!material)return;const timer=setInterval(()=>{void inspect(material).catch(e=>setError(String(e)));},500);return()=>clearInterval(timer);},[running,material?.material_id]);
  async function start(){setBusy(true);setError('');try{const m=material??await request<Material>(`/research/${kind}/${basisId}/review-materials`,{});await request(`/research/review-materials/${m.material_id}/reviews`,{expected_material_fingerprint:m.material_fingerprint,...(latest?{retry_of:latest.run_id}:{})});await inspect(m);}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function cancel(){if(!latest)return;try{await request(`/research/technical-reviews/${latest.run_id}/cancel`,{});}catch(e){setError(String(e));}}
  async function exportPackage(){if(!material)return;setBusy(true);try{const r=await request<{archive:{sha256:string}}>(`/research/review-materials/${material.material_id}/export`,{});setDownload(`/api/data/archives/${r.archive.sha256}`);}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <section aria-label="模型技术审阅与验证交付"><h4>模型技术审阅与验证交付</h4><button disabled={busy||running} onClick={()=>void start()}>{latest?'重试技术审阅':'审阅冻结材料'}</button>{running&&<button onClick={()=>void cancel()}>取消技术审阅</button>}
    {material&&<p>冻结材料 {material.material_fingerprint.slice(0,16)}</p>}
    {latest&&<><p>当前技术审阅 {latest.status}</p><p>{latest.backend} · {latest.resolved_model??latest.model} · {latest.finished_at??latest.started_at}</p>{latest.error&&<p role="alert">{latest.error.code}</p>}
      {latest.review_record&&<><p>阻断问题{latest.review_record.blocking_issues_resolved?'已有核实处理依据':'仍有未解决证据缺口'} · 审阅记录完整与正式资格分别判断。</p><details><summary>复现、异议与审阅局限</summary><p>{latest.review_record.method}</p><ul>{latest.review_record.issues.map(i=><li key={i.issue_id}>{i.severity} · {i.description} · {i.resolution?.basis??'尚无核实处理依据'}</li>)}</ul><ul>{latest.review_record.limitations.map((l,i)=><li key={i}>{l}</li>)}</ul><pre>{JSON.stringify(latest.review_record.host_unresolved_gate_evidence,null,2)}</pre></details></>}
    </>}
    {delivery&&<><p>{delivery.preliminary?'真实验证交付未完成':'验证交付完整'} · 结论 {delivery.validation_verdict} · 实验 {delivery.experiment_status} · 正式能力 {delivery.capability_status}</p><p>{delivery.human_review_label}</p><details><summary>交付缺口与全部审阅尝试</summary><ul>{delivery.gaps.map((g,i)=><li key={i}>{g}</li>)}</ul><ul>{runs.map(r=><li key={r.run_id}>{r.run_id.slice(0,8)} · {r.backend} · {r.status} · {r.retry_of?'关联重试':'首次任务'}</li>)}</ul></details></>}
    {material&&<button disabled={busy||running} onClick={()=>void exportPackage()}>导出验证包</button>}{download&&<a href={download} download>下载验证包</a>}{error&&<p role="alert">{error}</p>}
  </section>;
}
