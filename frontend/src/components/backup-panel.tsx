import {useEffect,useState} from 'react';
import {request} from '../api';
type Backup={backup_id:string;completed_at:string;attachment_count:number;restore_point:{account_version:number;event_count:number;account_confirmed_at:string|null}};
type State={latest_backup_known_corrupt:boolean;latest_success:Backup|null;uncovered_changes:boolean;last_check:{error:{code:string}|null}|null;pending_restore:{state:string;backup_id:string}|null;recovery:{state:string;locked_at?:string;restore_point?:{account_version:number};analysis_gap?:string}};
export function BackupPanel(){
  const [state,setState]=useState<State|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[file,setFile]=useState<File|null>(null),[notice,setNotice]=useState('');
  async function refresh(){try{setState(await request<State>('/runtime/backups/status'));setError('');}catch(e){setError(String(e));}}
  useEffect(()=>{void refresh();},[]);
  async function backup(){setBusy(true);try{await request('/runtime/backups',{method:'POST'});setNotice('备份已完成，数据库与引用附件已校验。');await refresh();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function restore(){if(!file)return;setBusy(true);try{const response=await fetch('/api/runtime/restores',{method:'POST',headers:{'Content-Type':'application/zip'},body:file});const data=await response.json();if(!response.ok)throw new Error(data.detail?.code??'恢复包未通过校验');setNotice('恢复包已校验并待重启。当前账户尚未替换，请关闭所有本机服务后重新启动。');await refresh();}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <section><h2>备份与恢复</h2><p>自动备份只在程序实际运行且有变化时进行；停机期间没有新备份，恢复以最近成功备份为界。</p>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {!state?<p>正在读取备份…</p>:<>
      <p>{state.latest_success?`最近成功备份：${new Date(state.latest_success.completed_at).toLocaleString('zh-CN')} · 账户版本 ${state.latest_success.restore_point.account_version} · ${state.latest_success.restore_point.event_count} 项事件 · ${state.latest_success.attachment_count} 个附件`:'尚无成功备份'}</p>
      {state.latest_backup_known_corrupt&&<p role="alert">最近备份的导出校验发现损坏，不能作为可恢复材料；请重新完整备份。</p>}<p>{state.uncovered_changes?'有尚未覆盖的持久化变化':'当前持久化事实已被最近备份覆盖'}</p>
      {state.last_check?.error&&<p role="alert">最近备份失败：{state.last_check.error.code}；此前成功备份仍为恢复边界。</p>}
      <button disabled={busy} onClick={()=>void backup()}>现在完整备份</button>{state.latest_success&&<a href={`/api/runtime/backups/${state.latest_success.backup_id}/export`} download>导出已校验恢复包</a>} <button disabled={busy} onClick={()=>void refresh()}>刷新备份状态</button>
      <p className="muted">恢复包保留原始账户和材料内容，供原值重建；下载后请保存在自己的受限目录。</p>
      <details><summary>恢复已有备份</summary><p>先校验数据库、原件清单、哈希、事件和账户投影。通过后排队等待重启，运行中的账户不被覆盖。</p>
        <label>恢复包文件<input type="file" accept=".zip,application/zip" onChange={e=>setFile(e.target.files?.[0]??null)}/></label><button disabled={busy||!file} onClick={()=>void restore()}>校验并排队恢复</button>
      </details>
      {state.pending_restore&&<p>恢复状态：待重启；所有本机服务停止后才应用恢复点。</p>}
      {state.recovery.state==='RECOVERY_LOCK'&&<p role="status">恢复锁生效：恢复的账户版本 {state.recovery.restore_point?.account_version}。旧授权仅作为历史；当前账户、部署、资金用途和可能遗漏的撤回仍须核实。可以观察与同步账户，正式动作及旧通知保持关闭。未运行期间的分析覆盖不补造。</p>}
    </>}
  </section>;
}
