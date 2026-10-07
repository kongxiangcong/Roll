import {useEffect,useState} from 'react';
import {Account,Draft,Receipt,request} from '../api';
type CsvDraft=Draft&{file:{filename:string;encoding:string;sha256:string};rows:{row:number;raw:string;fields:Record<string,string>}[];warnings:{row:number;reason:unknown}[];receipt:Receipt|null;revision_of:string|null};
const labels:Record<string,string>={cash_balance:'账面现金',positions:'持仓',broker_available:'券商可用资金',permission_profile:'账户交易权限',external_cash_in:'外部投入',external_cash_out:'外部取出',investment_income:'投资收益到账',investment_expenses:'税费与投资支出',pending_income:'待结算应收',pending_expenses:'待结算应付'};
function summary(field:string,value:unknown):string{
  if(value===undefined||value===null)return '未知';
  if(field==='positions')return (value as Account['positions']).map(p=>`${p.instrument} ${p.quantity}股，取得成本${p.acquisition_cost??'未知'}元`).join('；')||'无持仓';
  if(field==='permission_profile')return (value as Account['permission_profile']).map(p=>`${p.market}/${p.board} ${p.status}`).join('；')||'未登记';
  return String(value);
}
function issues(value:unknown):string{
  if(typeof value==='string')return value;
  if(Array.isArray(value))return value.map(issues).join('；');
  const item=value as {row?:number;reason?:unknown};
  return item?.row!==undefined?`${item.row?'第'+item.row+'行':'文件'}：${issues(item.reason)}`:JSON.stringify(value);
}
export function SyncCsv({account,onDone}:{account:Account;onDone:()=>void}){
  const [file,setFile]=useState<File|null>(null),[encoding,setEncoding]=useState('utf-8');
  const [revisionOf,setRevisionOf]=useState<string|null>(null);
  const [draft,setDraft]=useState<CsvDraft|null>(null),[key,setKey]=useState(''),[receipt,setReceipt]=useState<Receipt|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[queried,setQueried]=useState(false);
  function remember(d:CsvDraft,k:string){setDraft(d);setKey(k);setReceipt(d.receipt);sessionStorage.setItem('roll.pending-csv',JSON.stringify({draft_id:d.draft_id,key:k}));}
  useEffect(()=>{const saved=sessionStorage.getItem('roll.pending-csv');if(saved){const s=JSON.parse(saved);request<CsvDraft>(`/account/csv/drafts/${s.draft_id}`).then(d=>remember(d,s.key)).catch(()=>sessionStorage.removeItem('roll.pending-csv'));}},[]);
  async function upload(){if(!file)return;setBusy(true);setError('');try{
    const query=new URLSearchParams({filename:file.name,encoding,expected_account_version:String(account.version)});
    if(revisionOf)query.set('revision_of',revisionOf);
    const response=await fetch(`/api/account/csv/drafts?${query}`,{method:'POST',headers:{'Content-Type':'text/csv'},body:file});
    const value=await response.json();if(!response.ok)throw new Error(issues(value.detail));remember(value,crypto.randomUUID());
  }catch(e){setError(String(e));}finally{setBusy(false);}}
  async function confirm(){setBusy(true);setError('');try{setReceipt(await request<Receipt>('/account/confirm',{draft_id:draft!.draft_id,idempotency_key:key}));sessionStorage.removeItem('roll.pending-csv');}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function revise(){setBusy(true);setError('');try{const current=await request<Account>('/account');remember(await request<CsvDraft>(`/account/csv/drafts/${draft!.draft_id}/revise`,{encoding,expected_account_version:current.version}),crypto.randomUUID());}catch(e){setError(String(e));}finally{setBusy(false);}}
  if(receipt)return <section><h2>CSV整批已确认，回执已保存</h2><p>账户版本 {receipt.account_version} · 回执 {receipt.receipt_id}</p><button onClick={async()=>{try{await request(`/account/receipts/${receipt.receipt_id}`);setQueried(true);}catch(e){setError(String(e));}}}>查询CSV回执</button>{queried&&<p role="status">CSV回执查询成功</p>}<button onClick={onDone}>回到今天</button>{error&&<p role="alert">{error}</p>}</section>;
  return <section><h2>Roll CSV导入</h2><p>初始现金、持仓与权限使用同一基线文件；后续事件按文件行顺序整批确认。上传和预览不会入账。</p><p><a href="/api/account/csv/template" download>下载Roll CSV模板</a> · ROLL-CSV-2 · <a href="/api/account/csv/guide" target="_blank" rel="noreferrer">字段填写说明</a></p>
    <label>文件编码<select value={encoding} onChange={e=>setEncoding(e.target.value)}><option value="utf-8">UTF-8（含BOM）</option><option value="gb18030">GB18030</option></select></label>
    {!draft?<><label>Roll CSV文件<input type="file" accept=".csv,text/csv" onChange={e=>setFile(e.target.files?.[0]??null)}/></label><button className="primary" disabled={busy||!file} onClick={()=>void upload()}>上传并预览整批</button></>:
    <><h3>{draft.status==='READY'?'整批确认前的差异':'原文件已保留，请修订'}</h3><p>{draft.file.filename} · {draft.rows.length}行 · 编码 {draft.file.encoding}</p>{draft.issues?.map((v,i)=><p role="status" key={i}>{issues(v)}</p>)}{draft.warnings.map((v,i)=><p role="status" key={i}>{issues(v)}</p>)}
      {draft.rows.some(r=>r.fields.fee_status==='PROVISIONAL')&&<p>费用暂估，实际费用仍未知</p>}
      {Array.isArray(draft.preview.rights_fee_breakdown_pending?.after)&&draft.preview.rights_fee_breakdown_pending.after.length>0&&<p>配股总支付有依据，费用分拆仍待核；确认后只扣一次总支付。</p>}
      <dl>{Object.entries(draft.preview).filter(([f])=>f in labels).map(([f,v])=><div key={f}><dt>{labels[f]}</dt><dd>之前：{summary(f,v.before)}<br/>之后：{summary(f,v.after)}</dd></div>)}</dl>
      <button className="primary" disabled={busy||draft.status!=='READY'} onClick={()=>void confirm()}>确认整批入账</button><button disabled={busy} onClick={()=>void revise()}>按当前版本重新预览原文件</button><button disabled={busy} onClick={()=>{setRevisionOf(draft.draft_id);setDraft(null);sessionStorage.removeItem('roll.pending-csv');}}>选择修订文件</button>
      <details><summary>查看原行与文件身份</summary><p>SHA-256 {draft.file.sha256}</p><a href={`/api/account/csv/files/${draft.file.sha256}`} download={draft.file.filename}>下载保留的原文件</a><table><thead><tr><th>行</th><th>原始材料</th></tr></thead><tbody>{draft.rows.map(r=><tr key={r.row}><td>{r.row}</td><td><pre>{r.raw}</pre></td></tr>)}</tbody></table></details></>}
    {error&&<p role="alert">{error}</p>}</section>;
}
