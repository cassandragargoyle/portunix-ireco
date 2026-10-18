# Testing Methodology - portunix-ireco

## Overview

This document defines standard procedures for testing in the portunix-ireco project
with emphasis on detailed logging, structured test output, and reproducible results.

## Verbose Testing Framework

### Core Principles

All tests should provide:

- **Detailed logging** with clear indicators for success/error/warning
- **Verbose mode** for debugging, activated by test runner flags
- **Structured steps** with sequential numbering
- **Timing information** and summary at test completion
- **Clear differentiation** for success and error states

### Test Output Standards

**Minimal output (default):**

```text
=== RUN   TestFeature
--- PASS: TestFeature (2.34s)
PASS
```

**Verbose output (debugging):**

```text
================================================================================
STARTING: FeatureName
Description: Test feature functionality with detailed logging
Time: 2026-01-15T10:30:00Z
================================================================================

STEP 1: Setup test environment
   Binary/service found
   Configuration loaded

STEP 2: Test main functionality
   Executing: command --flag value
   Output: (truncated to relevant portion)
   Assertion passed

================================================================================
COMPLETED: FeatureName
Duration: 2.345s
Steps: 3
================================================================================
```

## Test Structure

### Recommended Pattern

Every test should follow this structure:

1. **Setup** - Prepare test environment, dependencies, and test data
2. **Execution** - Run the functionality under test
3. **Verification** - Assert expected outcomes
4. **Cleanup** - Restore state if necessary (prefer using test framework teardown)

### Test Naming Convention

- Test names should describe what is being tested
- Use descriptive names: `TestUserLogin_WithInvalidPassword_ReturnsError`
- Group related tests logically

## Container-Based Testing

### Isolation Policy

Software installation and integration testing SHOULD be performed in isolated containers when possible, to protect the host development system.

#### Benefits

- **Host protection**: Prevents contamination of development environment
- **Isolation**: Each test runs in clean, reproducible environment
- **Safety**: Eliminates risk of conflicts with existing host software
- **Consistency**: Standardized testing environment across all developers

#### Recommended Base Images

- **Ubuntu**: `ubuntu:22.04` or `ubuntu:24.04` (primary testing)
- **Debian**: `debian:bookworm` (compatibility testing)
- **Alpine**: `alpine:latest` (minimal environment testing)

#### Container Testing Workflow

1. **Environment preparation** - Create fresh container instance
2. **Dependency setup** - Install required dependencies in container
3. **Test execution** - Run tests inside isolated container
4. **Result collection** - Capture output and artifacts
5. **Cleanup** - Destroy container after test completion

## Acceptance Protocol

### Template

When testing is completed, create an acceptance protocol document:

```markdown
# Acceptance Protocol - Issue #{number}

**Issue**: {issue-title}
**Branch**: feature/{number}-{short-name}
**Tester**: {tester-name}
**Date**: {test-date}
**Testing OS**: {operating-system} (host/container/VM)

## Test Summary
- Total test scenarios: {count}
- Passed: {count}
- Failed: {count}
- Skipped: {count}

## Test Results
### Functional Tests
- [ ] Feature works as specified
- [ ] Acceptance criteria met
- [ ] Edge cases handled

### Regression Tests
- [ ] Existing functionality unaffected
- [ ] Cross-platform compatibility verified

## Final Decision
**STATUS**: [PASS/FAIL/CONDITIONAL]

**Approval for merge**: [YES/NO]
**Date**: {approval-date}
**Tester signature**: {tester-name}
```

## Recommended Practices

### 1. Test Early, Test Often

- Write tests alongside implementation, not after
- Run the full test suite before committing
- Use CI/CD to enforce test execution on every push

### 2. Clear Error Messages

- When a test fails, the message should explain what was expected vs what happened
- Include relevant context (input values, configuration state)
- Avoid generic messages like "test failed"

### 3. Independent Tests

- Tests should not depend on execution order
- Each test should set up its own prerequisites
- Clean up any state changes after each test

### 4. Coverage Targets

- Aim for meaningful coverage, not just high percentages
- Focus on critical paths and error handling
- Test boundary conditions and edge cases

### 5. Optional-dependency markers

Tests that depend on host-provided binaries or optional Python
packages must use a pytest marker so they skip cleanly in
environments where the prerequisite is absent. Markers live in
`pyproject.toml` under `[tool.pytest.ini_options].markers`. The
skip behaviour is wired in `tests/conftest.py:pytest_collection_modifyitems`.

Currently registered markers:

| Marker                 | Skips when…                                                  | Owner       |
|------------------------|--------------------------------------------------------------|-------------|
| `requires_tesseract`   | `tesseract` binary is not on `PATH`.                         | issue 007   |
| `requires_pdf2image`   | `pdf2image` Python package (or Poppler) is not importable.   | issue 007   |

Apply via module-scoped `pytestmark = [pytest.mark.requires_tesseract,
pytest.mark.requires_pdf2image]` or per-test
`@pytest.mark.requires_tesseract`. A skipped test must never be
counted as a pass for acceptance — the tester runs the suite with all
prerequisites installed.

## Process Enforcement

### Developer Responsibilities

- Add tests for all new functionality
- Ensure all tests pass before requesting review
- Document any manual testing steps required

### Tester Responsibilities

- Execute tests in clean environment
- Create acceptance protocol with detailed results
- Report issues with reproduction steps

---

**Created**: 2026-04-19
**Version**: 1.0
