#!/usr/bin/env python3
"""Bounded routed load and cap refusal on memory-only copies of synthetic DBs."""
import argparse
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import ssl
import statistics
import subprocess
import time
from urllib.parse import urlsplit

from certificate_monitor_notifications import PinnedHTTPSConnection
from ntfy_cluster_fixture import NAMESPACE, EDGE

spec = importlib.util.spec_from_file_location("owned_cluster_path", Path(__file__).with_name("qualify-ntfy-cluster-path.py"))
path = importlib.util.module_from_spec(spec)
spec.loader.exec_module(path)
WORK, BASE, call, save, exec_read, pod = path.WORK, path.BASE, path.call, path.save, path.exec_read, path.pod


def inspect_db(raw, cap):
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.deserialize(raw)
        assert connection.execute("pragma integrity_check").fetchone()[0] == "ok"
        page_size = connection.execute("pragma page_size").fetchone()[0]
        original_pages = connection.execute("pragma page_count").fetchone()[0]
        copy_initial_max = connection.execute("pragma max_page_count").fetchone()[0]
        maximum = connection.execute("pragma max_page_count=" + str(cap)).fetchone()[0]
        assert maximum == cap and page_size == 4096
        connection.execute("create table independent_cap_probe(value blob)")
        allocated = 0
        while allocated <= 80 * 1024**2:
            try:
                connection.execute("insert into independent_cap_probe values (zeroblob(16384))")
                allocated += 16384
            except sqlite3.OperationalError as error:
                assert error.sqlite_errorcode == sqlite3.SQLITE_FULL
                break
        else:
            raise RuntimeError("independent_db_cap_not_enforced")
        return {"originalFileBytes": len(raw), "originalPageSize": page_size,
                "originalPageCount": original_pages,
                "independentConnectionInitialMaxPages": copy_initial_max,
                "configuredCapAppliedToIndependentCopy": maximum,
                "independentFullRefusal": True, "copyPayloadBytesBeforeRefusal": allocated,
                "serverConnectionMaxPagesQueried": False,
                "originalLiveDBModifiedByProbe": False}
    finally:
        connection.close()


