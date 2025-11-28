"""Tests for executor loop (foreach) functionality."""

import sys
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from amplifier_module_tool_recipes.executor import RecipeExecutor
from amplifier_module_tool_recipes.models import Recipe
from amplifier_module_tool_recipes.models import Step

# Create mock module to avoid dependency on amplifier_app_cli
mock_session_spawner = MagicMock()
sys.modules["amplifier_app_cli"] = MagicMock()
sys.modules["amplifier_app_cli.session_spawner"] = mock_session_spawner


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.session = MagicMock()
    coordinator.config = {"agents": {}}
    return coordinator


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    manager = MagicMock()
    manager.create_session.return_value = "test-session-id"
    manager.load_state.return_value = {
        "current_step_index": 0,
        "context": {},
        "completed_steps": [],
        "started": "2025-01-01T00:00:00",
    }
    return manager


class TestExecutorLoops:
    """Tests for foreach loop execution."""

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_foreach_iterates_over_list(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Step iterates over each item in list."""
        mock_spawn.side_effect = AsyncMock(side_effect=["result_a", "result_b", "result_c"])

        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop-step",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{items}}",
                    collect="results",
                ),
            ],
            context={"items": ["a", "b", "c"]},
        )

        result = await executor.execute_recipe(recipe, {}, temp_dir)

        # Should have called spawn_sub_session 3 times (once per item)
        assert mock_spawn.call_count == 3
        assert result["results"] == ["result_a", "result_b", "result_c"]

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_empty_list_skips_step(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Empty foreach list skips step without error."""
        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop-step",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{items}}",
                    collect="results",
                ),
            ],
            context={"items": []},
        )

        result = await executor.execute_recipe(recipe, {}, temp_dir)

        # No calls should be made for empty list
        assert mock_spawn.call_count == 0
        # Step should be tracked as skipped
        assert "_skipped_steps" in result
        assert "loop-step" in result["_skipped_steps"]

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_collect_aggregates_results(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Collect variable contains all iteration results."""
        mock_spawn.side_effect = AsyncMock(side_effect=["analysis_1", "analysis_2"])

        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="analyze-files",
                    agent="analyzer",
                    prompt="Analyze {{current_file}}",
                    foreach="{{files}}",
                    as_var="current_file",
                    collect="analyses",
                ),
            ],
            context={"files": ["file1.py", "file2.py"]},
        )

        result = await executor.execute_recipe(recipe, {}, temp_dir)

        assert result["analyses"] == ["analysis_1", "analysis_2"]

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_as_changes_loop_variable_name(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Custom 'as' name is used for loop variable."""
        mock_spawn.side_effect = AsyncMock(side_effect=["done"])

        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop",
                    agent="a",
                    prompt="Process {{my_item}}",
                    foreach="{{items}}",
                    as_var="my_item",
                    collect="results",
                ),
            ],
            context={"items": ["x"]},
        )

        await executor.execute_recipe(recipe, {}, temp_dir)

        # Verify the loop was executed once with custom variable name
        assert mock_spawn.call_count == 1

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_max_iterations_enforced(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Exceeding max_iterations fails recipe."""
        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{items}}",
                    max_iterations=3,  # Limit to 3
                ),
            ],
            context={"items": ["a", "b", "c", "d", "e"]},  # 5 items exceeds limit
        )

        with pytest.raises(ValueError, match="exceeds max_iterations"):
            await executor.execute_recipe(recipe, {}, temp_dir)

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_non_list_foreach_fails(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Non-list foreach variable fails with clear error."""
        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{value}}",
                ),
            ],
            context={"value": "not-a-list"},  # String, not list
        )

        with pytest.raises(ValueError, match="must be a list"):
            await executor.execute_recipe(recipe, {}, temp_dir)

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_undefined_foreach_variable_fails(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Undefined foreach variable fails with clear error."""
        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{undefined_var}}",
                ),
            ],
            context={},  # No 'undefined_var' defined
        )

        with pytest.raises(ValueError, match="Undefined variable"):
            await executor.execute_recipe(recipe, {}, temp_dir)

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_loop_variable_scoped_to_step(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Loop variable not available after loop completes."""
        mock_spawn.side_effect = AsyncMock(side_effect=["loop_result", "final_result"])

        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{items}}",
                    collect="results",
                ),
                Step(
                    id="after",
                    agent="a",
                    prompt="After loop: {{results}}",
                    output="final",
                ),
            ],
            context={"items": ["x"]},
        )

        result = await executor.execute_recipe(recipe, {}, temp_dir)

        # Loop variable 'item' should not be in final context
        assert "item" not in result
        # But collect variable should be available
        assert "results" in result

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_iteration_failure_stops_loop(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Any iteration failure immediately fails the recipe (fail-fast)."""
        # First call succeeds, second fails
        mock_spawn.side_effect = [AsyncMock(return_value="ok")(), Exception("Iteration error")]

        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{items}}",
                    collect="results",
                ),
            ],
            context={"items": ["a", "b", "c"]},
        )

        with pytest.raises(ValueError, match="iteration 1 failed"):
            await executor.execute_recipe(recipe, {}, temp_dir)

        # Only 2 calls made (first succeeded, second failed)
        assert mock_spawn.call_count == 2

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_output_without_collect_returns_last(
        self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir
    ):
        """Without collect, output stores last iteration result."""
        mock_spawn.side_effect = AsyncMock(side_effect=["first", "second", "last"])

        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{items}}",
                    output="result",  # Not using collect
                ),
            ],
            context={"items": ["a", "b", "c"]},
        )

        result = await executor.execute_recipe(recipe, {}, temp_dir)

        # Output should be last iteration result
        assert result["result"] == "last"

    @pytest.mark.asyncio
    @patch("amplifier_app_cli.session_spawner.spawn_sub_session")
    async def test_nested_variable_in_foreach(self, mock_spawn, mock_coordinator, mock_session_manager, temp_dir):
        """Nested variable reference in foreach works."""
        mock_spawn.side_effect = AsyncMock(side_effect=["result_a", "result_b"])

        executor = RecipeExecutor(mock_coordinator, mock_session_manager)

        recipe = Recipe(
            name="test",
            description="test",
            version="1.0.0",
            steps=[
                Step(
                    id="loop",
                    agent="a",
                    prompt="Process {{item}}",
                    foreach="{{data.files}}",
                    collect="results",
                ),
            ],
            context={"data": {"files": ["a.py", "b.py"]}},
        )

        result = await executor.execute_recipe(recipe, {}, temp_dir)

        assert result["results"] == ["result_a", "result_b"]


class TestLoopValidation:
    """Tests for loop field validation in Step model."""

    def test_foreach_must_contain_variable_reference(self):
        """foreach must contain {{variable}} syntax."""
        step = Step(
            id="test",
            agent="a",
            prompt="p",
            foreach="not-a-variable",
        )
        errors = step.validate()
        assert any("foreach must contain a variable reference" in e for e in errors)

    def test_as_must_be_valid_variable_name(self):
        """as must be alphanumeric with underscores."""
        step = Step(
            id="test",
            agent="a",
            prompt="p",
            foreach="{{items}}",
            as_var="invalid-name!",
        )
        errors = step.validate()
        assert any("'as' must be a valid variable name" in e for e in errors)

    def test_collect_must_be_valid_variable_name(self):
        """collect must be alphanumeric with underscores."""
        step = Step(
            id="test",
            agent="a",
            prompt="p",
            foreach="{{items}}",
            collect="invalid-name!",
        )
        errors = step.validate()
        assert any("'collect' must be a valid variable name" in e for e in errors)

    def test_max_iterations_must_be_positive(self):
        """max_iterations must be positive."""
        step = Step(
            id="test",
            agent="a",
            prompt="p",
            foreach="{{items}}",
            max_iterations=0,
        )
        errors = step.validate()
        assert any("max_iterations must be positive" in e for e in errors)

    def test_valid_loop_step_passes_validation(self):
        """Valid loop step passes validation."""
        step = Step(
            id="test",
            agent="a",
            prompt="p",
            foreach="{{items}}",
            as_var="current_item",
            collect="results",
            max_iterations=50,
        )
        errors = step.validate()
        assert not errors
