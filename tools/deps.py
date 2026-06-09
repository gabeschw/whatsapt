from dataclasses import dataclass
import sqlite3


@dataclass
class AgentDeps:
    db: sqlite3.Connection
