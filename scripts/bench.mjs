import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { mkdirSync, appendFileSync, writeFileSync, readFileSync, existsSync, copyFileSync, openSync, closeSync, unlinkSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { chromium, firefox } from '@playwright/test';
import { strict as assert } from 'node:assert';
import { localSite } from './local-site.mjs';
const args=Object.fromEntries(process.argv.slice(2).map(arg=>{const [k,v]=arg.replace(/^--/,'').split('=');return[k,v??'true'];}));
const target=args.target||'native',opponent=args.opponent||'baseline',candidate=args.candidate||'candidate';
const games=Number(args.games||64),timeMs=Number(args.ms||1950),label=args.label||target+'-'+candidate+'-vs-'+opponent+'-'+timeMs;
const profiles=['baseline','candidate','no_lmr','no_quiescence','no_tablebase'];
if(!['native','chrome','firefox'].includes(target)||!profiles.includes(candidate)||![...profiles,'legacy'].includes(opponent)||!Number.isInteger(games)||games<2||games%2!==0||!Number.isFinite(timeMs)||timeMs<1||timeMs>1950||!/^[a-z0-9_-]+$/i.test(label))throw new Error('Invalid benchmark arguments.');
mkdirSync('artifacts/strength',{recursive:true});
const sourceHash=createHash('sha256');
for(const file of ['board.rs','game.rs','search.rs','tablebase.rs'])sourceHash.update(readFileSync('engine/src/'+file));
sourceHash.update(readFileSync('engine/data/two_piece.bin'));
const engineHash=sourceHash.digest('hex');
const wasmHash=target==='native'?null:createHash('sha256').update(readFileSync('dist/web/engine/jungle_wasm_bg.wasm')).digest('hex');
const lockPath='artifacts/strength/'+label+'.lock';
for(;;){
 try{const fd=openSync(lockPath,'wx');writeFileSync(fd,JSON.stringify({pid:process.pid,engineHash}));closeSync(fd);break;}
 catch(error){
  if(error.code!=='EEXIST')throw error;
  let alive=false;
  try{process.kill(JSON.parse(readFileSync(lockPath,'utf8')).pid,0);alive=true;}catch{}
  if(!alive){unlinkSync(lockPath);continue;}
  await new Promise(resolve=>setTimeout(resolve,1000));
 }
}
process.on('exit',()=>{try{if(JSON.parse(readFileSync(lockPath,'utf8')).pid===process.pid)unlinkSync(lockPath);}catch{}});
class Rpc{
 constructor(command,parameters){
  this.pending=[];
  this.child=spawn(command,parameters,{stdio:['pipe','pipe','inherit'],windowsHide:true});
  createInterface({input:this.child.stdout}).on('line',line=>{
   const task=this.pending.shift();if(!task)return;
   try{const value=JSON.parse(line);if(value.error)task.reject(new Error(value.error));else task.resolve(value);}catch(e){task.reject(e);}
  });
  this.child.on('exit',code=>{for(const p of this.pending)p.reject(new Error('Opponent exited: '+code));this.pending=[];});
 }
 call(request){return new Promise((resolve,reject)=>{this.pending.push({resolve,reject});this.child.stdin.write(JSON.stringify(request)+'\n');});}
 close(){this.child.stdin.end();this.child.kill();}
}
const executable='target/release/jungle-bench'+(process.platform==='win32'?'.exe':'');
const executableHash=createHash('sha256').update(readFileSync(executable)).digest('hex');
const snapshotExecutable=resolve('artifacts/strength/engine-'+executableHash+(process.platform==='win32'?'.exe':''));
if(!existsSync(snapshotExecutable))copyFileSync(executable,snapshotExecutable);
const native=new Rpc(snapshotExecutable,['serve']);
const legacy=opponent==='legacy'?new Rpc('python',['scripts/legacy-opponent.py']):null;
let browser,page,site;
async function browserEngine(){
 site=await localSite();
 browser=target==='firefox'?await firefox.launch():await chromium.launch({channel:'chrome'});
 page=await browser.newPage();await page.goto(site.url);
 await page.locator('[data-engine-ready="true"]').waitFor();
 await page.evaluate(async()=>{
  const engineUrl=new URL('engine/jungle_wasm.js',document.baseURI).href;
  const code='let e;onmessage=async({data:d})=>{try{if(d.op==="init"){e=await import(d.url);await e.default({module_or_path:await(await fetch(d.wasm)).arrayBuffer()});postMessage({ready:true});}else{postMessage({id:d.id,result:JSON.parse(e.search(JSON.stringify(d.position),JSON.stringify(d.options),()=>{}))});}}catch(error){postMessage({id:d.id,error:String(error)})}}';
  const url=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));
  const worker=new Worker(url,{type:'module'});URL.revokeObjectURL(url);
  let id=0;const pending=new Map();
  const ready=new Promise((resolve,reject)=>{
   worker.onmessage=({data})=>{if(data.ready){resolve(true);return;}const task=pending.get(data.id);if(task){pending.delete(data.id);data.error?task.reject(new Error(data.error)):task.resolve(data.result);}};
   worker.onerror=event=>reject(new Error(event.message));
  });
  worker.postMessage({op:'init',url:engineUrl,wasm:new URL('engine/jungle_wasm_bg.wasm',document.baseURI).href});await ready;
  window.benchmarkSearch=(position,options)=>new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});worker.postMessage({id:key,op:'search',position,options});});
 });
}
async function search(position,profile,history){
 const options={difficulty:'hard',time_ms:timeMs,profile};
 if(profile==='legacy')return legacy.call({position,options,history});
 if(target==='native')return native.call({op:'search',position,options});
 return page.evaluate(({position,options})=>window.benchmarkSearch(position,options),{position,options});
}
function random(seed){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return seed>>>0;}
async function opening(number){
 let state=await native.call({op:'inspect'}),seed=number+1729,history=[];
 for(let ply=0;ply<8+(number%5);ply++){
  seed=random(seed);const m=state.moves[seed%state.moves.length];
  history.push({...m,piece:state.position.board[m.from]});
  state=await native.call({op:'apply',position:state.position,from:m.from,to:m.to});
  if(state.outcome.kind!=='ongoing')return opening(number+1000);
 }
 return{state,history};
}
const path='artifacts/strength/'+label+'.jsonl';
let records=existsSync(path)?readFileSync(path,'utf8').trim().split(/\r?\n/).filter(Boolean).map(l=>JSON.parse(l)):[];
if(records.length>games||records.some((r,index)=>r.game!==index+1||r.engineHash!==engineHash||r.timeMs!==timeMs||r.target!==target||r.candidate!==candidate||r.opponent!==opponent||r.executableHash!==executableHash||(r.wasmHash??null)!==wasmHash))throw new Error('Existing benchmark results belong to another engine, artifact, opponent, or budget. Use a new label.');
try{
 if(target!=='native'&&records.length<games)await browserEngine();
 for(let game=records.length;game<games;game++){
  const pair=Math.floor(game/2),candidateSide=game%2===0?'blue':'red';
  let{state,history}=await opening(pair);
  let plies=0,elapsedNative=0,elapsedOpponent=0;
  const start=Date.now();
  while(state.outcome.kind==='ongoing'){
   assert.ok(plies<1600,'Missing termination');
   const profile=state.position.side===candidateSide?candidate:opponent;
   const result=await search(state.position,profile,history);
   const m=result.best_move;assert.ok(m && state.moves.some(v=>v.from===m.from&&v.to===m.to),'Illegal or missing benchmark move');
   if(profile===candidate)elapsedNative+=result.elapsed_ms;else elapsedOpponent+=result.elapsed_ms;
   history.push({...m,piece:state.position.board[m.from]});
   state=await native.call({op:'apply',position:state.position,from:m.from,to:m.to});plies++;
   if(plies%20===0)console.log(JSON.stringify({label,game:game+1,plies,phase:'playing'}));
  }
  const score=state.outcome.winner===null ? .5 : state.outcome.winner===candidateSide ? 1 : 0;
  const record={game:game+1,pair,openingRng:'xorshift32-v1',candidateSide,candidate,opponent,target,timeMs,engineHash,executableHash,wasmHash,score,plies,outcome:state.outcome,elapsedMs:Date.now()-start,searchMs:{candidate:elapsedNative,opponent:elapsedOpponent}};
  appendFileSync(path,JSON.stringify(record)+'\n');records.push(record);console.log(JSON.stringify(record));
 }
 const scores=records.map(r=>r.score),score=scores.reduce((a,b)=>a+b,0)/scores.length;
 const paired=[];
 for(let i=0;i+1<scores.length;i+=2)paired.push((scores[i]+scores[i+1])/2);
 let seed=913;const samples=[];
 for(let i=0;i<5000;i++){let sum=0;for(let j=0;j<paired.length;j++){seed=random(seed);sum+=paired[seed%paired.length];}samples.push(sum/paired.length);}
 samples.sort((a,b)=>a-b);
 const interval=[samples[125],samples[4874]];
 const margin=Math.sqrt(Math.log(40)/(2*paired.length));
 const conservative=[Math.max(0,score-margin),Math.min(1,score+margin)];
 const elo=s=>s>0&&s<1?400*Math.log10(s/(1-s)):null;
 const summary={target,candidate,opponent,timeMs,engineHash,wasmHash,games:records.length,score,
  wins:scores.filter(s=>s===1).length,draws:scores.filter(s=>s===.5).length,losses:scores.filter(s=>s===0).length,
  pairedBootstrap95:interval,pairedHoeffding95:conservative,improvementSupported:conservative[0]>.5,
  eloEstimate:elo(score),eloBootstrap95:interval.map(elo),ratingNote:'Elo-style score conversion for this match only; null endpoints are unbounded, not a finite rating claim.',createdAt:new Date().toISOString()};
 writeFileSync('artifacts/strength/'+label+'.json',JSON.stringify(summary,null,2));console.log(JSON.stringify(summary));
}finally{native.close();legacy?.close();await browser?.close();site?.close();}
