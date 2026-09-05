import { test,expect,type Page } from '@playwright/test';
async function ready(page:Page,path='/'){
 await page.goto(path);await expect(page.getByTestId('app')).toHaveAttribute('data-engine-ready','true');
}
function save(pieces:[number,number][],quiet=0){
 const board=Array<number>(63).fill(0);for(const[s,p]of pieces)board[s]=p;
 return {format_version:1,rules_id:'jungle-tiger-ew-quiet100-v1',initial:{board,side:'blue',quiet},moves:[],cursor:0,settings:{human:'blue',mode:'human',difficulty:'easy'}};
}
async function load(page:Page,value:unknown){
 await page.getByTestId('load-file').setInputFiles({name:'test.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
}
test('root and nested static paths load every engine and animal asset',async({page})=>{
 const failures:string[]=[];page.on('response',response=>{if(response.status()>=400)failures.push(response.url());});
 for(const path of ['/','/nested/']){
  await ready(page,path);
  await expect(page.locator('[data-square]')).toHaveCount(63);await expect(page.locator('.piece img')).toHaveCount(16);
  expect(await page.locator('.piece img').evaluateAll(images=>images.every(image=>(image as HTMLImageElement).naturalWidth>0))).toBe(true);
 }
 expect(failures).toEqual([]);
});
for(const aiFirst of [false,true])for(const flipped of [false,true]){
 test('first-player selection: '+(aiFirst?'AI':'human')+', flip '+flipped,async({page})=>{
  await ready(page);
  if(flipped)await page.getByRole('button',{name:/Flip board/}).click();
  await page.locator('.new-game').click();
  await page.getByRole('button',{name:aiFirst?/AI moves first/:/I move first/}).click();
  await page.getByLabel('New game difficulty').selectOption('easy');
  await page.getByRole('button',{name:/Start game/}).click();
  await expect(page.getByTestId('app')).toHaveAttribute('data-ply',aiFirst?'1':'0');
  await expect(page.getByTestId('app')).toHaveAttribute('data-turn',aiFirst?'red':'blue');
  await expect(page.getByTestId('board')).toHaveAttribute('data-flipped',String(flipped));
 });
}
test('undo cancels Hard search and rejects stale results',async({page})=>{
 await ready(page);await page.getByLabel('Difficulty',{exact:true}).selectOption('hard');
 await page.locator('[data-square="48"]').click();await page.locator('[data-square="41"]').click();
 await expect(page.getByTestId('app')).toHaveAttribute('data-thinking','true');
 await page.evaluate(()=>{document.addEventListener('pointerdown',()=>{const start=performance.now();const frame=()=>{if(document.querySelector('[data-testid=app]')?.getAttribute('data-ply')==='0'){(window as Window & {testInputResponseMs?:number}).testInputResponseMs=performance.now()-start;}else requestAnimationFrame(frame);};requestAnimationFrame(frame);},{once:true});});
 await page.getByRole('button',{name:/Undo/}).click();
 await expect(page.getByTestId('app')).toHaveAttribute('data-ply','0');
 await page.waitForTimeout(2200);
 await expect(page.getByTestId('app')).toHaveAttribute('data-ply','0');
 await expect(page.getByTestId('app')).toHaveAttribute('data-turn','blue');
 const uiResponseMs=await page.evaluate(()=>(window as Window & {testInputResponseMs?:number}).testInputResponseMs);
 expect(uiResponseMs).toBeLessThan(100);
 await test.info().attach('ui-response-during-hard-search',{body:JSON.stringify({uiResponseMs,limitMs:100}),contentType:'application/json'});
});
test('den entry and the 100-ply draw are displayed correctly',async({page})=>{
 await ready(page);
 await load(page,save([[10,7],[6,-8]]));
 await page.locator('[data-square="10"]').click();await page.locator('[data-square="3"]').click();
 await expect(page.getByTestId('app')).toHaveAttribute('data-outcome','den_entry');
 await expect(page.getByRole('alert')).toContainText('Blue wins');
 await load(page,save([[56,6],[6,-7]],99));
 await page.locator('[data-square="56"]').click();await page.locator('[data-square="49"]').click();
 await expect(page.getByTestId('app')).toHaveAttribute('data-outcome','no_capture_draw');
 await expect(page.getByRole('alert')).toContainText('100 plies');
});
test('save download, import and redo preserve a whole turn',async({page})=>{
 await ready(page);await page.getByLabel('Difficulty',{exact:true}).selectOption('easy');
 await page.locator('[data-square="48"]').click();await page.locator('[data-square="41"]').click();
 await expect(page.getByTestId('app')).toHaveAttribute('data-ply','2');
 await page.getByRole('button',{name:/Undo/}).click();
 await expect(page.getByTestId('app')).toHaveAttribute('data-ply','0');
 const promise=page.waitForEvent('download');await page.getByRole('button',{name:'Save game',exact:true}).click();
 const download=await promise;const path=await download.path();expect(path).toBeTruthy();
 await page.getByTestId('load-file').setInputFiles(path!);
 await page.getByRole('button',{name:/Redo/}).click();
 await expect(page.getByTestId('app')).toHaveAttribute('data-ply','2');
});
test('invalid save is rejected without replacing the game',async({page})=>{
 await ready(page);
 await load(page,{format_version:99});
 await expect(page.getByRole('alert')).toContainText('Invalid save');
 await expect(page.getByTestId('app')).toHaveAttribute('data-ply','0');
 await expect(page.locator('.piece')).toHaveCount(16);
});
test('an oversized file chosen through Load restores normal play',async({page})=>{
 await ready(page);await page.getByLabel('Difficulty',{exact:true}).selectOption('easy');
 const pending=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Load game',exact:true}).click();
 const chooser=await pending;
 await chooser.setFiles({name:'too-large.json',mimeType:'application/json',buffer:Buffer.alloc(4*1024*1024+1,32)});
 await expect(page.getByRole('alert')).toContainText('4 MiB');
 await expect(page.getByTestId('game-status')).toHaveText('Your move');
 await page.locator('[data-square="48"]').click();await page.locator('[data-square="41"]').click();
 await expect(page.getByTestId('app')).toHaveAttribute('data-ply','2');
});
test('disabled browser storage does not prevent initialization or mute',async({page})=>{
 await page.addInitScript(()=>{
  for(const method of ['getItem','setItem'])Object.defineProperty(Storage.prototype,method,{value:()=>{throw new DOMException('Storage disabled','SecurityError');}});
 });
 await ready(page);await page.getByRole('button',{name:'Mute sound',exact:true}).click();
 await expect(page.getByRole('button',{name:'Unmute sound',exact:true})).toHaveAttribute('aria-pressed','true');
});
test('initialization errors provide a recovery action',async({page})=>{
 await page.route('**/engine/jungle_wasm_bg.wasm',route=>route.abort());
 await page.goto('/');await expect(page.getByRole('button',{name:'Try again'})).toBeVisible();
});
test('complete AI-vs-AI game from the normal starting position',async({page})=>{
 await ready(page);await page.locator('.new-game').click();
 await page.getByRole('button',{name:/AI vs AI/}).click();
 await page.getByLabel('New game difficulty').selectOption('easy');
 await page.getByRole('button',{name:/Start game/}).click();
 await expect(page.getByTestId('app')).not.toHaveAttribute('data-outcome','ongoing',{timeout:110000});
 expect(Number(await page.getByTestId('app').getAttribute('data-ply'))).toBeGreaterThan(10);
 await test.info().attach('full-game-result',{body:JSON.stringify({plies:Number(await page.getByTestId('app').getAttribute('data-ply')),outcome:await page.getByTestId('app').getAttribute('data-outcome')}),contentType:'application/json'});
 await page.screenshot({path:'artifacts/screenshots/full-game-'+(process.env.JUNGLE_REPORT_LABEL||'local')+'-'+test.info().project.name+'.png',fullPage:true});
});
test('layout and piece labels remain usable at supported sizes',async({page})=>{
 await ready(page);
 for(const [width,height]of [[800,600],[1180,800],[1600,1000]]){
  await page.setViewportSize({width,height});
  const metrics=await page.evaluate(()=>{
   const board=document.querySelector('[data-testid=board]')!.getBoundingClientRect();
   const buttons=[...document.querySelectorAll('.board-controls button')].map(b=>b.getBoundingClientRect());
   return{width:innerWidth,scrollWidth:document.documentElement.scrollWidth,board:{width:board.width,height:board.height,bottom:board.bottom},bottom:Math.max(...buttons.map(b=>b.bottom))};
  });
  expect(metrics.scrollWidth).toBeLessThanOrEqual(width+1);
  expect(Math.abs(metrics.board.width/metrics.board.height-7/9)).toBeLessThan(.005);
  expect(metrics.board.bottom).toBeLessThanOrEqual(height);
  expect(metrics.bottom).toBeLessThanOrEqual(height);
 }
});
test('a complete human-vs-AI game uses only displayed legal destinations',async({page})=>{
 test.setTimeout(240000);
 await ready(page);await page.getByLabel('Difficulty',{exact:true}).selectOption('easy');
 for(let turn=0;turn<800;turn++){
  if(await page.getByTestId('app').getAttribute('data-outcome')!=='ongoing')break;
  const previous=Number(await page.getByTestId('app').getAttribute('data-ply'));
  const origins=await page.locator('[data-square]').evaluateAll(buttons=>buttons.filter(b=>b.getAttribute('aria-label')?.includes(', Blue ')).map(b=>b.getAttribute('data-square')));
  let destination:string|null=null;
  for(const origin of origins){
   await page.locator('[data-square="'+origin+'"]').click();
   destination=await page.evaluate(()=>((document.querySelector('[data-legal=true].capture-target')||document.querySelector('[data-legal=true]')) as HTMLElement|null)?.dataset.square??null);
   if(destination!==null)break;
  }
  expect(destination).not.toBeNull();
  await page.locator('[data-square="'+destination+'"]').click();
  await page.waitForFunction(previous=>{const app=document.querySelector('[data-testid=app]')!;return Number(app.getAttribute('data-ply'))>previous&&(app.getAttribute('data-outcome')!=='ongoing'||app.getAttribute('data-turn')==='blue'&&app.getAttribute('data-thinking')==='false');},previous);
 }
 await expect(page.getByTestId('app')).not.toHaveAttribute('data-outcome','ongoing');
 await test.info().attach('human-full-game-result',{body:JSON.stringify({plies:Number(await page.getByTestId('app').getAttribute('data-ply')),outcome:await page.getByTestId('app').getAttribute('data-outcome')}),contentType:'application/json'});
});
