# portunix-ireco Development Instructions

# CLAUDE.md (root)
@docs/contributing/
@docs/contributing/ISSUE-DEVELOPMENT-METHODOLOGY.md
@docs/contributing/TRANSLATION-WORKFLOW.md
@docs/contributing/TESTING_METHODOLOGY.md
@docs/contributing/GITHUB-WORKFLOW.md

## Project Information
- **GitHub Repository**: <https://github.com/cassandragargoyle/portunix-ireco>
- **Project Name**: portunix-ireco
- **Primary Purpose**: Purpose to be defined
- **Primary Language**: To be determined
- **Platforms**: Linux, Windows (macOS development status TBD)

## Security Guidelines
- Never run destructive commands without confirmation
- Always warn about potential data loss before executing risky operations
- Require explicit confirmation for operations that could lose implemented code

## Project Structure
- `/docs/` - Documentation including contributing guidelines
- `/scripts/` - Installation and setup scripts
- `/templates/` - Project templates
- `/config/` - Configuration files
- `/tests/` - Tests and validation
- `/utils/` - Helper utilities
- `/.claude/` - AI assistant configuration and roles

## Coding Guidelines & Development Instructions

### Strict Rules
- Code, code comments, and user messages must be in English (see [Multilingual Team Communication](docs/contributing/README.md#multilingual-team-communication))
- Communication with team members can be in their preferred language, but documentation remains in English
- When implementing new features, always check existing project structure first
- Prefer editing existing files over creating new ones
- Do not add "Generated with [Claude Code]" signatures to code or files
- NEVER add "Co-Authored-By: Claude" to code files or git commits
See docs/contributing/CODE-STYLE-*.md for language-specific guidelines

### General Principles
- Follow existing conventions and styles in the project
- Always explore existing code before creating new implementations
- Maintain consistency with established patterns
- All program text (messages, labels, constants) in English
- Comments in English, written as phrases (no ending periods)
- English is the official project language per multilingual team guidelines

### TODO Management
- Follow the established TODO format: `TODO:NNN [INITIALS]: description` (see [TODO Guidelines](docs/contributing/TODO-GUIDELINES.md))
- Use per-file sequential numbering (001, 002, 003, etc.)
- Refer to [docs/contributing/TODO-GUIDELINES.md](docs/contributing/TODO-GUIDELINES.md) for complete standards
- Use `TODO:XXX` as temporary placeholder, then request proper numbering

### Issue Tracking & Documentation
- **GitHub is the single source of truth** for the issue list (status, assignee, labels):
  <https://github.com/cassandragargoyle/portunix-ireco/issues>
- Long-form write-ups live in `docs/issues/NNN-name.md`, where `NNN` = GitHub issue number
- Archived (done) write-ups live in `docs/issues/done/`; there is no `internal/` or `public/` directory anymore
- There are no overview tables in `docs/issues/README.md` or `docs/issues/done/README.md`
- Legacy issues 001–007 map 1:1 to GitHub issues (`007` = `#7`)
- The repository is public: no customer data, real company identifiers, personal data, or links into private repositories in issues

#### Issue Workflow Process

1. **Creating new issue** (use the `create-issue` skill):
   - Create the GitHub issue first — GitHub assigns the number `NNN`
   - The GitHub body is short (English) and links to the issue file
   - Create `docs/issues/NNN-name.md` with the full write-up

2. **Updating existing issue:**
   - Edit `docs/issues/NNN-name.md` and synchronize relevant changes (title, labels, state) to GitHub

3. **Completing issue:**
   - Update the status in the issue file (✅ Implemented, ❌ Closed, or ➡️ Moved)
   - Move the file (and its verbatims file): `git mv docs/issues/NNN-name*.md docs/issues/done/`,
     then `git add docs/issues/done/NNN-name*.md` (`git mv` stages only the move)
   - Close the GitHub issue: `gh issue close NNN`
   - After the archive is on `main` on GitHub, point the "Full details" link in the
     GitHub issue body to `docs/issues/done/` (the old link returns 404)

See [docs/contributing/ISSUE-MANAGEMENT.md](docs/contributing/ISSUE-MANAGEMENT.md) for details.

### Team Communication
- English is the primary language for all project communication (see [Multilingual Team Communication](docs/contributing/README.md#multilingual-team-communication))
- Use simple, clear English to accommodate non-native speakers
- Avoid idioms, colloquialisms, and culture-specific references
- Team initials assignment follows collision resolution (JS → JSm if JS exists) (see [Team Initials Assignment](docs/contributing/README.md#team-initials-assignment-and-collision-resolution))

### AI Assistant Guidelines
- Claude Code is the preferred AI assistant with pre-configured context
- Alternative AI tools require users to prepare their own context materials
- Follow established AI assistant best practices in [docs/contributing/AI-ASSISTANTS.md](docs/contributing/AI-ASSISTANTS.md)

### Translation Workflow
- Use `.translated/` directory structure for team member translations
- Follow ISO 639-1 language codes (cs, de, fr, etc.)
- Refer to [docs/contributing/TRANSLATION-WORKFLOW.md](docs/contributing/TRANSLATION-WORKFLOW.md) for complete process
- Translations are temporary and can be regenerated as needed

### Repository Management
- Main branch is `main` (not `master`)
- Issues tracked on GitHub (see Issue Tracking & Documentation)
- Branches: `feature/NNN-short-name`, `fix/NNN-short-name`; commits: `feat(NNN): ...`
- License: MIT (see LICENSE)
- Remote `origin`: https://github.com/cassandragargoyle/portunix-ireco (Gitea is a read-only archive)

### System Information Detection
- **Always use** `portunix system info` for OS detection when Portunix is available
- **Only if Portunix is not available**, then use manual detection methods
- Don't write custom OS detection scripts when Portunix already provides this functionality

## Development Setup

### Prerequisites
To be defined based on project requirements

### Initial Setup
```bash
# Clone the repository
git clone https://github.com/cassandragargoyle/portunix-ireco.git
cd portunix-ireco

# Add project-specific setup commands here
```

### Build Instructions
```bash
# Add build commands here
```

## Testing

### Testing Methodology
- Refer to [docs/contributing/TESTING_METHODOLOGY.md](docs/contributing/TESTING_METHODOLOGY.md) for detailed testing standards
- Use verbose testing framework for integration tests to provide clear debugging output
- Always include step-by-step logging, timing, and error tracking in test output

### Testing Framework
- Framework: To be determined
- Test command: `# Add test command here`
- Coverage target: 80%

### Running Tests
```bash
# Add test command here
```

## Project-Specific Information

### Dependencies
Dependencies to be documented

### Architecture
Architecture to be documented

### Key Components
Key components to be documented

### Configuration
Configuration to be documented

### Deployment
Deployment process to be documented