# Recipe Schema Reference

**Complete YAML specification for Amplifier recipes**

This document defines the complete schema for recipe YAML files. Every field, constraint, and behavior is documented here.

## Overview

Recipes are declarative YAML specifications that define multi-step agent workflows. The tool-recipes module parses and executes these specifications.

**Schema Version:** 1.0.0

## Top-Level Structure

```yaml
name: string                    # Required
description: string             # Required
version: string                 # Required (semver format)
author: string                  # Optional
created: ISO8601 datetime       # Optional
updated: ISO8601 datetime       # Optional
tags: list[string]             # Optional
context: dict                   # Optional - Initial context variables
steps: list[Step]              # Required - At least one step
```

### Top-Level Fields

#### `name` (required)

**Type:** string
**Constraints:**
- Must be unique within your recipe library
- Alphanumeric, hyphens, underscores only
- Max length: 100 characters

**Purpose:** Identifies the recipe in logs and UI.

**Examples:**
```yaml
name: "code-review-flow"
name: "dependency-upgrade"
name: "test-generation-pipeline"
```

#### `description` (required)

**Type:** string
**Constraints:**
- Max length: 500 characters
- Should be a single paragraph

**Purpose:** Human-readable explanation of what the recipe does.

**Examples:**
```yaml
description: "Multi-stage code review with analysis, feedback, and validation"
description: "Systematic dependency upgrade with audit, planning, and validation"
```

#### `version` (required)

**Type:** string (semantic versioning)
**Constraints:**
- Must follow semver: `MAJOR.MINOR.PATCH`
- Example: `1.0.0`, `2.3.1`, `0.1.0-beta`

**Purpose:** Track recipe evolution and compatibility.

**Breaking change semantics:**
- MAJOR: Incompatible changes (different inputs/outputs)
- MINOR: Backward-compatible additions (new optional steps)
- PATCH: Bug fixes, documentation updates

**Examples:**
```yaml
version: "1.0.0"
version: "2.1.3"
version: "0.5.0-alpha"
```

#### `author` (optional)

**Type:** string
**Purpose:** Credit recipe creator.

**Examples:**
```yaml
author: "Jane Doe <jane@example.com>"
author: "DevOps Team"
```

#### `created` (optional)

**Type:** ISO8601 datetime string
**Purpose:** Track recipe creation date.

**Examples:**
```yaml
created: "2025-11-18T14:30:00Z"
created: "2025-11-18T14:30:00-08:00"
```

#### `updated` (optional)

**Type:** ISO8601 datetime string
**Purpose:** Track last modification date.

**Examples:**
```yaml
updated: "2025-11-20T09:15:00Z"
```

#### `tags` (optional)

**Type:** list of strings
**Purpose:** Categorize recipes for discovery.

**Examples:**
```yaml
tags: ["code-quality", "analysis", "python"]
tags: ["security", "audit", "dependencies"]
tags: ["documentation", "improvement"]
```

#### `context` (optional)

**Type:** dictionary (string keys, any values)
**Purpose:** Define initial context variables available to all steps.

**Examples:**
```yaml
context:
  project_name: "my-app"
  target_version: "3.11"
  severity_threshold: "high"
```

**Usage in steps:**
```yaml
steps:
  - id: "analyze"
    prompt: "Analyze {{project_name}} for Python {{target_version}} compatibility"
```

#### `steps` (required)

**Type:** list of Step objects
**Constraints:**
- At least one step required
- Step IDs must be unique within recipe
- Steps execute in order

**Purpose:** Define the workflow.

---

## Step Object

Each step represents one agent invocation in the workflow.

```yaml
- id: string                    # Required - Unique within recipe
  agent: string                 # Required - Agent name or sub-agent config
  mode: string                  # Optional - Agent mode (if agent supports)
  prompt: string                # Required - Prompt template with variables
  condition: string             # Optional - Expression that must evaluate to true
  foreach: string               # Optional - Variable containing list to iterate
  as: string                    # Optional - Loop variable name (default: "item")
  collect: string               # Optional - Variable to collect all iteration results
  max_iterations: integer       # Optional - Safety limit (default: 100)
  output: string                # Optional - Variable name for step result
  agent_config: dict            # Optional - Override agent configuration
  timeout: integer              # Optional - Max execution time (seconds)
  retry: dict                   # Optional - Retry configuration
  on_error: string              # Optional - Error handling strategy
  depends_on: list[string]      # Optional - Step IDs that must complete first
```

