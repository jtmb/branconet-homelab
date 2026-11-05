"""Bounded read-only focused-result qualification; never launches application tests."""
import hashlib
import json
import pathlib
import re
import subprocess

OUT = pathlib.Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OWNER = pathlib.Path(r"\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\configuration-json-focused-20261015-v1")
PREP = ROOT / "docs/implementation-evidence/configuration-json-focused-preparation"
FRONT = ROOT / "k8s-rewrite/front-end"
sha = lambda b: hashlib.sha256(b).hexdigest()
read = lambda p: json.loads(p.read_bytes())
records = []

def retain(relative):
    source = OWNER / relative
    data = source.read_bytes()
    assert len(data) <= 1048576, "Retained record exceeds fixed bound"
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    assert target.read_bytes() == source.read_bytes()
    records.append(dict(path=relative, bytes=len(data), sha256=sha(data)))
    return data

manifest = read(PREP / "manifest.json")
expectations = read(PREP / "expectations.json")
mutations = read(PREP / "mutations.json")
pins = []
for row in manifest:
    current = (FRONT / row["path"]).read_bytes()
    staged = (OWNER / "source" / row["path"]).read_bytes()
    assert sha(current) == row["sha256"] and staged == current
    pins.append(dict(kind="source", path=row["path"], bytes=len(current), sha256=sha(current)))
for name in ["controller.py", "run.cjs", "manifest.json", "mutations.json", "expectations.json"]:
    current = (PREP / name).read_bytes()
    assert current == (OWNER / name).read_bytes()
    pins.append(dict(kind="packet", path=name, bytes=len(current), sha256=sha(current)))
