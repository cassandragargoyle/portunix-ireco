# portunix-ireco Development Instructions

<!-- CLAUDE.md (root) -->

@.claude/roles/current.md

## Project Information

- **Repository**: <https://github.com/cassandragargoyle/portunix-ireco> (GitHub — single source of truth)
- **Project Name**: portunix-ireco ({{PROJECT_DESCRIPTION}})
- **Primary Purpose**: {{PRIMARY_PURPOSE}}
- **Primary Language**: {{PRIMARY_LANGUAGE}}
- **Platforms**: {{SUPPORTED_PLATFORMS}}

## Security Guidelines

- Never run destructive commands without confirmation
- Always warn about potential data loss before executing risky operations
- Require explicit confirmation for operations that could lose implemented code
- Follow secure coding practices for {{PRIMARY_LANGUAGE}}

## Project Structure

- `/docs/` - Documentation including contributing guidelines
- `/src/` - Source code
- `/config/` - Configuration files
- `/tests/` - Tests and validation
- `/scripts/` - Build and utility scripts
- `/templates/` - Project templates (if applicable)

## Coding Guidelines & Development Instructions

### Strict Rules

- Code, code comments, and user messages must be in English (see [Multilingual Team Communication](docs/contributing/README.md#multilingual-team-communication))
- Communication with team members can be in their preferred language, but documentation remains in English
- When implementing new features, always check existing project structure first
- Prefer editing existing files over creating new ones
- Do not add "Generated with [Claude Code]" signatures to code or files
- Use established project patterns and conventions

### General Principles

- Follow existing conventions and styles in the project
- Always explore existing code before creating new implementations
- Maintain consistency with established patterns
- All program text (messages, labels, constants) in English
- Comments in English, written as phrases (no ending periods)
- English is the official project language per multilingual team guidelines

### Language-Specific Guidelines

{{LANGUAGE_SPECIFIC_GUIDELINES}}

### TODO Management

- Follow the established TODO format: `TODO:NNN [INITIALS]: description` (see [TODO Guidelines](docs/contributing/TODO-GUIDELINES.md))
- Use per-file sequential numbering (001, 002, 003, etc.)
- Refer to [docs/contributing/TODO-GUIDELINES.md](docs/contributing/TODO-GUIDELINES.md) for complete standards
- Use `TODO:XXX` as temporary placeholder, then request proper numbering

### Issue Tracking & Documentation

- Issues are managed per project individually
- May sync to GitHub repositories when applicable
- portunix-ireco-specific issues: {{COMMON_ISSUE_TYPES}}

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
- Issues tracked on GitHub (https://github.com/cassandragargoyle/portunix-ireco/issues)
- {{LICENSE_TYPE}} license - {{LICENSE_SCOPE}}
- Links use format: https://github.com/cassandragargoyle/portunix-ireco

## Build & Development

### Prerequisites

{{PREREQUISITES}}

### Setup Commands

```bash
# Clone repository
git clone https://github.com/cassandragargoyle/portunix-ireco.git
cd portunix-ireco

{{SETUP_COMMANDS}}
```

### Build Commands

{{BUILD_COMMANDS}}

### Testing

- Testing framework: {{TESTING_FRAMEWORK}}
- Run tests: {{TEST_COMMAND}}
- Coverage target: {{COVERAGE_TARGET}}

### Dependencies

{{DEPENDENCIES_INFO}}

## Project-Specific Guidelines

### Architecture

{{ARCHITECTURE_INFO}}

### Key Components

{{KEY_COMPONENTS}}

### Configuration

{{CONFIGURATION_INFO}}

### Deployment

{{DEPLOYMENT_INFO}}

---

*This file provides development context and guidelines for portunix-ireco. Keep it updated as the project evolves.*
