# AutoCode Copilot Instructions

## Architecture Overview
AutoCode is a Julia function database system with MCP (Model Context Protocol) integration. The core architecture consists of:

- **Code Database** (`code_db.py`): Central repository storing Julia functions with metadata, tests, and modifications
- **MCP Server** (`src/autocode/mcp_autocode_server.py`): JSON-RPC 2.0 server exposing database operations as tools
- **Modular Components**:
  - `models.py`: Pydantic data models (Function, UnitTest, TestResult, etc.)
  - `julia_parsers.py`: Pure Python Julia code parsing utilities
  - `persistence.py`: Pickle-based database serialization
  - `semantic.py`: OpenAI embedding-based semantic search with hash fallback
  - `ui.py`: User interface components

## Key Patterns & Conventions

### Function Storage & Metadata
- Functions stored with: name, description, code, modules, tags
- Module-based organization: functions belong to named modules (e.g., "array_utils", "math_utils")
- Tag system for categorization and filtering
- Each function has unique UUID and tracks modification history

### Julia Code Parsing
- Handles multiple function declaration styles:
  ```julia
  function add_numbers(x, y)  # Multi-line form
      return x + y
  end

  inc(x) = x + 1  # Single-line form
  ```
- Robust parsing skips truncated/unterminated functions
- Extracts docstrings from comments or triple-quoted strings

### Testing Framework
- Unit tests run via Julia subprocess calls
- Tests stored as separate objects linked to functions
- Test execution creates temporary files to avoid parsing conflicts
- Coverage reporting aggregates test results across all functions

### Semantic Search
- Uses OpenAI embeddings when available, falls back to SHA256 hash-based pseudo-embeddings
- Cosine similarity for finding semantically similar functions
- Supports natural language queries against function descriptions and code

## Developer Workflows

### Function Generation
```bash
# Generate from natural language
python code_db_cli.py generate-function --description "merge two sorted arrays"
python code_db_cli.py generate-function --description "compute factorial" --module "math_utils"
```

### Database Operations
```bash
# List and search
python code_db_cli.py list-functions --module "array_utils"
python code_db_cli.py search-functions --query "sort"

# Export/Import
python code_db_cli.py export-function --function-id FUNC_ID --file function.json
python code_db_cli.py import-function --file function.json
```

### MCP Server Usage
```bash
# Start MCP server
python src/autocode/mcp_autocode_server.py

# Available tools: generate_function, run_tests, semantic_search, list_functions, etc.
```

## Integration Points

### External Dependencies
- **Julia**: Required for test execution and function validation
- **OpenAI**: Optional for semantic embeddings (graceful fallback to hash-based)
- **Ell**: AI library for function generation
- **Colorama/Tabulate**: CLI output formatting

### File Formats
- Database: Pickle serialization (`code_db.pkl`)
- Function export: JSON format with code, tests, metadata
- Dependencies: DOT format for visualization (`deps.dot`)

## Code Organization Patterns

### Import Structure
```python
# Core database operations
import code_db

# Modular components
from src.autocode.models import Function, UnitTest
from src.autocode.julia_parsers import parse_julia_function
from src.autocode.persistence import save_db, load_db
```

### Error Handling
- Graceful fallbacks (OpenAI unavailable → hash embeddings)
- Subprocess error capture for Julia execution
- File operation error handling with informative messages

### State Management
- Global database instance with lazy loading
- Modification timestamps on all changes
- CLI state persistence in `~/.code_db_cli_state.json`

## Common Tasks

### Adding New Functions
1. Use `generate-function` for AI-assisted creation
2. Or `add-function` with manual code entry
3. Assign to appropriate modules and add descriptive tags
4. Generate and attach unit tests

### Testing Workflow
1. Generate tests using `generate_test` tool
2. Run tests with `run_tests` (supports streaming for long operations)
3. Check coverage with `coverage_report`
4. Debug failures using temporary file outputs

### Search & Discovery
1. `list_functions` with module/tag filters
2. `search_functions` for keyword matching
3. `semantic_search` for natural language queries
4. `get_function` for detailed function information

## Development Best Practices

### When Modifying Functions
- Always update description to reflect changes
- Add modification record with your name and change description
- Re-run tests to ensure functionality preserved
- Update tags if behavior categories change

### When Adding Modules
- Use consistent naming (snake_case)
- Group related functions logically
- Update module documentation in function descriptions

### Performance Considerations
- Semantic search uses embeddings - cache results for repeated queries
- Test execution creates temporary files - ensure cleanup on errors
- Database operations are synchronous - consider async for high-throughput scenarios
