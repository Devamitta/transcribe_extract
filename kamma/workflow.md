# Kamma Workflow

## Overview

This workflow guides the development process from planning through execution and verification.

## Phases

### Phase 1: Plan Mode

**Objective:** Define what needs to be done before doing it.

1. **Analyze Context**
   - Read relevant project files to understand current state
   - Identify what the user wants to accomplish
   - Check existing threads and their status

2. **Propose Approaches**
   - Suggest 2-3 approaches ranked from simplest to most complex
   - Include confidence rating (1-10) for each approach
   - Highlight trade-offs and dependencies

3. **User Selection**
   - Wait for user to select an approach
   - Clarify any ambiguities before proceeding

4. **Generate Plan**
   - Create detailed plan.md with specific tasks
   - Each task should be independently verifiable
   - Include acceptance criteria for each task

### Phase 2: Execution

**Objective:** Execute the plan systematically.

1. **Task-by-Task Execution**
   - Work through tasks in order
   - Verify each task before moving to next
   - Log progress and any blockers

2. **Handle Deviations**
   - If requirements change, return to Plan Mode
   - Document any scope changes

3. **Commit Progress**
   - Use descriptive commit messages
   - Commit after each logical unit of work

### Phase 3: Verification

**Objective:** Ensure the work is complete and correct.

1. **Run Tests**
   - Execute any existing tests
   - Verify expected behavior

2. **Code Quality**
   - Run linting and formatting
   - Fix any issues found

3. **User Review**
   - Present final result to user
   - Wait for approval before marking complete

## Thread Structure

Each thread has:
- `spec.md` - High-level specification
- `plan.md` - Detailed task list
- Status tracking in `kamma/threads.md`

## Commands

- `/kamma:1-plan` - Create new thread plan
- `/kamma:2-do` - Execute current thread
- `/kamma:3-verify` - Verify thread completion