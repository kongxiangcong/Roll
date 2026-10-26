import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-documents.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/12-docling/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/12-docling/browser-results.json'}]],timeout:90000});
