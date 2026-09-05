import { readFileSync } from 'node:fs';
export function timingCases(){
 const rows=readFileSync('artifacts/corpus.jsonl','utf8').trim().split(/\r?\n/).map(line=>JSON.parse(line).expected).filter(row=>row.outcome.kind==='ongoing'&&row.moves.length>1);
 const result=[0,20,50,100,150,250,400,800].map(index=>({name:'corpus-'+index,position:rows[index].position}));
 const board=pieces=>{const squares=Array(63).fill(0);for(const [square,piece]of pieces)squares[square]=piece;return squares;};
 result.push({name:'river-block',position:{board:board([[21,7],[42,8],[22,-1],[6,-7]]),side:'blue',quiet:0}});
 result.push({name:'exact-endgame',position:{board:board([[56,7],[6,-8]]),side:'blue',quiet:0}});
 return result;
}
export function timingSave(position,difficulty){
 return {format_version:1,rules_id:'jungle-tiger-ew-quiet100-v1',initial:position,moves:[],cursor:0,
  settings:{mode:'human',human:position.side==='blue'?'red':'blue',difficulty}};
}
export function searchDiagnostics(text,responseMs){
 const match=text.match(/Depth (\d+) · ([\d,]+) nodes/);
 if(!match)throw new Error('Search diagnostics were not published by the UI.');
 const depth=Number(match[1]),nodes=Number(match[2].replaceAll(',',''));
 return {depth,nodes,reportedNodesPerSecond:responseMs>0?nodes*1000/responseMs:0};
}
// Executed in the application's WebView/browser, not in the Node test runner.
// This independently includes UI scheduling between a ready snapshot and the
// committed reply. Piece-animation completion is intentionally not included.
export function observeReadyTurn(priorRevision){
 const app=document.querySelector('[data-testid=app]');
 window.jungleTurnTiming={readyAt:null,durationMs:null};
 const observer=new MutationObserver(()=>{
  const revision=Number(app.getAttribute('data-revision')),ply=app.getAttribute('data-ply');
  if(revision>=priorRevision+1&&ply==='0'&&window.jungleTurnTiming.readyAt===null)window.jungleTurnTiming.readyAt=performance.now();
  if(revision>=priorRevision+2&&ply==='1'&&app.getAttribute('data-thinking')==='false'&&window.jungleTurnTiming.readyAt!==null){
   window.jungleTurnTiming.durationMs=performance.now()-window.jungleTurnTiming.readyAt;observer.disconnect();
  }
 });
 observer.observe(app,{attributes:true,attributeFilter:['data-revision','data-ply','data-thinking']});
}
export function timingSummary(target,samples,extra={}){
 const limits={easy:100,medium:500,hard:2000},difficulties={};
 for(const [difficulty,limit]of Object.entries(limits)){
  const values=samples.filter(s=>s.difficulty===difficulty).map(s=>s.responseMs).sort((a,b)=>a-b);
  const median=(values[Math.floor((values.length-1)/2)]+values[Math.floor(values.length/2)])/2;
  difficulties[difficulty]={samples:values.length,limitMs:limit,medianMs:median,p95Ms:values[Math.ceil(values.length*.95)-1],maxMs:values.at(-1),overruns:values.filter(v=>v>limit).length};
 }
 return {passed:Object.values(difficulties).every(d=>d.samples===10&&d.overruns===0),target,difficulties,samples,...extra,createdAt:new Date().toISOString()};
}
