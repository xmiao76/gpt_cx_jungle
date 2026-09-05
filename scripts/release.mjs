import { spawnSync } from 'node:child_process';
import { readFileSync,writeFileSync,copyFileSync,mkdirSync,readdirSync,statSync,existsSync } from 'node:fs';
import { resolve,join,relative } from 'node:path';
import { run,metadata } from './tasks.mjs';
import { packageIdentity,engineHash,files,sha } from './artifacts.mjs';
import { pagesClient,verifyHostedArtifact } from './pages.mjs';
const node=process.execPath,root=resolve(import.meta.dirname,'..');
process.chdir(root);
const mode=process.argv[2]||'verify';
const read=file=>JSON.parse(readFileSync(file,'utf8'));
const write=(file,value)=>writeFileSync(file,JSON.stringify(value,null,2));
function stage(){
 mkdirSync('release/v1',{recursive:true});mkdirSync('artifacts',{recursive:true});
 const folder='target/release/bundle/nsis';
 const installers=readdirSync(folder).filter(file=>file.endsWith('.exe')).map(file=>join(folder,file)).sort((a,b)=>statSync(b).mtimeMs-statSync(a).mtimeMs);
 if(!installers.length)throw new Error('NSIS installer was not built.');
 copyFileSync('target/release/Jungle.exe','release/v1/Jungle.exe');
 copyFileSync(installers[0],'release/v1/Jungle-Setup.exe');
 copyFileSync('prompt_template.md','release/v1/prompt_template.md');
 copyFileSync('LICENSE','release/v1/LICENSE');
 write('release/v1/checksums.json',packageIdentity());
}
function requireReport(path){
 if(!existsSync(path))throw new Error('Required evidence is missing: '+path);
 const report=read(path);if(report.passed!==true)throw new Error('Required check did not pass: '+path);return report;
}
function requireStrength(){
 const names=['final-native-baseline','final-native-legacy','final-chrome-baseline','final-chrome-legacy'];
 return names.map(name=>{
  const path='artifacts/strength/'+name+'.json';
  if(!existsSync(path))throw new Error('Strength comparison is still outstanding: '+name);
  const report=read(path);
  if(report.games!==64||report.timeMs!==1950||report.engineHash!==engineHash())throw new Error('Strength evidence does not match this engine: '+name);
  const expectedTarget=name.includes('native')?'native':'chrome';
  const expectedOpponent=name.endsWith('legacy')?'legacy':'baseline';
  if(report.target!==expectedTarget||report.opponent!==expectedOpponent||report.candidate!=='candidate')throw new Error('Strength evidence is for a different comparison: '+name);
  if(report.target==='chrome'&&report.wasmHash!==sha('dist/web/engine/jungle_wasm_bg.wasm'))throw new Error('Browser strength evidence is for a different WebAssembly artifact.');
  if(report.score<.5)throw new Error('Engine strength regressed: '+name);
  return report;
 });
}
function install(){
 const folder=resolve('artifacts/install-test');
 mkdirSync(folder,{recursive:true});
 run(resolve('release/v1/Jungle-Setup.exe'),['/S','/D='+folder],{windowsHide:true});
 const executable=join(folder,'Jungle.exe');
 if(!existsSync(executable))throw new Error('The installer did not produce the application.');
 const expected=Buffer.from(readFileSync('release/v1/Jungle.exe'));
 const marker=Buffer.from('__TAURI_BUNDLE_TYPE_VAR_UNK');
 const offset=expected.indexOf(marker);
 if(offset<0||expected.indexOf(marker,offset+1)>=0)throw new Error('Cannot identify the portable bundle marker.');
 expected.write('NSS',offset+marker.length-3,'ascii');
 if(!expected.equals(readFileSync(executable)))throw new Error('Installed executable differs beyond the expected NSIS bundle marker.');
 write('artifacts/installation.json',{passed:true,executable,sha:sha(executable),portableHash:sha('release/v1/Jungle.exe'),installerHash:sha('release/v1/Jungle-Setup.exe'),bundleMarker:'UNK -> NSS',createdAt:new Date().toISOString()});
 return executable;
}
function gui(executable){
 const setup=spawnSync('powershell.exe',['-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/setup-edge-driver.ps1'],{encoding:'utf8',windowsHide:true});
 if(setup.status!==0)throw new Error(setup.stderr);
 const driver=setup.stdout.trim().split(/\r?\n/).at(-1);
 for(const scale of [1,1.25,1.5,2]){
  run(node,['scripts/desktop-test.mjs'],{env:{...process.env,JUNGLE_EXE:executable,JUNGLE_EDGE_DRIVER:driver,JUNGLE_TEST_SCALE:String(scale),JUNGLE_TEST_FULL:scale===1?'1':'0',JUNGLE_OFFLINE:'1'}});
 }
}
function packagedSmoke(){
 run(resolve('release/v1/Jungle.exe'),['--smoke-test','--report',resolve('artifacts/packaged-smoke.json')],{windowsHide:true});
 const report=requireReport('artifacts/packaged-smoke.json');
 write('artifacts/packaged-smoke.json',{...report,executableHash:sha('release/v1/Jungle.exe'),engineHash:engineHash(),createdAt:new Date().toISOString()});
}
function aggregate(){
 const identity=packageIdentity();
 const desktop=[1,1.25,1.5,2].map(scale=>requireReport('artifacts/desktop-'+scale+'.json'));
 const browser=read('artifacts/browser-e2e.json');
 if(browser.stats.unexpected||browser.stats.interrupted||browser.stats.skipped||browser.stats.expected<30)throw new Error('Browser end-to-end coverage is incomplete.');
 const parity=['chrome','firefox'].map(name=>requireReport('artifacts/parity-'+name+'.json'));
 if(parity.some(p=>p.count!==10000||p.transitions<9000))throw new Error('The full parity corpus and state transitions were not tested.');
 const reference=requireReport('artifacts/reference-rules.json');
 if(reference.count!==10000||reference.engineHash!==identity.engine||parity.some(p=>p.corpusHash!==reference.corpusHash))throw new Error('The golden corpus was not checked against the independent rules implementation.');
 const timing=['native','chrome','firefox'].map(name=>requireReport('artifacts/timing-'+name+'.json'));
 const installation=requireReport('artifacts/installation.json');
 if(installation.portableHash!==identity.desktop||installation.installerHash!==identity.installer||desktop.some(report=>report.executableHash!==installation.sha))throw new Error('Installed desktop verification does not match the current package.');
 if(browser.config?.metadata?.webHash!==identity.web)throw new Error('Browser tests were run against a different web bundle.');
 if(desktop.some(report=>!report.offlineProxy||report.layouts?.length!==3||Math.abs(report.actualScale-report.requestedScale)>.01))throw new Error('The offline desktop size/scaling matrix is incomplete.');
 if(!desktop[0].checks.some(check=>check.name==='full-game'&&check.passed&&check.outcome!=='ongoing'))throw new Error('A complete installed desktop game was not verified.');
 if(!desktop[0].checks.some(check=>check.name==='human-full-game'&&check.passed&&check.outcome!=='ongoing'))throw new Error('A complete human-vs-AI desktop game was not verified.');
 const smoke=requireReport('artifacts/packaged-smoke.json');
 if(smoke.executableHash!==identity.desktop||smoke.engineHash!==identity.engine)throw new Error('Packaged smoke evidence is stale.');
 if(parity.some(report=>report.engineHash!==identity.engine||report.wasmHash!==identity.wasm||report.webHash!==identity.web))throw new Error('Parity evidence is stale.');
 if(timing.some(report=>report.engineHash!==identity.engine||(report.target==='native'?report.executableHash!==installation.sha:report.wasmHash!==identity.wasm||report.webHash!==identity.web)))throw new Error('Timing evidence is stale.');
 const strength=requireStrength();
 const report={passed:true,identity,desktop,browser:browser.stats,parity,reference,timing,installation,smoke,strength,createdAt:new Date().toISOString()};
 write('artifacts/release-validation.json',report);return report;
}
async function deploy(){
 const report=requireReport('artifacts/release-validation.json'),identity=packageIdentity();
 if(JSON.stringify(report.identity)!==JSON.stringify(identity))throw new Error('Release artifacts changed after verification. Rerun release verification.');
 requireStrength();
 const site=metadata(),project=site.project;
 const assets=files('dist/web');
 if(assets.length>20000)throw new Error('The static site exceeds the Pages free-tier file count.');
 for(const file of assets){
  if(statSync(file).size>25*1024*1024)throw new Error('Static asset exceeds Pages limits: '+file);
 }
 if(existsSync('dist/web/_worker.js')||existsSync('functions'))throw new Error('This deployment must remain static-only.');
 const pages=await pagesClient(project);
 const previous=await pages.current();
 write('artifacts/pre-deployment.json',{project,previous,createdAt:new Date().toISOString()});
 const message='Jungle verified release '+identity.web.slice(0,16)+' '+Date.now();
 const preview=await pages.upload('release-check',message+' preview');
 const previewAssets=await verifyHostedArtifact(preview.url);
 for(const browser of ['chrome','firefox'])run(node,['scripts/browser-check.mjs',browser],{env:{...process.env,JUNGLE_URL:preview.url,JUNGLE_REPORT_LABEL:'preview'}});
 if(metadata().project!==project)throw new Error('model_base_name changed during preview validation. Recheck the intended destination before promotion.');
 if((await pages.current())?.id!==previous?.id)throw new Error('Production changed during preview validation; inspect the new state before promoting.');
 let promoted;
 try{
  promoted=await pages.upload('main',message+' production');
  if((await pages.current())?.id!==promoted.id)throw new Error('Production is no longer our deployment.');
  const publicAssets=await verifyHostedArtifact(site.url);
  for(const browser of ['chrome','firefox'])run(node,['scripts/browser-check.mjs',browser],{env:{...process.env,JUNGLE_URL:site.url,JUNGLE_REPORT_LABEL:'production'}});
  run(node,['node_modules/playwright/cli.js','test','--grep','complete AI-vs-AI'],{env:{...process.env,JUNGLE_URL:site.url,JUNGLE_REPORT_LABEL:'production'}});
  write('artifacts/deployment.json',{passed:true,project,url:site.url,identity,previous,preview,promoted,previewAssets,publicAssets,createdAt:new Date().toISOString()});
 }catch(error){
  if(!promoted){
   const active=await pages.current().catch(()=>null);
   if(active?.deployment_trigger?.metadata?.commit_message===message+' production')promoted=active;
  }
  const rollback=await pages.rollback(previous,promoted).catch(failure=>({restored:false,error:String(failure)}));
  write('artifacts/deployment.json',{passed:false,project,error:String(error),previous,promoted,rollback,createdAt:new Date().toISOString()});
  throw new Error(String(error)+'; rollback: '+JSON.stringify(rollback));
 }
}
function handoff(){
 const deployed=requireReport('artifacts/deployment.json');
 const validation=aggregate();
 if(JSON.stringify(deployed.identity)!==JSON.stringify(validation.identity)||deployed.project!==metadata().project)throw new Error('The handoff does not match the verified deployment.');
 const folder='release/v1/validation';mkdirSync(folder,{recursive:true});
 const reports=['release-validation','deployment','installation','packaged-smoke','browser-e2e','browser-e2e-production','reference-rules',
  ...[1,1.25,1.5,2].map(scale=>'desktop-'+scale),...['native','chrome','firefox'].map(target=>'timing-'+target),...['chrome','firefox'].map(target=>'parity-'+target)];
 for(const name of reports)copyFileSync('artifacts/'+name+'.json',folder+'/'+name+'.json');
 for(const name of ['final-native-baseline','final-native-legacy','final-chrome-baseline','final-chrome-legacy'])for(const extension of ['json','jsonl'])copyFileSync('artifacts/strength/'+name+'.'+extension,folder+'/'+name+'.'+extension);
 copyFileSync('prompt_template.md','release/v1/prompt_template.md');
 copyFileSync('LICENSE','release/v1/LICENSE');
 const manifest=files('release/v1').filter(file=>!file.endsWith('manifest.json')).map(file=>({file:relative('release/v1',file).replaceAll('\\','/'),bytes:statSync(file).size,sha256:sha(file)}));
 write('release/v1/manifest.json',{version:metadata().version,url:deployed.url,files:manifest,createdAt:new Date().toISOString()});
 console.log(JSON.stringify({passed:true,folder:resolve('release/v1'),url:deployed.url}));
}
try{
 if(mode==='package'){run(node,['scripts/tasks.mjs','desktop-build']);stage();}
 else if(mode==='stage'){stage();}
 else if(mode==='install'){console.log(install());}
 else if(mode==='desktop'){packagedSmoke();gui(install());}
 else if(mode==='smoke'){packagedSmoke();}
 else if(mode==='record'){console.log(JSON.stringify(aggregate()));}
 else if(mode==='handoff'){handoff();}
 else if(mode==='verify'){
  run('cargo',['fmt','--all','--','--check']);
  // Tauri's custom-protocol static check embeds frontendDist even on a clean checkout.
  run(node,['scripts/tasks.mjs','build']);
  run('cargo',['clippy','--workspace','--all-targets','--all-features','--','-D','warnings']);
  run('cargo',['test','-p','jungle-engine','--release']);
  run('cargo',['run','-p','jungle-engine','--release','--bin','jungle-tablebase','--','engine/data/two_piece.bin','--check']);
  run(node,['node_modules/vitest/vitest.mjs','run']);
  run(node,['--test','scripts/release.test.mjs']);
  run(node,['scripts/tasks.mjs','desktop-build']);stage();
  packagedSmoke();
  gui(install());
  run(node,['node_modules/playwright/cli.js','test']);
  for(const browser of ['chrome','firefox'])run(node,['scripts/parity.mjs',browser]);
  run(node,['scripts/reference-check.mjs']);
  run(node,['scripts/timing.mjs']);
  console.log(JSON.stringify(aggregate()));
 }else if(mode==='deploy')await deploy();
 else throw new Error('Unknown release operation.');
}catch(error){console.error(error.stack||error);process.exitCode=1;}
