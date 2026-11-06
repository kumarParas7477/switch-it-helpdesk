"""Tests for the agent loop. The Anthropic client is faked, so no API credits are spent."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import agent
import tools
from agent import run_agent


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(name, args, block_id="toolu_1"):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=args)


def response(stop_reason, *content):
    return SimpleNamespace(stop_reason=stop_reason, content=list(content))


def fake_client(*responses):
    """A client whose messages.create returns each scripted response in turn."""
    client = MagicMock()
    client.messages.create.side_effect = list(responses)
    return client


@pytest.fixture
def tickets_file(tmp_path, monkeypatch):
    """Point the tools at a temporary tickets file so tests don't touch real data."""
    path = tmp_path / "tickets.json"
    path.write_text("[]")
    monkeypatch.setattr(tools, "TICKETS_FILE", path)
    return path


def test_tool_use_then_final_text():
    client = fake_client(
        response("tool_use", tool_use_block("search_knowledge_base", {"query": "vpn"})),
        response("end_turn", text_block("Try reconnecting your VPN.")),
    )
    messages = [{"role": "user", "content": "My VPN keeps dropping"}]

    reply = run_agent(client, messages, "alex@example.com")

    assert reply == "Try reconnecting your VPN."
    assert client.messages.create.call_count == 2
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]

    tool_result = messages[2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "toolu_1"
    assert tool_result["is_error"] is False
    assert "KB0001" in tool_result["content"]


def test_no_tool_call_returns_immediately():
    client = fake_client(response("end_turn", text_block("Hello!")))
    assert run_agent(client, [{"role": "user", "content": "Hi"}], "alex@example.com") == "Hello!"
    assert client.messages.create.call_count == 1


def test_parallel_tool_calls_return_results_in_one_message():
    client = fake_client(
        response(
            "tool_use",
            tool_use_block("search_knowledge_base", {"query": "vpn"}, "toolu_1"),
            tool_use_block("search_knowledge_base", {"query": "wifi"}, "toolu_2"),
        ),
        response("end_turn", text_block("Done")),
    )
    messages = [{"role": "user", "content": "VPN and Wi-Fi are broken"}]

    run_agent(client, messages, "alex@example.com")

    assert [r["tool_use_id"] for r in messages[2]["content"]] == ["toolu_1", "toolu_2"]


def test_failing_tool_is_reported_to_claude_without_crashing():
    client = fake_client(
        response("tool_use", tool_use_block("no_such_tool", {})),
        response("end_turn", text_block("Sorry, that didn't work.")),
    )
    messages = [{"role": "user", "content": "Do something"}]

    reply = run_agent(client, messages, "alex@example.com")

    assert reply == "Sorry, that didn't work."
    assert messages[2]["content"][0]["is_error"] is True
    assert "Unknown tool" in messages[2]["content"][0]["content"]


def test_max_iterations_stops_a_runaway_loop():
    looping = [
        response("tool_use", tool_use_block("search_knowledge_base", {"query": "vpn"}))
        for _ in range(agent.MAX_ITERATIONS + 5)
    ]
    client = fake_client(*looping)

    reply = run_agent(client, [{"role": "user", "content": "Help"}], "alex@example.com")

    assert "too many steps" in reply
    assert client.messages.create.call_count == agent.MAX_ITERATIONS


def test_refusal_returns_a_message_and_keeps_history_valid():
    client = fake_client(response("refusal"))
    messages = [{"role": "user", "content": "Something declined"}]

    reply = run_agent(client, messages, "alex@example.com")

    assert "can't help" in reply
    assert [m["role"] for m in messages] == ["user"]


def test_tools_use_signed_in_user_not_the_email_claude_sends(tickets_file):
    client = fake_client(
        response(
            "tool_use",
            tool_use_block(
                "create_ticket",
                {
                    "user_email": "someone.else@example.com",
                    "short_description": "VPN down",
                    "category": "network",
                    "urgency": "high",
                },
            ),
        ),
        response("end_turn", text_block("Created.")),
    )

    run_agent(client, [{"role": "user", "content": "File a ticket"}], "alex@example.com")

    assert json.loads(tickets_file.read_text())[0]["user_email"] == "alex@example.com"


def test_model_comes_from_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-test-model")
    client = fake_client(response("end_turn", text_block("Hi")))

    run_agent(client, [{"role": "user", "content": "Hi"}], "alex@example.com")

    assert client.messages.create.call_args.kwargs["model"] == "claude-test-model"


def test_ticket_numbers_start_at_first_and_increment(tickets_file):
    first = tools.create_ticket("a@example.com", "One", "other", "low")
    second = tools.create_ticket("a@example.com", "Two", "other", "low")

    assert first["ticket"]["number"] == "INC0010001"
    assert second["ticket"]["number"] == "INC0010002"


def test_get_open_tickets_filters_by_user_and_state(tickets_file):
    tools.create_ticket("a@example.com", "Mine", "other", "low")
    tools.create_ticket("b@example.com", "Theirs", "other", "low")
    closed = tools.create_ticket("a@example.com", "Old", "other", "low")["ticket"]
    tickets = json.loads(tickets_file.read_text())
    tickets[-1] = {**closed, "state": "Resolved"}
    tickets_file.write_text(json.dumps(tickets))

    open_tickets = tools.get_open_tickets("A@example.com")["tickets"]

    assert [t["short_description"] for t in open_tickets] == ["Mine"]
