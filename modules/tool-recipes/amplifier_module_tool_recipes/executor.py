"""Recipe execution engine."""

import asyncio
import datetime
import re
from pathlib import Path
from typing import Any

from .expression_evaluator import ExpressionError
from .expression_evaluator import evaluate_condition
from .models import Recipe
from .models import Step
from .session import SessionManager


class SkipRemainingError(Exception):
    """Raised when step fails with on_error='skip_remaining'."""

    pass


class RecipeExecutor:
    """Executes recipe workflows with checkpointing and resumption."""

    def __init__(self, coordinator: Any, session_manager: SessionManager):
        """
        Initialize executor.

        Args:
            coordinator: Amplifier coordinator for agent spawning
            session_manager: Session persistence manager
        """
        self.coordinator = coordinator
        self.session_manager = session_manager

    async def execute_recipe(
        self,
        recipe: Recipe,
        context_vars: dict[str, Any],
        project_path: Path,
        session_id: str | None = None,
        recipe_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        Execute recipe with checkpointing and resumption.

        Args:
            recipe: Recipe to execute
            context_vars: Initial context variables (merged with recipe.context)
            project_path: Current project directory
            session_id: Optional session ID to resume
            recipe_path: Optional path to recipe file (saved to session)

        Returns:
            Final context dict with all step outputs
        """
        # Create or resume session
        is_resuming = session_id is not None

        if is_resuming:
            state = self.session_manager.load_state(session_id, project_path)
            current_step_index = state["current_step_index"]
            context = state["context"]
            completed_steps = state.get("completed_steps", [])
            session_started = state["started"]
        else:
            session_id = self.session_manager.create_session(recipe, project_path, recipe_path)
            current_step_index = 0
            context = {**recipe.context, **context_vars}
            completed_steps = []
            session_started = datetime.datetime.now().isoformat()

        # Add metadata to context
        context["recipe"] = {
            "name": recipe.name,
            "version": recipe.version,
            "description": recipe.description,
        }
        context["session"] = {
            "id": session_id,
            "started": session_started,
            "project": str(project_path.resolve()),
        }

        try:
            # Execute remaining steps
            for i in range(current_step_index, len(recipe.steps)):
                step = recipe.steps[i]

                # Add step metadata to context
                context["step"] = {"id": step.id, "index": i}

                # Check condition if present
                if step.condition:
                    try:
                        condition_result = evaluate_condition(step.condition, context)
                    except ExpressionError as e:
                        raise ValueError(f"Step '{step.id}': condition error: {e}") from e

                    if not condition_result:
                        # Skip this step - record in state but don't execute
                        skipped_steps = context.get("_skipped_steps", [])
                        skipped_steps.append(step.id)
                        context["_skipped_steps"] = skipped_steps
                        continue

                # Handle foreach loops
                if step.foreach:
                    try:
                        await self._execute_loop(step, context)
                        # Update completed steps and session state after loop completes
                        completed_steps.append(step.id)
                        state = {
                            "session_id": session_id,
                            "recipe_name": recipe.name,
                            "recipe_version": recipe.version,
                            "started": context["session"]["started"],
                            "current_step_index": i + 1,
                            "context": context,
                            "completed_steps": completed_steps,
                            "project_path": str(project_path.resolve()),
                        }
                        self.session_manager.save_state(session_id, project_path, state)
                        continue
                    except SkipRemainingError:
                        break

                # Execute step with retry
                try:
                    result = await self.execute_step_with_retry(step, context)

                    # Store output if specified
                    if step.output:
                        context[step.output] = result

                    # Update completed steps and session state
                    completed_steps.append(step.id)

                    state = {
                        "session_id": session_id,
                        "recipe_name": recipe.name,
                        "recipe_version": recipe.version,
                        "started": context["session"]["started"],
                        "current_step_index": i + 1,
                        "context": context,
                        "completed_steps": completed_steps,
                        "project_path": str(project_path.resolve()),
                    }

                    # Checkpoint after each step
                    self.session_manager.save_state(session_id, project_path, state)

                except SkipRemainingError:
                    # Skip remaining steps
                    break

        except Exception:
            # Save state even on error for resumption
            if "state" in locals():
                self.session_manager.save_state(session_id, project_path, state)
            raise

        # Cleanup old sessions
        self.session_manager.cleanup_old_sessions(project_path)

        return context

    async def execute_step_with_retry(self, step: Step, context: dict[str, Any]) -> Any:
        """
        Execute step with retry logic.

        Args:
            step: Step to execute
            context: Current context variables

        Returns:
            Step result

        Raises:
            Exception if all retries fail and on_error='fail'
            SkipRemainingError if on_error='skip_remaining'
        """
        retry_config = step.retry or {}
        max_attempts = retry_config.get("max_attempts", 1)
        backoff = retry_config.get("backoff", "exponential")
        delay = retry_config.get("initial_delay", 5)
        max_delay = retry_config.get("max_delay", 300)

        last_error = None

        for attempt in range(max_attempts):
            try:
                result = await self.execute_step(step, context)
                return result

            except Exception as e:
                last_error = e

                # If final attempt or not retryable
                if attempt == max_attempts - 1:
                    # Handle based on on_error strategy
                    if step.on_error == "fail":
                        raise
                    if step.on_error == "continue":
                        return None  # Continue with None result
                    if step.on_error == "skip_remaining":
                        raise SkipRemainingError() from e

                # Wait before retry
                await asyncio.sleep(min(delay, max_delay))

                # Adjust delay for next attempt
                if backoff == "exponential":
                    delay *= 2
                # Linear backoff keeps same delay

        # Shouldn't reach here, but handle just in case
        if step.on_error == "fail" and last_error:
            raise last_error
        return None

    async def execute_step(self, step: Step, context: dict[str, Any]) -> Any:
        """
        Execute single step by spawning sub-agent.

        Args:
            step: Step to execute
            context: Current context variables

        Returns:
            Step result from agent
        """
        # Import spawn helper from app layer
        from amplifier_app_cli.session_spawner import spawn_sub_session

        # Substitute variables in prompt
        instruction = self.substitute_variables(step.prompt, context)

        # Add mode if specified
        if step.mode:
            mode_instruction = f"MODE: {step.mode}\n\n"
            instruction = mode_instruction + instruction

        # Get parent session and agents config from coordinator
        parent_session = self.coordinator.session
        agents = self.coordinator.config.get("agents", {})

        # Spawn sub-session with agent
        result = await spawn_sub_session(
            agent_name=step.agent,
            instruction=instruction,
            parent_session=parent_session,
            agent_configs=agents,
            sub_session_id=None,  # Let spawner generate ID
        )

        return result

    async def _execute_loop(self, step: Step, context: dict[str, Any]) -> None:
        """
        Execute a step with foreach iteration.

        Simple, fail-fast implementation per philosophy:
        - No checkpointing (restart on failure)
        - No partial completion (fail-fast)
        - Minimal state tracking

        Args:
            step: Step with foreach field
            context: Current context variables

        Raises:
            ValueError: If foreach variable invalid or iteration fails
            SkipRemainingError: If on_error='skip_remaining' and iteration fails
        """
        # Resolve foreach variable (step.foreach is guaranteed non-None by caller)
        assert step.foreach is not None
        items = self._resolve_foreach_variable(step.foreach, context)

        if not isinstance(items, list):
            raise ValueError(f"Step '{step.id}': foreach variable must be a list, got {type(items).__name__}")

        if not items:
            # Empty list - skip step (common case, not an error)
            skipped_steps = context.get("_skipped_steps", [])
            skipped_steps.append(step.id)
            context["_skipped_steps"] = skipped_steps
            return

        if len(items) > step.max_iterations:
            raise ValueError(f"Step '{step.id}': foreach exceeds max_iterations ({len(items)} > {step.max_iterations})")

        # Get loop variable name
        loop_var = step.as_var or "item"
        results = []

        for idx, item in enumerate(items):
            # Set loop variable in context
            context[loop_var] = item

            try:
                result = await self.execute_step_with_retry(step, context)
                results.append(result)
            except SkipRemainingError:
                # Propagate skip_remaining
                raise
            except Exception as e:
                # Fail fast - no partial completion in MVP
                raise ValueError(f"Step '{step.id}' iteration {idx} failed: {e}") from e
            finally:
                # Clean up loop variable (scoped to loop only)
                if loop_var in context:
                    del context[loop_var]

        # Store results
        if step.collect:
            context[step.collect] = results
        elif step.output and results:
            context[step.output] = results[-1]  # Last iteration result

    def _resolve_foreach_variable(self, foreach: str, context: dict[str, Any]) -> Any:
        """
        Resolve {{variable}} to its value.

        Args:
            foreach: String containing {{variable}} reference
            context: Current context variables

        Returns:
            The resolved value

        Raises:
            ValueError: If variable syntax invalid or undefined
        """
        pattern = r"\{\{(\w+(?:\.\w+)*)\}\}"
        match = re.match(pattern, foreach.strip())
        if not match:
            raise ValueError(f"Invalid foreach syntax: {foreach}")

        var_path = match.group(1)
        parts = var_path.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                raise ValueError(f"Undefined variable in foreach: {foreach}")
        return value

    def substitute_variables(self, template: str, context: dict[str, Any]) -> str:
        """
        Replace {{variable}} references with context values.

        Args:
            template: String with {{variable}} placeholders
            context: Dict with variable values

        Returns:
            String with variables substituted

        Raises:
            ValueError if variable undefined
        """
        pattern = r"\{\{(\w+(?:\.\w+)?)\}\}"

        def replace(match: re.Match) -> str:
            var_ref = match.group(1)

            # Handle nested references (recipe.name, session.id, etc.)
            if "." in var_ref:
                parts = var_ref.split(".")
                value = context
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        raise ValueError(
                            f"Undefined variable: {{{{{var_ref}}}}}. "
                            f"Available variables: {', '.join(sorted(context.keys()))}"
                        )
                return str(value)

            # Handle direct references
            if var_ref not in context:
                available = ", ".join(sorted(context.keys()))
                raise ValueError(f"Undefined variable: {{{{{var_ref}}}}}. Available variables: {available}")

            return str(context[var_ref])

        return re.sub(pattern, replace, template)
