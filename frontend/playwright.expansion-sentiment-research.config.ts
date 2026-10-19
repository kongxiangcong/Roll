import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-sentiment-research.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/16-sentiment/trained-candidate-01/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/16-sentiment/trained-candidate-01/browser-results.json'}]],timeout:90000});
