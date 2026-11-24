#!/usr/bin/env python3
"""Closed preparation/control admission; never a full compiler/image permit."""
import datetime as dt
import json
import importlib.util
import os
from pathlib import Path
import time


def admit(operator, report, lease_path):
    def need(value, message):
        if not value:
            raise RuntimeError(message)
    need(os.getuid() == 0 and lease_path.resolve() == lease_path and
         lease_path.is_relative_to(operator.ROOT), 'Original root-owned confined probe lease required')
    lease = json.loads(lease_path.read_text())
    age = time.time() - dt.datetime.fromisoformat(lease['at'].replace('Z', '+00:00')).timestamp()
    need(lease['owner'] == operator.OWNER and lease['platform'] == 'linux' and
         lease['purpose'] == 'context-oci-qualification' and lease['exclusive'] is True and
         lease['nativeStageActive'] is False and 0 <= age < 180,
         'Fresh original exclusive closed-probe lease required')
    need(lease['sourceRevision'] == report['source']['revision'] and
         lease['sourceSha256'] == report['source']['sourceSha256'] and
         lease['extensionSha256'] == report['extension']['sourceSha256'], 'Original probe identity differs')
    need(lease['growthBytes'] == 768 * 1024**2 and type(lease['nativeBudgetBytes']) is int and
         lease['nativeBudgetBytes'] > 0, 'Complete bounded-probe peak required')
    live = operator.task_allocated()
    need(live + lease['nativeBudgetBytes'] + lease['growthBytes'] <= operator.CEILING and
         report['windowsFreeBytes'] - lease['growthBytes'] >= operator.FLOOR and
         report['destinationFreeBytes'] - lease['growthBytes'] >= operator.FLOOR,
         'Original paired cap or reserves do not admit this probe')
    path = Path(__file__).with_name('veyra-linux-cgroup-limits.py')
    spec = importlib.util.spec_from_file_location('veyra_effective_cgroups', path)
    limits = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(limits)
    lease['effectiveCgroup'] = limits.current()
    need(lease.get('fullCompilerAdmitted') is False, 'Probe must not claim compiler/image authority')
    lease['_admittedProcess'] = [os.getpid(), operator.birth(os.getpid())]
    lease['_admittedRoot'] = [operator.ROOT.stat().st_dev, operator.ROOT.stat().st_ino]
    return lease


def retained(operator, report, lease, receipt):
    if (lease is not receipt.get('closedProbeAdmission') or
            lease.get('_admittedProcess') != [os.getpid(), operator.birth(os.getpid())] or
            lease.get('_admittedRoot') != [operator.ROOT.stat().st_dev, operator.ROOT.stat().st_ino] or
            lease.get('purpose') != 'context-oci-qualification' or
            lease.get('sourceSha256') != report['source']['sourceSha256']):
        raise RuntimeError('Only this same live originally admitted closed probe may continue')
    return lease
