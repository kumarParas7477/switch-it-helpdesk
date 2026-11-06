"""The agent's tools: what Claude can ask us to do, and the code that does it.

Claude never runs anything itself. It reads TOOLS (the menu), asks for a tool by
name, and run_tool() does the work. To move to ServiceNow later, only the three
tool functions need to change; the menu and the agent loop stay the same.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
KB_FILE = DATA_DIR / "kb.json"
TICKETS_FILE = DATA_DIR / "tickets.json"

FIRST_TICKET_NUMBER = 10001
MAX_KB_RESULTS = 3
CATEGORIES = ["network", "account", "email", "hardware", "software", "access", "other"]
URGENCIES = ["low", "medium", "high"]
CLOSED_STATES = {"Resolved", "Closed", "Canceled"}
TICKET_STATES = ["New", "Awaiting Approval", "In Progress", *CLOSED_STATES]
STOP_WORDS = {"a", "an", "and", "the", "my", "i", "is", "it", "to", "of", "on", "in", "for", "not", "how", "do", "can", "keeps", "with"}

# Claude chooses tools from these descriptions, so they say when to use each one.
TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search IT help articles by keyword and return the best matches with their "
            "troubleshooting steps. Use this first for any IT problem or how-to question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords describing the problem, e.g. 'vpn disconnecting'.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_open_tickets",
        "description": (
            "List a user's open support tickets. Use this when the user asks about their "
            "tickets, and before creating a ticket, to avoid duplicates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_email": {"type": "string", "description": "The user's email address."},
            },
            "required": ["user_email"],
        },
    },
    {
        "name": "create_ticket",
        "description": (
            "Create a support ticket and return its INC number. Use this when the knowledge "
            "base did not solve the problem or the user asks for a ticket, and only after "
            "get_open_tickets shows no open ticket for the same issue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_email": {"type": "string", "description": "The user's email address."},
                "short_description": {
                    "type": "string",
                    "description": "One-line summary of the problem, e.g. 'VPN drops every 10 minutes'.",
                },
                "category": {"type": "string", "enum": CATEGORIES},
                "urgency": {
                    "type": "string",
                    "enum": URGENCIES,
                    "description": "high = cannot work at all; medium = work is impaired; low = minor issue.",
                },
            },
            "required": ["user_email", "short_description", "category", "urgency"],
        },
    },
]


def _words(text):
    """Split text into lowercase words, dropping a trailing 's' so 'drops' matches 'drop'."""
    return {word.rstrip("s") for word in re.findall(r"[a-z0-9]+", text.lower())} - STOP_WORDS


def _load_tickets():
    return json.loads(TICKETS_FILE.read_text())


def search_knowledge_base(query):
    articles = json.loads(KB_FILE.read_text())
    query_words = _words(query)

    scored = []
    for article in articles:
        # A match in the title or keywords says more than one in the body text.
        strong = _words(article["title"] + " " + " ".join(article["keywords"]))
        weak = _words(article["content"])
        score = 3 * len(query_words & strong) + len(query_words & weak)
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return {
        "articles": [
            {"id": a["id"], "title": a["title"], "content": a["content"]}
            for _, a in scored[:MAX_KB_RESULTS]
        ]
    }


def get_open_tickets(user_email):
    return {
        "tickets": [
            ticket
            for ticket in _load_tickets()
            if ticket["user_email"].lower() == user_email.lower()
            and ticket["state"] not in CLOSED_STATES
        ]
    }


def create_ticket(user_email, short_description, category, urgency):
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}")
    if urgency not in URGENCIES:
        raise ValueError(f"urgency must be one of {URGENCIES}")

    tickets = _load_tickets()
    last_number = max(
        (int(ticket["number"].removeprefix("INC")) for ticket in tickets),
        default=FIRST_TICKET_NUMBER - 1,
    )
    ticket = {
        "number": f"INC{last_number + 1:07d}",
        "user_email": user_email,
        "short_description": short_description,
        "category": category,
        "urgency": urgency,
        "state": "New",
        "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    tickets.append(ticket)
    TICKETS_FILE.write_text(json.dumps(tickets, indent=2) + "\n")
    return {"ticket": ticket}


def update_ticket(number, state, note=None):
    """Change a ticket's state. Left out of TOOLS so the terminal agent can't close tickets."""
    if state not in TICKET_STATES:
        raise ValueError(f"state must be one of {TICKET_STATES}")

    tickets = _load_tickets()
    for ticket in tickets:
        if ticket["number"] == number:
            ticket["state"] = state
            if note:
                ticket.setdefault("notes", []).append(note)
            TICKETS_FILE.write_text(json.dumps(tickets, indent=2) + "\n")
            return {"ticket": ticket}
    raise ValueError(f"No ticket numbered {number}")


_TOOL_FUNCTIONS = {
    "search_knowledge_base": search_knowledge_base,
    "get_open_tickets": get_open_tickets,
    "create_ticket": create_ticket,
}


def run_tool(name, args):
    """Run a tool and return its result as a JSON string.

    Errors come back as {"error": ...} instead of raising, so Claude can read what
    went wrong and recover or explain it, and the agent keeps running.
    """
    try:
        if name not in _TOOL_FUNCTIONS:
            raise ValueError(f"Unknown tool: {name}")
        return json.dumps(_TOOL_FUNCTIONS[name](**args))
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
