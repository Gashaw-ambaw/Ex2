# Rules for Claude Code

Project: Ex2, a web-based teaching tool (attendance first). Phase: design (EDD draft done, STP next).

1. The full assignment text is in private_data/AssEX2.md (git-ignored). Read it when a requirement is unclear.
   You may quote short lines from it in chat only. Do not open other files in private_data/.
2. Reading and searching need no permission. Create, edit or delete repo files only after I approve your plan.
3. Never run git add, commit or push unless I ask for it in that message.
4. No real names, IDs or .env content in chat or files. Use synthetic data from sample_data/.
5. If a claim has no source, ask me. Do not add it.
6. KISS: when there is a choice, take the simpler version that works. A simple working version
   beats a better plan that may not work; we improve it later. Keep documents and plans short too.
7. Before building anything, check for an existing tool, library or ready solution. Build only the glue (D17).
8. Documents: English Markdown, short, in the style and length of the existing text.
9. docs/decisions.md holds settled decisions only. Open questions go to docs/project_plan.md.
10. Record AI-assisted work in AI_USAGE.md.
11. When coding starts: show the plan first, write tests first, small steps.
12. Change propagation rule: when a decision changes, first list every
document and file that mentions it (docs/*.md, README.md, CLAUDE.md,
AI_USAGE.md, code, tests). Go in order: SoW, SRS, SDD, EDD, code, tests.
Start from the earliest document where it appears. For each file, say
whether it is affected and what changes. Show me this list as a short
plan. Apply the edits only after I approve. Mark proposals [P] and
closed decisions differently, and tell me which one this is.

13. Decision entries (decisions.md): short and focused,
two lines at most. Put what, why, rejected and who in those two lines.

14. At the end of each step, list the decisions I made or approved in this step
that are not in decisions.md. Propose a two-line entry for each. Only
decisions that change behavior, scope, cost or a document; not technical
details marked [P]. I decide what goes in.