# AutoCode Development Roadmap

This document outlines potential future directions for the AutoCode project, based on ideas for new features and improvements. The roadmap is organized into phases, from short-term enhancements to long-term strategic goals.

---

## Phase 1: Core Workflow & Intelligence Enhancements (Short-Term)

This phase focuses on adding high-value intelligence and analysis features to the existing command-line tool and database.

- **[ ] Function Dependency Visualization:**
    - Create a command to generate and view a dependency graph of functions within the database.
    - This will help users understand code structure and the impact of potential changes.

- **[ ] Performance Benchmarking Framework:**
    - Add functionality to define, run, and store performance benchmarks for functions.
    - Track performance over time as functions are modified.

- **[ ] Code Similarity Detection:**
    - Implement a feature that, upon adding a new function, automatically checks for semantically similar functions already in the database.
    - This will help prevent code duplication and encourage reuse.

- **[ ] Debug Harness Integration:**
    - Add a CLI command to quickly send a function from the database to the `debug_harness.jl` file.
    - `python code_db_cli.py debug-function <function_id>`

---

## Phase 2: Deep IDE Integration (Medium-Term)

The goal of this phase is to move AutoCode's functionality directly into the developer's editor, reducing context switching and streamlining the workflow. A VS Code extension would be the primary deliverable.

- **[ ] **VS Code Extension: Core Features**:**
    - **[ ] Custom Sidebar Panel:** Create a panel to browse, search, and view functions from the AutoCode database without leaving the editor.
    - **[ ] Command Palette Integration:** Expose key actions like `search-functions` and `get-function` through the VS Code command palette.

- **[ ] **VS Code Extension: Editor Enhancements**:**
    - **[ ] CodeLens Actions:** Provide in-editor buttons above functions to:
        - `Save to AutoCode`
        - `Run AutoCode tests`
        - `View modification history`
    - **[ ] Inline Diagnostics:** Display metadata from the database directly in the editor, such as test coverage status or the date of the last modification.

---

## Phase 3: Advanced Refactoring & AI (Long-Term)

Building on the dependency analysis and IDE integration, this phase introduces powerful, intelligent tools for modifying and generating code.

- **[ ] Automated Refactoring Tools:**
    - **[ ] Safe Rename:** A tool to rename a function and automatically update all its call sites within the database.
    - **[ ] Extract Function:** A tool to select a block of code within a function and have it automatically extracted into a new, separate function in the database.

- **[ ] Intelligent Autocompletion:**
    - Use the semantic search engine to power a more advanced autocompletion system that can suggest entire relevant functions from the database as you type.

- **[ ] Enhanced Test Generation:**
    - Improve the AI test generation to support more complex strategies, such as property-based testing or automatically targeting common Julia edge cases.

---

## Future Vision: Polyglot Support

This is a strategic, architectural goal to expand AutoCode beyond its Julia-centric origins.

- **[ ] Pluggable Language Architecture:**
    - Refactor the core logic to be language-agnostic.
    - Isolate language-specific components (parsing, test execution) into "language plugins."

- **[ ] Add Python Support:**
    - As a proof-of-concept, create a language plugin for Python. This would involve implementing a Python parser and a test runner for a framework like `pytest`.
