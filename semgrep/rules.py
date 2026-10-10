# ai-generated: 100% - Claude Code wrote the test cases for semgrep/rules.yml (CI-SPEC.md P-31)
import os
import sqlite3

COLUMNS = ("id", "state")
conn = sqlite3.connect(":memory:")


def update(ticket_id, state):
    assignments = ", ".join(f"{c} = ?" for c in COLUMNS)
    # ruleid: svcdesk-sql-text-from-fstring
    conn.execute(f"UPDATE tickets SET {assignments} WHERE id = ?", [state, ticket_id])


def find(team):
    # ruleid: svcdesk-sql-text-from-fstring
    query = f"SELECT * FROM tickets WHERE team = '{team}'"
    return conn.execute(query).fetchall()


def get(ticket_id):
    # ok: svcdesk-sql-text-from-fstring
    return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def log_query(ticket_id):
    # ok: svcdesk-sql-text-from-fstring
    print(f"SELECT * FROM tickets WHERE id = {ticket_id}")


def port():
    # ruleid: svcdesk-env-read-outside-settings
    return os.environ.get("SVCDESK_PORT_INTERNAL", "8080")


def db_path():
    # ruleid: svcdesk-env-read-outside-settings
    return os.getenv("SVCDESK_DB")


def token():
    # ruleid: svcdesk-env-read-outside-settings
    return os.environ["KB_TOKEN"]


class Settings:
    @classmethod
    def from_env(cls, env=None):
        # ok: svcdesk-env-read-outside-settings
        url = os.environ.get("KB_INDEX_URL", "http://kb-index:8080")
        return url


def from_mapping(env):
    # ok: svcdesk-env-read-outside-settings
    return env.get("SVCDESK_C1", "wallclock")
