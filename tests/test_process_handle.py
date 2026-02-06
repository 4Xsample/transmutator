"""Tests for ProcessHandle subprocess control."""

import subprocess
import pytest

from src.converter import ProcessHandle


class TestProcessHandleInit:
    """Initial state and no-op safety."""

    def test_initial_state(self):
        handle = ProcessHandle()
        assert handle.process is None
        assert not handle.is_paused

    def test_kill_no_process(self):
        handle = ProcessHandle()
        handle.kill()  # must not raise

    def test_pause_no_process(self):
        handle = ProcessHandle()
        handle.pause()
        assert not handle.is_paused

    def test_resume_no_process(self):
        handle = ProcessHandle()
        handle.resume()


class TestProcessHandleKill:
    """Killing a subprocess."""

    def test_kill_running_process(self):
        handle = ProcessHandle()
        process = subprocess.Popen(
            ["sleep", "60"],
            start_new_session=True,
        )
        handle.process = process
        assert process.poll() is None

        handle.kill()
        process.wait(timeout=5)
        assert process.poll() is not None

    def test_kill_already_dead(self):
        handle = ProcessHandle()
        process = subprocess.Popen(
            ["true"],
            start_new_session=True,
        )
        process.wait(timeout=5)
        handle.process = process
        handle.kill()  # must not raise


class TestProcessHandlePauseResume:
    """Pause (SIGSTOP) and resume (SIGCONT)."""

    def test_pause_sets_flag(self):
        handle = ProcessHandle()
        process = subprocess.Popen(["sleep", "60"], start_new_session=True)
        handle.process = process

        handle.pause()
        assert handle.is_paused

        handle.resume()
        handle.kill()
        process.wait(timeout=5)

    def test_resume_clears_flag(self):
        handle = ProcessHandle()
        process = subprocess.Popen(["sleep", "60"], start_new_session=True)
        handle.process = process

        handle.pause()
        assert handle.is_paused
        handle.resume()
        assert not handle.is_paused

        handle.kill()
        process.wait(timeout=5)

    def test_kill_while_paused(self):
        handle = ProcessHandle()
        process = subprocess.Popen(["sleep", "60"], start_new_session=True)
        handle.process = process

        handle.pause()
        assert handle.is_paused

        handle.kill()
        process.wait(timeout=5)
        assert process.poll() is not None
        assert not handle.is_paused

    def test_double_pause_is_safe(self):
        handle = ProcessHandle()
        process = subprocess.Popen(["sleep", "60"], start_new_session=True)
        handle.process = process

        handle.pause()
        handle.pause()  # second pause must not raise
        assert handle.is_paused

        handle.kill()
        process.wait(timeout=5)

    def test_resume_without_pause_is_safe(self):
        handle = ProcessHandle()
        process = subprocess.Popen(["sleep", "60"], start_new_session=True)
        handle.process = process

        handle.resume()  # no prior pause
        assert not handle.is_paused

        handle.kill()
        process.wait(timeout=5)

    def test_pause_resume_cycle(self):
        """Multiple pause/resume cycles on the same process."""
        handle = ProcessHandle()
        process = subprocess.Popen(["sleep", "60"], start_new_session=True)
        handle.process = process

        for _ in range(3):
            handle.pause()
            assert handle.is_paused
            handle.resume()
            assert not handle.is_paused

        handle.kill()
        process.wait(timeout=5)
        assert process.poll() is not None
