const fs = require("fs"), path = require("path"), assert = require("assert/strict"), cp = require("child_process");
assert.equal(process.getuid(),1000); assert.equal(process.getgid(),1000); assert.equal(process.versions.node,"22.23.3");
const missing=["/usr/local/bin/npm","/usr/local/bin/npx","/usr/local/bin/corepack","/usr/local/bin/yarn","/usr/local/bin/yarnpkg","/usr/local/lib/node_modules/npm","/usr/local/lib/node_modules/corepack","/opt/yarn-v1.22.22"];
for(const p of missing) assert(!fs.existsSync(p));
for(const dir of ["/data","/home/shell","/app/.next/cache"]){fs.mkdirSync(dir,{recursive:true});const p=path.join(dir,".maintenance-write-check");fs.writeFileSync(p,"");fs.unlinkSync(p);}
const copies=[];
function walk(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){if(!entry.isDirectory())continue;const p=path.join(dir,entry.name);if(entry.name==="deepmerge-ts"&&fs.existsSync(path.join(p,"package.json"))){const version=JSON.parse(fs.readFileSync(path.join(p,"package.json"),"utf8")).version;assert.equal(version,"8.0.0");copies.push({path:p,version});}walk(p);}}
walk("/app/node_modules");assert(copies.length>0);
const perl=cp.execFileSync("dpkg-query",["-W","-f=${Version}","perl-base"],{encoding:"utf8"});cp.execFileSync("dpkg",["--compare-versions",perl,"ge","5.36.0-7+deb12u4"]);
const cli=JSON.parse(cp.execFileSync("kubectl",["version","--client","-o","json"],{encoding:"utf8"})).clientVersion;assert.equal(cli.gitVersion,"v1.37.1");
console.log(JSON.stringify({node:process.versions.node,uid:process.getuid(),gid:process.getgid(),runtimePackageManagersAbsent:true,writablePaths:["/data","/home/shell","/app/.next/cache"],deepmergeCopies:copies,prisma:require("prisma/package.json").version,prismaClient:require("@prisma/client/package.json").version,perlBase:perl,kubectl:cli,passed:true}));
