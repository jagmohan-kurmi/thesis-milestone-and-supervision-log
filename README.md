# Thesis Milestone and Supervision Log

An offline SQLite CLI for thesis milestones, dependencies, supervision meetings, action items, and overdue/completion summaries. It does not encode or claim to replace institution-specific rules.

```powershell
pip install -e .
python -m thesis_milestone_and_supervision_log init --db fixtures\thesis.sqlite
python -m thesis_milestone_and_supervision_log --db fixtures\thesis.sqlite add-milestone "Ethics submission" 2026-12-01
python -m thesis_milestone_and_supervision_log --db fixtures\thesis.sqlite add-meeting 2026-11-19 "Student, supervisor" "Confirm scope"
python -m thesis_milestone_and_supervision_log --db fixtures\thesis.sqlite add-action "Submit ethics" "Student" --due 2026-12-01
python -m thesis_milestone_and_supervision_log --db fixtures\thesis.sqlite report --format both --today 2026-11-19
python -m unittest discover -s tests -v
```

See `RESEARCH.md` and `fixtures/`. Export produces JSON; Markdown reporting is available directly.
