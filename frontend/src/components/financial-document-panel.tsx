import {useState} from 'react';
import {request} from '../api';
type Parse={parse_id:string;status:string;source_sha256:string;first_page:number;last_page:number;parser_version:string;evidence_kind:string;review_required:boolean;errors:string[];warnings?:string[];attempt_artifact?:{sha256:string}|null;artifact:{sha256:string}|null};
type Provenance={page_no:number;bbox?:Record<string,number|string>};
type Cell={text:string;start_row_offset?:number;start_col_offset?:number;row_span?:number;col_span?:number};
type Artifact={confidence:unknown;warnings:string[];document:{texts?:{text:string;prov:Provenance[]}[];tables?:{prov:Provenance[];data:{num_rows:number;num_cols:number;table_cells:Cell[]}}[]}};
export function FinancialDocumentPanel({sha,page}:{sha:string;page:number}){
 const [first,setFirst]=useState(page),[last,setLast]=useState(page),[parses,setParses]=useState<Parse[]>([]),[artifact,setArtifact]=useState<Artifact|null>(null),[selected,setSelected]=useState<Parse|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const base=`/market/financial/documents/${sha}/parses`;
 async function read(){const value=await request<{parses:Parse[]}>(base);setParses(value.parses);return value.parses;}
 async function action(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function parse(){setArtifact(null);setSelected(null);const value=await request<Parse>(base,{first_page:first,last_page:last,idempotency_key:crypto.randomUUID(),basis:'用户显式请求已保存PDF的表格与页码派生，原件及财务事实保持'});await read();if(value.status==='FAILED')setError(value.errors.includes('DOCLING_ISOLATED_RUNTIME_NOT_VERIFIED')?'Docling解析环境尚未就绪，请继续查看原PDF。':value.errors.join('；'));}
 async function show(value:Parse){if(!value.artifact)return;setArtifact(await request<Artifact>('/data/archives/'+value.artifact.sha256));setSelected(value);}
 async function cancel(){const current=await read();const run=current.find(r=>r.status==='RUNNING');if(run)await request('/market/financial/document-parses/'+run.parse_id+'/cancel',{});else setError('当前没有运行中的文档解析');}
 function provenance(values:Provenance[]){return values.map((p,i)=><section key={i}><p><a href={`/api/data/archives/${sha}#page=${p.page_no}`} target="_blank" rel="noreferrer">原PDF第{p.page_no}页</a></p>{p.bbox&&<details><summary>原表边界</summary><pre>{JSON.stringify(p.bbox,null,2)}</pre></details>}</section>);}
 return <details><summary>PDF表格与页码解析</summary>
  <p>解析表与结构化数值并列供核对，均需回看原件；跨页表头、单位、括号负数及脚注不自动合并或改数。失败或未就绪仍可查看原PDF。</p>
  <label>解析起页<input type="number" min={1} value={first} disabled={busy} onChange={e=>{setFirst(Number(e.target.value));setArtifact(null);}}/></label><label>解析末页<input type="number" min={first} max={first+7} value={last} disabled={busy} onChange={e=>{setLast(Number(e.target.value));setArtifact(null);}}/></label>
  <button disabled={busy||first<1||last<first||last-first>=8} onClick={()=>void action(parse)}>解析已存PDF选定页</button><button disabled={busy} onClick={()=>void action(async()=>{await read();})}>查询文档解析记录</button>{busy&&<button onClick={()=>void action(cancel)}>取消文档解析</button>}
  {parses.map(p=><p key={p.parse_id}>{p.evidence_kind==='METHOD_CASE'?'METHOD工程派生':'本地文档派生'} · {p.first_page}—{p.last_page}页 · {p.status}{p.warnings?.length?` · ${p.warnings.join('；').replace('PAGES_WITHOUT_TEXT_OR_TABLE:','选定页未提取到文本或表格：')}`:''}{!p.artifact&&p.attempt_artifact&&<> · <a href={`/api/data/archives/${p.attempt_artifact.sha256}`} target="_blank" rel="noreferrer">解析尝试原件</a></>}{p.artifact&&<> · <button disabled={busy} onClick={()=>void action(()=>show(p))}>查看本次表格与文本</button></>}</p>)}
  {artifact&&selected&&<section aria-label="文档派生内容"><p>Docling {selected.parser_version} · 表格待核 · 置信度{artifact.confidence===null?'未知':JSON.stringify(artifact.confidence)} · <a href={`/api/data/archives/${selected.artifact!.sha256}`} target="_blank" rel="noreferrer">完整派生工件</a></p><p>{artifact.warnings.join('；')}</p>
   {artifact.document.tables?.map((t,i)=><section key={i}><h4>表格{i+1}</h4>{provenance(t.prov)}<div style={{overflowX:'auto',maxWidth:'100%'}}><table><tbody>{Array.from({length:Math.min(t.data.num_rows,200)},(_,row)=><tr key={row}>{t.data.table_cells.filter(c=>(c.start_row_offset??0)===row).sort((a,b)=>(a.start_col_offset??0)-(b.start_col_offset??0)).map((c,j)=><td key={j} rowSpan={c.row_span??1} colSpan={c.col_span??1}>{c.text}</td>)}</tr>)}</tbody></table></div>{t.data.num_rows>200&&<p>显示前200行，完整内容见派生工件；未更改保存的表格。</p>}</section>)}
   {(artifact.document.texts??[]).slice(0,100).map((t,i)=><section key={i}><p>{t.text}</p>{provenance(t.prov)}</section>)}{(artifact.document.texts?.length??0)>100&&<p>显示前100段，完整文本及脚注见派生工件。</p>}
  </section>}
  {error&&<p role="alert">{error}</p>}
 </details>;
}
