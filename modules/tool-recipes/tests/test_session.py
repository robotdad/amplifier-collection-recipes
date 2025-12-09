"""Tests for session management and persistence."""

import datetime
import json
import re
from pathlib import Path

from amplifier_module_tool_recipes.models import Recipe
from amplifier_module_tool_recipes.models import Step
from amplifier_module_tool_recipes.session import SessionManager
from amplifier_module_tool_recipes.session import generate_session_id
from amplifier_module_tool_recipes.session import get_project_slug


class TestGenerateSessionId:
    """Tests for session ID generation."""

    def test_format_matches_w3c_trace_context(self):
        """Session ID should follow W3C Trace Context pattern."""
        session_id = generate_session_id()
        # Format: {span}-{timestamp}_{identifier}
        # Example: 7cc787dd22d54f6c-20251118-114317_recipe
        pattern = r"^[0-9a-f]{16}-\d{8}-\d{6}_recipe$"
        assert re.match(pattern, session_id), f"Session ID {session_id} doesn't match expected pattern"

    def test_unique_session_ids(self):
        """Each call should generate unique session ID."""
        ids = [generate_session_id() for _ in range(100)]
        assert len(set(ids)) == 100, "Generated session IDs should be unique"

    def test_session_id_contains_timestamp(self):
        """Session ID should contain current date."""
        session_id = generate_session_id()
        today = datetime.datetime.now().strftime("%Y%m%d")
        assert today in session_id

    def test_session_id_ends_with_recipe(self):
        """Session ID should end with _recipe identifier."""
        session_id = generate_session_id()
        assert session_id.endswith("_recipe")


class TestGetProjectSlug:
    """Tests for project path to slug conversion."""

    def test_converts_path_to_slug(self, temp_dir: Path):
        """Path should be converted to slug format."""
        slug = get_project_slug(temp_dir)
        assert "/" not in slug
        assert "\\" not in slug

    def test_removes_leading_dash(self, temp_dir: Path):
        """Leading dash from absolute path should be removed."""
        slug = get_project_slug(temp_dir)
        assert not slug.startswith("-")

    def test_absolute_path_conversion(self):
        """Absolute path should be converted correctly."""
        path = Path("/home/user/projects/my-app")
        slug = get_project_slug(path)
        # Should contain the path components separated by dashes
        assert "home" in slug
        assert "user" in slug
        assert "my-app" in slug


