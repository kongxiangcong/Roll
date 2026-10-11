import {useEffect,useState} from 'react';
import {request} from '../api';
type Channel={version:number;enabled:boolean;server:string;topic_configured:boolean;app_base_url:string;auth_configured:boolean};
const errors:Record<string,string>={CHANNEL_ORIGIN_CHANGE_REQUIRES_NEW_OR_CLEARED_AUTH:'更换服务器须填写新认证或明确清除原认证。',CHANNEL_CONFIG_VERSION_CONFLICT:'配置已被另一窗口改变，请刷新后重试。',CHANNEL_CONFIG_INCOMPLETE:'启用前请填写服务器、主题和应用地址。',CHANNEL_URL_INVALID:'地址须为完整HTTP/HTTPS地址，不得含认证、查询或片段。',CHANNEL_CONFIG_SAVE_FAILED:'本机配置保存失败，请核对文件访问权限。'};
export function NotificationChannelPanel(){
  const [config,setConfig]=useState<Channel|null>(null),[server,setServer]=useState(''),[topic,setTopic]=useState(''),[base,setBase]=useState(''),[token,setToken]=useState(''),[clear,setClear]=useState(false),[enabled,setEnabled]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  function populate(c:Channel){setConfig(c);setServer(c.server);setBase(c.app_base_url);setEnabled(c.enabled);setTopic('');setToken('');setClear(false);}
  useEffect(()=>{void request<Channel>('/notification-channel').then(populate).catch(()=>setError('通知渠道暂时无法读取。'));},[]);
  async function save(){
    if(!config)return;setBusy(true);setError('');
    try{const c=await request<Channel>('/notification-channel',{expected_version:config.version,enabled,
      ...(server.trim()?{server:server.trim()}:{}),...(topic.trim()?{topic:topic.trim()}:{}),...(base.trim()?{app_base_url:base.trim()}:{}),
      ...(token?{token}:{}),clear_auth:clear});populate(c);}catch(e){const code=e instanceof Error?e.message:'';setError(errors[code]??'配置保存失败，请核对填写内容。认证不会回显。');}finally{setToken('');setBusy(false);}
  }
  return <section aria-label="通知渠道"><h2>通知渠道</h2><p>默认关闭；保存配置不会发送验收消息。</p><p>使用一个ntfy自用目标。启用后后台发送当前有效提醒，真实接入和终端链接验收须配置后另行完成。</p>
    {error&&<p role="alert">{error}</p>}
    {config&&<form onSubmit={e=>{e.preventDefault();void save();}}><fieldset disabled={busy}>
      <label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>启用外部渠道</label>
      <label>服务器地址<input value={server} onChange={e=>setServer(e.target.value)} placeholder="https://ntfy.sh"/></label>
      <label>主题<input value={topic} onChange={e=>setTopic(e.target.value)} maxLength={64} placeholder={config.topic_configured?'主题已配置，留空保留':'仅字母、数字、短横线或下划线'}/></label>
      <label>应用地址<input value={base} onChange={e=>setBase(e.target.value)} placeholder="自用终端能够访问的Roll地址"/></label>
      <p>{config.auth_configured?'认证已配置':'未配置认证'}</p><label>认证令牌<input type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)}/></label>
      <p className="muted">同一服务器留空保留认证；换服务器须新认证或明确清除。认证仅存本机私有文件，不进入备份或报告。</p>
      <label><input type="checkbox" checked={clear} onChange={e=>setClear(e.target.checked)}/>清除已保存认证</label>
      <button type="submit" disabled={busy}>保存渠道配置</button>
    </fieldset></form>}
  </section>;
}
