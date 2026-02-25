# Agent Guide — Long-Running Agent Session Protocol

> This document defines how each AI agent session should behave.
> There are TWO modes: **Initializer** (first run) and **Coding Agent** (all subsequent runs).
> The initializer has already run. All future sessions are Coding Agent sessions.

---

## Coding Agent — Session Protocol

### Step 1: Get Your Bearings (MANDATORY, every session)

```bash
# 1. Where am I?
pwd

# 2. Run environment check
source init.sh

# 3. Read progress history
cat agent-progress.md

# 4. Read feature status
python3 -c "
import json
with open('feature_list.json') as f:
    features = json.load(f)
for feat in features:
    status = 'PASS' if feat['passes'] else 'TODO'
    print(f\"[{status}] {feat['id']}: {feat['description']}\")
"

# 5. Check recent git history
git log --oneline -20
```

### Step 2: Pick ONE Feature

- Read `feature_list.json`
- Find the **first** feature with `"passes": false`
- Features are ordered by dependency (Phase 1 before 2, etc.)
- **Work on exactly ONE feature per session**

### Step 3: Implement

- Write code, fix bugs, create files as needed
- Follow existing code patterns and conventions
- All analysis text should be in **Chinese** (matching existing templates)
- Run syntax checks after every file change:
  ```bash
  python3 -c "import py_compile; py_compile.compile('path/to/file.py', doraise=True)"
  ```

### Step 4: Verify

- Test the feature end-to-end, not just unit-level
- For template files: generate at least 5 scenarios and inspect output
- For scripts: run with small data and check output format
- For training: run a few iterations and confirm loss output
- **Only mark a feature as passing after thorough verification**

### Step 5: Update Feature Status

When a feature passes verification, update `feature_list.json`:

```python
import json

with open('feature_list.json', 'r') as f:
    features = json.load(f)

for feat in features:
    if feat['id'] == 'F-X.X':  # the feature you completed
        feat['passes'] = True
        break

with open('feature_list.json', 'w') as f:
    json.dump(features, f, ensure_ascii=False, indent=2)
```

**CRITICAL: Do NOT remove or edit feature descriptions or steps. Only change `passes` from `false` to `true`.**

### Step 6: Commit Progress

```bash
git add -A
git commit -m "feat(F-X.X): <brief description of what was done>"
```

Use descriptive commit messages. Examples:
- `feat(F-2.3.3): implement disk metric templates (5 generators)`
- `fix(F-2.3.1): fix syntax error in cpu_templates.py line 176`

### Step 7: Update Progress Log

Append a new session entry to `agent-progress.md`:

```markdown
## Session N — <Brief Title> (YYYY-MM-DD)

**What was done:**
- <bullet points of changes>

**Features completed:**
- F-X.X: <description>

**Known issues:**
- <any issues discovered but not fixed>

**Next session should:**
1. <specific next action>
2. <specific next action>
```

---

## Rules

1. **ONE feature per session.** Do not try to do everything at once.
2. **Leave the codebase in a clean state.** No half-implemented features, no broken imports.
3. **Never delete or modify feature definitions** in feature_list.json. Only flip `passes` to `true`.
4. **Always commit before ending a sessiont agent needs git history.
5. **Always update agent-progress.md.** The next agent needs context.
6. **Fix bugs before adding features.** If init.sh reports syntax errors, fix them first.
7. **Test like a user would.** Run the actual scripts, not just import checks.

---

## File Reference

| File | Purpose |
|------|---------|
| `init.sh` | Environment setup and validation. Run at session start. |
| `feature_list.json` | Feature tracking. JSON array, each with `passes` boolean. |
| `agent-progress.md` | Cross-session memory. Append-only progress log. |
| `AGENT_GUIDE.md` | This ession protocol for coding agents. |
| `openspec/requirements.md` | Project requirements and user stories. |
| `openspec/design.md` | Technical design and architecture. |
| `openspec/tasks.md` | Task breakdown with phases and dependencies. |

---

## Known Codebase Issues (as of Session 0)

These should be fixed BEFORE working on new features:

1. `data/templates/cpu_templates.py` line 176: `rnchoice` should be `rng.choice`
2. `data/templates/memory_templates.py` line 148: truncated line `rng.unifor   avail = ...`
3. `data/templates/disk_templates.py`: NOT YET CREATED (imported in __init__.py)
4. `data/templates/network_templates.py`: NOT YET CREATED (imported in __init__.py)
5. `data/templates/composite_templates.py`: NOT YET CREATED (imported in __init__.py)
6. `scripts/gen_templates.py`: abandoned/incomplete, can be deleted
7. Memory template analysis text is in English, should be Chinese
