import { execFileSync } from "node:child_process";
import { mkdir, writeFile, readFile, chmod } from "node:fs/promises";
import path from "node:path";

/** Owned synthetic child: emits deliberately private raw output and fixed progress. */
export async function fakeAnsible(dir: string) {
  const bin = path.join(dir, "ansible-bin"); await mkdir(bin);
  if (process.platform === "win32") {
    const source = path.join(bin, "fixture.cs");
    await writeFile(source, `using System; using System.IO; using System.Text; using System.Threading;
class Fixture { static int Main(string[] args) {
  string d=Environment.GetEnvironmentVariable("BORTUS_FAKE_ANSIBLE"); if(String.IsNullOrEmpty(d)||!Directory.Exists(d)) return 90;
  File.AppendAllText(Path.Combine(d,"calls.log"),String.Join(" ",Array.ConvertAll(args,a=>Convert.ToBase64String(Encoding.UTF8.GetBytes(a))))+"\\n");
  string plugin=Environment.GetEnvironmentVariable("ANSIBLE_CALLBACK_PLUGINS");
  bool safe=Environment.GetEnvironmentVariable("ANSIBLE_STDOUT_CALLBACK")=="bortus_progress"&&File.Exists(Path.Combine(plugin,"bortus_progress.py"))&&Environment.GetEnvironmentVariable("ANSIBLE_LOG_PATH")=="NUL";
  File.WriteAllText(Path.Combine(d,"environment-status.json"),safe?"{\\"fixedCallback\\":true}":"{\\"fixedCallback\\":false}");
  Console.WriteLine("TASK ["+Environment.GetEnvironmentVariable("ANSIBLE_BECOME_PASSWORD")+" : private task]");
  Console.Error.WriteLine("module stderr "+Environment.GetEnvironmentVariable("BOTRUS_SECRETS_KEY"));
  string mode=File.ReadAllText(Path.Combine(d,"mode.txt")).Trim(); if(mode=="unsupported") return 0;
  Console.Write("BORTUS_PROGRESS_V1 start\\nBORTUS_PROGRESS_V1 role:kubernetes:running\\n"); Console.Out.Flush();
  Thread.Sleep(mode=="slow"?10000:700);
  Console.Write("BORTUS_PROGRESS_V1 complete:"+(mode=="failed"?"failed":"success")+"\\n"); return mode=="failed"?9:0;
} }`);
    execFileSync("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe", ["/nologo", `/out:${path.join(bin, "ansible-playbook.exe")}`, source], { stdio: "pipe" });
  } else {
    const executable = path.join(bin, "ansible-playbook");
    await writeFile(executable, `#!/usr/bin/env node
const fs=require('node:fs'),path=require('node:path'),d=process.env.BORTUS_FAKE_ANSIBLE;
if(!d||!fs.existsSync(d))process.exit(90);
fs.appendFileSync(path.join(d,'calls.log'),process.argv.slice(2).map(v=>Buffer.from(v).toString('base64')).join(' ')+'\\n');
fs.writeFileSync(path.join(d,'environment-status.json'),JSON.stringify({fixedCallback:process.env.ANSIBLE_STDOUT_CALLBACK==='bortus_progress'&&fs.existsSync(path.join(process.env.ANSIBLE_CALLBACK_PLUGINS,'bortus_progress.py'))&&process.env.ANSIBLE_LOG_PATH==='/dev/null'}));
process.stdout.write('TASK ['+process.env.ANSIBLE_BECOME_PASSWORD+' : private task]\\n');process.stderr.write('module stderr '+process.env.BOTRUS_SECRETS_KEY+'\\n');
const mode=fs.readFileSync(path.join(d,'mode.txt'),'utf8').trim();if(mode==='unsupported')process.exit(0);
process.stdout.write('BORTUS_PROGRESS_V1 start\\nBORTUS_PROGRESS_V1 role:kubernetes:running\\n');
setTimeout(()=>{process.stdout.write('BORTUS_PROGRESS_V1 complete:'+(mode==='failed'?'failed':'success')+'\\n');process.exit(mode==='failed'?9:0);},mode==='slow'?10000:700);
`); await chmod(executable, 0o755);
  }
  return {
    bin,
    env: { BORTUS_FAKE_ANSIBLE: bin, PATH: bin + path.delimiter + (process.env.PATH || "") },
    async calls() { const raw = await readFile(path.join(bin, "calls.log"), "utf8").catch(error => { if (error.code === "ENOENT") return ""; throw error; });
      return raw.trim() ? raw.trim().split("\n").map(line => line.split(" ").map(arg => Buffer.from(arg, "base64").toString())) : []; },
    async mode(mode: "success" | "failed" | "unsupported" | "slow") { await writeFile(path.join(bin, "mode.txt"), mode); },
    async callbackSafe() { return JSON.parse(await readFile(path.join(bin, "environment-status.json"), "utf8")).fixedCallback === true; },
  };
}
