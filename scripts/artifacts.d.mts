export function sha(file:string):string;
export function files(folder:string):string[];
export function treeHash(folder:string):string;
export function engineHash():string;
export function packageIdentity():{engine:string;desktop:string;installer:string;web:string;wasm:string};
