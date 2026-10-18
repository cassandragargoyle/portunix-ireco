# Issue Development Methodology

## Overview

This document defines the mandatory workflow for issue development in the portunix-ireco project.
This methodology ensures quality, traceability, and proper testing before code integration into the main branch.

## Development Workflow

### Phase 1: Issue Creation & Planning

#### Role: Architect / Product Owner

1. **Issue Creation**
   - Create the GitHub issue first — GitHub assigns `{number}` (use `/create-issue`)
   - Create file `docs/issues/{number}-{slug}.md` and link it from the GitHub issue
     (use lowercase kebab-case slug per
     [ISSUE-MANAGEMENT.md](ISSUE-MANAGEMENT.md#file-naming))
   - Keep the GitHub body short; details live in the file (no README tables)
   - Define acceptance criteria and requirements
   - Assign type and priority labels on GitHub

2. **Technical Planning**
   - Define technical requirements
   - Identify affected components
   - Estimate implementation complexity
   - Branch naming convention: `feature/{number}-{short-name}` (features/enhancements),
     `fix/{number}-{short-name}` (bug fixes)

### Phase 2: Implementation

#### Role: Developer

1. **Branch Setup**
   - Assign the GitHub issue to yourself: `gh issue edit {number} --add-assignee @me`
   - Create feature branch from main: `git checkout -b feature/{number}-{short-name}`
   - Ensure branch is up-to-date with main before starting

2. **Development Process**
   - Follow existing code conventions and patterns
   - Implement minimal diffs with maximum impact
   - Add appropriate tests for new functionality
   - Document changes in code comments (English only)
   - Commit frequently with descriptive messages

3. **Pre-Testing Validation**
   - Run local tests and verify build
   - Verify no breaking changes to existing functionality
   - Self-review code changes

4. **Merge Restriction**
   - **CRITICAL**: Developer MUST NOT merge to main branch at this stage
   - Feature branch remains separate until tester approval
   - Push feature branch to repository for tester access

### Phase 3: Testing & Validation

#### Role: Tester

1. **Test Environment Setup**
   - Checkout feature branch: `git checkout feature/{number}-{short-name}`
   - Build and deploy in test environment
   - Prepare test data and scenarios
   - **OS Validation**: Verify testing environment matches tester role (Linux tester -> Linux tests, Windows tester -> Windows tests)
   - For container/VM testing: Accept tests based on container/VM OS, not host OS

2. **Testing Execution**
   - Execute functional tests based on acceptance criteria
   - Perform regression testing on related components
   - Test cross-platform compatibility (Windows/Linux)
   - Validate edge cases and error handling

3. **Acceptance Protocol Creation**
   - Create acceptance protocol document: `docs/testing/acceptance-{issue-number}.md`
   - Document all test scenarios and results
   - Include screenshots/logs where applicable
   - Record any issues or recommendations
   - **MANDATORY**: Document testing OS (host OS for local tests, container/VM OS for containerized tests)

4. **Acceptance Decision**
   - **PASS**: Issue ready for merge - create approval document
   - **FAIL**: Document blocking issues, return to developer
   - **CONDITIONAL**: List required changes before approval

### Phase 4: Integration

#### Role: Developer (with Tester approval)

1. **Pre-Merge Validation**
   - Verify acceptance protocol exists and shows PASS status
   - Ensure all tester recommendations are addressed
   - Rebase feature branch on current main if needed

2. **Merge Process**
   - Create merge request/pull request with acceptance protocol reference
   - Merge feature branch to main: `git merge feature/{number}-{short-name}`

3. **Issue Closure & Archival**
   - Update status to `✅ Implemented` in the issue file header and add the closing date
   - Archive the file (and its verbatims file):
     `git mv docs/issues/{number}-{slug}*.md docs/issues/done/`
   - Commit both changes (status update + archival) in a single commit,
     e.g. `docs({number}): close issue — archive to done/`
   - Close the GitHub issue with reference to the acceptance protocol:
     `gh issue close {number} --comment "Implemented, acceptance: docs/testing/acceptance-{number}.md"`

4. **Post-Merge Cleanup**
   - Delete feature branch after successful merge
   - Update any related documentation
   - Notify team of completed feature

### Issue Reference Resolution

Any tooling, slash command, or script that resolves an issue reference
by number (e.g. `/implement-issue 42`) **must look in both locations**:

1. `docs/issues/{number}-*.md` (active)
2. `docs/issues/done/{number}-*.md` (archived)

`{number}` is the GitHub issue number zero-padded to three digits
(`#42` → `042`). New issue files are always created in `docs/issues/`;
archival into `done/` happens only at closure. The GitHub issue
(`gh issue view {number}`) holds the current status and assignee.

## Quality Gates

### Mandatory Requirements

- Issue must have defined acceptance criteria
- Code must pass all automated tests
- Feature branch must build successfully
- Tester must create acceptance protocol
- Acceptance protocol must show PASS status
- No merge to main without tester approval

### Acceptance Protocol Template

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
- [x] Feature works as specified
- [x] Acceptance criteria met
- [ ] Edge cases handled

### Regression Tests
- [x] Existing functionality unaffected
- [x] Cross-platform compatibility verified

## Final Decision
**STATUS**: [PASS/FAIL/CONDITIONAL]

**Approval for merge**: [YES/NO]
**Date**: {approval-date}
**Tester signature**: {tester-name}
```

## Process Enforcement

### Developer Responsibilities

- Follow all development phases in order
- Never bypass testing phase
- Never merge without tester approval
- Maintain feature branch until approval received

### Tester Responsibilities

- Test within reasonable timeframe
- Provide detailed acceptance protocol
- Clearly communicate pass/fail status
- Document all findings and recommendations

### Architect/Product Owner Responsibilities

- Provide clear acceptance criteria
- Review acceptance protocols when needed
- Make final decisions on conditional approvals

## Exception Handling

### Critical Hotfixes

- May bypass normal workflow with architect approval
- Must be tested immediately after deployment
- Retroactive acceptance protocol required within 24 hours

### Testing Delays

- If tester unavailable, architect may designate alternate tester
- Testing deadline: 48 hours for normal issues, 24 hours for high priority
- Escalation to architect if testing timeline exceeded

## Benefits of This Methodology

1. **Quality Assurance**: Every change is thoroughly tested before integration
2. **Traceability**: Clear documentation trail from issue to implementation
3. **Risk Reduction**: No untested code reaches main branch
4. **Team Coordination**: Clear roles and responsibilities
5. **Documentation**: Comprehensive testing records for future reference

---

**Version**: 1.0
**Status**: Active
