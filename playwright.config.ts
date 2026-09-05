import { defineConfig } from '@playwright/test';
import { treeHash } from './scripts/artifacts.mjs';
const label=process.env.JUNGLE_REPORT_LABEL;
if(label&&!/^[a-z0-9-]+$/.test(label))throw new Error('Invalid test report label.');
export default defineConfig({
  testDir:'./web-tests',timeout:120000,expect:{timeout:10000},workers:1,
  metadata:{webHash:treeHash('dist/web')},
  reporter:[['list'],['json',{outputFile:'artifacts/browser-e2e'+(label?'-'+label:'')+'.json'}]],
  use:{baseURL:process.env.JUNGLE_URL||'http://127.0.0.1:4174',viewport:{width:1180,height:800},screenshot:'only-on-failure',trace:'retain-on-failure'},
  projects:[{name:'chrome',use:{browserName:'chromium',channel:'chrome'}},{name:'firefox',use:{browserName:'firefox'}}],
  webServer:process.env.JUNGLE_URL?undefined:{command:'node scripts/static-server.mjs',url:'http://127.0.0.1:4174',reuseExistingServer:true},
});
