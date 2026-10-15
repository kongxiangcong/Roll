import {useState} from 'react';
import {request} from '../api';
type Saved={consumer_id:string;purpose:string;revision:number;status:string;gaps:string[];day:string;recorded_at:string};
export function SuccessorInputConsumerPanel({bindingId,methodModel}:{bindingId:string;methodModel:boolean}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[source,setSource]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
  const base='/research/successor-primary-center-bindings/'+bindingId+'/input-consumer',current=records.find(r=>r.consumer_id===selected),purpose=methodModel?'METHOD_VALIDATION':'RESEARCH';
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function load(){const saved=await request<Saved[]>(base);setRecords(saved);setSelected(saved.at(-1)?.consumer_id??'');}
  async function advance(){const saved=await request<Saved[]>(base),revision=Math.max(0,...saved.filter(r=>r.purpose===purpose).map(r=>r.revision));const result=await request<Saved>(base,{purpose,...(methodModel?{method_observation_date:source}:{packet_id:source}),expected_revision:revision,idempotency_key:crypto.randomUUID(),basis:'核对原来源与冻结模型并推进独立输入状态；不启动真实时钟或授资格'});setRecords([...saved,result]);setSelected(result.consumer_id);}
  return <details><summary>来源输入与冻结模型消费者</summary><p>读取原件、计算冻结特征和预测，推进独立影子状态。保留人工轨迹及真实起点；未知来源拒绝，漏日期不补造预测。</p>
    <p>{methodModel?'当前为METHOD模型，仅测试环境允许按原CAL日期验证管线。':'选择已经保存的当天盘后输入包；日线、状态、行动和规则依据不全时保留拒绝原因。'}</p>
    <label>{methodModel?'METHOD输入观察日':'盘后输入包版本'}<input aria-label={methodModel?'METHOD输入观察日':'盘后输入包版本'} type={methodModel?'date':'text'} value={source} disabled={busy} onChange={e=>setSource(e.target.value)}/></label>
    <button disabled={busy||!source} onClick={()=>void action(advance)}>消费来源并推进独立状态</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的输入消费</button>
    {!!records.length&&<label>输入消费版本<select aria-label="输入消费版本" value={selected} disabled={busy} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.consumer_id} value={r.consumer_id}>{r.recorded_at} · {r.revision} · {r.status}</option>)}</select></label>}
    {busy&&<p role="status">正在核验输入及计算冻结模型…</p>}
    {current&&<><p>{current.purpose==='METHOD_VALIDATION'?'METHOD':'REAL来源'}输入消费 · 版本{current.revision} · {current.status} · NOT_GRANTED</p><p>{current.gaps.join(' / ')}</p><details><summary>输入、预测与独立状态</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const result=await request<{matches_original:boolean}>('/research/successor-input-consumers/'+current.consumer_id+'/replay',{});setNotice(result.matches_original?'输入消费原件重放一致':'输入消费重放不一致');})}>重放保存的输入消费</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
