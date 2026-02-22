---
description: Always update documentation before creating a git commit
---

Whenever you are about to create a git commit containing new features, bug fixes, or significant changes to the repository, you MUST follow this checklist:

1. Review and update `CHANGELOG.md` with a summary of the changes under the `[Unreleased]` section.
2. Review and update `BACKLOG.md` if the changes address an existing backlog item, moving it to the `Completed` section.
3. Review and update `README.md` if the changes introduce new CLI commands, alter the configuration format, or require new setup steps.
4. Review and update `ROADMAP.md` if the completed backlog tasks fundamentally complete a major Epic and it needs to be moved to the completed Epic status.
5. If you have created or updated the `task.md` or `walkthrough.md` artifacts during the session, ensure they accurately reflect the final state of the code.
6. Only after these documentation files are updated, stage them along with your code changes (`git add`).
7. Finally, commit the changes using `git commit`.

// turbo
git status
