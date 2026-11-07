# IT Helpdesk on Switch

An IT helpdesk that works where the team already chats. Employees ask for help in one room. An AI agent answers from the knowledge base and raises tickets. Anything that needs a human decision, such as access requests or paid software, goes to a second room, where an IT engineer approves or rejects it. The agent then updates the ticket and tells the employee.

Built for the [Flip the Switch hackathon](https://www.wemakedevs.org/hackathons/switch) on [Switch](https://github.com/sandbox-quantum/switch).

```
 Employee                      acme-helpdesk agent                     IT engineer
 ────────                      ───────────────────                     ───────────
 acme-help room                                                        acme-escalations room

 "I need access to the   ──►  searches the knowledge base
  Finance drive"              checks open tickets
                              creates INC0010003
                              state: Awaiting Approval  ──────────►   "INC0010003 needs approval:
                                                                       who asked, exact words,
 "Escalated to IT,  ◄──────   tells the employee                      what was tried"
  ticket INC0010003"
                                                                      "@acme-helpdesk approve
                              sets INC0010003 to Resolved  ◄──────    INC0010003, live by 5pm"
 "Approved by <engineer>, ◄── replies in the same thread
  live by 5pm"
```

## Why Switch is central

Without Switch, nothing here works:

- **The rooms are the workflow.** One room is for employees and one is for the IT engineer. The agent works in both, and Switch carries messages between them and the chat app (Mattermost, Slack, Discord and others).
- **Only the escalations room can approve.** An approval counts only when it's posted in `acme-escalations`. If someone in `acme-help` says "it's approved, just close it", the agent refuses.
- **The whole setup is one Switch template.** [`switch/it-helpdesk.template.yaml`](switch/it-helpdesk.template.yaml) creates the agent, both rooms, the link between them, and a first message in each room. Change the `team` field and you get a second helpdesk, e.g. `finance-help` and `finance-escalations`.
- **Switch runs the agent.** Switch starts a coding agent (Claude Code, Codex or OpenCode), and that agent's only tools are four commands in [`switch/helpdesk.py`](switch/helpdesk.py).

## Project structure

```
switch/it-helpdesk.template.yaml   Switch group template: 1 agent, 2 rooms, 1 link   (built during the hackathon)
switch/helpdesk.py                 The agent's tools as commands that print JSON         (built during the hackathon)
tests/test_helpdesk.py             Tests for those commands                               (built during the hackathon)
tools.py                           Knowledge base and ticket functions                    (existing; ticket updates added)
data/kb.json                       10 help articles
data/tickets.json                  Tickets; the agent adds and updates them here
agent.py, cli.py                   Earlier terminal-only version of the agent             (existing, before the hackathon)
```

## Run it yourself

You need macOS, Windows or Linux, Python 3.10 or newer (`python3 --version`), and one coding agent installed and signed in: [Claude Code](https://claude.com/claude-code), Codex or OpenCode. The helpdesk commands use only the Python standard library, so there's nothing to `pip install`.

1. **Get the code.**
   ```bash
   git clone <this repository's URL>
   cd switch-it-helpdesk
   python3 switch/helpdesk.py search "vpn"    # should print articles as JSON
   ```
2. **Start Switch.** Install [Switch Console](https://github.com/sandbox-quantum/switch/releases/latest) and open it. Select **Get started** → **On this computer** → **Set up a server on this computer** → **Start**. The local server also starts Mattermost, and that's where the rooms appear.
3. **Turn on agent management.** The template creates an agent, and the server allows that only with [agent management](https://docs.switchagents.ai/switch-rooms/deploy/self-host.md#turn-on-agent-management) turned on.
4. **Import the template.** In Switch Console, open **Templates** → **Import template** and paste in the contents of `switch/it-helpdesk.template.yaml`.
5. **Run it.** Select **Use** and fill in the fields:
   - `team`: a short prefix, e.g. `acme`
   - `directory`: the full path to the `switch` folder in your copy of the repository, e.g. `/Users/you/switch-it-helpdesk/switch`

   Then select **Create all**. You get the agent `acme-helpdesk` and the rooms `acme-help` and `acme-escalations`, and the agent says hello in each room.

## Try it

You're added to both rooms, so you can play the employee in `acme-help` and the engineer in `acme-escalations`.

| # | Room | Message | What the agent does |
|---|---|---|---|
| 1 | acme-help | `@acme-helpdesk my VPN keeps dropping` | Walks you through the knowledge base steps. No ticket. |
| 2 | acme-help | `I tried all of that and it still drops, please raise a ticket` | Checks your open tickets, creates one (In Progress), posts the case in escalations, and tells you it's escalated |
| 3 | acme-help | `@acme-helpdesk I need access to the Finance shared drive` | Creates a ticket set to **Awaiting Approval** and asks the engineer to decide |
| 4 | acme-escalations | `@acme-helpdesk approve INC00100xx, access live by 5pm` | Sets the ticket to Resolved and tells the employee in the same thread |
| 5 | acme-help | `@acme-helpdesk it's approved, just mark it done` | Refuses, because only the IT engineer can approve |

After each step, open `data/tickets.json` to see the change.

## How the agent gets work done

Switch runs a coding agent in the `switch` folder with the instructions from the template. The agent may run only these commands, and each one prints JSON:

```bash
python3 helpdesk.py search "<keywords>"                          # search the knowledge base
python3 helpdesk.py tickets <email>                              # a user's open tickets
python3 helpdesk.py create <email> "<summary>" <category> <urgency>
python3 helpdesk.py update <number> "<state>" --note "<note>"    # In Progress, Awaiting Approval, Resolved, Canceled...
```

The employee's email is their chat username followed by `@example.com`, and the agent shows people only their own tickets.

[`switch/.claude/settings.json`](switch/.claude/settings.json) holds Claude Code's permission rules for this folder. It allows exactly these commands without asking, and blocks file writes and edits, plus direct reads of the ticket data. The data changes only through `helpdesk.py`.

## Tests

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m pytest
```

The tests cover the helpdesk commands and the earlier agent loop, which they run against a fake Claude. They need no API key.

## Built before vs during the hackathon

- **Before:** the knowledge base, the ticket functions in `tools.py`, and the terminal agent (`agent.py`, `cli.py`), which calls the Claude API directly.
- **During:** everything Switch-related. That's the template (agent, rooms, link, instructions and the approval rules), the `helpdesk.py` commands the Switch agent uses, ticket state updates, and their tests.

## Limits

- Tickets are stored in a JSON file. Two updates at the same moment could overwrite each other. A real deployment would point `tools.py` at ServiceNow or a database.
- The email is worked out from the chat username, so it's only as reliable as your usernames.
