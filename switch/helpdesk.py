"""Command-line helpdesk tools for the Switch agent.

Switch runs Claude Code as the agent, and Claude Code runs these commands. They
use the same functions as the terminal agent, and print JSON for it to read.

    python3 helpdesk.py search "vpn dropping"
    python3 helpdesk.py tickets alex@example.com
    python3 helpdesk.py create alex@example.com "VPN drops hourly" network medium
    python3 helpdesk.py update INC0010003 "Awaiting Approval" --note "Sent to IT"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import tools


def build_parser():
    parser = argparse.ArgumentParser(description="IT helpdesk tools")
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search", help="Search the knowledge base")
    search.add_argument("query")

    tickets = commands.add_parser("tickets", help="List a user's open tickets")
    tickets.add_argument("user_email")

    create = commands.add_parser("create", help="Create a ticket")
    create.add_argument("user_email")
    create.add_argument("short_description")
    create.add_argument("category", help=f"One of {tools.CATEGORIES}")
    create.add_argument("urgency", help=f"One of {tools.URGENCIES}")

    update = commands.add_parser("update", help="Change a ticket's state")
    update.add_argument("number")
    update.add_argument("state", help=f"One of {tools.TICKET_STATES}")
    update.add_argument("--note")

    return parser


def run_command(args):
    if args.command == "search":
        return tools.search_knowledge_base(args.query)
    if args.command == "tickets":
        return tools.get_open_tickets(args.user_email)
    if args.command == "create":
        return tools.create_ticket(args.user_email, args.short_description, args.category, args.urgency)
    return tools.update_ticket(args.number, args.state, args.note)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        print(json.dumps(run_command(args), indent=2))
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
