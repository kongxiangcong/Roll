import {useEffect,useState} from 'react';
import {request} from '../api';
type Component={component:string;status:string;reason?:string;result_fingerprint?:string;details?:unknown};
type Gate={status:string;reasons:string[];details:Record<string,unknown>};
type Manifest={validation_id:string;freeze_id:string;validation_verdict:string;preliminary:boolean;experiment_status:string;review_status:string;capability_status:string;evidence_kind:string;evidence_cutoff:string;complete_protocol_fingerprint:string;gates:Record<string,Gate>;incomplete_checks:string[];unresolved_items:string[];manifest_archive:{sha256:string};input_archive:{sha256:string};monitoring_method_validation:{checks_passed:boolean}};
type Frozen={freeze_id:string;complete_protocol_fingerprint:string};
export function Validation({protocolId}:{protocolId:string}){
  const [freezes,setFreezes]=useState<Frozen[]>([]),[records,setRecords]=useState<Manifest[]>([]),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  async function load(){const f=await request<Frozen[]>(`/research/protocols/${protocolId}/complete-freezes`);setFreezes(f);if(f.length)setRecords(await request<Manifest[]>(`/research/complete-freezes/${f[0].freeze_id}/validations`));}
  useEffect(()=>{void load().catch(e=>setError(String(e)));},[protocolId]);
  async function check(){setBusy(true);setError('');try{await load();const f=(await request<Frozen[]>(`/research/protocols/${protocolId}/complete-freezes`))[0];if(!f)throw Error('请先冻结完整实验并推进连续影子');await request(`/research/complete-freezes/${f.freeze_id}/validations`,{purpose:'DIAGNOSTIC',expected_complete_protocol_fingerprint:f.complete_protocol_fingerprint,basis:'查看当前冻结实验验证结果与证据缺口；非确认性查看'});await load();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function replay(id:string){try{const r=await request<{matches_original:boolean;network_calls:number}>(`/research/validations/${id}/replay`,{});setNotice(`验证重放${r.matches_original?'一致':'不一致'} · 联网 ${r.network_calls} 次`);}catch(e){setError(String(e));}}
  const latest=records.at(-1);
  return <section aria-label="自动验证与门槛证据"><h3>自动验证与门槛证据</h3><p>按冻结协议检查连续净值、概率支持与稳健性。确认性和真实前向材料不足时，保留具体缺口。</p><button disabled={busy} onClick={()=>void check()}>检查当前验证证据</button>
    {!latest&&<p>{freezes.length?'尚未执行自动验证':'尚无完整冻结实验'} · 正式能力未启用</p>}
    {latest&&<><p>初步结论 {latest.validation_verdict} · {latest.evidence_kind} · 截止 {latest.evidence_cutoff}</p><p>实验 {latest.experiment_status} · 审阅 {latest.review_status} · 能力 {latest.capability_status} · 未经人工独立复核</p>
      <table><caption>G1—G7 分项依据</caption><thead><tr><th>门槛</th><th>结果</th><th>依据与缺口</th></tr></thead><tbody>{Object.entries(latest.gates).map(([name,g])=><tr key={name}><td>{name}</td><td>{g.status}</td><td>{g.reasons.join('、')||'冻结输入重放一致'}<details><summary>{name} 证据详情</summary>{name==='G5'?Object.entries(g.details).map(([group,items])=><section key={group}><h4>{group}</h4><ul>{(items as Component[]).map((c,i)=><li key={i}>{c.component} · {c.status} · {c.reason}<details><summary>分项输入、阈值和结果</summary><pre>{JSON.stringify(c,null,2)}</pre></details></li>)}</ul></section>):<pre>{JSON.stringify(g.details,null,2)}</pre>}</details></td></tr>)}</tbody></table>
      <p>监测方法固定输入检查：{latest.monitoring_method_validation.checks_passed?'通过':'未通过'} · METHOD_CASE · 不计真实漂移或 G7</p>
      <details><summary>未完成检查与未决事项</summary><ul>{[...latest.incomplete_checks,...latest.unresolved_items].map((g,i)=><li key={i}>{g}</li>)}</ul></details>
      <p><a href={`/api/data/archives/${latest.manifest_archive.sha256}`} download>验证清单</a> · <a href={`/api/data/archives/${latest.input_archive.sha256}`} download>归档验证输入</a></p><button onClick={()=>void replay(latest.validation_id)}>重放验证清单</button><p>已保存 {records.length} 次诊断；不增加确认性 PASS 判定点。</p></>}
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </section>;
}
