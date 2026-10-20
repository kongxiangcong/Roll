import base from './playwright.config';
import {defineConfig} from '@playwright/test';
const servers=Array.isArray(base.webServer)?base.webServer.map((server,index)=>index===0?{...server,env:{...server.env,ROLL_RUNTIME_ROLE:'API'}}:server):base.webServer;
export default defineConfig({...base,webServer:servers,testMatch:'expansion-authority.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/04-actions/authority-20261020/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/04-actions/authority-20261020/browser-results.json'}]]});
