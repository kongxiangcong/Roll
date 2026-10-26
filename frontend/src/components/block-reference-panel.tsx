import {useState} from 'react';
import {request} from '../api';
type Case={status:string;calendar_sessions?:number;block_sessions?:number;effective_block_upper_bound?:number;member_calendar_sessions?:number;mean?:number;lower_95?:number|null;upper_95?:number|null;same_indices_max_statistic_error?:number;error?:string};
type Saved={reference_id:string;recorded_at:string;cutoff:string;library:{version:string};cases:Record<string,Case>};
const value=(v:number|null|undefined)=>v==null?'不足':v.toPrecision(8);
const status=(v:string)=>({NUMERICALLY_CONSISTENT:'数值一致',INCOMPLETE_ALIGNED_CALENDAR_SCORES:'日历评分缺失，不能计算区间',INSUFFICIENT_MEMBER_SUPPORT:'条件成员不足',INSUFFICIENT_CALENDAR_SUPPORT:'日历长度不足',INSUFFICIENT_RESAMPLED_MEMBER_SUPPORT:'重采样成员不足',IMPLEMENTATION_DIFFERENCE:'实现差异，需核查',SOURCE_INPUT_ERROR:'输入错误'}[v]??v);
export function BlockReferencePanel({probabilityId}:{probabilityId:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  const current=records.find(r=>r.reference_id===selected),base='/research/probability-references/'+probabilityId+'/block-reference';
  async function run(create:boolean){setBusy(true);setError('');setMessage('');try{
    if(create){const result=await request<Saved>(base,{idempotency_key:crypto.randomUUID(),basis:'用户核对同截止归档日历及成对区块统计；METHOD样本仅验证数值实现'});setRecords([...records,result]);setSelected(result.reference_id);}
    else {const saved=await request<Saved[]>(base);setRecords(saved);setSelected(saved.at(-1)?.reference_id??'');}
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  async function replay(){if(!current)return;setBusy(true);setError('');try{const result=await request<{matches_original:boolean}>('/research/block-references/'+current.reference_id+'/replay',{});setMessage(result.matches_original?'区块原工件校验一致 · 未重新抽样':'工件不一致');}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <details className="block-reference"><summary>区块统计独立库核验</summary>
    <p>完整原窗口日历按日期成对重采样。缺失日期保留为未知，观察到的条件非成员日保留为空组；同日证券一起抽样。</p>
    <p>20/40日非循环移动区块 · 2000次 · seed 1701 · 各端点单侧95%，合起来中央90%。绝对容差1e-12仅用于统计量核验；不同随机实现的区间端点另列。</p>
    <button disabled={busy} onClick={()=>void run(true)}>核对保存样本的区块统计</button><button disabled={busy} onClick={()=>void run(false)}>查看保存的区块核验</button>
    {busy&&<p role="status">正在读取或核验区块统计…</p>}
    {!!records.length&&<label>保存的区块核验<select value={selected} onChange={e=>{setSelected(e.target.value);setMessage('');}}>{records.map(r=><option key={r.reference_id} value={r.reference_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>arch {current.library.version} · NOT_GRANTED</p><p>原截止 {current.cutoff} · 假设与独立有效性未获验证</p>
      {['SOURCE:','METHOD:'].map(prefix=><section key={prefix}><h4>{prefix==='SOURCE:'?'来源样本：完整日历支持':'METHOD：人工可检验样本，仅验证计算'}</h4><div className="reference-table"><table><thead><tr><th>样本与区块</th><th>状态</th><th>日历/有效块上限</th><th>均值</th><th>下/上端点</th></tr></thead><tbody>{Object.entries(current.cases).filter(([key])=>key.startsWith(prefix)).map(([key,c])=><tr key={key}><td>{key}</td><td>{status(c.status)}</td><td>{c.calendar_sessions??'未知'} / {c.effective_block_upper_bound??'未知'}</td><td>{value(c.mean)}</td><td>{value(c.lower_95)} / {value(c.upper_95)}</td></tr>)}</tbody></table></div></section>)}
      <details><summary>冻结方法对照、固定索引核验及随机口径差异</summary><pre>{JSON.stringify(current.cases,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void replay()}>校验保存的区块核验工件</button>
      <p>METHOD数值通过不增加来源的有效独立块，不改变G1—G7或资格。</p>
    </>}{message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
