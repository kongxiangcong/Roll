import {createElement,Fragment,ReactNode} from 'react';

// Render a bounded subset as React text. Source HTML never enters the DOM as markup.
function inline(text:string):ReactNode[]{
 const parts:ReactNode[]=[];const pattern=/\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*/g;let start=0;let m:RegExpExecArray|null;
 while((m=pattern.exec(text))){parts.push(text.slice(start,m.index));if(m[3])parts.push(<strong key={m.index}>{m[3]}</strong>);else if(/^https?:\/\//i.test(m[2])||/^\/api\/company-research\/(materials\/[^/]+\/original|snapshots\/[^/]+|report-charts\/[a-f0-9]{64})$/.test(m[2]))parts.push(<a key={m.index} href={m[2]} target="_blank" rel="noreferrer">{m[1]}</a>);else parts.push(m[1]+' ('+m[2]+')');start=pattern.lastIndex;}
 parts.push(text.slice(start));return parts;
}
export function ReportMarkdown({markdown}:{markdown:string}){
 const lines=markdown.split(/\r?\n/);const blocks:ReactNode[]=[];let i=0;
 const separator=(s:string)=>/^\s*\|[\s|:\-]+\|\s*$/.test(s);
 const cells=(s:string)=>s.trim().replace(/^\|/,'').replace(/\|$/,'').split(/(?<!\\)\|/).map(c=>c.replace(/\\\|/g,'|'));
 while(i<lines.length){const line=lines[i].trim();if(!line){i++;continue;}const key=i;const heading=/^(#{1,6})\s+(.+)$/.exec(line);
  if(heading){blocks.push(createElement('h'+heading[1].length,{key},...inline(heading[2])));i++;continue;}
  if(line.startsWith('|')&&separator(lines[i+1]??'')){
   const head=cells(line);i+=2;const rows:string[][]=[];
   while(i<lines.length){if(!lines[i].trim()){let n=i+1;while(n<lines.length&&!lines[n].trim())n++;if(lines[n]?.trim().startsWith('|')&&!separator(lines[n+1]??'')){i=n;continue;}break;}if(!lines[i].trim().startsWith('|')||separator(lines[i+1]??''))break;rows.push(cells(lines[i++]));}
   blocks.push(<div className="report-table" key={key}><table><thead><tr>{head.map((c,j)=><th key={j}>{inline(c)}</th>)}</tr></thead><tbody>{rows.map((row,j)=><tr key={j}>{head.map((_,k)=><td key={k}>{inline(row[k]??'')}</td>)}</tr>)}</tbody></table></div>);continue;
  }
  const chart=/^!\[([^\]]*)\]\(\/api\/company-research\/report-charts\/([0-9a-f]{64})\)$/.exec(line);
  if(chart){blocks.push(<figure key={key}><img src={'/api/company-research/report-charts/'+chart[2]} alt={chart[1]}/><figcaption>{chart[1]}</figcaption></figure>);i++;continue;}
  blocks.push(<p key={key}>{inline(line)}</p>);i++;
 }
 return <article className="report-markdown" aria-label="报告正文">{blocks.map((b,j)=><Fragment key={j}>{b}</Fragment>)}</article>;
}
