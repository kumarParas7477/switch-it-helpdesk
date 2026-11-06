"""The agent: a loop that lets Claude call tools until it has an answer.

    send messages + tools -> Claude asks for tools? run them, send results, repeat
                          -> otherwise, return Claude's text

run_agent() knows nothing about terminals or Slack, so any interface can call it.
"""

import json
import os

from tools import TOOLS, run_tool

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 16000
MAX_ITERATIONS = 10

SYSTEM_PROMPT = """You are a friendly IT helpdesk assistant for company employees.

How to help:
- For any IT problem or how-to question, search the knowledge base first and walk the user through the steps you find, in plain language.
- Create a ticket when the steps did not solve the problem, no article applies, or the user asks for one. Check the user's open tickets first; if one already covers the same issue, point them to it instead of creating a duplicate.
- Whenever you create or mention a ticket, tell the user its ticket number.
- Base troubleshooting steps on the knowledge base. If it has nothing relevant, say so rather than inventing company-specific procedures.
- Keep replies short and easy to follow, in a form that also reads well in a chat app.

The user you are helping is signed in as {user_email}."""


def run_agent(client, messages, user_email):
    """Run one user turn and return Claude's final text.

    `messages` is the conversation so far, ending with the user's new message. It is
    updated in place, so the caller keeps the full history for the next turn.
    """
    model = os.getenv("CLAUDE_MODEL") or DEFAULT_MODEL
    system = SYSTEM_PROMPT.format(user_email=user_email)

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # A declined request has no content to add to the history.
        if response.stop_reason == "refusal":
            return "Sorry, I can't help with that request. Please contact the service desk directly."

        # Keep every block as-is, not just the text: the API needs them on the next call.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            text = "".join(block.text for block in response.content if block.type == "text")
            return text or "Sorry, I couldn't come up with a reply. Please try rephrasing."

        # Claude can ask for several tools at once. All results go back in one message.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            args = dict(block.input)
            # Identity comes from the interface, never from the model, so a message
            # like "show me Bob's tickets" can't reach another user's data.
            if "user_email" in args:
                args["user_email"] = user_email
            print(f"🔧 {block.name}({json.dumps(args)})")
            result = run_tool(block.name, args)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,  # Tells Claude which request this answers.
                "content": result,
                "is_error": "error" in json.loads(result),
            })
        messages.append({"role": "user", "content": tool_results})

    return "Sorry, this is taking too many steps. Please try again or contact the service desk."
