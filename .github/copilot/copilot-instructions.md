# GitHub Copilot Instructions

## Priority Guidelines

When generating code for this repository:

1. **Version Compatibility**: Always detect and respect the exact versions of languages, frameworks, and libraries used in this project
2. **Context Files**: Prioritize patterns and standards defined in the .github/copilot directory
3. **Codebase Patterns**: When context files don't provide specific guidance, scan the codebase for established patterns
4. **Architectural Consistency**: Maintain the layered, modular architecture and established boundaries
5. **Code Quality**: Prioritize maintainability, performance, security, and testability in all generated code

## Technology Version Detection

- **Languages**: Python 3.11+ (see shebangs and code style), Julia (see .jl files and module usage)
- **Frameworks/Libraries**: pytest, pydantic, subprocess, OpenAI, colorama, tabulate, ell, Julia standard library
- **Versioning**: Use only features available in Python 3.11 and Julia 1.x. Do not use features from later versions.
- **Dependency Management**: Respect imports and module boundaries as seen in `src/autocode/` and `tests/`

## Context Files

Prioritize the following files in .github/copilot directory (if they exist):
- **architecture.md**: System architecture guidelines
- **tech-stack.md**: Technology versions and framework details
- **coding-standards.md**: Code style and formatting standards
- **folder-structure.md**: Project organization guidelines
- **exemplars.md**: Exemplary code patterns to follow

## Codebase Scanning Instructions

When context files don't provide specific guidance:
1. Identify similar files to the one being modified or created
2. Analyze patterns for:
   - Naming conventions (snake_case for Python, lower_case for Julia modules)
   - Code organization (modular, with clear separation between core, UI, persistence, and semantic logic)
   - Error handling (try/except in Python, error returns in Julia)
   - Logging (print statements, no external logging framework)
   - Documentation style (docstrings in Python, comments and docstrings in Julia)
   - Testing patterns (pytest for Python, @test for Julia)
3. Follow the most consistent patterns found in the codebase
4. When conflicting patterns exist, prioritize patterns in newer files or files with higher test coverage
5. Never introduce patterns not found in the existing codebase

## Code Quality Standards

### Maintainability
- Write self-documenting code with clear naming
- Follow the naming and organization conventions evident in the codebase
- Keep functions focused on single responsibilities
- Limit function complexity and length to match existing patterns

### Performance
- Follow existing patterns for memory and resource management
- Match existing patterns for handling computationally expensive operations
- Optimize according to patterns evident in the codebase

### Security
- Follow existing patterns for input validation
- Apply the same sanitization techniques used in the codebase
- Handle sensitive data according to existing patterns

### Testability
- Follow established patterns for testable code
- Match dependency injection approaches used in the codebase
- Apply the same patterns for managing dependencies
- Follow established mocking and test double patterns
- Match the testing style used in existing tests

## Documentation Requirements
- Follow the exact documentation format found in the codebase
- Match the docstring style and completeness of existing comments
- Document parameters, returns, and exceptions in the same style
- Follow existing patterns for usage examples
- Match class-level documentation style and content

## Testing Approach

### Unit Testing
- Match the exact structure and style of existing unit tests
- Follow the same naming conventions for test functions and methods
- Use the same assertion patterns found in existing tests
- Apply the same mocking approach used in the codebase
- Follow existing patterns for test isolation

### Integration Testing
- Follow the same integration test patterns found in the codebase
- Match existing patterns for test data setup and teardown
- Use the same approach for testing component interactions
- Follow existing patterns for verifying system behavior

### Test-Driven Development
- Follow TDD patterns evident in the codebase
- Match the progression of test cases seen in existing code
- Apply the same refactoring patterns after tests pass

## Python Guidelines
- Detect and adhere to the specific Python version in use (3.11)
- Follow the same import organization found in existing modules
- Match type hinting approaches if used in the codebase
- Apply the same error handling patterns found in existing code
- Follow the same module organization patterns

## Julia Guidelines
- Detect and adhere to the specific Julia version in use (1.x)
- Follow the same module and function organization as in `misc.jl` and `tests/`
- Use `using Test` and `@test` for unit tests
- Document functions with comments and docstrings as seen in the codebase

## Version Control Guidelines
- Follow Semantic Versioning patterns as applied in the codebase
- Match existing patterns for documenting breaking changes
- Follow the same approach for deprecation notices

## General Best Practices
- Follow naming conventions exactly as they appear in existing code
- Match code organization patterns from similar files
- Apply error handling consistent with existing patterns
- Follow the same approach to testing as seen in the codebase
- Match logging patterns from existing code
- Use the same approach to configuration as seen in the codebase

## Project-Specific Guidance
- Scan the codebase thoroughly before generating any code
- Respect existing architectural boundaries without exception
- Match the style and patterns of surrounding code
- When in doubt, prioritize consistency with existing code over external best practices
