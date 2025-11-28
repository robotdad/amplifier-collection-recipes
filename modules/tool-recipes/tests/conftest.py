"""Pytest fixtures for tool-recipes tests."""

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import directly from submodules to avoid amplifier_core dependency in __init__.py
from amplifier_module_tool_recipes.models import Recipe
from amplifier_module_tool_recipes.models import Step
from amplifier_module_tool_recipes.session import SessionManager

# Module mocking is handled per-test-module via autouse fixture
# to avoid polluting sys.modules for other test directories

_mock_modules = ["amplifier_app_cli", "amplifier_app_cli.session_spawner"]


@pytest.fixture(scope="module", autouse=True)
def mock_amplifier_app_cli():
    """Mock amplifier_app_cli modules for tests in this directory.

    Uses module scope to install mocks once per test module,
    and restores original modules after all tests in the module complete.
    This prevents pollution of sys.modules for tests in other directories.
    """
    # Save any existing module entries
    original_modules: dict[str, types.ModuleType] = {}
    for mod in _mock_modules:
        if mod in sys.modules:
            original_modules[mod] = sys.modules[mod]

    # Install mocks
    mock_session_spawner = MagicMock()
    sys.modules["amplifier_app_cli"] = MagicMock()
    sys.modules["amplifier_app_cli.session_spawner"] = mock_session_spawner

    yield

    # Restore original modules after tests complete
    for mod in _mock_modules:
        if mod in original_modules:
            sys.modules[mod] = original_modules[mod]
        elif mod in sys.modules:
            del sys.modules[mod]


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_step() -> Step:
    """Create a sample step for testing."""
    return Step(
        id="test-step",
        agent="test-agent",
        prompt="Test prompt with {{variable}}",
        output="result",
        timeout=60,
    )


@pytest.fixture
def sample_recipe(sample_step: Step) -> Recipe:
    """Create a sample recipe for testing."""
    return Recipe(
        name="test-recipe",
        description="A test recipe",
        version="1.0.0",
        steps=[sample_step],
        context={"variable": "test-value"},
    )


@pytest.fixture
def multi_step_recipe() -> Recipe:
    """Create a multi-step recipe with dependencies."""
    return Recipe(
        name="multi-step-recipe",
        description="Recipe with multiple steps",
        version="1.0.0",
        steps=[
            Step(
                id="step-1",
                agent="agent-a",
                prompt="First step: {{input}}",
                output="first_result",
            ),
            Step(
                id="step-2",
                agent="agent-b",
                prompt="Second step using {{first_result}}",
                output="second_result",
                depends_on=["step-1"],
            ),
            Step(
                id="step-3",
                agent="agent-c",
                prompt="Final step: {{first_result}} and {{second_result}}",
                depends_on=["step-1", "step-2"],
            ),
        ],
        context={"input": "initial-input"},
    )


@pytest.fixture
def session_manager(temp_dir: Path) -> SessionManager:
    """Create a session manager with temp directory."""
    return SessionManager(base_dir=temp_dir, auto_cleanup_days=7)


@pytest.fixture
def sample_yaml_content() -> str:
    """Return valid YAML content for a recipe."""
    return """
name: yaml-test-recipe
description: A recipe loaded from YAML
version: 2.0.0

context:
  file_path: /path/to/file

steps:
  - id: analyze
    agent: code-analyzer
    prompt: "Analyze file: {{file_path}}"
    output: analysis
    timeout: 120

  - id: report
    agent: reporter
    prompt: "Generate report from: {{analysis}}"
    depends_on:
      - analyze
"""


@pytest.fixture
def yaml_recipe_file(temp_dir: Path, sample_yaml_content: str) -> Path:
    """Create a YAML recipe file in temp directory."""
    recipe_path = temp_dir / "test-recipe.yaml"
    recipe_path.write_text(sample_yaml_content)
    return recipe_path


class MockCoordinator:
    """Mock coordinator for testing."""

    def __init__(self, available_agents: list[str] | None = None):
        self._available_agents = available_agents or []

    @property
    def available_agents(self) -> list[str]:
        return self._available_agents


@pytest.fixture
def mock_coordinator() -> MockCoordinator:
    """Create a mock coordinator."""
    return MockCoordinator(available_agents=["test-agent", "code-analyzer", "reporter"])
