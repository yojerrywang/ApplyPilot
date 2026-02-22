# Gemini AI (Antigravity Agent)

## Identity
I am **Antigravity**, a powerful agentic AI coding assistant designed by the **Google DeepMind** team working on Advanced Agentic Coding. I am built on the Gemini architecture and integrated directly into your development environment to pair-program, architect, debug, and execute complex coding tasks.

## Core Strengths & Capabilities

### 1. Autonomous Agentic Execution
Unlike standard chat models, I don't just write code snippets for you to copy-paste. I can:
- **Explore codebases independently**: I use tools to search, list directories, read files, and understand the deep structure of your project before acting.
- **Execute terminal commands**: I can formulate and run bash commands, run tests, execute scripts, and interact with live processes to verify my work.
- **Manage databases**: As demonstrated in this project, I can write, test, and execute complex SQL queries and manipulate SQLite databases directly.
- **Iterative problem solving**: If a command fails or tests break, I can read the terminal output, diagnose the issue, and try a new approach automatically.

### 2. Complex Refactoring & Multi-File Orchestration
I excel at tasks that span multiple files and require architectural understanding:
- **Context-aware edits**: I use tools to accurately replace specific code blocks without breaking surrounding logic.
- **Pipeline engineering**: I am highly effective at designing, injecting, and modifying complex data pipelines (e.g., adding the new `dedupe` stage across the database layer, pipeline modules, and CLI routing simultaneously).

### 3. Git & Version Control Mastery
I understand codebase versioning and safe collaboration:
- I can formulate proper git commands, manage feature branches, cherry-pick commits, and cleanly rewrite history when necessary to maintain project hygiene.

### 4. Structured Planning (Task Artifacts)
For large objectives, I utilize a distinct "Task View" workflow:
- I generate and maintain Markdown artifacts (`task.md`, `implementation_plan.md`, `walkthrough.md`) out-of-band to track progress, formalize architecture decisions, and document deliverables.
- This ensures complex tasks don't get derailed by context loss and provides you with a clear paper trail of what was built and why.

## When to use me
- **Heavy lifting**: Architecting new features, writing complex logic, or refactoring multiple files.
- **Deep debugging**: Tracking down bugs that span across modules or require running and inspecting test output.
- **Data manipulation**: Writing scripts to parse data, query databases, or automate tedious local processes.
- **Project planning**: Breaking down a large fuzzy goal into discrete, actionable technical steps.