def finish_observations(observed):
    backend = pod(NAMESPACE, "app=ntfy-qualification")
    observed["runtime"] = exec_read(NAMESPACE, backend["metadata"]["name"], ["/bin/sh", "-ec",
        "for f in memory.current memory.peak memory.events cpu.stat pids.current pids.max; "
        "do echo $f; if test -r /sys/fs/cgroup/$f; then cat /sys/fs/cgroup/$f; "
        "else echo not-exposed-by-kernel; fi; done; "
        "grep -E '^(VmRSS|Threads):' /proc/1/status; du -k /cache /auth /tmp"]).decode()
    staged = json.loads((WORK / "stage-result.json").read_text())
    claim = call(["get", "pvc", "private-ntfy-qualification-cache", "-n", NAMESPACE, "-o", "json"])
    assert claim["metadata"]["uid"] == staged["claim"]["uid"]
    volume = call(["get", "volumes.longhorn.io", staged["longhorn"]["name"],
                   "-n", "longhorn-system", "-o", "json"])
    assert volume["metadata"]["uid"] == staged["longhorn"]["uid"] and volume["status"]["robustness"] == "healthy"
    replicas = call(["get", "replicas.longhorn.io", "-n", "longhorn-system", "-o", "json"])["items"]
    matches = [r for r in replicas if r["spec"].get("volumeName") == staged["longhorn"]["name"]]
    assert len(matches) == 2 and all(r["status"].get("currentState") == "running" for r in matches)
    observed["replicas"] = [{"uid": r["metadata"]["uid"], "node": r["spec"].get("nodeID"),
                             "state": r["status"].get("currentState")} for r in matches]
    result = {"passed": True, "observations": observed, "productionChanged": False,
        "serverMaxPageCountIndependentlyObserved": False,
        "livePIDsCeiling": "Existing kubelet ceiling; observed separately, not local Docker64",
        "memoryPeak": "Unavailable if not exposed by this kernel; not a sampled peak claim",
        "remaining": ["Installed autonomous rotation/monitor/watchdog/attended/lifecycle/network acceptance"]}
    save("state-result.json", result)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finish-observations", action="store_true")
    if parser.parse_args().finish_observations:
        assert not (WORK / "state-result.json").exists()
        previous = json.loads((WORK / "state-failure.json").read_text())
        observed = previous["observations"]
        assert observed["boundedLoad"]["messages"] == 20 and observed["boundedLoad"]["errors"] == 0
        assert observed["cache"]["independentFullRefusal"] and observed["auth"]["independentFullRefusal"]
        save("state-finish-started.json", {"reason": "Finish resource/replica metadata only; no repeat messages or cap probes",
                                         "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        finish_observations(observed)
        return
    assert json.loads((WORK / "path-result.json").read_text())["passed"]
    assert not (WORK / "state-started.json").exists(), "reconcile_existing_state_check"
    save("state-started.json", {"sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "maximumMessages": 20, "maximumSubscribers": 3, "messageMaximumBytes": 4096,
        "copyPayloadMaximumBytes": 80 * 1024**2, "maximumSeconds": 180})
    backend = pod(NAMESPACE, "app=ntfy-qualification")
    edge = pod(EDGE, "app=ntfy-edge")
    deadline = time.monotonic() + 180
    tokens = json.loads((WORK / "synthetic-client.json").read_text())["tokens"]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    context = ssl.create_default_context(cafile=str(WORK / "public-fixture-ca.crt"))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with (WORK / "state-forward.log").open("xb") as output:
        forward = subprocess.Popen(BASE + ["port-forward", "-n", EDGE, "pod/" + edge["metadata"]["name"],
            f"{port}:8443", "--address=127.0.0.1"], stdout=output, stderr=subprocess.STDOUT)
    observed = {}
    try:
        def request(method, target, token, body=None):
            c = PinnedHTTPSConnection(urlsplit(f"https://{path.NAME}:{port}/"), "127.0.0.1", context)
            try:
                c.request(method, target, body=body, headers={"Authorization": "Bearer " + token})
                response = c.getresponse()
                raw = response.read(256 * 1024 + 1)
                assert len(raw) <= 256 * 1024 and response.status == 200
                return raw
            finally:
                c.close()
        started = time.monotonic()
        while True:
            try:
                request("GET", "/v1/health", tokens[2])
                break
            except (OSError, http.client.HTTPException):
                pass
            assert time.monotonic() - started < 20 and forward.poll() is None
            time.sleep(.2)
        ids, durations = [], []
        for index in range(20):
            t = time.monotonic()
            data = json.loads(request("POST", "/bortus-certificates", tokens[0],
                                     ("bounded-cluster-" + str(index)).encode()))
            durations.append((time.monotonic() - t) * 1000)
            ids.append(data["id"])
            assert time.monotonic() < deadline
        # Three concurrent bounded poll subscribers, not a persistent fan-out
        # benchmark. Credentials remain only in parent memory.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(request, "GET", "/bortus-certificates/json?poll=1&since=all", tokens[2])
                       for _ in range(3)]
            for future in futures:
                received = {json.loads(line).get("id") for line in future.result(timeout=10).splitlines()}
                assert set(ids) <= received
        observed["boundedLoad"] = {"messages": 20, "concurrentPollSubscribers": 3,
            "errors": 0, "publishP50Millis": statistics.median(durations),
            "publishP95Millis": sorted(durations)[18], "soakStressOrCapacityClaim": False}
        name = backend["metadata"]["name"]
        cache = exec_read(NAMESPACE, name, ["cat", "/cache/cache.db"], limit=4 * 1024**2)
        auth = exec_read(NAMESPACE, name, ["cat", "/auth/user.db"], limit=4 * 1024**2)
        observed["cache"] = inspect_db(cache, 16384)
        observed["auth"] = inspect_db(auth, 1024)
        assert sum(observed[n]["copyPayloadBytesBeforeRefusal"] for n in ("cache", "auth")) <= 80 * 1024**2
        assert time.monotonic() < deadline
        finish_observations(observed)
    except Exception as error:
        save("state-failure.json", {"reason": type(error).__name__, "observations": observed,
                                   "reconcileBeforeRetry": True})
        raise
    finally:
        forward.terminate()
        try:
            forward.wait(timeout=10)
        except subprocess.TimeoutExpired:
            forward.kill()
            forward.wait(timeout=5)


if __name__ == "__main__":
    main()
