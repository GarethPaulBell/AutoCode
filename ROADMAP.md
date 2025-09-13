
# AutoCode Development Roadmap (User-Tested Priorities)

This roadmap is now driven by real-world road testing and user pain points. Items below are prioritized based on actual workflow bottlenecks, missing features, and usability issues encountered by target users.

---

## Phase 1: Critical Usability & Robustness (Immediate)

- **[ ] User-Friendly Error Messages Everywhere**
    - All operations (benchmarking, import/export, test failures, circular dependencies, etc.) must provide clear, actionable error messages.
    - No more cryptic stack traces or silent failures.

- **[ ] Test Output & Coverage Improvements**
    - Show detailed, readable test results (pass/fail, error trace, summary) for every function and module.
    - Ensure coverage is always up-to-date and accurate after any change.

- **[ ] AI Test Generation Quality**
    - Make AI-generated tests context-aware and signature-matching. No more generic or mismatched tests.
    - Add property-based and edge-case test generation as first-class features.

- **[ ] Import/Export Collision Handling**
    - Warn or prompt on module/function name collisions during import/export. No silent overwrites or duplicates.

- **[ ] Circular Dependency & Recursion Detection**
    - Detect and warn about circular dependencies and infinite recursion in functions and modules.
    - Provide tools to analyze and break dependency cycles.

- **[ ] Benchmarking: Input Validation & Feedback**
    - Benchmarking must validate input and provide clear feedback if the input is not a function or script.
    - Document expected input types and error handling.

- **[ ] Function/Module Discovery & Docs**
    - Add commands/UI to view all docstrings, signatures, and metadata for a module or function at a glance.

---

## Phase 2: Workflow Intelligence & Advanced Search (Short-Term)

- **[ ] Code Similarity & Duplication Detection**
    - On adding a new function, automatically check for semantically similar functions in the database.
    - Warn and suggest reuse to prevent duplication.

- **[ ] Semantic Search Ranking & Filtering**
    - Improve semantic search to rank by true relevance and allow filtering by module/tag.
    - Make tag-based search and auto-suggestion prominent in the UI/CLI.

- **[ ] Tag System Enhancements**
    - Enforce or suggest tags on function creation. Allow searching, filtering, and reporting by tag.

- **[ ] Dependency Visualization & Analysis**
    - Generate dependency graphs with built-in viewer and cycle/bottleneck detection.
    - Summarize dependency health and highlight issues.

---

## Phase 3: Deep IDE Integration (Medium-Term)

- **[ ] VS Code Extension: Core Features**
    - **[ ] Custom Sidebar Panel:** Browse, search, and view functions/modules from the AutoCode database.
    - **[ ] Command Palette Integration:** Expose key actions like `search-functions` and `get-function`.

- **[ ] VS Code Extension: Editor Enhancements**
    - **[ ] CodeLens Actions:** In-editor buttons for `Save to AutoCode`, `Run AutoCode tests`, `View modification history`.
    - **[ ] Inline Diagnostics:** Show test coverage, last modification date, and other metadata directly in the editor.

---

## Phase 4: Advanced Refactoring & AI (Long-Term)

- **[ ] Automated Refactoring Tools**
    - **[ ] Safe Rename:** Rename a function and update all call sites in the database.
    - **[ ] Extract Function:** Select code and extract to a new function in the database.

- **[ ] Intelligent Autocompletion**
    - Use semantic search to suggest entire relevant functions as you type.

- **[ ] Enhanced Test Generation**
    - Support property-based, randomized, and edge-case test generation for Julia and future languages.

---

## Future Vision: Polyglot & Extensibility

- **[ ] Pluggable Language Architecture**
    - Refactor core logic to be language-agnostic. Isolate language-specific components into plugins.

- **[ ] Add Python Support**
    - Implement a Python plugin (parser, test runner, etc.) as a proof-of-concept for polyglot support.
