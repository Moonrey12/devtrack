"""Command-line interface for DevTrack: parses arguments and prints results."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from devtrack import repositories
from devtrack.database import get_connection, init_db

from devtrack.validators import (
    PRIORITY_NAMES,
    ValidationError,
    parse_priority,
    validate_deadline,
    validate_name,
    validate_optional_text,
    validate_title,
)

STATUS_CHOICES = ["todo", "in_progress", "completed"]

PRIORITY_CHOICES = ["low", "medium", "high"]

def positive_int(value: str) -> int:
    """argparse type: accept only whole numbers that are 1 or greater."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a whole number")
    if number < 1:
        raise argparse.ArgumentTypeError("id must be 1 or greater")
    return number


def get_db_path() -> Path:
    """Return the database path: DEVTRACK_DB if set, else ~/.devtrack/devtrack.db."""
    override = os.environ.get("DEVTRACK_DB")
    if override:
        return Path(override)
    return Path.home() / ".devtrack" / "devtrack.db"


def cmd_project_add(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `project add`."""
    name = validate_name(args.name)
    description = validate_optional_text(args.description, "Description")
    tech_stack = validate_optional_text(args.tech_stack, "Tech stack")
    try:
        project_id = repositories.add_project(conn, name, description, tech_stack)
    except sqlite3.IntegrityError:
        print(f"Error: a project named '{name}' already exists.", file=sys.stderr)
        return 1
    print(f"Added project #{project_id}: {name}")
    return 0


def cmd_project_list(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `project list`."""
    projects = repositories.list_projects(conn)
    if not projects:
        print("No projects yet. Add one with: devtrack project add NAME")
        return 0
    print(f"{'ID':<4} {'NAME':<25} TECH STACK")
    print("-" * 50)
    for p in projects:
        print(f"{p['id']:<4} {p['name']:<25} {p['tech_stack'] or '-'}")
    return 0


def cmd_project_show(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `project show`."""
    project = repositories.get_project(conn, args.project_id)
    if project is None:
        print(f"Error: no project with id {args.project_id}.", file=sys.stderr)
        return 1
    print(f"Project #{project['id']}: {project['name']}")
    print(f"  Description: {project['description'] or '-'}")
    print(f"  Tech stack:  {project['tech_stack'] or '-'}")
    print(f"  Created:     {project['created_at']}")
    return 0

def cmd_task_add(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `task add`."""
    title = validate_title(args.title)
    priority = parse_priority(args.priority) if args.priority else None
    deadline = validate_deadline(args.deadline) if args.deadline else None
    if repositories.get_project(conn, args.project_id) is None:
        print(f"Error: no project with id {args.project_id}.", file=sys.stderr)
        return 1
    task_id = repositories.add_task(conn, args.project_id, title, priority, deadline)
    print(f"Added task #{task_id} to project #{args.project_id}: {title}")
    return 0


def cmd_task_list(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `task list`."""
    project = repositories.get_project(conn, args.project_id)
    if project is None:
        print(f"Error: no project with id {args.project_id}.", file=sys.stderr)
        return 1
    tasks = repositories.list_tasks(conn, args.project_id, args.status)
    if not tasks:
        suffix = f" with status '{args.status}'" if args.status else ""
        print(f"No tasks{suffix} in project '{project['name']}'.")
        return 0
    print(f"Tasks for project #{project['id']}: {project['name']}")
    print(f"{'ID':<4} {'STATUS':<12} {'PRIORITY':<9} {'DEADLINE':<11} TITLE")
    print("-" * 60)
    for t in tasks:
        priority = PRIORITY_NAMES.get(t["priority"], "-")
        deadline = t["deadline"] or "-"
        print(f"{t['id']:<4} {t['status']:<12} {priority:<9} {deadline:<11} {t['title']}")
    return 0


def cmd_task_edit(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `task edit`: change a task's priority and/or deadline."""
    if args.priority is None and args.deadline is None:
        print("Error: nothing to change; use --priority and/or --deadline.", file=sys.stderr)
        return 1
    priority_value = None
    deadline_value = None
    if args.priority is not None and args.priority != "none":
        priority_value = parse_priority(args.priority)
    if args.deadline is not None and args.deadline.strip().lower() != "none":
        deadline_value = validate_deadline(args.deadline)
    task = repositories.get_task(conn, args.task_id)
    if task is None:
        print(f"Error: no task with id {args.task_id}.", file=sys.stderr)
        return 1
    # Keep the current value for anything the user did not mention.
    new_priority = task["priority"] if args.priority is None else priority_value
    new_deadline = task["deadline"] if args.deadline is None else deadline_value
    repositories.set_task_priority_deadline(conn, args.task_id, new_priority, new_deadline)
    print(
        f"Task #{task['id']}: priority={PRIORITY_NAMES.get(new_priority, '-')}, "
        f"deadline={new_deadline or '-'}"
    )
    return 0
        
def cmd_task_status(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `task status`."""
    task = repositories.get_task(conn, args.task_id)
    if task is None:
        print(f"Error: no task with id {args.task_id}.", file=sys.stderr)
        return 1
    repositories.update_task_status(conn, args.task_id, args.status)
    print(f"Task #{task['id']}: {task['status']} -> {args.status}")
    return 0


def cmd_task_delete(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `task delete`, asking for confirmation unless --yes is given."""
    task = repositories.get_task(conn, args.task_id)
    if task is None:
        print(f"Error: no task with id {args.task_id}.", file=sys.stderr)
        return 1
    if not args.yes:
        try:
            answer = input(f"Delete task #{task['id']} '{task['title']}'? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return 0
    repositories.delete_task(conn, args.task_id)
    print(f"Deleted task #{task['id']}: {task['title']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with its subcommands."""
    parser = argparse.ArgumentParser(
        prog="devtrack", description="Developer productivity tracker."
    )
    parser.set_defaults(parser=parser, func=None)
    subparsers = parser.add_subparsers(dest="command")

    project = subparsers.add_parser("project", help="manage projects")
    project.set_defaults(parser=project, func=None)
    actions = project.add_subparsers(dest="action")

    add = actions.add_parser("add", help="add a project")
    add.add_argument("name", help="project name")
    add.add_argument("-d", "--description", help="short description")
    add.add_argument("-t", "--tech-stack", help="e.g. 'Python,SQLite'")
    add.set_defaults(func=cmd_project_add)

    lst = actions.add_parser("list", help="list all projects")
    lst.set_defaults(func=cmd_project_list)

    show = actions.add_parser("show", help="show one project")
    show.add_argument("project_id", type=positive_int, help="project id")
    show.set_defaults(func=cmd_project_show)

    task = subparsers.add_parser("task", help="manage tasks")
    task.set_defaults(parser=task, func=None)
    task_actions = task.add_subparsers(dest="action")

    task_add = task_actions.add_parser("add", help="add a task to a project")
    task_add.add_argument("project_id", type=positive_int, help="project id")
    task_add.add_argument("title", help="task title")
    task_add.add_argument("--priority", choices=PRIORITY_CHOICES, help="low, medium, or high")
    task_add.add_argument("--deadline", help="due date as YYYY-MM-DD")
    task_add.set_defaults(func=cmd_task_add)

    task_list = task_actions.add_parser("list", help="list a project's tasks")
    task_list.add_argument("project_id", type=positive_int, help="project id")
    task_list.add_argument("--status", choices=STATUS_CHOICES, help="filter by status")
    task_list.set_defaults(func=cmd_task_list)

    task_status = task_actions.add_parser("status", help="change a task's status")
    task_status.add_argument("task_id", type=positive_int, help="task id")
    task_status.add_argument("status", choices=STATUS_CHOICES, help="new status")
    task_status.set_defaults(func=cmd_task_status)

    task_edit = task_actions.add_parser("edit", help="change a task's priority or deadline")
    task_edit.add_argument("task_id", type=positive_int, help="task id")
    task_edit.add_argument(
        "--priority", choices=PRIORITY_CHOICES + ["none"], help="new priority, or 'none' to clear"
    )

    task_edit.add_argument("--deadline", help="new due date YYYY-MM-DD, or 'none' to clear")
    task_edit.set_defaults(func=cmd_task_edit)
    task_delete = task_actions.add_parser("delete", help="delete a task")
    task_delete.add_argument("task_id", type=positive_int, help="task id")
    task_delete.add_argument(
        "-y", "--yes", action="store_true", help="skip the confirmation question"
    )
    task_delete.set_defaults(func=cmd_task_delete)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return an exit code (0 = success, 1 = error)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.func is None:
        args.parser.print_help()
        return 1

    try:
        db_path = get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = get_connection(db_path)
        try:
            init_db(conn)
            return args.func(args, conn)
        finally:
            conn.close()
    except ValidationError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except sqlite3.Error as error:
        print(f"Error: database problem: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Error: cannot access the database location: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())