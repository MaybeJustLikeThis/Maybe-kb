"""Tests for SQLite-backed chat history."""
from pathlib import Path
from kb.data.chat_history import ChatHistory


def test_create_session_returns_session(tmp_path: Path):
    ch = ChatHistory(tmp_path / "chat.db")
    ch.initialize()
    session = ch.create_session("测试对话")
    assert session.session_id
    assert len(session.session_id) == 12
    assert session.title == "测试对话"
    ch.close()


def test_add_and_get_messages(tmp_path: Path):
    ch = ChatHistory(tmp_path / "chat.db")
    ch.initialize()
    sid = ch.create_session().session_id
    ch.add_message(sid, "user", "什么是Python?")
    ch.add_message(sid, "assistant", "Python是一种编程语言。")

    msgs = ch.get_messages(sid)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[0].content == "什么是Python?"
    assert msgs[1].role == "assistant"
    ch.close()


def test_list_sessions_most_recent_first(tmp_path: Path):
    ch = ChatHistory(tmp_path / "chat.db")
    ch.initialize()
    s1 = ch.create_session("A")
    s2 = ch.create_session("B")

    sessions = ch.list_sessions()
    assert sessions[0].session_id == s2.session_id
    ch.close()


def test_delete_session_cascades_messages(tmp_path: Path):
    ch = ChatHistory(tmp_path / "chat.db")
    ch.initialize()
    sid = ch.create_session().session_id
    ch.add_message(sid, "user", "test")
    ch.delete_session(sid)
    assert ch.get_messages(sid) == []
    assert len(ch.list_sessions()) == 0
    ch.close()


def test_chat_history_lazy_init(tmp_path: Path):
    """initialize() is idempotent — calling twice doesn't error."""
    ch = ChatHistory(tmp_path / "chat.db")
    ch.initialize()
    ch.initialize()  # no error
    ch.close()
