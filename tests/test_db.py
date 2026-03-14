import pytest
import sqlite3
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from geminiclaw import db

TEST_DB_PATH = "test_claw.db"

@pytest.fixture(autouse=True)
def setup_teardown_db():
    # Setup
    db.DB_PATH = TEST_DB_PATH
    db.init_db()
    
    yield
    
    # Teardown
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_init_db():
    assert os.path.exists(TEST_DB_PATH)
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    table = cursor.fetchone()
    assert table is not None
    conn.close()

def test_insert_message():
    db.insert_message("123", "456", "789", "Hello prompt")
    
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages")
    row = cursor.fetchone()
    assert row is not None
    assert row['channel_id'] == '123'
    assert row['message_id'] == '456'
    assert row['author_id'] == '789'
    assert row['prompt'] == 'Hello prompt'
    assert row['status'] == 'pending'
    conn.close()

def test_get_pending_message():
    db.insert_message("123", "456", "789", "Hello prompt")
    
    row = db.get_pending_message()
    assert row is not None
    assert row['channel_id'] == '123'
    assert row['prompt'] == 'Hello prompt'

def test_get_pending_message_none():
    row = db.get_pending_message()
    assert row is None

def test_update_message_status():
    db.insert_message("123", "456", "789", "Hello prompt")
    row = db.get_pending_message()
    msg_id = row['id']
    
    # Update status only
    db.update_message_status(msg_id, 'processing')
    
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM messages WHERE id = ?", (msg_id,))
    updated_row = cursor.fetchone()
    assert updated_row['status'] == 'processing'
    
    # Update with response
    db.update_message_status(msg_id, 'completed', 'Test response')
    cursor.execute("SELECT status, response FROM messages WHERE id = ?", (msg_id,))
    updated_row = cursor.fetchone()
    assert updated_row['status'] == 'completed'
    assert updated_row['response'] == 'Test response'
    conn.close()

def test_threads_table():
    # Test initial state (not active)
    assert db.is_thread_active("thread123") is False
    
    # Set active
    db.set_thread_active("thread123", True)
    assert db.is_thread_active("thread123") is True
    
    # Set inactive
    db.set_thread_active("thread123", False)
    assert db.is_thread_active("thread123") is False
    
    # Test multiple threads
    db.set_thread_active("thread456", True)
    assert db.is_thread_active("thread123") is False
    assert db.is_thread_active("thread456") is True

def test_thread_session():
    db.set_thread_active("thread123", True)
    assert db.get_thread_session("thread123") is None
    
    db.set_thread_session("thread123", "sess123")
    assert db.get_thread_session("thread123") == "sess123"