assert len(pins) == 16
dispatch = json.loads(retain("dispatch-terminal.json"))
staged = json.loads(retain("staged.json"))
retain("started.json")
assert dispatch["actualExit"] == 0 and dispatch["stagedFilesUnchanged"]
assert dispatch["durationSeconds"] < 220
assert staged["stagedFiles"] == 16 and staged["sourceFiles"] == 11
assert staged["boot"] == "19d54e89-533f-46e2-b89d-25657251c8d7"
results = []
for mode in ["pristine", "old-parse", "save-noop", "remove-noop"]:
    expected = expectations[mode]
    assert next(r for r in dispatch["controllers"] if r["mode"] == mode)["controllerExit"] == 0
    outer = json.loads(retain(mode + "/outer-terminal.json"))
    complete = json.loads(retain(mode + "/" + mode + "-complete.json"))
    status = json.loads(retain(mode + "/" + mode + "-status.json"))
    out = retain(mode + "/" + mode + ".stdout")
    err = retain(mode + "/" + mode + ".stderr")
    assert complete["record"] == status
    assert outer["actualExit"] == 0 and outer["primary"] is None and not outer["createUncertain"]
    assert outer["sourceUnchanged"] and not outer["oldCorpusReplayed"]
    assert outer["cleanup"] == dict(actualExit=0, exactCIDAbsent=True, exactNameAbsent=True)
    assert complete["runnerError"] is None and complete["restorationFailures"] == []
    assert complete["sourceUnchanged"] and complete["noOldCorpus"] and not complete["browserEvidence"]
    assert status["status"] == expected["exit"] and status["signal"] is None and status["errorCode"] is None
    assert err == b"" and sha(out) == status["stdoutSHA256"] and sha(err) == status["stderrSHA256"]
    assert len(out) == status["stdoutBytes"] and len(err) == status["stderrBytes"]
    assert status["testSHA256"] == next(r["sha256"] for r in manifest if r["path"] == "tests/request-json-response.test.ts")
    if mode == "pristine":
        assert status["sourceMutation"] is None
    else:
        assert status["sourceMutation"] == {k: mutations[mode][k] for k in ["path", "mutantSHA256"]}
    text = out.decode("utf-8")
    failures = re.findall(r"^not ok \d+ - (.+)$", text, re.M)
    successes = re.findall(r"^ok \d+ - (.+)$", text, re.M)
    assert failures == [r["name"] for r in expected["failures"]]
    assert len(successes) + len(failures) == 5
    for label, count in [("tests", 5), ("pass", len(successes)), ("fail", len(failures)), ("cancelled", 0), ("skipped", 0), ("todo", 0)]:
        assert re.search(r"^# " + label + " " + str(count) + r"$", text, re.M)
    for witness in expected["failures"]:
        block = re.search(r"^not ok \d+ - " + re.escape(witness["name"]) + r"\n(.*?)(?=^(?:ok|not ok) \d+ - |\Z)", text, re.M | re.S).group(1)
        for token in ["failureType: 'testCodeFailure'", "code: 'ERR_ASSERTION'", "name: 'AssertionError'", "operator: '" + witness["operator"] + "'"]:
            assert token in block
        assert re.search(r"request-json-response\.test\.ts:" + str(witness["line"]) + r":\d+", block)
    created = json.loads(retain(mode + "/created-inspect.json"))[0]
    completed = json.loads(retain(mode + "/completed-inspect.json"))[0]
    cid = retain(mode + "/container.cid").decode().strip()
    name = "bortus-configuration-json-focused-20261015-v1-" + mode
    assert re.fullmatch("[a-f0-9]{64}", cid) and cid == outer["confirmedOwnedCID"]
    assert created["Id"] == completed["Id"] == cid and created["Name"] == completed["Name"] == "/" + name
    assert completed["State"]["Running"] is False and completed["State"]["ExitCode"] == 0
    host = created["HostConfig"]
    assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
    assert host["NanoCpus"] == 2000000000 and host["Memory"] == host["MemorySwap"] == 1073741824
    assert host["PidsLimit"] == 256 and created["Config"]["User"] == "1000:1000"
    assert created["Config"]["Image"] == "node@sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d"
    for suffix in ["create.stdout", "create.stderr", "remove.stdout", "remove.stderr"]:
        retain(mode + "/" + suffix)
    assert (OUT / mode / "create.stdout").read_text().strip() == cid
    assert (OUT / mode / "remove.stdout").read_text().strip() == cid
    # One fresh exact CID/name query pair per mode; no host-birth or self-absence chain.
    absent = subprocess.run(["wsl.exe", "-d", "Ubuntu", "--", "/usr/bin/docker", "inspect", "--format", "{{.Id}}", cid], capture_output=True, timeout=10)
    named = subprocess.run(["wsl.exe", "-d", "Ubuntu", "--", "/usr/bin/docker", "container", "ls", "-aq", "--filter", "name=^/" + name + "$"], capture_output=True, timeout=10)
    assert absent.returncode != 0 and not absent.stdout.strip() and named.returncode == 0 and not named.stdout.strip()
    results.append(dict(mode=mode, actualOuterExit=0, actualChildExit=status["status"], tests=5, passed=len(successes), failed=len(failures),
                        failureWitnesses=expected["failures"], completeSourceRestoration=True, cid=cid, name=name,
                        freshExactCIDAbsent=True, freshExactNameAbsent=True))
for pin in pins:
    target = FRONT / pin["path"] if pin["kind"] == "source" else PREP / pin["path"]
    assert sha(target.read_bytes()) == pin["sha256"]
result = dict(status="FOCUSED QUALIFICATION PASSED", sourceAndPacketPins=pins, sourceFiles=11, packetFiles=5, sourceAndStagedBytesCurrent=True,
              results=results, dispatchSeconds=dispatch["durationSeconds"], retainedRecords=records, hostPIDStartOrAllBirthProofClaimed=False,
              qualificationScope="Five realHTTP helper/decoder/QueryStore/MutationTask tests and three exact sensitivity controls; no new functional test execution by qualifier.")
(OUT / "qualification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(status=result["status"], sourceFiles=11, packetFiles=5, modes=4, records=len(records), exactCIDNamePairsAbsent=4)))