### Step Fields

#### `id` (required)

**Type:** string
**Constraints:**
- Must be unique within recipe
- Alphanumeric, hyphens, underscores only
- Max length: 50 characters

**Purpose:** Identify step in logs, resumption, and dependency references.

**Examples:**
```yaml
- id: "analyze-code"
- id: "generate-tests"
- id: "validate-results"
```

#### `agent` (required)

**Type:** string (agent name)
**Purpose:** Specify which agent to spawn for this step.

**Agent sources:**
- Built-in agents (installed via collections)
- Profile-defined agents (in your active profile)
- Custom agents (in `.amplifier/agents/`)

**Examples:**
```yaml
- agent: "zen-architect"
- agent: "bug-hunter"
- agent: "test-coverage"
- agent: "custom-analyzer"
```

**Validation:**
- Agent must be available when recipe executes
- Tool checks agent availability before starting recipe
- Fails fast if agent not found

#### `mode` (optional)

**Type:** string
**Purpose:** Specify agent mode if agent supports multiple modes.

**Example (zen-architect modes):**
```yaml
- agent: "zen-architect"
  mode: "ANALYZE"    # Analysis mode

- agent: "zen-architect"
  mode: "ARCHITECT"  # Design mode

- agent: "zen-architect"
  mode: "REVIEW"     # Review mode
```

**Behavior:**
- If omitted, agent uses default mode
- If specified but agent doesn't support modes, ignored with warning
- Mode passed to agent via context injection

#### `prompt` (required)

**Type:** string (template)
**Purpose:** Define what the agent should do.

**Template variables:**
- `{{variable_name}}` - Replaced with context value
- Context sources:
  - Top-level `context` dict
  - Previous step outputs (if step specified `output`)
  - Recipe metadata (`{{recipe.name}}`, `{{recipe.version}}`)

**Examples:**

Simple prompt:
```yaml
prompt: "Analyze the Python code for type safety issues"
```

With variables:
```yaml
prompt: "Analyze {{file_path}} for compatibility with Python {{target_version}}"
```

Multi-line prompt:
```yaml
prompt: |
  Review this code for security issues:

  File: {{file_path}}
  Previous analysis: {{analysis}}

  Focus on: {{focus_areas}}
```

Accessing previous step output:
```yaml
steps:
  - id: "analyze"
    prompt: "Analyze {{file_path}}"
    output: "analysis"

  - id: "improve"
    prompt: "Given this analysis: {{analysis}}, suggest improvements"
```

**Undefined variables:**
- If variable undefined, step fails with clear error
- Use `context` dict to define required variables upfront
- Check variable availability with `depends_on`

#### `condition` (optional)

**Type:** string (expression)
**Purpose:** Skip step if condition evaluates to false.

**Syntax:**
- Variable references: `{{variable}}` or `{{object.property}}`
- Comparison operators: `==`, `!=`
- Boolean operators: `and`, `or`
- String literals: `'value'` or `"value"`

**Examples:**

Simple equality:
```yaml
- id: "critical-fix"
  condition: "{{severity}} == 'critical'"
  agent: "auto-fixer"
  prompt: "Auto-fix critical issues"
```

With nested variable access:
```yaml
- id: "apply-fixes"
  condition: "{{analysis.severity}} == 'critical'"
  agent: "fixer"
  prompt: "Apply fixes for: {{analysis.issues}}"
```

Compound conditions:
```yaml
- id: "deploy"
  condition: "{{tests_passed}} == 'true' and {{review_approved}} == 'true'"
  agent: "deployer"
  prompt: "Deploy to production"
```

Alternative conditions:
```yaml
- id: "escalate"
  condition: "{{severity}} == 'critical' or {{severity}} == 'high'"
  agent: "notifier"
  prompt: "Escalate to on-call team"
```

