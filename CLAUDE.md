# Rules for Claude Code

Project: Ex2, a web-based teaching tool (attendance first).
Current phase: design only, no code.

1. Analyze read-only first. Do not create, edit or delete files unless asked.
2. After analysis, stop and wait for approval.
3. Never run git add, commit or push. The user does that.
4. Never print or commit private data: private_data/, .env, real names or IDs.
   Use synthetic data from sample_data/ only.
5. Documents are English Markdown, short (about 1-1.5 pages each).
6. docs/decisions.md holds settled decisions only; open questions go to
   docs/project_plan.md.
7. Mark AI-assisted work  in AI_USAGE.md.
8. When coding starts: show the plan first, write tests first, small steps.