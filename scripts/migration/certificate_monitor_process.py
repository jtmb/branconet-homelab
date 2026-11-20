"""Bounded local CLI transport for the independent certificate monitor."""
import os
import selectors
import signal
import subprocess
import time


class MonitorProcessError(RuntimeError):
    """Fixed reason codes only: never expose argv, stdin or backend output."""


def run_bounded(command, *, data=None, output_limit, timeout=25, stderr_limit=16384):
    """Drain stdin/stdout/stderr concurrently; enforce limits while reading.

    Each invocation owns a fresh process group. On timeout, output overflow or
    pipe failure, kill/reap only that group, not other tools or services.
    """
    if output_limit < 1 or stderr_limit < 1 or timeout <= 0:
        raise ValueError("invalid_process_limit")
    if data is not None and len(data) > 512 * 1024:
        raise MonitorProcessError("process_input_limit")
    try:
        child = subprocess.Popen(command, stdin=subprocess.PIPE if data else subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError:
        raise MonitorProcessError("process_unavailable") from None
    output = bytearray()
    stderr_bytes = 0
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (child.stdout, child.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            pending = memoryview(data or b"")
            if child.stdin:
                os.set_blocking(child.stdin.fileno(), False)
                selector.register(child.stdin, selectors.EVENT_WRITE)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MonitorProcessError("process_timeout")
                for key, _ in selector.select(remaining):
                    stream = key.fileobj
                    if stream is child.stdin:
                        try:
                            count = os.write(stream.fileno(), pending[:65536])
                        except BlockingIOError:
                            continue
                        pending = pending[count:]
                        if not pending:
                            selector.unregister(stream)
                            stream.close()
                    else:
                        try:
                            chunk = os.read(stream.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(stream)
                            continue
                        if stream is child.stdout:
                            if len(output) + len(chunk) > output_limit:
                                raise MonitorProcessError("process_output_limit")
                            output.extend(chunk)
                        else:
                            stderr_bytes += len(chunk)
                            if stderr_bytes > stderr_limit:
                                raise MonitorProcessError("process_stderr_limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MonitorProcessError("process_timeout")
            try:
                code = child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                raise MonitorProcessError("process_timeout") from None
            if code:
                raise MonitorProcessError("process_failed")
            return bytes(output)
    except OSError:
        raise MonitorProcessError("process_io_failed") from None
    finally:
        # Descendants can retain pipes even after the CLI exits. The group was
        # created here and cannot contain unrelated pre-existing processes.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream:
                stream.close()
