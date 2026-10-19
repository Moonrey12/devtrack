"""Command-line interface for DevTrack: parses arguments and prints results."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from devtrack import repositories
from devtrack.database import get_connection, init_db


def get_db_path() -> Path:
    """Return the database path: DEVTRACK_DB if set, else ~/.devtrack/devtrack.db."""
    override = os.environ.get("DEVTRACK_DB")
    if override:
        return Path(override)
    return Path.home() / ".devtrack" / "devtrack.db"


def cmd_project_add(args: argparse.Namespace, conn: sqlite3.Connection) -> int:
    """Handle `project add`."""
    name = args.name.strip()
    if not name:
        print("Error: project name cannot be empty.", file=sys.stderr)
        return 1
    try:
        project_id = repositories.add_project(
            conn, name, args.description, args.tech_stack
        )
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
    show.add_argument("project_id", type=int, help="project id")
    show.set_defaults(func=cmd_project_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return an exit code (0 = success, 1 = error)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.func is None:
        args.parser.print_help()
        return 1

    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    try:
        init_db(conn)
        return args.func(args, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())