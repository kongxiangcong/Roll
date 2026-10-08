import {useEffect,useState} from 'react';
import {request} from '../api';

export type BackendSettings={version:number;backend:'CODEX'|'DEEPSEEK';saved_at:string|null};
export function BackendPanel(){
  const [settings,setSettings]=useState<BackendSettings|null>(null),[choice,setChoice]=useState('CODEX'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  function populate(value:BackendSettings){setSettings(value);setChoice(value.backend);}
  useEffect(()=>{let current=true;void request<BackendSettings>('/agents/settings').then(value=>{if(current)populate(value);}).catch(e=>{if(current)setError(String(e));});return ()=>{current=false;};},[]);
  async function save(){if(!settings)return;setBusy(true);try{populate(await request<BackendSettings>('/agents/settings',{expected_version:settings.version,backend:choice}));setError('');}catch(e){setError(String(e));void request<BackendSettings>('/agents/settings').then(populate);}finally{setBusy(false);}}
  return <section><h2>取证后端</h2><p>后续任务使用此设置；运行中任务保留原后端。</p><label>取证后端<select aria-label="取证后端" disabled={busy||!settings} value={choice} onChange={e=>setChoice(e.target.value)}><option value="CODEX">Codex</option><option value="DEEPSEEK">DeepSeek</option></select></label><button disabled={busy||!settings||choice===settings.backend} onClick={()=>void save()}>保存取证后端</button>{error&&<p role="alert">{error}</p>}{settings&&<p className="muted">已保存：{settings.backend==='CODEX'?'Codex':'DeepSeek'} · 设置版本 {settings.version}</p>}</section>;
}
