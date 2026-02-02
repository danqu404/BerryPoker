"""Database connection and initialization."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

DATABASE_PATH = Path(__file__).parent.parent / "berrypoker.db"


def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Hands table - records each hand played
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            hand_number INTEGER NOT NULL,
            pot_size INTEGER NOT NULL,
            winner_names TEXT NOT NULL,
            actions TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Player stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT UNIQUE NOT NULL,
            hands_played INTEGER DEFAULT 0,
            hands_won INTEGER DEFAULT 0,
            total_profit INTEGER DEFAULT 0
        )
    ''')

    # Player hand results - detailed per-player per-hand results
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_hand_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hand_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            starting_stack INTEGER NOT NULL,
            ending_stack INTEGER NOT NULL,
            profit INTEGER NOT NULL,
            is_winner BOOLEAN NOT NULL,
            hole_cards TEXT,
            FOREIGN KEY (hand_id) REFERENCES hands(id)
        )
    ''')

    conn.commit()
    conn.close()


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
