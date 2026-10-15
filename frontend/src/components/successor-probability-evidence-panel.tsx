import {useState} from 'react';
import {request} from '../api';
type Reference={reference_id:string;recorded_at:string};
type Binding={binding_id:string;recorded_at:string;G3_status:string;cutoff:string;phases:Record<string,{mature_unique:number;selected_mature:number;missing_calendar_sessions:number;gaps:string[]}>};
export function SuccessorProbabilityEvidencePanel({freezeId,parentFreezeId,fingerprint}:{freezeId:string;parentFreezeId:string;fingerprint:string}){
  const [probabilities,setProbabilities]=useState<Reference[]>([]),[blocks,setBlocks]=useState<Reference[]>([]),[probability,setProbability]=useState(''),[block,setBlock]=useState('');
  const [records,setRecords]=useState<Binding[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const base='/research/policy-successor-freezes/'+freezeId+'/probability-evidence',current=records.find(r=>r.binding_id===selected);
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function choose(id:string){setProbability(id);setBlocks([]);setBlock('');if(!id)return;const values=await request<Reference[]>('/research/probability-references/'+id+'/block-reference');setBlocks(values);setBlock(values.at(-1)?.reference_id??'');}
  async function sources(){const values=await request<Reference[]>('/research/complete-freezes/'+parentFreezeId+'/probability-reference');setProbabilities(values);await choose(values.at(-1)?.reference_id??'');}
  async function bind(){const saved=await request<Binding>(base,{expected_complete_protocol_fingerprint:fingerprint,probability_reference_id:probability,block_reference_id:block,idempotency_key:crypto.randomUUID(),basis:'绑定同一前驱模型和原截止的保存概率/区块参照；CAL复用不是独立验证'});setRecords([...records,saved]);setSelected(saved.binding_id);}
  async function load(){const saved=await request<Binding[]>(base);setRecords(saved);setSelected(saved.at(-1)?.binding_id??'');}
  return <details><summary>后继概率证据绑定</summary><p>只关联同一前驱冻结、模型和截止的保存参照。CAL拟合窗口复用，来源不足与METHOD算术例证分开；不会授予独立校准有效性。</p>
    <button disabled={busy} onClick={()=>void action(sources)}>读取可关联的概率与区块参照</button>
    {!!probabilities.length&&<><label>已保存概率参照<select disabled={busy} value={probability} onChange={e=>void action(()=>choose(e.target.value))}>{probabilities.map(r=><option key={r.reference_id} value={r.reference_id}>{r.recorded_at}</option>)}</select></label><label>对应区块参照<select disabled={busy} value={block} onChange={e=>setBlock(e.target.value)}><option value="">选择同来源区块参照</option>{blocks.map(r=><option key={r.reference_id} value={r.reference_id}>{r.recorded_at}</option>)}</select></label></>}
    {!blocks.length&&<p>先在同一研究报告保存概率核验及其区块核验，再读取关联来源。</p>}
    <button disabled={busy||!probability||!block} onClick={()=>void action(bind)}>保存后继概率证据绑定</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的概率绑定</button>
    {busy&&<p role="status">正在核对原件绑定…</p>}
    {!!records.length&&<label>保存的后继概率绑定<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.binding_id} value={r.binding_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>G3 {current.G3_status} · 独立校准未验证 · NOT_GRANTED</p><p>原标签可知截至 {current.cutoff}</p>
      {Object.entries(current.phases).map(([name,p])=><article key={name}><h4>{name==='BEFORE_CALIBRATION'?'校准前支持':'校准后支持'}</h4><p>成熟唯一 {p.mature_unique} · 已选成熟 {p.selected_mature} · 缺失或未知日历 {p.missing_calendar_sessions}</p><details><summary>成熟支持与验证缺口</summary><pre>{JSON.stringify(p,null,2)}</pre></details></article>)}
      <button disabled={busy} onClick={()=>void action(async()=>{const saved=await request<{matches_original:boolean}>('/research/successor-probability-evidence/'+current.binding_id+'/replay',{});setNotice(saved.matches_original?'概率绑定原工件校验一致 · 未重新评分':'概率绑定工件不一致');})}>校验后继概率绑定工件</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
