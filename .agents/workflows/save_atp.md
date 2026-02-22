---
description: Triggered when the user says "save atp". Automatically updates documentation and commits changes.
---

When the user says "save atp", you must automatically:
1. Review the current git diff to see what changes were made.
2. Update `CHANGELOG.md` with the new changes under the `[Unreleased]` section.
3. Update `BACKLOG.md` by moving any completed tasks to the `Completed` section.
4. Update `README.md` if the changes affect usage or setup.
5. Create a git commit containing both the code and the documentation updates with a descriptive message.

// turbo-all
git status
