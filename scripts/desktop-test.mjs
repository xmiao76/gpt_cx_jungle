import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, readFileSync, appendFileSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { strict as assert } from 'node:assert';
import { timingCases,timingSave,timingSummary,searchDiagnostics,observeReadyTurn } from './timing-cases.mjs';
import { sha,engineHash } from './artifacts.mjs';
const root=resolve(import.meta.dirname,'..');
const application=resolve(process.env.JUNGLE_EXE||join(root,'target/release/Jungle.exe'));
const scale=Number(process.env.JUNGLE_TEST_SCALE||1);
function nativeDriver(){
  if(process.env.JUNGLE_EDGE_DRIVER)return resolve(process.env.JUNGLE_EDGE_DRIVER);
  const result=spawnSync('powershell.exe',['-NoProfile','-ExecutionPolicy','Bypass','-File',join(root,'scripts/setup-edge-driver.ps1')],{cwd:root,encoding:'utf8',windowsHide:true});
  if(result.status!==0)throw new Error(result.stderr||'Unable to prepare the matching WebView2 driver.');
  return resolve(result.stdout.trim().split(/\r?\n/).at(-1));
}
const driverPath=nativeDriver();
const port=4445;
mkdirSync(join(root,'artifacts/screenshots'),{recursive:true});
const logPath=join(root,'artifacts/desktop-driver-'+scale+'.log');
writeFileSync(logPath,'');
const driver=spawn('tauri-driver.exe',['--port',String(port),'--native-port','4446','--native-driver',driverPath],{
  cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe'],
  env:{...process.env,JUNGLE_GUI_TEST:'1',...(process.env.JUNGLE_OFFLINE==='1'?{WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS:'--proxy-server=http://127.0.0.1:9 --proxy-bypass-list=tauri.localhost;ipc.localhost;localhost;127.0.0.1'}:{})}
});
driver.stdout.on('data',data=>appendFileSync(logPath,data));
driver.stderr.on('data',data=>appendFileSync(logPath,data));
const base='http://127.0.0.1:'+port;
let session;
async function request(method,path,body){
  const response=await fetch(base+path,{method,headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok || data.value?.error)throw new Error(JSON.stringify(data));
  return data.value;
}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(check,label,timeout=30000){
  const deadline=Date.now()+timeout;let last;
  while(Date.now()<deadline){try{const value=await check();if(value)return value;}catch(error){last=error;}await delay(150);}
  throw new Error('Timed out: '+label+(last?' '+last.message:''));
}
async function execute(script,args=[]){return request('POST','/session/'+session+'/execute/sync',{script,args});}
async function configure(width,height){
  const result=await request('POST','/session/'+session+'/execute/async',{script:'const done=arguments[arguments.length-1];window.__TAURI_INTERNALS__.invoke("diagnostic_window",{scale:arguments[0],width:arguments[1],height:arguments[2]}).then(done).catch(error=>done({error:String(error)}))',args:[scale,width,height]});
  if(result.error)throw new Error(result.error);
  await wait(async()=>Math.abs(await execute('return devicePixelRatio')-scale)<.01,'native rasterization scale');
  return result;
}
async function find(selector){const value=await request('POST','/session/'+session+'/element',{using:'css selector',value:selector});return value['element-6066-11e4-a52e-4f735466cecf'];}
async function click(selector){return request('POST','/session/'+session+'/element/'+await find(selector)+'/click',{});}
async function textButton(text){
  const value=await request('POST','/session/'+session+'/element',{using:'xpath',value:'//button[contains(normalize-space(.),'+JSON.stringify(text)+')]'});
  return request('POST','/session/'+session+'/element/'+value['element-6066-11e4-a52e-4f735466cecf']+'/click',{});
}
async function appAttr(name){return execute('return document.querySelector("[data-testid=app]")?.getAttribute(arguments[0])',[name]);}
async function screenshot(name){const data=await request('GET','/session/'+session+'/screenshot');writeFileSync(join(root,'artifacts/screenshots/'+name+'.png'),Buffer.from(data,'base64'));}
async function nativeDialog(file){
  const child=spawnSync('powershell.exe',['-NoProfile','-ExecutionPolicy','Bypass','-File',join(root,'scripts/native-file-dialog.ps1'),'-ApplicationPath',application,'-FilePath',file],{encoding:'utf8',windowsHide:true,timeout:25000});
  console.log(child.stdout.trim());
  if(child.stderr)console.log(child.stderr.trim());
  if(child.status!==0)throw new Error('Native file dialog failed: '+child.stdout+child.stderr);
}
const checks=[];
try{
  await wait(async()=>{try{await request('GET','/status');return true;}catch{return false;}},'WebDriver start');
  const launchStart=performance.now();
  const result=await fetch(base+'/session',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({capabilities:{alwaysMatch:{'tauri:options':{application},browserName:'wry'}}})});
  const created=await result.json();
  if(!result.ok || created.value?.error)throw new Error(JSON.stringify(created));
  session=created.value.sessionId;
  await wait(()=>appAttr('data-engine-ready'),'native engine initialization');
  const startupMs=performance.now()-launchStart;
  assert.equal(await appAttr('data-runtime'),'native');
  const systemScale=await execute('return window.devicePixelRatio');
  const initialViewport=await execute('return {width:innerWidth,height:innerHeight,outerWidth,outerHeight,availableWidth:screen.availWidth,availableHeight:screen.availHeight,scale:devicePixelRatio}');
  const nativeBounds=await request('POST','/session/'+session+'/execute/async',{script:'const done=arguments[arguments.length-1];window.__TAURI_INTERNALS__.invoke("diagnostic_bounds").then(done).catch(error=>done({error:String(error)}));',args:[]});
  if(nativeBounds.error)throw new Error(nativeBounds.error);
  if(nativeBounds.workArea){
    const {position,outer,workArea}=nativeBounds;
    assert.ok(position.x>=workArea.position.x&&position.y>=workArea.position.y,'Default window origin must remain in the work area');
    assert.ok(position.x+outer.width<=workArea.position.x+workArea.size.width+1&&position.y+outer.height<=workArea.position.y+workArea.size.height+1,'Default window must fit the monitor work area');
  }
  console.log(JSON.stringify({phase:'default-window',...initialViewport}));
  if(process.env.JUNGLE_TEST_TIMING!=='1')await screenshot('desktop-'+scale+'-system-default');
  await configure(1180,800);
  const actualScale=await execute('return window.devicePixelRatio');
  console.log(JSON.stringify({phase:'desktop-ready',application,requestedScale:scale,systemScale,actualScale}));
  if(process.env.JUNGLE_TEST_TIMING==='1'){
    const samples=[];
    for(const difficulty of ['easy','medium','hard'])for(const scenario of timingCases()){
      const revision=Number(await appAttr('data-revision'));
      await execute('('+observeReadyTurn.toString()+')(arguments[0]);',[revision]);
      await execute('const input=document.querySelector("[data-testid=load-file]");const transfer=new DataTransfer();transfer.items.add(new File([JSON.stringify(arguments[0])],"timing.json",{type:"application/json"}));input.files=transfer.files;input.dispatchEvent(new Event("change",{bubbles:true}));',[timingSave(scenario.position,difficulty)]);
      await wait(async()=>Number(await appAttr('data-revision'))>=revision+2&&await appAttr('data-ply')==='1'&&await appAttr('data-thinking')==='false','native timed AI turn');
      const adapterResponseMs=Number(await appAttr('data-response-ms'));
      const uiResponseMs=await execute('return window.jungleTurnTiming.durationMs');
      assert.ok(Number.isFinite(uiResponseMs),'The UI-ready response interval must be observed');
      const responseMs=Math.max(adapterResponseMs,uiResponseMs);
      const diagnostic=searchDiagnostics(await execute('return document.querySelector(".engine-details").textContent'),responseMs);
      samples.push({difficulty,case:scenario.name,responseMs,adapterResponseMs,uiResponseMs,...diagnostic});console.log(JSON.stringify({target:'native',difficulty,case:scenario.name,responseMs}));
    }
    const report=timingSummary('native',samples,{application,startupMs,executableHash:sha(application),engineHash:engineHash()});
    writeFileSync(join(root,'artifacts/timing-native.json'),JSON.stringify(report,null,2));
    if(!report.passed)throw new Error('Native response limit exceeded.');
    console.log(JSON.stringify({target:'native',passed:true,difficulties:report.difficulties}));
  } else {
  await screenshot('desktop-'+scale+'-initial');
  await click('select[aria-label="Difficulty"] option[value="easy"]');
  await click('[data-square="48"]');await click('[data-square="41"]');
  await wait(async()=>Number(await appAttr('data-ply'))>=2,'human move and AI response');
  const responseMs=Number(await appAttr('data-response-ms'));
  assert.ok(responseMs<=100,'Easy exceeded its response limit: '+responseMs);
  checks.push({name:'human-ai',passed:true,responseMs,analysis:await execute('return document.querySelector(".engine-details").textContent')});
  await textButton('Undo');await wait(async()=>await appAttr('data-ply')==='0','undo result');
  await textButton('Redo');await wait(async()=>await appAttr('data-ply')==='2','redo result');
  await textButton('Flip board');
  assert.equal(await execute('return document.querySelector("[data-testid=board]").dataset.flipped'),'true');
  checks.push({name:'undo-redo-flip',passed:true});
  const save=join(root,'artifacts/desktop-save-'+Date.now()+'.json');
  await textButton('Save game');await nativeDialog(save);
  await wait(()=>existsSync(save),'saved file');
  assert.equal(JSON.parse(readFileSync(save,'utf8')).format_version,1);
  await click('.new-game');await textButton('Start game');
  await wait(async()=>await appAttr('data-ply')==='0','new game before load');
  await textButton('Load game');await nativeDialog(save);
  await wait(async()=>await appAttr('data-ply')==='2' && await execute('return document.querySelector("[data-testid=game-status]").textContent.toLowerCase()')==='your move','native save import');
  checks.push({name:'native-file-dialog-save-load',passed:true,save});
  await click('select[aria-label="Difficulty"] option[value="hard"]');
  await click('[data-square="41"]');await click('[data-square="34"]');
  await wait(async()=>await appAttr('data-thinking')==='true','Hard search starts');
  await execute('window.testInputResponseMs=null;document.addEventListener("pointerdown",()=>{const start=performance.now();const frame=()=>{if(document.querySelector("[data-testid=app]").dataset.ply==="2"){window.testInputResponseMs=performance.now()-start;}else requestAnimationFrame(frame);};requestAnimationFrame(frame);},{once:true});');
  await textButton('Undo');await wait(async()=>await appAttr('data-ply')==='2','undo pending Hard search');
  const uiResponseMs=await wait(()=>execute('return window.testInputResponseMs'),'responsive UI frame');
  assert.ok(uiResponseMs<100,'Thinking must not block UI feedback: '+uiResponseMs);
  await delay(2100);assert.equal(await appAttr('data-ply'),'2');
  checks.push({name:'cancel-hard-search',passed:true,uiResponseMs});
  await click('select[aria-label="Difficulty"] option[value="easy"]');
  await textButton('How to play');await wait(()=>execute('return !!document.querySelector("dialog[open]")'),'help');
  await click('[aria-label="Close dialog"]');
  const layouts=[];
  for(const [width,height]of [[800,600],[1180,800],[1600,1000]]){
    await configure(width,height);await delay(250);
    const layout=await execute('return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,scale:devicePixelRatio,board:(()=>{const r=document.querySelector("[data-testid=board]").getBoundingClientRect();return {width:r.width,height:r.height,left:r.left,top:r.top,bottom:r.bottom}})()}');
    assert.ok(layout.scrollWidth<=layout.width+1,'Horizontal overflow at '+width+'x'+height);
    assert.ok(Math.abs(layout.board.width/layout.board.height-7/9)<.005,'Board aspect ratio');
    layouts.push(layout);await screenshot('desktop-'+scale+'-'+width+'x'+height);
  }
  if(process.env.JUNGLE_TEST_FULL!=='0'){
    await configure(1180,800);
    for(const aiFirst of [false,true])for(const flipped of [false,true]){
      const actual=await execute('return document.querySelector("[data-testid=board]").dataset.flipped');
      if(actual!==String(flipped))await textButton('Flip board');
      await click('.new-game');await textButton(aiFirst?'AI moves first':'I move first');await textButton('Start game');
      await wait(async()=>await appAttr('data-ply')===(aiFirst?'1':'0')&&await appAttr('data-turn')===(aiFirst?'red':'blue'),'native first-player choice');
      assert.equal(await execute('return document.querySelector("[data-testid=board]").dataset.flipped'),String(flipped));
    }
    checks.push({name:'first-player-and-flip-matrix',passed:true,cases:4});
    await click('.new-game');await textButton('AI vs AI');await textButton('Start game');
    await wait(async()=>{const plies=Number(await appAttr('data-ply'));const outcome=await appAttr('data-outcome');if(plies && plies%10===0)console.log(JSON.stringify({phase:'desktop-full-game',plies,outcome}));return outcome!=='ongoing';},'complete desktop watch game',180000);
    checks.push({name:'full-game',passed:true,plies:Number(await appAttr('data-ply')),outcome:await appAttr('data-outcome')});
    await screenshot('desktop-'+scale+'-full-game');
    await click('.new-game');await textButton('Play against AI');await textButton('I move first');await textButton('Start game');
    await wait(async()=>await appAttr('data-ply')==='0','new human game');
    const humanDeadline=Date.now()+240000;
    while(await appAttr('data-outcome')==='ongoing'){
      assert.ok(Date.now()<humanDeadline,'Human-vs-AI game must terminate');
      const previous=Number(await appAttr('data-ply'));
      const origins=await execute('return [...document.querySelectorAll("[data-square]")].filter(b=>b.getAttribute("aria-label").includes(", Blue ")).map(b=>b.dataset.square)');
      let destination=null;
      for(const origin of origins){
        await click('[data-square="'+origin+'"]');
        destination=await execute('return (document.querySelector("[data-legal=true].capture-target")||document.querySelector("[data-legal=true]"))?.dataset.square??null');
        if(destination!==null)break;
      }
      assert.notEqual(destination,null,'The human must have a displayed legal destination');
      await click('[data-square="'+destination+'"]');
      await wait(async()=>Number(await appAttr('data-ply'))>previous&&(await appAttr('data-outcome')!=='ongoing'||await appAttr('data-turn')==='blue'&&await appAttr('data-thinking')==='false'),'human move and AI reply');
    }
    checks.push({name:'human-full-game',passed:true,plies:Number(await appAttr('data-ply')),outcome:await appAttr('data-outcome')});
    await screenshot('desktop-'+scale+'-human-full-game');
    const races=await request('POST','/session/'+session+'/execute/async',{script:`
      const done=arguments[arguments.length-1],invoke=window.__TAURI_INTERNALS__.invoke;
      (async()=>{
        for(let index=0;index<16;index++){
          await invoke('engine_command',{request:JSON.stringify({type:'new',settings:{human:'blue',mode:'human',difficulty:'easy'}})});
          const before=JSON.parse(await invoke('engine_command',{request:'{"type":"snapshot"}'}));
          const search=invoke('engine_search',{position:JSON.stringify(before.position),options:JSON.stringify({time_ms:20,max_depth:2,profile:'baseline'}),job:'race-'+index,revision:before.revision});
          const reset=invoke('engine_command',{request:JSON.stringify({type:'new',settings:before.settings})});
          await Promise.allSettled([search,reset]);
          const after=JSON.parse(await invoke('engine_command',{request:'{"type":"snapshot"}'}));
          if(after.revision!==before.revision+1||after.cursor!==0||after.position.side!=='blue'||after.legal_moves.length!==24)throw new Error('Concurrent reset changed the new game.');
          try{await invoke('engine_search',{position:JSON.stringify(before.position),options:'{"time_ms":1}',job:'stale-'+index,revision:before.revision});throw new Error('Stale revision was accepted.');}
          catch(error){if(!String(error).includes('position changed'))throw error;}
        }
        return {cases:16,passed:true};
      })().then(done,error=>done({error:String(error)}));`,args:[]});
    assert.ok(races.passed,JSON.stringify(races));
    checks.push({name:'concurrent-native-search-reset-protocol',...races});
  }
  const resources=await execute('return performance.getEntriesByType("resource").map(r=>r.name)');
  assert.ok(resources.every(url=>url.startsWith('http://tauri.localhost/')||url.startsWith('http://ipc.localhost/')||url.startsWith('data:')),'Unexpected network dependency');
  const report={passed:true,application,executableHash:sha(application),startupMs,initialViewport,nativeBounds,requestedScale:scale,systemScale,actualScale,offlineProxy:process.env.JUNGLE_OFFLINE==='1',scalingMethod:'Windows WebView2 rasterization; system display settings unchanged',checks,layouts,createdAt:new Date().toISOString()};
  writeFileSync(join(root,'artifacts/desktop-'+scale+'.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
  }
}catch(error){
  if(session){try{console.log(JSON.stringify({diagnostic:await execute('return {url:location.href,text:document.body.innerText.slice(0,1600),width:innerWidth,height:innerHeight,dpr:devicePixelRatio}')}));}catch{}}
  if(session){try{await screenshot('desktop-'+scale+'-failure');}catch{}}
  writeFileSync(join(root,'artifacts/'+(process.env.JUNGLE_TEST_TIMING==='1'?'timing-native':'desktop-'+scale)+'.json'),JSON.stringify({passed:false,error:String(error),checks},null,2));
  throw error;
}finally{
  if(session){try{await request('DELETE','/session/'+session);}catch{}}
  driver.kill();
}
