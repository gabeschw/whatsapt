from dataclasses import dataclass
import sqlite3


@dataclass
class AgentDeps:
    conn: sqlite3.Connection
