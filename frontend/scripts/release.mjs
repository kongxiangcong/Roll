import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const hash=path=>createHash('sha256').update(readFileSync(path)).digest('hex');
let commit=null,dirty=null;
try {commit=execFileSync('git',['rev-parse','HEAD']).toString().trim();dirty=!!execFileSync('git',['status','--porcelain','--untracked-files=no']).toString().trim();}catch{}
writeFileSync('dist/release.json',JSON.stringify({source_commit:commit,source_dirty:dirty,built_at:new Date().toISOString(),frontend_lock_sha256:hash('package-lock.json'),index_sha256:hash('dist/index.html')},null,2));
