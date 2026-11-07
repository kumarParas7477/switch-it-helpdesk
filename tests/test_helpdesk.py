"""Tests for the commands the Switch agent runs, and for updating tickets."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import helpdesk
import tools


@pytest.fixture
def tickets_file(tmp_path, monkeypatch):
    """Point the tools at a temporary tickets file so tests don't touch real data."""
    path = tmp_path / "tickets.json"
    path.write_text("[]")
    monkeypatch.setattr(tools, "TICKETS_FILE", path)
    return path


def run(capsys, *argv):
    code = helpdesk.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_search_prints_matching_articles(capsys):
    code, output = run(capsys, "search", "vpn dropping")

    assert code == 0
    assert output["articles"][0]["id"] == "KB0001"


def test_approval_workflow_from_create_to_resolved(tickets_file, capsys):
    _, created = run(capsys, "create", "alex@example.com", "Marketing drive access", "access", "medium")
    number = created["ticket"]["number"]

    run(capsys, "update", number, "Awaiting Approval")
    _, waiting = run(capsys, "tickets", "alex@example.com")
    assert waiting["tickets"][0]["state"] == "Awaiting Approval"

    code, resolved = run(capsys, "update", number, "Resolved", "--note", "Approved by Sam")
    assert code == 0
    assert resolved["ticket"]["notes"] == ["Approved by Sam"]

    _, still_open = run(capsys, "tickets", "alex@example.com")
    assert still_open["tickets"] == []


def test_invalid_category_reports_error_and_saves_nothing(tickets_file, capsys):
    code, output = run(capsys, "create", "alex@example.com", "Problem", "vpn", "low")

    assert code == 1
    assert "category must be one of" in output["error"]
    assert json.loads(tickets_file.read_text()) == []


def test_update_rejects_unknown_ticket_and_state(tickets_file, capsys):
    code, output = run(capsys, "update", "INC0099999", "Resolved")
    assert code == 1
    assert "No ticket numbered" in output["error"]

    code, output = run(capsys, "update", "INC0099999", "Approved")
    assert code == 1
    assert "state must be one of" in output["error"]


def test_terminal_agent_cannot_update_tickets():
    assert "update_ticket" not in [tool["name"] for tool in tools.TOOLS]
    assert "error" in json.loads(tools.run_tool("update_ticket", {"number": "INC0010001", "state": "Closed"}))


def test_tickets_created_at_the_same_time_are_all_kept(tickets_file):
    def create(i):
        return tools.create_ticket("alex@example.com", f"Problem {i}", "other", "low")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(create, range(20)))

    numbers = [t["number"] for t in json.loads(tickets_file.read_text())]
    assert len(numbers) == 20
    assert len(set(numbers)) == 20
