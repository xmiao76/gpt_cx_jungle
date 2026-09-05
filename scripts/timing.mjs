import { chromium,firefox } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { mkdirSync,writeFileSync,existsSync } from 'node:fs';
import { timingCases,timingSave,timingSummary,searchDiagnostics,observeReadyTurn } from './timing-cases.mjs';
import { sha,engineHash,treeHash } from './artifacts.mjs';
import { localSite } from './local-site.mjs';
mkdirSync('artifacts',{recursive:true});
const targets=process.argv.slice(2).length?process.argv.slice(2):['native','chrome','firefox'];
if(targets.some(target=>!['native','chrome','firefox'].includes(target)))throw new Error('Timing targets must be native, chrome, or firefox.');
for(const target of targets){
 if(target==='native'){
  const executable=process.env.JUNGLE_EXE||(existsSync('artifacts/install-test/Jungle.exe')?'artifacts/install-test/Jungle.exe':'release/v1/Jungle.exe');
  const result=spawnSync(process.execPath,['scripts/desktop-test.mjs'],{stdio:'inherit',windowsHide:true,env:{...process.env,JUNGLE_EXE:executable,JUNGLE_TEST_TIMING:'1',JUNGLE_TEST_SCALE:'1',JUNGLE_OFFLINE:'1'}});
  if(result.status!==0)throw new Error('Native timing checks failed.');continue;
 }
 const browser=target==='firefox'?await firefox.launch():await chromium.launch({channel:'chrome'});
 const page=await browser.newPage({viewport:{width:1180,height:800}});
 const site=await localSite();
 try{
  const start=performance.now();await page.goto(site.url);
  await page.locator('[data-engine-ready="true"]').waitFor();const startupMs=performance.now()-start;
  const samples=[];
  for(const difficulty of ['easy','medium','hard'])for(const scenario of timingCases()){
   const revision=Number(await page.getByTestId('app').getAttribute('data-revision'));
   await page.evaluate(observeReadyTurn,revision);
   await page.getByTestId('load-file').setInputFiles({name:'timing.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(timingSave(scenario.position,difficulty)))});
   await page.waitForFunction(revision=>{const app=document.querySelector('[data-testid=app]');return Number(app?.getAttribute('data-revision'))>=revision+2&&app?.getAttribute('data-ply')==='1'&&app?.getAttribute('data-thinking')==='false';},revision);
   const adapterResponseMs=Number(await page.getByTestId('app').getAttribute('data-response-ms'));
   const uiResponseMs=await page.evaluate(()=>window.jungleTurnTiming.durationMs);
   if(!Number.isFinite(uiResponseMs))throw new Error('The UI-ready response interval was not observed.');
   const responseMs=Math.max(adapterResponseMs,uiResponseMs);
   const diagnostic=searchDiagnostics(await page.locator('.engine-details').textContent(),responseMs);
   samples.push({difficulty,case:scenario.name,responseMs,adapterResponseMs,uiResponseMs,...diagnostic});
   console.log(JSON.stringify({target,difficulty,case:scenario.name,responseMs}));
  }
  const report=timingSummary(target,samples,{startupMs,version:browser.version(),engineHash:engineHash(),wasmHash:sha('dist/web/engine/jungle_wasm_bg.wasm'),webHash:treeHash('dist/web')});
  writeFileSync('artifacts/timing-'+target+'.json',JSON.stringify(report,null,2));console.log(JSON.stringify({target,passed:report.passed,difficulties:report.difficulties}));
  if(!report.passed)throw new Error(target+' exceeded a response limit.');
 }finally{site.close();await browser.close();}
}
