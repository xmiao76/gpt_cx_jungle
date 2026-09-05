import { readFileSync,readdirSync,statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join,relative } from 'node:path';
export const sha=file=>createHash('sha256').update(readFileSync(file)).digest('hex');
export function files(folder){
 return readdirSync(folder,{withFileTypes:true}).flatMap(item=>item.isDirectory()?files(join(folder,item.name)):[join(folder,item.name)]).sort();
}
export function treeHash(folder){
 const hash=createHash('sha256');
 for(const file of files(folder))hash.update(relative(folder,file).replaceAll('\\','/')+'\0').update(readFileSync(file));
 return hash.digest('hex');
}
export function engineHash(){
 const hash=createHash('sha256');
 for(const file of ['board.rs','game.rs','search.rs','tablebase.rs'])hash.update(readFileSync('engine/src/'+file));
 return hash.update(readFileSync('engine/data/two_piece.bin')).digest('hex');
}
export function packageIdentity(){
 return{engine:engineHash(),desktop:sha('release/v1/Jungle.exe'),installer:sha('release/v1/Jungle-Setup.exe'),web:treeHash('dist/web'),wasm:sha('dist/web/engine/jungle_wasm_bg.wasm')};
}
