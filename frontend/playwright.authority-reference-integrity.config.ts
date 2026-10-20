import base from './playwright.config';
import {defineConfig} from '@playwright/test';

const evidence = '../.scratch/roll-capability-expansion/evidence/02-daily/contract-20261020';
const servers = Array.isArray(base.webServer) ? base.webServer.map((server, index) =>
  index === 0 ? {...server, env: {...server.env, ROLL_RUNTIME_ROLE: 'API'}} : server) : base.webServer;
export default defineConfig({
  ...base, webServer: servers, testMatch: 'authority-reference-integrity.spec.ts',
  outputDir: `${evidence}/browser-results`,
  reporter: [['list'], ['json', {outputFile: `${evidence}/browser-results.json`}]],
});
