"""
Tests for src/services/process_manager.py

Covers: process execution, timeout, env setup, error handling
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from src.services.process_manager import ProcessManager


# =========================================================================
# _get_delphi_env
# =========================================================================

class TestGetDelphiEnv:
    def test_with_studio_path(self):
        pm = ProcessManager()
        env = pm._get_delphi_env(
            r"C:\Program Files (x86)\Embarcadero\Studio\22.0\bin\dcc32.exe"
        )
        assert "BDS" in env
        assert "BDSINCLUDE" in env
        assert "BDSCOMMONDIR" in env
        assert env["BDS"].endswith("22.0")

    def test_without_studio_path(self):
        pm = ProcessManager()
        env = pm._get_delphi_env(r"C:\tools\dcc32.exe")
        assert env == {}

    def test_empty_path(self):
        pm = ProcessManager()
        env = pm._get_delphi_env("")
        assert env == {}


# =========================================================================
# execute
# =========================================================================

class TestExecute:
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """execute returns (code, stdout, stderr) for a clean run."""
        pm = ProcessManager()

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        type(mock_process).pid = PropertyMock(return_value=12345)

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            code, stdout, stderr = await pm.execute("dcc32.exe", ["test.dpr"], 30)

        assert code == 0
        assert stdout == "output"
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        """execute wraps TimeoutError in RuntimeError."""
        pm = ProcessManager()

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        type(mock_process).pid = PropertyMock(return_value=12345)

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch.object(pm, "kill_process", AsyncMock()) as mock_kill:
                with pytest.raises(RuntimeError, match="进程执行失败"):
                    await pm.execute("dcc32.exe", ["test.dpr"], 1)

                mock_kill.assert_awaited_once_with(mock_process)

    @pytest.mark.asyncio
    async def test_file_not_found_raises_runtime_error(self):
        """execute raises RuntimeError when executable doesn't exist."""
        pm = ProcessManager()
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="编译器可执行文件不存在"):
                await pm.execute("missing.exe", [], 30)

    @pytest.mark.asyncio
    async def test_generic_error_raises_runtime_error(self):
        """execute raises RuntimeError on unexpected errors."""
        pm = ProcessManager()
        with patch("asyncio.create_subprocess_exec", side_effect=PermissionError("denied")):
            with pytest.raises(RuntimeError, match="进程执行失败"):
                await pm.execute("dcc32.exe", [], 30)


# =========================================================================
# kill_process
# =========================================================================

class TestKillProcess:
    @pytest.mark.asyncio
    async def test_kills_and_waits(self):
        pm = ProcessManager()
        mock_process = MagicMock()
        # kill() and wait() are sync in real Process, but wait is actually async
        mock_process.wait = AsyncMock()

        await pm.kill_process(mock_process)

        mock_process.kill.assert_called_once()
        mock_process.wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_lookup_error_handled(self):
        """kill_process handles ProcessLookupError gracefully."""
        pm = ProcessManager()
        mock_process = AsyncMock()
        mock_process.kill.side_effect = ProcessLookupError()

        # Should not raise
        await pm.kill_process(mock_process)

    @pytest.mark.asyncio
    async def test_generic_error_handled(self):
        """kill_process handles unexpected errors gracefully."""
        pm = ProcessManager()
        mock_process = AsyncMock()
        mock_process.kill.side_effect = Exception("unexpected")

        # Should not raise
        await pm.kill_process(mock_process)


# =========================================================================
# execute_with_callback
# =========================================================================

class TestExecuteWithCallback:
    @pytest.mark.asyncio
    async def test_successful_execution_with_callbacks(self):
        pm = ProcessManager()

        # Simulate a process that returns line by line
        mock_process = AsyncMock()
        mock_process.returncode = 0

        # Simulate readline returning lines then empty
        stdout_lines = [b"line1\n", b"line2\n", b""]
        stderr_lines = [b"err1\n", b""]

        async def fake_stdout_readline():
            return stdout_lines.pop(0) if stdout_lines else b""

        async def fake_stderr_readline():
            return stderr_lines.pop(0) if stderr_lines else b""

        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = fake_stdout_readline
        mock_process.stderr = MagicMock()
        mock_process.stderr.readline = fake_stderr_readline

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            stdout_cb = MagicMock()
            stderr_cb = MagicMock()

            code, stdout, stderr = await pm.execute_with_callback(
                "dcc32.exe", ["test.dpr"], 30,
                stdout_callback=stdout_cb,
                stderr_callback=stderr_cb,
            )

        assert code == 0
        assert "line1" in stdout
        assert "line2" in stdout
        assert "err1" in stderr
        assert stdout_cb.call_count == 2
        assert stderr_cb.call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_in_callback(self):
        pm = ProcessManager()

        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        # The error wraps in RuntimeError at the outer catch
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch.object(pm, "kill_process", AsyncMock()):
                with pytest.raises(RuntimeError, match="进程执行失败"):
                    await pm.execute_with_callback("dcc32.exe", [], 0.001)
