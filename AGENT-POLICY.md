<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md section 5; the lecturer reviewed each justification -->
# Agent policy: what the reviewer sub-agent may not do, and why

`.claude/agents/reviewer.md` declares a `disallowedTools` list. Technically it is a denylist (the agent keeps every
tool not named here); it is narrow on purpose, so that the reviewer can read, grep and run the test suite but cannot
take any action whose blast radius reaches beyond this working tree. One line per denied entry, each a blast-radius
decision:

- Bash(rm *): deleting files is the one action a reviewer can take that is not undone by discarding its diff; a wrong glob removes the SQLite data directory, the specs or the tests the reviewer is meant to check, and git only restores what was committed.
- Bash(git push *): a push publishes to the shared repository and, through the course's acceptance receipts, can turn an unreviewed tree into a graded submission; the reviewer's output must stay local until a human decides to push.
- Bash(docker *): starting containers reaches outside the working tree, binds host ports, creates volumes and images that outlive the agent and, in the Tier B sandbox, would be the only way for student code to escape the egress block; review needs none of it, `uv run pytest` runs the suite in-process.
- WebFetch: the review must be grounded in this repository and the course's API.md, not in whatever a URL returns; fetching arbitrary pages is also the classic prompt-injection path, so the reviewer works offline like the graded service does.
