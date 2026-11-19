"""Local-first thesis milestones, meetings, actions, and dependency reports."""
from __future__ import annotations

import argparse, json, sqlite3, sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = {"planned", "active", "blocked", "done", "cancelled"}

class LogError(ValueError):
    pass

def iso_date(value: str) -> str:
    if not isinstance(value, str):
        raise LogError("date must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise LogError(f"invalid date: {value}") from exc

def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS milestones (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL,
      notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS dependencies (
      milestone_id INTEGER NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
      depends_on_id INTEGER NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
      PRIMARY KEY (milestone_id, depends_on_id),
      CHECK (milestone_id != depends_on_id)
    );
    CREATE TABLE IF NOT EXISTS meetings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      meeting_date TEXT NOT NULL, participants TEXT NOT NULL,
      notes TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS actions (
      id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER REFERENCES meetings(id),
      description TEXT NOT NULL, owner TEXT NOT NULL, due_date TEXT,
      status TEXT NOT NULL DEFAULT 'planned', created_at TEXT NOT NULL
    );
    """)
    db.commit()
    return db

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def add_milestone(db: sqlite3.Connection, title: str, due: str, status: str = "planned",
                  notes: str = "", dependencies: list[int] | None = None) -> int:
    if not title.strip(): raise LogError("milestone title must not be blank")
    iso_date(due)
    if status not in STATUSES: raise LogError(f"status must be one of {sorted(STATUSES)}")
    cur = db.execute("INSERT INTO milestones(title,due_date,status,notes,created_at) VALUES(?,?,?,?,?)",
                     (title.strip(), iso_date(due), status, notes, now()))
    mid = int(cur.lastrowid)
    for dep in dependencies or []:
        if not isinstance(dep, int): raise LogError("dependency ids must be integers")
        db.execute("INSERT INTO dependencies(milestone_id,depends_on_id) VALUES(?,?)", (mid, dep))
    db.commit()
    return mid

def set_status(db: sqlite3.Connection, mid: int, status: str) -> None:
    if status not in STATUSES: raise LogError(f"status must be one of {sorted(STATUSES)}")
    cur = db.execute("UPDATE milestones SET status=? WHERE id=?", (status, mid))
    if cur.rowcount != 1: raise LogError(f"unknown milestone id {mid}")
    db.commit()

def add_meeting(db: sqlite3.Connection, meeting_date: str, participants: str, notes: str) -> int:
    cur = db.execute("INSERT INTO meetings(meeting_date,participants,notes,created_at) VALUES(?,?,?,?)",
                     (iso_date(meeting_date), participants, notes, now()))
    db.commit()
    return int(cur.lastrowid)

def add_action(db: sqlite3.Connection, description: str, owner: str, due: str | None,
               meeting_id: int | None = None, status: str = "planned") -> int:
    if not description.strip() or not owner.strip(): raise LogError("action and owner are required")
    if status not in STATUSES: raise LogError(f"status must be one of {sorted(STATUSES)}")
    if meeting_id is not None and db.execute("SELECT 1 FROM meetings WHERE id=?", (meeting_id,)).fetchone() is None:
        raise LogError(f"unknown meeting id {meeting_id}")
    cur = db.execute("INSERT INTO actions(meeting_id,description,owner,due_date,status,created_at) VALUES(?,?,?,?,?,?)",
                     (meeting_id, description.strip(), owner.strip(), iso_date(due) if due else None, status, now()))
    db.commit()
    return int(cur.lastrowid)

def report(db: sqlite3.Connection, today: str | None = None) -> dict[str, Any]:
    today = iso_date(today) if today else date.today().isoformat()
    milestones = [dict(r) for r in db.execute("SELECT * FROM milestones ORDER BY due_date,id")]
    actions = [dict(r) for r in db.execute("SELECT * FROM actions ORDER BY COALESCE(due_date,'9999'),id")]
    for m in milestones:
        m["overdue"] = m["status"] not in {"done", "cancelled"} and m["due_date"] < today
        m["dependencies"] = [r["depends_on_id"] for r in db.execute(
            "SELECT depends_on_id FROM dependencies WHERE milestone_id=? ORDER BY depends_on_id", (m["id"],))]
    for a in actions:
        a["overdue"] = a["status"] not in {"done", "cancelled"} and a["due_date"] is not None and a["due_date"] < today
    meetings = [dict(r) for r in db.execute("SELECT * FROM meetings ORDER BY meeting_date,id")]
    return {"as_of": today, "milestones": milestones, "meetings": meetings, "actions": actions,
            "summary": {"overdue_milestones": sum(m["overdue"] for m in milestones),
                        "completed_milestones": sum(m["status"] == "done" for m in milestones),
                        "overdue_actions": sum(a["overdue"] for a in actions)}}

def markdown_report(data: dict[str, Any]) -> str:
    lines = [f"# Thesis progress report ({data['as_of']})",
              "", "This is a local project report, not an institution-wide rule or supervisor verdict.",
              "", "## Milestones"]
    for m in data["milestones"]:
        dep = ", ".join(map(str, m["dependencies"])) or "none"
        lines.append(f"- [{m['status']}] {m['title']} — due {m['due_date']} — dependencies: {dep}")
    lines += ["", "## Actions"]
    for a in data["actions"]:
        due = a["due_date"] or "no date"
        lines.append(f"- [{a['status']}] {a['description']} — owner: {a['owner']} — due {due}")
    return "\n".join(lines) + "\n"

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    ms = sub.add_parser("add-milestone"); ms.add_argument("title"); ms.add_argument("due"); ms.add_argument("--status", default="planned"); ms.add_argument("--notes", default=""); ms.add_argument("--depends", nargs="*", type=int)
    ss = sub.add_parser("set-status"); ss.add_argument("id", type=int); ss.add_argument("status")
    mm = sub.add_parser("add-meeting"); mm.add_argument("date"); mm.add_argument("participants"); mm.add_argument("notes")
    ac = sub.add_parser("add-action"); ac.add_argument("description"); ac.add_argument("owner"); ac.add_argument("--due"); ac.add_argument("--meeting", type=int); ac.add_argument("--status", default="planned")
    rp = sub.add_parser("report"); rp.add_argument("--today"); rp.add_argument("--format", choices=("json","markdown","both"), default="json")
    ex = sub.add_parser("export"); ex.add_argument("output", type=Path)
    p.add_argument("--db", type=Path, default=Path("thesis.sqlite"))
    args = p.parse_args(argv)
    try:
        db = connect(args.db)
        if args.cmd == "init": print(json.dumps({"database": str(args.db)}, indent=2))
        elif args.cmd == "add-milestone": print(add_milestone(db,args.title,args.due,args.status,args.notes,args.depends))
        elif args.cmd == "set-status": set_status(db,args.id,args.status)
        elif args.cmd == "add-meeting": print(add_meeting(db,args.date,args.participants,args.notes))
        elif args.cmd == "add-action": print(add_action(db,args.description,args.owner,args.due,args.meeting,args.status))
        elif args.cmd in {"report","export"}:
            data = report(db, getattr(args,"today",None))
            if args.cmd == "report":
                if args.format in {"json","both"}: sys.stdout.write(json.dumps(data,indent=2)+"\n")
                if args.format in {"markdown","both"}: sys.stdout.write(markdown_report(data))
            else:
                args.output.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8"); print(args.output)
    except (LogError, sqlite3.IntegrityError, OSError) as exc:
        p.error(str(exc))
    finally:
        db.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