class TestSessionManager:
    """Tests for SessionManager class."""

    def test_create_session(self, session_manager: SessionManager, sample_recipe: Recipe, temp_dir: Path):
        """create_session should create session directory and return ID."""
        session_id = session_manager.create_session(sample_recipe, temp_dir)

        assert session_id is not None
        assert "_recipe" in session_id

        # Session directory should exist
        session_dir = session_manager.get_session_dir(session_id, temp_dir)
        assert session_dir.exists()

    def test_create_session_saves_initial_state(
        self, session_manager: SessionManager, sample_recipe: Recipe, temp_dir: Path
    ):
        """create_session should save initial state."""
        session_id = session_manager.create_session(sample_recipe, temp_dir)

        state = session_manager.load_state(session_id, temp_dir)
        assert state["session_id"] == session_id
        assert state["recipe_name"] == sample_recipe.name
        assert state["current_step_index"] == 0
        assert state["completed_steps"] == []

    def test_session_exists(self, session_manager: SessionManager, sample_recipe: Recipe, temp_dir: Path):
        """session_exists should return True for existing sessions."""
        session_id = session_manager.create_session(sample_recipe, temp_dir)

        assert session_manager.session_exists(session_id, temp_dir)
        assert not session_manager.session_exists("nonexistent", temp_dir)

    def test_save_and_load_state(self, session_manager: SessionManager, sample_recipe: Recipe, temp_dir: Path):
        """State should be saved and loadable."""
        session_id = session_manager.create_session(sample_recipe, temp_dir)

        # Update state
        new_state = {
            "session_id": session_id,
            "recipe_name": sample_recipe.name,
            "recipe_version": sample_recipe.version,
            "started": datetime.datetime.now().isoformat(),
            "current_step_index": 1,
            "context": {"test": "value"},
            "completed_steps": ["step-1"],
            "project_path": str(temp_dir),
        }
        session_manager.save_state(session_id, temp_dir, new_state)

        # Load and verify
        loaded = session_manager.load_state(session_id, temp_dir)
        assert loaded["current_step_index"] == 1
        assert loaded["completed_steps"] == ["step-1"]
        assert loaded["context"]["test"] == "value"

    def test_load_state_not_found(self, session_manager: SessionManager, temp_dir: Path):
        """load_state should raise FileNotFoundError for nonexistent session."""
        import pytest

        with pytest.raises(FileNotFoundError):
            session_manager.load_state("nonexistent", temp_dir)

    def test_list_sessions_empty(self, session_manager: SessionManager, temp_dir: Path):
        """list_sessions should return empty list when no sessions exist."""
        sessions = session_manager.list_sessions(temp_dir)
        assert sessions == []

    def test_list_sessions(self, session_manager: SessionManager, temp_dir: Path):
        """list_sessions should return all sessions for project."""
        # Create multiple recipes with different names
        recipe1 = Recipe(
            name="recipe-1",
            description="First recipe",
            version="1.0.0",
            steps=[Step(id="s1", agent="a", prompt="p")],
        )
        recipe2 = Recipe(
            name="recipe-2",
            description="Second recipe",
            version="1.0.0",
            steps=[Step(id="s1", agent="a", prompt="p")],
        )

        session_manager.create_session(recipe1, temp_dir)
        session_manager.create_session(recipe2, temp_dir)

        sessions = session_manager.list_sessions(temp_dir)
        assert len(sessions) == 2

        recipe_names = {s["recipe_name"] for s in sessions}
        assert recipe_names == {"recipe-1", "recipe-2"}

    def test_list_sessions_sorted_by_time(self, session_manager: SessionManager, temp_dir: Path):
        """list_sessions should return sessions sorted by time (newest first)."""
        import time

        recipe = Recipe(
            name="test-recipe",
            description="Test",
            version="1.0.0",
            steps=[Step(id="s1", agent="a", prompt="p")],
        )

        # Create sessions with slight delay
        session1 = session_manager.create_session(recipe, temp_dir)
        time.sleep(0.1)
        session2 = session_manager.create_session(recipe, temp_dir)

        sessions = session_manager.list_sessions(temp_dir)
        assert len(sessions) == 2
        # Newest first
        assert sessions[0]["session_id"] == session2
        assert sessions[1]["session_id"] == session1

    def test_cleanup_old_sessions(self, session_manager: SessionManager, temp_dir: Path):
        """cleanup_old_sessions should delete sessions older than threshold."""
        recipe = Recipe(
            name="test-recipe",
            description="Test",
            version="1.0.0",
            steps=[Step(id="s1", agent="a", prompt="p")],
        )

        # Create a session
        session_id = session_manager.create_session(recipe, temp_dir)

        # Modify state to have old timestamp
        session_dir = session_manager.get_session_dir(session_id, temp_dir)
        state_file = session_dir / "state.json"

        with open(state_file) as f:
            state = json.load(f)

        # Set started time to 10 days ago
        old_time = datetime.datetime.now() - datetime.timedelta(days=10)
        state["started"] = old_time.isoformat()

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f)

        # Cleanup with 7 day threshold
        deleted = session_manager.cleanup_old_sessions(temp_dir)
        assert deleted == 1

        # Session should no longer exist
        assert not session_manager.session_exists(session_id, temp_dir)

    def test_cleanup_keeps_recent_sessions(self, session_manager: SessionManager, temp_dir: Path):
        """cleanup_old_sessions should keep sessions within threshold."""
        recipe = Recipe(
            name="test-recipe",
            description="Test",
            version="1.0.0",
            steps=[Step(id="s1", agent="a", prompt="p")],
        )

        session_id = session_manager.create_session(recipe, temp_dir)

        # Cleanup should not delete recent session
        deleted = session_manager.cleanup_old_sessions(temp_dir)
        assert deleted == 0
        assert session_manager.session_exists(session_id, temp_dir)

    def test_get_sessions_dir(self, session_manager: SessionManager, temp_dir: Path):
        """get_sessions_dir should return correct path."""
        sessions_dir = session_manager.get_sessions_dir(temp_dir)
        assert "recipe-sessions" in str(sessions_dir)

    def test_get_session_dir(self, session_manager: SessionManager, sample_recipe: Recipe, temp_dir: Path):
        """get_session_dir should return correct path for session."""
        session_id = session_manager.create_session(sample_recipe, temp_dir)
        session_dir = session_manager.get_session_dir(session_id, temp_dir)

        assert session_id in str(session_dir)
        assert session_dir.exists()
