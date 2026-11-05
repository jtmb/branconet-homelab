import { execFileSync } from "node:child_process";
import { mkdir, writeFile, readFile, chmod } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

/** Disposable executable; never contacts a cluster. Log uses encoded individual arguments. */
export async function fakeKubectl(dir: string) {
  const bin = path.join(dir, "fake-bin");
  await mkdir(bin);
  const log = path.join(bin, "calls.log");
  if (process.platform === "win32") {
    const source = path.join(bin, "fixture.cs");
    await writeFile(source, `using System; using System.IO; using System.Text; using System.Threading;
class Fixture { static int Main(string[] args) {
  string d=Environment.GetEnvironmentVariable("BORTUS_FAKE_KUBECTL");
  if(String.IsNullOrEmpty(d)||!Directory.Exists(d)) return 90;
  using(Mutex m=new Mutex(false,"Local\\\\BortusFixture${randomUUID().replaceAll("-", "")}")) {
    m.WaitOne(); try { File.AppendAllText(Path.Combine(d,"calls.log"),String.Join(" ",Array.ConvertAll(args,a=>Convert.ToBase64String(Encoding.UTF8.GetBytes(a))))+"\\n"); } finally { m.ReleaseMutex(); }
  }
  int p=Array.IndexOf(args,"get");
  Thread.Sleep(50);
  if(Array.IndexOf(args,"logs")>=0) { Console.Write("fixture log line\\n"); return 0; }
  if(p<0) {
    if(File.Exists(Path.Combine(d,"allow-flux-sync")) && Array.IndexOf(args,"annotate")>=0 && Array.IndexOf(args,"gitrepository")>=0) { Console.Write(File.ReadAllText(Path.Combine(d,"gitrepository.json"))); return 0; }
    if(File.Exists(Path.Combine(d,"allow-rotation-reload")) && Array.IndexOf(args,"patch")>=0 && Array.Exists(args,a=>a=="deployment"||a=="statefulset"||a=="daemonset")) { string rotationResource=args[Array.IndexOf(args,"patch")+1]; File.Copy(Path.Combine(d,"rotation-reload.json"),Path.Combine(d,rotationResource+".json"),true); Console.Write(File.ReadAllText(Path.Combine(d,rotationResource+".json"))); return 0; }
    if(File.Exists(Path.Combine(d,"allow-flux-mutations")) && (Array.IndexOf(args,"patch")>=0 || Array.IndexOf(args,"delete")>=0) && Array.Exists(args,a=>a=="gitrepository"||a=="kustomization"||a=="helmrelease")) { Console.Write("fixture Flux mutation completed"); return 0; }
    Console.Write("private-command-output-marker"); Console.Error.Write("private-command-error-marker"); return 1;
  }
  string r=args[p+1]; string f=Path.Combine(d,r+".json");
  if(r=="kustomizations") { int waited=0; while(File.Exists(Path.Combine(d,"hold-flux-discovery")) && waited<12000) { Thread.Sleep(20); waited+=20; } }
  string failure=Path.Combine(d,"failure.txt");
  if(File.Exists(failure)&&(File.ReadAllText(failure).Trim()=="all"||File.ReadAllText(failure).Trim()==r)) { Console.Error.Write("private-command-error-marker"); return 1; }
  if(Array.Exists(args,a=>a.StartsWith("custom-columns="))) {
    string table=Path.Combine(d,r+"-table.txt"); Console.Write(File.Exists(table)?File.ReadAllText(table):"");
  }
  else if(Array.IndexOf(args,"yaml")>=0) {
    string kind=r=="persistentvolumeclaim"?"PersistentVolumeClaim":r=="deployment"?"Deployment":r=="ingress"?"Ingress":r=="node"?"Node":r=="pod"?"Pod":r=="service"?"Service":"Namespace";
    string version=r=="deployment"?"apps/v1":r=="ingress"?"networking.k8s.io/v1":"v1";
    int ns=Array.IndexOf(args,"-n");
    Console.Write("apiVersion: "+version+"\\nkind: "+kind+"\\nmetadata:\\n  name: "+args[p+2]+"\\n  resourceVersion: \\"1\\"\\n"+(ns>=0?"  namespace: "+args[ns+1]+"\\n":""));
  }
  else Console.Write(File.Exists(f)?File.ReadAllText(f):"{\\"items\\":[]}");
  return 0;
} }`);
    execFileSync("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe", ["/nologo", `/out:${path.join(bin, "kubectl.exe")}`, source], { stdio: "pipe" });
  } else {
    const executable = path.join(bin, "kubectl");
    await writeFile(executable, `#!/usr/bin/env node
const fs=require('node:fs'),path=require('node:path');
const d=process.env.BORTUS_FAKE_KUBECTL,a=process.argv.slice(2);
if(!d||!fs.existsSync(d))process.exit(90);
fs.appendFileSync(path.join(d,'calls.log'),a.map(v=>Buffer.from(v).toString('base64')).join(' ')+'\\n');
const p=a.indexOf('get');
Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,50);
if(a.includes('logs')){process.stdout.write('fixture log line\\n');process.exit(0);}
if(p<0){if(fs.existsSync(path.join(d,'allow-flux-sync'))&&a.includes('annotate')&&a.includes('gitrepository')){process.stdout.write(fs.readFileSync(path.join(d,'gitrepository.json'),'utf8'));process.exit(0);}if(fs.existsSync(path.join(d,'allow-rotation-reload'))&&a.includes('patch')&&['deployment','statefulset','daemonset'].includes(a[a.indexOf('patch')+1])){const r=a[a.indexOf('patch')+1];fs.copyFileSync(path.join(d,'rotation-reload.json'),path.join(d,r+'.json'));process.stdout.write(fs.readFileSync(path.join(d,r+'.json'),'utf8'));process.exit(0);}if(fs.existsSync(path.join(d,'allow-flux-mutations'))&&(a.includes('patch')||a.includes('delete'))&&a.some(v=>['gitrepository','kustomization','helmrelease'].includes(v))){process.stdout.write('fixture Flux mutation completed');process.exit(0);}process.stdout.write('private-command-output-marker');process.stderr.write('private-command-error-marker');process.exit(1);}
const f=path.join(d,a[p+1]+'.json');
if(a[p+1]==='kustomizations'){let waited=0;while(fs.existsSync(path.join(d,'hold-flux-discovery'))&&waited<12000){Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,20);waited+=20;}}
const failure=path.join(d,'failure.txt');
if(fs.existsSync(failure)&&['all',a[p+1]].includes(fs.readFileSync(failure,'utf8').trim())){process.stderr.write('private-command-error-marker');process.exit(1);}
const kinds={persistentvolumeclaim:'PersistentVolumeClaim',deployment:'Deployment',ingress:'Ingress',node:'Node',pod:'Pod',service:'Service',namespace:'Namespace'};
const resource=a[p+1],ns=a.indexOf('-n');
const table=path.join(d,resource+'-table.txt');
process.stdout.write(a.some(v=>v.startsWith('custom-columns='))?(fs.existsSync(table)?fs.readFileSync(table,'utf8'):''):a.includes('yaml')?'apiVersion: '+(resource==='deployment'?'apps/v1':resource==='ingress'?'networking.k8s.io/v1':'v1')+'\\nkind: '+kinds[resource]+'\\nmetadata:\\n  name: '+a[p+2]+'\\n  resourceVersion: "1"\\n'+(ns>=0?'  namespace: '+a[ns+1]+'\\n':''):fs.existsSync(f)?fs.readFileSync(f,'utf8'):'{"items":[]}');
`);
    await chmod(executable, 0o755);
  }
  return {
    bin,
    env: { BORTUS_FAKE_KUBECTL: bin, PATH: `${bin}${path.delimiter}${process.env.PATH || ""}` },
    async calls(): Promise<string[][]> {
      const value = await readFile(log, "utf8").catch(error => { if (error.code === "ENOENT") return ""; throw error; });
      return value.trim() ? value.trim().split("\n").map(line => line.split(" ").map(arg => Buffer.from(arg, "base64").toString())) : [];
    },
  };
}
