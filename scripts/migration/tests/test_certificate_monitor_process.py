import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from certificate_monitor_process import MonitorProcessError, run_bounded


class ProcessTests(unittest.TestCase):
    def run_python(self, source, **options):
        return run_bounded([sys.executable, "-B", "-c", source], **options)

    def test_large_patch_input_and_output_are_drained_concurrently(self):
        # A sequential write-then-read implementation can deadlock on full pipes.
        data = b"x" * (256 * 1024)
        result = self.run_python(
            "import sys; sys.stdout.buffer.write(b'y'*131072); sys.stdout.flush(); "
            "body=sys.stdin.buffer.read(); sys.stdout.buffer.write(str(len(body)).encode())",
            data=data, output_limit=256 * 1024, timeout=5)
        self.assertEqual(result, b"y" * 131072 + b"262144")

    def test_stdout_and_stderr_floods_are_stopped_at_the_transport_boundary(self):
        for stream, code in (("stdout", "process_output_limit"), ("stderr", "process_stderr_limit")):
            with self.subTest(stream=stream):
                with self.assertRaisesRegex(MonitorProcessError, "^" + code + "$"):
                    self.run_python(
                        f"import os,sys; fd=sys.{stream}.fileno()\nwhile True: os.write(fd,b'x'*8192)",
                        output_limit=1024, stderr_limit=1024, timeout=5)

    def test_failure_does_not_disclose_backend_output_or_command(self):
        with self.assertRaises(MonitorProcessError) as error:
            self.run_python("import sys; sys.stderr.write('sensitive-fixture-value'); sys.exit(7)",
                            output_limit=1024, timeout=5)
        self.assertEqual(str(error.exception), "process_failed")
        self.assertNotIn("sensitive-fixture-value", str(error.exception))

    def test_deadline_also_covers_descendants_holding_the_output_pipes(self):
        # The direct CLI exits, but its task-owned child keeps both pipes open.
        with self.assertRaisesRegex(MonitorProcessError, "^process_timeout$"):
            self.run_python(
                "import os,signal\n"
                "if os.fork()==0: signal.pause()\n"
                "else: os._exit(0)",
                output_limit=1024, timeout=0.2)


if __name__ == "__main__":
    unittest.main()
