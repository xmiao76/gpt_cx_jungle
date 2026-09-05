import { createServer } from 'node:http';
import { createReadStream, statSync } from 'node:fs';
import { resolve, extname, sep } from 'node:path';
const root=resolve(process.env.JUNGLE_STATIC_DIR||'dist/web');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.wasm':'application/wasm','.png':'image/png','.svg':'image/svg+xml','.json':'application/json'};
const server=createServer((req,res)=>{
 try{
  let path=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  if(path.startsWith('/nested/'))path=path.slice(7);
  if(path.endsWith('/'))path+='index.html';
  const file=resolve(root,'.'+path);
  if(!file.startsWith(root+sep)||!statSync(file).isFile()){res.writeHead(404);res.end('Not found');return;}
  res.writeHead(200,{'content-type':types[extname(file)]||'application/octet-stream','cache-control':'no-store'});
  createReadStream(file).pipe(res);
 }catch{res.writeHead(404);res.end('Not found');}
});
server.listen(Number(process.env.PORT||4174),'127.0.0.1',()=>console.log(JSON.stringify({url:'http://127.0.0.1:'+server.address().port+'/'})));
