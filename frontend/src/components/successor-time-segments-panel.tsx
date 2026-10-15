import {useState} from 'react';
import {request} from '../api';
type Saved={segmentation_id:string;recorded_at:string;G5_status:string;segments:{third:number;first_session:number|null;last_session:number|null;carry_in:{cash_yuan:string|null;boundary_state_known:boolean};economics:{net_return:number|null;maximum_drawdown:number|null};missing_declared_sessions:number[];unknown_nav_sessions:number[]}[]};
const percent=(v:number|null)=>v===null?'未知':(v*100).toFixed(2)+'%';
export function SuccessorTimeSegmentsPanel({stressId}:{stressId:string}){
  const [records,setRecords]=useState<Saved[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const current=records.find(r=>r.segmentation_id===selected),base='/research/successor-cost-stresses/'+stressId+'/time-segments';
  async function action(work:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function create(){const value=await request<Saved>(base,{idempotency_key:crypto.randomUUID(),basis:'同一保存轨迹按时间三段观察；保留前段现金和各lot，不重置资金或拼接收益'});setRecords([...records,value]);setSelected(value.segmentation_id);}
  async function load(){const values=await request<Saved[]>(base);setRecords(values);setSelected(values.at(-1)?.segmentation_id??'');}
  return <details><summary>同一轨迹的时间三段</summary><p>保留边界前现金、各lot与净值。缺失会话和未知边界不前向填充；三个时间视图不是独立样本，也不拼接成绩。</p>
    <button disabled={busy} onClick={()=>void action(create)}>保存原轨迹的时间分段</button><button disabled={busy} onClick={()=>void action(load)}>查看保存的时间分段</button>
    {busy&&<p role="status">正在读取保存轨迹…</p>}
    {!!records.length&&<label>时间分段版本<select disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{records.map(r=><option key={r.segmentation_id} value={r.segmentation_id}>{r.recorded_at}</option>)}</select></label>}
    {current&&<><p>METHOD时间三段 · G5 {current.G5_status} · NOT_GRANTED</p><div className="reference-table"><table><thead><tr><th>时间段</th><th>METHOD会话</th><th>承接现金（元）</th><th>分段收益率</th><th>最大回撤</th><th>未知净值</th></tr></thead><tbody>{current.segments.map(s=><tr key={s.third}><td>{s.third}</td><td>{s.first_session??'不足'}—{s.last_session??'不足'}</td><td>{s.carry_in.cash_yuan??'边界未知'}</td><td>{percent(s.economics.net_return)}</td><td>{percent(s.economics.maximum_drawdown)}</td><td>{s.unknown_nav_sessions.length}</td></tr>)}</tbody></table></div>
      <details><summary>原持仓承接与缺失会话明细</summary><pre>{JSON.stringify(current,null,2)}</pre></details>
      <button disabled={busy} onClick={()=>void action(async()=>{const value=await request<{matches_original:boolean}>('/research/successor-time-segments/'+current.segmentation_id+'/replay',{});setNotice(value.matches_original?'时间分段原工件重放一致':'分段重放不一致');})}>重放保存的时间分段</button>
    </>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
