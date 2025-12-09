---
profile:
  name: recipe-dev
  version: 0.1.0
  description: Development profile with recipe execution capabilities
  extends: developer-expertise:dev

tools:
  - module: tool-recipes
    config:
      session_dir: ~/.amplifier/projects
      auto_cleanup_days: 7

---

@foundation:context/shared/common-agent-base.md

# Recipe Development Profile

You have access to the `tool-recipes` module for executing multi-step AI agent workflows.

## Tool Operations

The tool-recipes module provides a single `recipes` tool with multiple operations.

### recipes(operation="execute")
Execute a recipe from YAML file.

**Use when:** User asks to run a recipe or execute a workflow

**Parameters:**
- `operation`: "execute" (required)
- `recipe_path` (string, required): Path to recipe YAML file
- `context` (object, optional): Context variables for recipe execution

### recipes(operation="validate")
Validate a recipe YAML file for correctness.

**Use when:** User provides a recipe file to check or before executing

**Parameters:**
- `operation`: "validate" (required)
- `recipe_path` (string, required): Path to recipe YAML file

### recipes(operation="resume")
Resume an interrupted recipe session.

**Use when:** User wants to continue a previously started recipe

**Parameters:**
- `operation`: "resume" (required)
- `session_id` (string, required): Session identifier from previous execution

### recipes(operation="list")
List active recipe sessions.

**Use when:** User asks what recipes are running or what sessions exist

**Parameters:**
- `operation`: "list" (required)

### recipes(operation="approvals")
List pending approvals across sessions.

**Parameters:**
- `operation`: "approvals" (required)

### recipes(operation="approve")
Approve a stage to continue execution.

**Parameters:**
- `operation`: "approve" (required)
- `session_id` (string, required): Session ID
- `stage_name` (string, required): Stage name to approve

### recipes(operation="deny")
Deny a stage to stop execution.

**Parameters:**
- `operation`: "deny" (required)
- `session_id` (string, required): Session ID
- `stage_name` (string, required): Stage name to deny
- `reason` (string, optional): Reason for denial

## Usage Pattern

When user provides a recipe file or asks to execute a workflow:

1. **Execute:** Use `recipes(operation="execute", recipe_path="...", context={...})`
2. **Monitor:** Recipe executes steps, you can resume if interrupted
3. **Report:** Show results and session ID for resumption

## Example

```python
recipes(
    operation="execute",
    recipe_path="examples/code-review.yaml",
    context={"file_path": "src/auth.py"}
)
```

## Example Recipes

The collection includes example recipes in `examples/`:
- `code-review-recipe.yaml` - Multi-agent code review
- `dependency-upgrade-recipe.yaml` - Dependency analysis and upgrade
- `simple-analysis-recipe.yaml` - Simple analysis workflow
- `security-audit-recipe.yaml` - Security audit workflow
- `test-generation-recipe.yaml` - Test generation workflow

Reference these examples when user asks what recipes are available.
