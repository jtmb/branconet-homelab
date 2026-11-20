#!/usr/bin/env python3
"""Read effective ancestor limits, including a delegated controller subgroup."""
from pathlib import Path


def current():
    path = next(line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    root, group = Path('/sys/fs/cgroup'), Path('/sys/fs/cgroup') / path.lstrip('/')
    memory, cpu, unit = [], [], None
    cursor = group
    while cursor.is_relative_to(root):
        if cursor.name.endswith('.service') and unit is None:
            unit = '/' + cursor.relative_to(root).as_posix()
        limit = (cursor / 'memory.max')
        if limit.exists():
            value = limit.read_text().strip()
            if value != 'max':
                memory.append(int(value))
        limit = cursor / 'cpu.max'
        if limit.exists():
            values = limit.read_text().split()
            if values[0] != 'max':
                cpu.append(int(values[0]) / int(values[1]))
        if cursor == root:
            break
        cursor = cursor.parent
    if not memory or not cpu or not 0 < min(memory) <= 4294967296 or not 0 < min(cpu) <= 1.5:
        raise RuntimeError('Original effective 4GiB/1.5CPU limits must remain active')
    return {'currentPath': path, 'unitPath': unit,
            'effectiveMemoryMaxBytes': min(memory), 'effectiveCpuCores': min(cpu)}
