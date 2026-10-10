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
  if(p<0) { Console.Write("private-command-output-marker"); Console.Error.Write("private-command-error-marker"); return 1; }
  string r=args[p+1]; string f=Path.Combine(d,r+".json");
  if(Array.IndexOf(args,"yaml")>=0) Console.Write("apiVersion: v1\\nkind: Namespace\\nmetadata:\\n  name: apps\\n");
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
if(p<0){process.stdout.write('private-command-output-marker');process.stderr.write('private-command-error-marker');process.exit(1);}
const f=path.join(d,a[p+1]+'.json');
process.stdout.write(a.includes('yaml')?'apiVersion: v1\\nkind: Namespace\\nmetadata:\\n  name: apps\\n':fs.existsSync(f)?fs.readFileSync(f,'utf8'):'{"items":[]}');
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
