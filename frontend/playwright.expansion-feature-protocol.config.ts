import base from './playwright.config';
import {defineConfig} from '@playwright/test';
const method=process.env.ROLL_FEATURE_METHOD==='1';
const servers=Array.isArray(base.webServer)?base.webServer.map((server,index)=>index===0?{...server,env:{...server.env,ROLL_RUNTIME_ROLE:'API'}}:server):base.webServer;
export default defineConfig({...base,webServer:servers,testMatch:method?'expansion-feature-protocol-method.spec.ts':'expansion-feature-protocol.spec.ts',outputDir:`../.scratch/roll-capability-expansion/evidence/22-features/${method?'method-':''}browser-results`,reporter:[['list'],['json',{outputFile:`../.scratch/roll-capability-expansion/evidence/22-features/${method?'method-':''}browser-results.json`}]],timeout:90000});
