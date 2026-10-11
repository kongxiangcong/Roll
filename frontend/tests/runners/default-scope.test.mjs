import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
import test from 'node:test';

test('default Playwright collection excludes historical positive DS and includes current scope',()=>{
  const result=spawnSync(process.execPath,[resolve('node_modules/@playwright/test/cli.js'),'test','--list','--config=playwright.default.config.ts'],{encoding:'utf8'});
  assert.equal(result.status,0,result.stdout+result.stderr);
  assert.doesNotMatch(result.stdout,/backend-switch\.spec\.ts|deepseek-evidence\.spec\.ts/);
  assert.match(result.stdout,/codex-only-scope\.spec\.ts/);
  for(const current of ['baseline','codex-evidence','reconcile','market-overflow'])assert.match(result.stdout,new RegExp(current+'\\.spec\\.ts'));
});

test('canonical runner exposes the same current files and refuses historical positive DS',()=>{
  const listed=spawnSync(process.execPath,['scripts/test-e2e.mjs','--list'],{encoding:'utf8'});
  assert.equal(listed.status,0,listed.stdout+listed.stderr);
  const expected=['baseline','cash-equity','codex-evidence','codex-only-scope','csv','fills','funding','market','market-overflow','reconcile','valuation'];
  assert.deepEqual(JSON.parse(listed.stdout),expected);
  const config=spawnSync(process.execPath,[resolve('node_modules/@playwright/test/cli.js'),'test','--list','--config=playwright.default.config.ts'],{encoding:'utf8'});
  assert.equal(config.status,0,config.stdout+config.stderr);
  const collected=[...new Set([...config.stdout.matchAll(/([\w-]+)\.spec\.ts/g)].map(match=>match[1]))].sort();
  assert.deepEqual(collected,[...expected].sort());
  const refused=spawnSync(process.execPath,['scripts/test-e2e.mjs','--file=deepseek-evidence'],{encoding:'utf8'});
  assert.notEqual(refused.status,0);
  assert.match(refused.stderr,/outside current default acceptance scope/);
});
