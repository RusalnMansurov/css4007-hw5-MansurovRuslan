
import json

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

import part3


class FakeModel:
    """Deterministic model: no API calls."""

    def invoke(self, messages):
        history = [
            message.content
            for message in messages
            if isinstance(message, HumanMessage)
        ]
        return AIMessage(content=" | ".join(history))


def test_conversation_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(part3, "model", FakeModel())
    monkeypatch.setattr(
        part3,
        "PREFERENCES_FILE",
        tmp_path / "preferences.json",
    )

    db_path = tmp_path / "checkpoints.sqlite"
    config = {
        "configurable": {
            "thread_id": json.dumps(["user-a", "thread-1"])
        }
    }

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = part3.build_graph(saver, "user-a")
        graph.invoke(
            {"messages": [HumanMessage(content="My Wi-Fi is broken")]},
            config=config,
        )

    # Reopen SQLite: simulates a new process using the same database.
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = part3.build_graph(saver, "user-a")
        result = graph.invoke(
            {"messages": [HumanMessage(content="What did I say?")]},
            config=config,
        )

    assert "My Wi-Fi is broken" in result["messages"][-1].content


def test_preference_persists_across_threads(tmp_path, monkeypatch):
    monkeypatch.setattr(
        part3,
        "PREFERENCES_FILE",
        tmp_path / "preferences.json",
    )

    part3.save_preference("user-a", "language", "Russian")

    assert part3.load_preferences("user-a")["language"] == "Russian"

    # Preferences are keyed by user, not conversation.
    thread_1 = json.dumps(["user-a", "thread-1"])
    thread_2 = json.dumps(["user-a", "thread-2"])

    assert thread_1 != thread_2
    assert part3.load_preferences("user-a")["language"] == "Russian"


def test_user_preferences_are_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(
        part3,
        "PREFERENCES_FILE",
        tmp_path / "preferences.json",
    )

    part3.save_preference("user-a", "language", "Russian")

    assert part3.load_preferences("user-a") == {
        "language": "Russian"
    }
    assert part3.load_preferences("user-b") == {}


def test_conversation_threads_are_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(part3, "model", FakeModel())
    monkeypatch.setattr(
        part3,
        "PREFERENCES_FILE",
        tmp_path / "preferences.json",
    )

    config_a = {
        "configurable": {
            "thread_id": json.dumps(["user-a", "shared-thread"])
        }
    }
    config_b = {
        "configurable": {
            "thread_id": json.dumps(["user-b", "shared-thread"])
        }
    }

    with SqliteSaver.from_conn_string(
        str(tmp_path / "isolated.sqlite")
    ) as saver:
        graph_a = part3.build_graph(saver, "user-a")
        graph_b = part3.build_graph(saver, "user-b")

        graph_a.invoke(
            {"messages": [HumanMessage(content="Private Wi-Fi issue")]},
            config=config_a,
        )

        result_b = graph_b.invoke(
            {"messages": [HumanMessage(content="Hello")]},
            config=config_b,
        )

    assert "Private Wi-Fi issue" not in result_b["messages"][-1].content