**Behavior:**
- Condition is `true` → Execute step normally
- Condition is `false` → Skip step, continue to next
- Undefined variable in condition → **Fail recipe** with clear error
- Invalid syntax → **Fail recipe** with parse error
- Skipped step with `output` field → Output variable remains undefined

**Rationale:** Fail fast on errors. Silent skips would mask configuration problems.

See [Condition Expressions](#condition-expressions) for complete syntax reference.

#### `foreach` (optional)

**Type:** string (variable reference)
**Purpose:** Iterate over a list, executing the step once per item.

**Syntax:**
- Must contain a variable reference: `{{variable_name}}`
- Referenced variable must be a list at runtime

**Examples:**
```yaml
- id: "discover-files"
  agent: "explorer"
  prompt: "List all Python files in {{directory}}"
  output: "files"  # Returns list: ["a.py", "b.py", "c.py"]

- id: "analyze-each"
  foreach: "{{files}}"
  as: "current_file"
  agent: "analyzer"
  prompt: "Analyze {{current_file}} for issues"
  collect: "file_analyses"
```

**Behavior:**
- `foreach` variable is list → Iterate over each item
- `foreach` variable is empty list → Skip step (no error)
- `foreach` variable is not a list → **Fail recipe** with clear error
- `foreach` variable undefined → **Fail recipe** with clear error
- Exceeds `max_iterations` → **Fail recipe** with limit error
- Any iteration fails → **Fail recipe** immediately (fail-fast)

**Rationale:** Fail fast and visibly. Silent partial failures hide bugs.

See [Looping and Iteration](#looping-and-iteration) for complete syntax reference.

#### `as` (optional)

**Type:** string (variable name)
**Default:** `"item"`
**Purpose:** Name of loop variable available within the iteration.

**Constraints:**
- Must be valid variable name (alphanumeric, underscores)
- Cannot conflict with reserved names (`recipe`, `step`, `session`)

**Examples:**
```yaml
# Using default "item"
- foreach: "{{files}}"
  prompt: "Process {{item}}"

# Using custom name
- foreach: "{{files}}"
  as: "current_file"
  prompt: "Process {{current_file}}"
```

**Scope:**
- Loop variable only available within the loop step
- Not available in subsequent steps (loop-scoped)

#### `collect` (optional)

**Type:** string (variable name)
**Purpose:** Aggregate all iteration results into a list variable.

**Constraints:**
- Must be valid variable name (alphanumeric, underscores)
- Cannot conflict with reserved names (`recipe`, `step`, `session`)

**Examples:**
```yaml
- id: "analyze-each"
  foreach: "{{files}}"
  as: "file"
  prompt: "Analyze {{file}}"
  collect: "all_analyses"  # List of all iteration results

- id: "summarize"
  prompt: "Summarize these analyses: {{all_analyses}}"
```

**Behavior:**
- Collects results in order of iteration
- Available to subsequent steps after loop completes
- If `collect` omitted and `output` specified, `output` contains last iteration result only

#### `max_iterations` (optional)

**Type:** integer
**Default:** 100
**Purpose:** Safety limit to prevent runaway loops.

**Constraints:**
- Must be positive integer

**Examples:**
```yaml
# Default limit of 100
- foreach: "{{files}}"
  prompt: "Process {{item}}"

# Higher limit for large batches
- foreach: "{{large_dataset}}"
  max_iterations: 500
  prompt: "Process {{item}}"

# Lower limit for safety
- foreach: "{{untrusted_input}}"
  max_iterations: 10
  prompt: "Process {{item}}"
```

**Behavior:**
- If list length exceeds `max_iterations`, recipe fails with clear error
- Error message shows actual count vs limit

#### `output` (optional)

**Type:** string (variable name)
**Purpose:** Store step result in context for later steps.

**Constraints:**
- Must be valid variable name (alphanumeric, underscores)
- Cannot conflict with reserved names (`recipe`, `step`, `session`)

**Examples:**
```yaml
- id: "analyze"
  prompt: "Analyze code"
  output: "analysis"     # Stores result as {{analysis}}

- id: "improve"
  prompt: "Review: {{analysis}}"
  output: "improvements" # Stores as {{improvements}}
```

**Behavior:**
- If omitted, step result not stored (use for terminal steps)
- Stored results persist across session checkpoints
- Available to all subsequent steps

#### `agent_config` (optional)

**Type:** dictionary (partial agent config)
**Purpose:** Override agent configuration for this step.

**Use cases:**
- Adjust temperature for creative vs analytical steps
- Use different models for different steps
- Add step-specific tools

**Example:**
```yaml
- id: "creative-brainstorm"
  agent: "zen-architect"
  agent_config:
    providers:
      - module: "provider-anthropic"
        config:
          temperature: 0.8  # More creative than agent's default
          model: "claude-opus-4"
    tools:
      - module: "tool-web-search"  # Add web search for this step only
  prompt: "Brainstorm innovative architectures"
```

**Merge behavior:**
- Specified fields override agent defaults
- Unspecified fields inherit from agent config
- Deep merge for nested dicts (providers, tools, etc.)

#### `timeout` (optional)

**Type:** integer (seconds)
**Default:** 600 (10 minutes)
**Purpose:** Prevent hanging on unresponsive steps.

**Examples:**
```yaml
- timeout: 300   # 5 minutes
- timeout: 1800  # 30 minutes for long-running analysis
```

**Behavior:**
- If step exceeds timeout, execution cancelled
- Error logged with clear timeout message
- Recipe can resume from checkpoint (step retries)

#### `retry` (optional)

**Type:** dictionary
**Purpose:** Configure retry behavior for transient failures.

**Schema:**
```yaml
retry:
  max_attempts: integer     # Default: 3
  backoff: string          # "exponential" or "linear", default: "exponential"
  initial_delay: integer   # Seconds, default: 5
  max_delay: integer       # Seconds, default: 300
```

**Example:**
```yaml
- id: "fetch-data"
  agent: "data-fetcher"
  prompt: "Fetch latest data from API"
  retry:
    max_attempts: 5
    backoff: "exponential"
    initial_delay: 10
    max_delay: 300
```

**Retry behavior:**
- Only retries on transient errors (network, timeout, rate limit)
- Does not retry on validation errors or agent failures
- Each retry logs attempt number and delay
- Exponential backoff: delay doubles each attempt (10s, 20s, 40s, ...)

#### `on_error` (optional)

**Type:** string (error handling strategy)
**Values:**
- `"fail"` (default) - Stop recipe execution
- `"continue"` - Log error, continue to next step
- `"skip_remaining"` - Skip remaining steps, mark recipe as partial success

**Examples:**
```yaml
- id: "optional-validation"
  agent: "validator"
  prompt: "Validate results"
  on_error: "continue"  # Don't fail recipe if validation fails
```

**Use cases:**
- `"continue"`: Optional validation, non-critical steps
- `"skip_remaining"`: Guard steps that make remaining work unnecessary
- `"fail"`: Default - any failure stops recipe

#### `depends_on` (optional)

**Type:** list of strings (step IDs)
**Purpose:** Explicit dependencies between steps.

**Default behavior:**
- Steps execute in order
- Each step depends on all previous steps

**Use `depends_on` when:**
- Future parallel execution (not yet implemented)
- Explicit dependency documentation
- Conditional step execution (future)

**Example:**
```yaml
steps:
  - id: "analyze-security"
    prompt: "Security analysis"
    output: "security_report"

  - id: "analyze-performance"
    prompt: "Performance analysis"
    output: "performance_report"

  - id: "generate-summary"
    depends_on: ["analyze-security", "analyze-performance"]
    prompt: "Summarize: {{security_report}} and {{performance_report}}"
```

**Validation:**
- Referenced step IDs must exist in recipe
- No circular dependencies
- Dependencies must appear before dependent step in YAML

---

## Variable Substitution

### Template Syntax

Variables use double-brace syntax: `{{variable_name}}`

### Variable Sources

Variables come from multiple sources (priority order):

1. **Step outputs** - `output` from previous steps
2. **Top-level context** - `context` dict in recipe
3. **Recipe metadata** - `recipe.*` variables
4. **Session metadata** - `session.*` variables

### Reserved Variables

Available in all steps:

```yaml
{{recipe.name}}         # Recipe name
{{recipe.version}}      # Recipe version
{{recipe.description}}  # Recipe description

{{session.id}}          # Current session ID
{{session.started}}     # Session start timestamp
{{session.project}}     # Project path (slugified)

{{step.id}}             # Current step ID
{{step.index}}          # Step number (0-based)
```

### Example

```yaml
context:
  file_path: "src/auth.py"
  severity: "high"

steps:
  - id: "analyze"
    prompt: |
      Recipe: {{recipe.name}} v{{recipe.version}}
      Session: {{session.id}}

      Analyze {{file_path}} for {{severity}}-severity issues
    output: "analysis"

  - id: "report"
    prompt: |
      Create report for:
      File: {{file_path}}
      Analysis: {{analysis}}

      Step {{step.index}} of recipe
```

### Undefined Variables

If variable undefined at runtime:
- Execution fails with clear error
- Error message shows variable name and available variables
- Session checkpointed (can fix and resume)

---

## Condition Expressions

Step conditions use a simple expression syntax for runtime evaluation.

### Syntax Overview

```
<expression> := <comparison> | <expression> "and" <expression> | <expression> "or" <expression>
<comparison> := <value> <operator> <value>
<operator>   := "==" | "!="
<value>      := <variable> | <string-literal>
<variable>   := "{{" identifier ("." identifier)* "}}"
<string>     := "'" chars "'" | '"' chars '"'
```

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equality | `{{status}} == 'approved'` |
| `!=` | Inequality | `{{status}} != 'pending'` |
| `and` | Both must be true | `{{a}} == 'x' and {{b}} == 'y'` |
| `or` | Either can be true | `{{a}} == 'x' or {{b}} == 'y'` |

### Variable References

Variables use the same `{{variable}}` syntax as prompt templates:

```yaml
# Simple variable
condition: "{{status}} == 'approved'"

# Nested access
condition: "{{report.severity}} == 'critical'"

# From step output
condition: "{{analysis_result}} != 'failed'"
```

### String Literals

String values must be quoted with single or double quotes:

```yaml
# Single quotes
condition: "{{status}} == 'approved'"

# Double quotes
condition: '{{status}} == "approved"'
```

### Boolean Logic

Combine conditions with `and` / `or`:

```yaml
# Both conditions must be true
condition: "{{security_passed}} == 'true' and {{tests_passed}} == 'true'"

# Either condition can be true
condition: "{{severity}} == 'critical' or {{severity}} == 'high'"

# Chained conditions (evaluated left to right)
condition: "{{a}} == 'x' and {{b}} == 'y' or {{c}} == 'z'"
```

**Note:** Operator precedence is left-to-right. For complex conditions, break into multiple steps.

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Condition evaluates to `true` | Execute step normally |
| Condition evaluates to `false` | Skip step, continue to next |
| Undefined variable | **Fail recipe** with clear error message |
| Invalid syntax | **Fail recipe** with parse error |

**Example error:**
```
Step 'critical-fix' condition error: Undefined variable in condition: {{missing}}.
Available: severity, analysis, report
```

### Session State

Skipped steps are tracked in session state:

```json
{
  "skipped_steps": [
    {
      "id": "critical-fix",
      "reason": "condition evaluated to false",
      "condition": "{{severity}} == 'critical'"
    }
  ]
}
```

### Complete Example

```yaml
name: "conditional-code-review"
description: "Review with conditional fixes based on severity"
version: "1.0.0"

context:
  file_path: "src/auth.py"

steps:
  - id: "analyze"
    agent: "analyzer"
    prompt: "Analyze {{file_path}} for issues"
    output: "analysis"

  - id: "critical-fix"
    condition: "{{analysis.severity}} == 'critical'"
    agent: "fixer"
    prompt: "Fix critical issues in {{file_path}}: {{analysis.issues}}"
    output: "fixes"

  - id: "high-priority-review"
    condition: "{{analysis.severity}} == 'high' or {{analysis.severity}} == 'critical'"
    agent: "reviewer"
    prompt: "Review high-priority issues: {{analysis}}"
    output: "review"

  - id: "report"
    agent: "reporter"
    prompt: |
      Generate report:
      Analysis: {{analysis}}
      Fixes: {{fixes}}
      Review: {{review}}
```

### Deferred Features

These operators are not yet implemented but may be added based on need:

- Numeric comparisons: `>`, `<`, `>=`, `<=`
- Negation: `not`
- String functions: `.contains()`, `.startswith()`, `.endswith()`
- Parentheses for grouping

---

## Looping and Iteration

Steps with a `foreach` field iterate over a list variable, executing the step once per item.

### Basic Syntax

```yaml
- id: "process-each"
  foreach: "{{items}}"     # Variable containing list
  as: "current_item"       # Loop variable name (default: "item")
  agent: "processor"
  prompt: "Process {{current_item}}"
  collect: "all_results"   # Aggregates iteration results
```

### How It Works

1. **Resolve `foreach` variable** → Must be a list
2. **For each item** in list:
   - Set loop variable (`as`) to current item
   - Substitute variables in prompt
   - Execute step (spawn agent)
   - Add result to collect list (if `collect` specified)
3. **After all iterations**:
   - Remove loop variable from context (scope ends)
   - Store collected results (if `collect` specified)

### Variable Scoping

```yaml
steps:
  - id: "process"
    foreach: "{{files}}"
    as: "current_file"
    prompt: "Process {{current_file}}"  # current_file available here
    output: "result"
    collect: "all_results"

  - id: "summary"
    prompt: "Summarize {{all_results}}"  # all_results available
    # current_file NOT available here (loop-scoped)
```

**Scope rules:**
- Loop variable (`as`) only available within the loop step
- `collect` variable available after loop completes
- Step `output` is the LAST iteration result (if not using `collect`)

### Error Handling (Fail-Fast)

| Scenario | Behavior |
|----------|----------|
| `foreach` variable is list | Iterate over each item |
| `foreach` variable is empty list | Skip step (no error) |
| `foreach` variable is not list | **Fail recipe** with clear error |
| `foreach` variable undefined | **Fail recipe** with clear error |
| Iteration exceeds `max_iterations` | **Fail recipe** with limit error |
| Any iteration fails | **Fail recipe** immediately |

**Rationale:** Fail fast and visibly during development. Silent partial failures hide bugs. If partial completion is needed later, that can be added.

### Interaction with Conditions

```yaml
- id: "process-if-needed"
  condition: "{{should_process}} == 'true'"  # Check BEFORE loop
  foreach: "{{files}}"
  as: "file"
  prompt: "Process {{file}}"
  collect: "results"
```

**Behavior:** Condition evaluated once. If false, entire loop skipped.

### Complete Example

```yaml
name: "batch-file-analyzer"
description: "Analyze multiple files and synthesize results"
version: "1.0.0"

context:
  directory: "src"

steps:
  - id: "discover-files"
    agent: "explorer"
    prompt: "List all Python files in {{directory}}"
    output: "files"

  - id: "analyze-each"
    foreach: "{{files}}"
    as: "current_file"
    agent: "analyzer"
    prompt: |
      Analyze {{current_file}} for:
      - Code complexity
      - Security issues
      - Performance concerns
    collect: "file_analyses"

  - id: "synthesize"
    agent: "zen-architect"
    mode: "ANALYZE"
    prompt: |
      Synthesize these individual file analyses into overall findings:

      {{file_analyses}}

      Prioritize by severity and provide actionable recommendations.
    output: "final_report"
```

### Edge Cases

1. **Empty list**: Skip step, no error (common case)
2. **Single item list**: Works like normal step (minimal overhead)
3. **Very large list**: Respect `max_iterations` (default 100)
4. **Nested variable in foreach**: `{{results.files}}` should work
5. **Loop variable shadows context**: Local scope takes precedence
6. **Condition + foreach**: Condition checked once, not per iteration

### Deferred Features

These features may be added based on real usage needs:

- `continue_on_error` - partial completion on failures
- Checkpointing/resumability for long loops
- Parallel iteration (`parallel: true`)
- Nested loops (`nested_foreach`)
- Index variable (`index_as`)
- Early termination (`break_if`)

---

## Validation Rules

The tool-recipes module validates recipes before execution:

### Recipe-Level Validation

- [ ] `name` present and valid format
- [ ] `description` present
- [ ] `version` present and valid semver
- [ ] `steps` list not empty
- [ ] All step IDs unique

### Step-Level Validation

- [ ] `id` present and unique
- [ ] `agent` present and available
- [ ] `prompt` present and non-empty
- [ ] `condition` contains at least one variable if present
- [ ] `timeout` positive integer if present
- [ ] `retry.max_attempts` positive if present
- [ ] `on_error` valid value if present
- [ ] `depends_on` references existing step IDs
- [ ] No circular dependencies

### Variable Validation

- [ ] Template variables have valid syntax
- [ ] Referenced variables will be available at runtime
- [ ] No conflicts with reserved variable names

### Runtime Validation

Before execution:
- [ ] All referenced agents installed and available
- [ ] All context variables defined or will be defined by prior steps
- [ ] Session directory writable
- [ ] No conflicting sessions for same recipe

---

## Complete Example

```yaml
name: "comprehensive-code-review"
description: "Multi-stage code review with security, performance, and maintainability analysis"
version: "2.1.0"
author: "Platform Team <platform@example.com>"
created: "2025-11-01T10:00:00Z"
updated: "2025-11-18T14:30:00Z"
tags: ["code-review", "security", "performance", "python"]

context:
  file_path: ""              # Required input
  severity_threshold: "high"  # Default severity level
  auto_fix: false            # Whether to auto-apply fixes

steps:
  - id: "security-scan"
    agent: "security-guardian"
    prompt: |
      Perform security audit on {{file_path}}
      Focus on severity: {{severity_threshold}}
    output: "security_findings"
    timeout: 600
    retry:
      max_attempts: 3
      backoff: "exponential"

  - id: "performance-analysis"
    agent: "performance-optimizer"
    prompt: "Analyze {{file_path}} for performance bottlenecks"
    output: "performance_findings"
    timeout: 600

  - id: "maintainability-review"
    agent: "zen-architect"
    mode: "REVIEW"
    prompt: |
      Review {{file_path}} for:
      - Code complexity
      - Philosophy alignment
      - Maintainability
    output: "maintainability_findings"
    timeout: 300

  - id: "synthesize-findings"
    agent: "zen-architect"
    mode: "ARCHITECT"
    prompt: |
      Synthesize findings from:

      Security: {{security_findings}}
      Performance: {{performance_findings}}
      Maintainability: {{maintainability_findings}}

      Prioritize by severity and provide actionable recommendations.
    output: "synthesis"
    timeout: 300

  - id: "generate-report"
    agent: "zen-architect"
    mode: "ANALYZE"
    prompt: |
      Create comprehensive review report:

      File: {{file_path}}
      Recipe: {{recipe.name}} v{{recipe.version}}
      Session: {{session.id}}

      Findings: {{synthesis}}

      Format as markdown with executive summary and detailed sections.
    output: "final_report"
    on_error: "continue"  # Report generation is non-critical
```

---

## Future Enhancements

These fields are documented for forward compatibility but not yet implemented:

### Parallel Execution

```yaml
- id: "parallel-analysis"
  parallel: true
  substeps:
    - id: "security"
      agent: "security-guardian"
      prompt: "Security scan"

    - id: "performance"
      agent: "performance-optimizer"
      prompt: "Performance scan"
```

---

## Schema Change History

### v1.1.0
- Looping and iteration (`foreach`, `as`, `collect`, `max_iterations`)
- Fail-fast iteration behavior

### v1.0.0 (Initial)
- Basic recipe structure
- Sequential step execution
- Context variables and template substitution
- Session persistence
- Conditional execution (`condition`)

---

**See Also:**
- [Recipes Guide](RECIPES_GUIDE.md) - Conceptual overview
- [Best Practices](BEST_PRACTICES.md) - Design patterns
- [Examples Catalog](EXAMPLES_CATALOG.md) - Working examples
