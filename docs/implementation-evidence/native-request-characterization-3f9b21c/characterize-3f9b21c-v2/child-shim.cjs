const cp=require('node:child_process'); const {syncBuiltinESMExports}=require('node:module');
const original=cp.spawn;cp.spawn=function(command,args,options){
 if(command===process.execPath && Array.isArray(args) && args.length===1 && args[0]==='/app/.next/standalone/server.js') args=['--require','/diagnostic/request-profiler.cjs',...args];
 return Reflect.apply(original,this,[command,args,options]);};syncBuiltinESMExports();
