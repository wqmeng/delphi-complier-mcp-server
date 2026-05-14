"""
Tests for src/tools/environment.py

Covers: check_environment, get_compile_history, service initialization
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass
from typing import Optional

from mcp.types import CallToolResult
from src.tools.environment import (
    check_environment,
    get_compile_history,
    set_config_manager,
    set_thirdparty_kb_service,
    _config_manager,
    _thirdparty_kb_service,
)


# =========================================================================
# Fixtures
# =========================================================================

@dataclass
class FakeCompiler:
    name: str
    path: str
    version: str
    is_default: bool = False


@dataclass
class FakeHistoryEntry:
    def to_dict(self):
        return {"id": 1, "status": "success"}


@pytest.fixture
def reset_globals():
    """Reset module-level globals before and after each test."""
    from src.tools import environment
    old_cm = environment._config_manager
    old_tks = environment._thirdparty_kb_service
    environment._config_manager = None
    environment._thirdparty_kb_service = None
    yield
    environment._config_manager = old_cm
    environment._thirdparty_kb_service = old_tks


@pytest.fixture
def mock_config_manager():
    cm = MagicMock()
    cm.get_all_compilers.return_value = [
        FakeCompiler(name="Delphi 12", path=r"C:\Studio\22.0\bin\dcc32.exe", version="22.0", is_default=True),
        FakeCompiler(name="Delphi 11", path=r"C:\Studio\21.0\bin\dcc32.exe", version="21.0"),
    ]
    cm.get_compiler.return_value = FakeCompiler(
        name="Delphi 12", path=r"C:\Studio\22.0\bin\dcc32.exe", version="22.0", is_default=True
    )
    return cm


# =========================================================================
# check_environment
# =========================================================================

class TestCheckEnvironment:
    @pytest.mark.asyncio
    async def test_no_config_manager_returns_error(self, reset_globals):
        """When config manager not set, return error."""
        result = await check_environment()
        assert result.isError is True
        assert "未初始化" in result.content[0].text

    @pytest.mark.asyncio
    async def test_with_valid_compilers(self, reset_globals, mock_config_manager):
        """Successful check returns compiler list."""
        set_config_manager(mock_config_manager)

        with patch("src.tools.environment.Validator") as MockValidator:
            validator_instance = MagicMock()
            validator_instance.validate_compiler_path.return_value = (True, "")
            MockValidator.return_value = validator_instance

            result = await check_environment()

        assert not result.isError
        text = result.content[0].text
        assert "available" in text.lower() or "可用" in text
        assert "Delphi 12" in text

    @pytest.mark.asyncio
    async def test_with_unavailable_compiler(self, reset_globals, mock_config_manager):
        """Compiler marked unavailable when validate fails."""
        set_config_manager(mock_config_manager)

        with patch("src.tools.environment.Validator") as MockValidator:
            validator_instance = MagicMock()
            # First compiler valid, second invalid
            validator_instance.validate_compiler_path.side_effect = [(True, ""), (False, "not found")]
            MockValidator.return_value = validator_instance

            result = await check_environment()

        assert not result.isError
        text = result.content[0].text
        assert "1 个可用" in text  # "2 (1 个可用)"

    @pytest.mark.asyncio
    async def test_with_thirdparty_paths(self, reset_globals, mock_config_manager):
        """Third-party library paths included in output."""
        set_config_manager(mock_config_manager)

        mock_tps = MagicMock()
        mock_tps.get_library_paths.return_value = [
            r"C:\Libs\ComponentA",
            r"C:\Libs\ComponentB",
        ]
        set_thirdparty_kb_service(mock_tps)

        with patch("src.tools.environment.Validator") as MockValidator:
            validator_instance = MagicMock()
            validator_instance.validate_compiler_path.return_value = (True, "")
            MockValidator.return_value = validator_instance

            result = await check_environment()

        assert not result.isError
        text = result.content[0].text
        assert "ComponentA" in text
        assert "2 个" in text or "2个" in text

    @pytest.mark.asyncio
    async def test_exception_in_check_returns_error(self, reset_globals):
        """Exception during check returns error result."""
        set_config_manager(MagicMock())

        with patch.object(MagicMock(), "get_all_compilers", side_effect=RuntimeError("boom")):
            # config_manager is a MagicMock, accessing it via the module global
            pass

        # Set config_manager to one that raises
        bad_cm = MagicMock()
        bad_cm.get_all_compilers.side_effect = RuntimeError("unexpected error")
        set_config_manager(bad_cm)

        result = await check_environment()
        assert result.isError
        assert "异常" in result.content[0].text or "error" in result.content[0].text.lower()


# =========================================================================
# get_compile_history
# =========================================================================

class TestGetCompileHistory:
    @pytest.mark.asyncio
    async def test_no_config_manager_returns_error_dict(self, reset_globals):
        """When config manager not set, return error dict."""
        result = await get_compile_history()
        assert result["success"] is False
        assert "未初始化" in result["message"]

    @pytest.mark.asyncio
    async def test_returns_history_entries(self, reset_globals):
        """Successful history query returns entries."""
        cm = MagicMock()
        cm.get_history.return_value = [FakeHistoryEntry(), FakeHistoryEntry()]
        set_config_manager(cm)

        result = await get_compile_history(limit=10)
        assert result["success"] is True
        assert len(result["entries"]) == 2
        assert result["entries"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_exception_returns_error(self, reset_globals):
        """Exception during history query returns error dict."""
        cm = MagicMock()
        cm.get_history.side_effect = RuntimeError("history error")
        set_config_manager(cm)

        result = await get_compile_history()
        assert result["success"] is False
        assert "异常" in result["message"] or "error" in result["message"].lower()


# =========================================================================
# Service setters
# =========================================================================

class TestServiceSetters:
    def test_set_config_manager(self, reset_globals):
        import src.tools.environment as env_mod
        cm = MagicMock()
        set_config_manager(cm)
        assert env_mod._config_manager is cm

    def test_set_thirdparty_kb_service(self, reset_globals):
        import src.tools.environment as env_mod
        svc = MagicMock()
        set_thirdparty_kb_service(svc)
        assert env_mod._thirdparty_kb_service is svc
