import base from './vite.config';
import {defineConfig} from 'vite';
import {resolve} from 'node:path';
// This runner shares installed packages, but all optimizer writes belong here.
export default defineConfig({...base,cacheDir:resolve('../.scratch/t29-vite-cache')});
