import {useEffect,useState} from 'react';
import {request} from '../api';

export type BackendSettings={version:number;backend:'CODEX'|'DEEPSEEK';saved_at:string|null;supported_backends?:string[];resave_required?:boolean};
export function BackendPanel(){
  const [settings,setSettings]=useState<BackendSettings|null>(null),[choice,setChoice]=useState('CODEX'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  function populate(value:BackendSettings){setSettings(value);setChoice('CODEX');}
  useEffect(()=>{let current=true;void request<BackendSettings>('/agents/settings').then(value=>{if(current)populate(value);}).catch(e=>{if(current)setError(String(e));});return ()=>{current=false;};},[]);
  async function save(){if(!settings)return;setBusy(true);try{populate(await request<BackendSettings>('/agents/settings',{expected_version:settings.version,backend:choice}));setError('');}catch(e){setError(String(e));void request<BackendSettings>('/agents/settings').then(populate);}finally{setBusy(false);}}
  return <section><h2>取证后端</h2><p>当前新任务使用 Codex；历史任务保留原后端与配置。</p><label>取证后端<select aria-label="取证后端" disabled={busy||!settings} value={choice} onChange={e=>setChoice(e.target.value)}><option value="CODEX">Codex</option></select></label><button disabled={busy||!settings||choice===settings.backend} onClick={()=>void save()}>保存取证后端</button>{error&&<p role="alert">{error}</p>}{settings&&<p className="muted">已保存：{settings.backend==='CODEX'?'Codex':'DeepSeek'} · 设置版本 {settings.version}</p>}{settings?.backend==='DEEPSEEK'&&<p role="status">历史设置为 DeepSeek。请保存为 Codex 后再使用设置后端启动新任务。</p>}</section>;
}
