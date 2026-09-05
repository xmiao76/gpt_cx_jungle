import { spawnSync, spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { chromium, firefox } from '@playwright/test';
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { strict as assert } from 'node:assert';
import { sha,engineHash,treeHash } from './artifacts.mjs';
import { localSite } from './local-site.mjs';
const backend=process.argv[2]||'chrome';
if(!['chrome','firefox'].includes(backend))throw new Error('Parity targets must be chrome or firefox.');
mkdirSync('artifacts',{recursive:true});
const native=spawnSync('target/release/jungle-bench.exe',['corpus','10000'],{encoding:'utf8',maxBuffer:100*1024*1024});
if(native.status!==0)throw new Error(native.stderr);
const corpus=native.stdout.trim().split(/\r?\n/).map(line=>JSON.parse(line));
const corpusHash=createHash('sha256').update(native.stdout.replace(/\r\n/g,'\n')).digest('hex');
writeFileSync('artifacts/corpus.jsonl',native.stdout);
const browser=backend==='firefox'?await firefox.launch():await chromium.launch({channel:'chrome'});
const page=await browser.newPage();
const site=await localSite();
try{
 await page.goto(site.url);
 await page.locator('[data-engine-ready="true"]').waitFor();
 const result=await page.evaluate(async records=>{
   const url=new URL('engine/jungle_wasm.js',document.baseURI).href;
   const engine=await import(url);
   await engine.default({module_or_path:await(await fetch(new URL('engine/jungle_wasm_bg.wasm',document.baseURI))).arrayBuffer()});
   let count=0,transitions=0;
   for(const [index,record] of records.entries()){
     const actual=JSON.parse(engine.inspect(JSON.stringify(record.expected.position)));
     if(JSON.stringify(actual)!==JSON.stringify(record.expected))return {passed:false,id:record.id,actual,expected:record.expected};
     const next=records[index+1]?.expected;
     if(next&&record.expected.outcome.kind==='ongoing'){
       const before=record.expected.position.board,after=next.position.board;
       const from=before.findIndex((piece,square)=>piece!==0&&after[square]===0);
       const to=after.findIndex((piece,square)=>piece!==0&&piece!==before[square]);
       const applied=JSON.parse(engine.apply(JSON.stringify(record.expected.position),from,to));
       if(JSON.stringify(applied)!==JSON.stringify(next))return {passed:false,id:record.id,transition:true,actual:applied,expected:next};
       transitions++;
     }
     count++;
   }
   return {passed:true,count,transitions};
 },corpus);
 assert.ok(result.passed,JSON.stringify(result));
 const report={...result,browser:backend,version:browser.version(),corpusHash,engineHash:engineHash(),wasmHash:sha('dist/web/engine/jungle_wasm_bg.wasm'),webHash:treeHash('dist/web'),createdAt:new Date().toISOString()};
 writeFileSync('artifacts/parity-'+backend+'.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
}finally{site.close();await browser.close();}
