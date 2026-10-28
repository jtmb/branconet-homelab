"""Read-only unit/process/open-file/map/mount exclusions for generated cleanup."""

import argparse

import datetime

import errno

import fcntl

import hashlib

import json

import os

from pathlib import Path

import re

import socket

import stat

import subprocess

import time

def need(condition, reason):
    if not condition:
        raise ValueError(reason)

def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=45)

def idle():
    # Check whole attempt roots; a daemon referencing sibling state also refuses.
    def under(value):
        value = value.removesuffix(' (deleted)')
        return any(value == str(BASE / n) or value.startswith(str(BASE / n) + '/') for n in ATTEMPTS)
    names = sorted({line.split()[0] for line in command('systemctl', 'list-units', '--all', '--state=active,activating,deactivating', '--plain', '--no-legend', '--no-pager').splitlines() if line.strip()})
    need(names and all(re.fullmatch(r'[A-Za-z0-9_.@:\\-]+', n) for n in names), 'unit_inventory')
    raw = command('systemctl', 'show', '--no-pager', '--property=Id,ExecStart,WorkingDirectory', '--', *names)
    # ExecStart can contain literal newlines and blank lines. Treat its full
    # output as opaque text; prove completeness separately with Id-only output.
    ids = command('systemctl', 'show', '--no-pager', '--property=Id', '--value', '--', *names)
    actual_ids = [line for line in ids.splitlines() if line]
    need(set(actual_ids) == set(names) and len(actual_ids) == len(names), 'incomplete_unit_inventory')
    need(not any(str(BASE / n) in raw for n in ATTEMPTS), 'active_unit_reference')
    checked = 0
    namespaces = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            checked += 1
            commandline = (proc / 'cmdline').read_bytes()
            need(not any(str(BASE / n).encode() in commandline for n in ATTEMPTS), 'process_argument_reference')
            for p in [proc / 'cwd', proc / 'root', proc / 'exe', *(proc / 'fd').iterdir()]:
                try:
                    need(not under(os.readlink(p)), 'active_process_reference')
                except OSError as e:
                    if e.errno not in (errno.ENOENT, errno.ESRCH):
                        raise
            for line in (proc / 'maps').read_text().splitlines():
                fields = line.split(None, 5)
                need(len(fields) != 6 or not under(fields[5]), 'mapped_tool_reference')
            ns = (proc / 'ns/mnt').stat().st_ino
            if ns not in namespaces:
                namespaces.add(ns)
                for line in (proc / 'mountinfo').read_text().splitlines():
                    fields = line.split()
                    # Includes overlay lowerdir/upperdir/workdir as well as bind roots.
                    decoded = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), line)
                    need(not any(str(BASE / n) in decoded for n in ATTEMPTS), 'mount_reference')
        except OSError as e:
            if e.errno not in (errno.ENOENT, errno.ESRCH):
                raise
    return {'processes': checked, 'mountNamespaces': len(namespaces), 'units': len(actual_ids), 'unitInventorySHA256': hashlib.sha256(raw.encode()).hexdigest()}
