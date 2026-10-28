"""Source-only candidate helper: guarded package edits and real publish checks."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

PACKAGES = {
    'Jackett.Server': {
        'Microsoft.AspNetCore.Mvc.NewtonsoftJson',
        'Microsoft.Extensions.Configuration',
        'System.Security.Cryptography.ProtectedData',
        'System.ServiceProcess.ServiceController',
        'System.Text.Encoding.CodePages',
    },
    'Jackett.Common': {
        'System.ServiceProcess.ServiceController',
        'System.Text.Encoding.CodePages',
        'System.Text.Json',
    },
}


def hashes(root, pattern):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob(pattern)) if p.is_file()}


def prepare(source, evidence):
    before = hashes(source, '*.cs')
    changed = {}
    for project, expected in PACKAGES.items():
        path = source / 'src' / project / (project + '.csproj')
        content = path.read_text()
        references = ET.fromstring(content).findall('.//PackageReference')
        actual = {item.attrib['Include'] for item in references
                  if item.get('Version') == '9.0.14'}
        if actual != expected:
            raise SystemExit('Pinned project package layout differs: ' + project)
        for name in sorted(expected):
            old = f'Include="{name}" Version="9.0.14"'
            if content.count(old) != 1:
                raise SystemExit('Pinned package reference differs: ' + name)
            content = content.replace(old, f'Include="{name}" Version="9.0.21"')
        path.write_text(content)
        changed[str(path.relative_to(source))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if before != hashes(source, '*.cs'):
        raise SystemExit('Application C# source changed unexpectedly')
    (source / 'NuGet.runtime.config').write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<configuration><packageSources><clear />'
        '<add key="nuget.org" value="https://api.nuget.org/v3/index.json" />'
        '</packageSources></configuration>\n')
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / 'source.json').write_text(json.dumps({
        'commit': '141e2013ecc872a51365db8491ea2728ebbbc763',
        'version': '0.24.1440', 'csharpUnchanged': before,
        'projectFilesAfter': changed, 'packageVersionBefore': '9.0.14',
        'packageVersionAfter': '9.0.21', 'publishedOrAccepted': False,
    }, indent=2) + '\n')


def verify(output, evidence):
    manifests = {}
    for app in ('jackett', 'JackettUpdater'):
        path = output / (app + '.deps.json')
        data = json.loads(path.read_text())
        libraries = data['libraries']
        runtime = [key for key in libraries if 'Microsoft.NETCore.App.Runtime.' in key]
        aspnet = [key for key in libraries if 'Microsoft.AspNetCore.App.Runtime.' in key]
        if not runtime or any(not key.endswith('/9.0.21') for key in runtime + aspnet):
            raise SystemExit('Unexpected published runtime pack: ' + app)
        if app == 'jackett' and not aspnet:
            raise SystemExit('Server ASP.NET runtime pack missing')
        old = [key for key in libraries if key.endswith('/9.0.14')]
        if old:
            raise SystemExit('Old .NET package remains in actual publish: ' + ','.join(old))
        manifests[app] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'runtimePacks': runtime, 'aspnetPacks': aspnet}
    for name in ('jackett', 'JackettUpdater', 'libcoreclr.so', 'libhostfxr.so',
                 'System.Private.CoreLib.dll', 'Microsoft.AspNetCore.Server.Kestrel.Core.dll'):
        if not (output / name).is_file() or (output / name).stat().st_size == 0:
            raise SystemExit('Actual published runtime file missing: ' + name)
    (evidence / 'publish.json').write_text(json.dumps({
        'manifests': manifests, 'fileSHA256': hashes(output, '*'),
        'runtimeVersion': '9.0.21', 'applicationRunOrAccepted': False,
    }, indent=2) + '\n')


def retain_locks(source, evidence):
    for project in ('DateTimeRoutines', 'Jackett.Common', 'Jackett.Server', 'Jackett.Updater'):
        relative = Path('src') / project / 'packages.lock.json'
        original = source / relative
        data = json.loads(original.read_text())
        if not data.get('dependencies'):
            raise SystemExit('Resolved dependency lock missing: ' + project)
        destination = evidence / 'locks' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)


if __name__ == '__main__':
    mode, source, evidence = sys.argv[1:]
    if mode == 'prepare':
        prepare(Path(source), Path(evidence))
    elif mode == 'verify':
        verify(Path(source), Path(evidence))
    elif mode == 'locks':
        retain_locks(Path(source), Path(evidence))
    else:
        raise SystemExit('Expected prepare, verify or locks')
