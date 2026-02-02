"""Unit tests for database functionality."""

import os
import pytest
import tempfile
from pathlib import Path


class TestDatabase:
    """Tests for database operations."""

    @pytest.fixture(autouse=True)
    def setup_test_db(self, monkeypatch):
        """Set up a temporary database for each test."""
        # Create temp directory for test database
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test_berrypoker.db"

        # Monkeypatch the DATABASE_PATH
        import database.db as db_module
        monkeypatch.setattr(db_module, 'DATABASE_PATH', self.test_db_path)

        yield

        # Cleanup
        if self.test_db_path.exists():
            os.remove(self.test_db_path)
        os.rmdir(self.temp_dir)

    def test_init_db_creates_tables(self):
        """Test that init_db creates required tables."""
        from database import init_db, get_db

        init_db()

        with get_db() as conn:
            cursor = conn.cursor()

            # Check hands table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='hands'"
            )
            assert cursor.fetchone() is not None

            # Check player_stats table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='player_stats'"
            )
            assert cursor.fetchone() is not None

            # Check player_hand_results table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='player_hand_results'"
            )
            assert cursor.fetchone() is not None

    def test_record_hand(self):
        """Test recording a hand to the database."""
        from database import init_db, HistoryManager

        init_db()

        hand_id = HistoryManager.record_hand(
            room_id='test-room',
            hand_number=1,
            pot_size=100,
            winners=['Alice'],
            actions=[
                {'player': 'Alice', 'action': 'raise', 'amount': 20, 'phase': 'preflop'},
                {'player': 'Bob', 'action': 'call', 'amount': 20, 'phase': 'preflop'}
            ],
            player_results=[
                {
                    'player_name': 'Alice',
                    'starting_stack': 100,
                    'ending_stack': 150,
                    'profit': 50,
                    'is_winner': True,
                    'hole_cards': [{'rank': 'A', 'suit': 'hearts'}, {'rank': 'K', 'suit': 'hearts'}]
                },
                {
                    'player_name': 'Bob',
                    'starting_stack': 100,
                    'ending_stack': 50,
                    'profit': -50,
                    'is_winner': False,
                    'hole_cards': [{'rank': '2', 'suit': 'clubs'}, {'rank': '7', 'suit': 'diamonds'}]
                }
            ]
        )

        assert hand_id is not None
        assert hand_id > 0

    def test_get_hand_history(self):
        """Test retrieving hand history."""
        from database import init_db, HistoryManager

        init_db()

        # Record a few hands
        for i in range(3):
            HistoryManager.record_hand(
                room_id='test-room',
                hand_number=i + 1,
                pot_size=50 + i * 10,
                winners=['Alice'],
                actions=[],
                player_results=[
                    {'player_name': 'Alice', 'starting_stack': 100, 'ending_stack': 100,
                     'profit': 0, 'is_winner': True}
                ]
            )

        history = HistoryManager.get_hand_history('test-room')

        assert len(history) == 3
        # Verify all hand numbers are present
        hand_numbers = {h['hand_number'] for h in history}
        assert hand_numbers == {1, 2, 3}

    def test_get_hand_details(self):
        """Test retrieving detailed hand information."""
        from database import init_db, HistoryManager

        init_db()

        hand_id = HistoryManager.record_hand(
            room_id='test-room',
            hand_number=1,
            pot_size=100,
            winners=['Alice'],
            actions=[{'player': 'Alice', 'action': 'raise', 'amount': 50, 'phase': 'preflop'}],
            player_results=[
                {'player_name': 'Alice', 'starting_stack': 100, 'ending_stack': 150,
                 'profit': 50, 'is_winner': True}
            ]
        )

        details = HistoryManager.get_hand_details(hand_id)

        assert details is not None
        assert details['room_id'] == 'test-room'
        assert details['pot_size'] == 100
        assert len(details['actions']) == 1
        assert len(details['player_results']) == 1

    def test_get_nonexistent_hand(self):
        """Test retrieving non-existent hand returns None."""
        from database import init_db, HistoryManager

        init_db()

        details = HistoryManager.get_hand_details(99999)
        assert details is None

    def test_player_stats_updated(self):
        """Test that player stats are updated correctly."""
        from database import init_db, HistoryManager

        init_db()

        # Record winning hand for Alice
        HistoryManager.record_hand(
            room_id='test-room',
            hand_number=1,
            pot_size=100,
            winners=['Alice'],
            actions=[],
            player_results=[
                {'player_name': 'Alice', 'starting_stack': 100, 'ending_stack': 150,
                 'profit': 50, 'is_winner': True},
                {'player_name': 'Bob', 'starting_stack': 100, 'ending_stack': 50,
                 'profit': -50, 'is_winner': False}
            ]
        )

        alice_stats = HistoryManager.get_player_stats('Alice')
        bob_stats = HistoryManager.get_player_stats('Bob')

        assert alice_stats['hands_played'] == 1
        assert alice_stats['hands_won'] == 1
        assert alice_stats['total_profit'] == 50

        assert bob_stats['hands_played'] == 1
        assert bob_stats['hands_won'] == 0
        assert bob_stats['total_profit'] == -50

    def test_player_stats_accumulate(self):
        """Test that stats accumulate across multiple hands."""
        from database import init_db, HistoryManager

        init_db()

        # Alice wins first hand
        HistoryManager.record_hand(
            room_id='test-room',
            hand_number=1,
            pot_size=100,
            winners=['Alice'],
            actions=[],
            player_results=[
                {'player_name': 'Alice', 'starting_stack': 100, 'ending_stack': 150,
                 'profit': 50, 'is_winner': True}
            ]
        )

        # Alice wins second hand
        HistoryManager.record_hand(
            room_id='test-room',
            hand_number=2,
            pot_size=200,
            winners=['Alice'],
            actions=[],
            player_results=[
                {'player_name': 'Alice', 'starting_stack': 150, 'ending_stack': 250,
                 'profit': 100, 'is_winner': True}
            ]
        )

        stats = HistoryManager.get_player_stats('Alice')

        assert stats['hands_played'] == 2
        assert stats['hands_won'] == 2
        assert stats['total_profit'] == 150

    def test_get_nonexistent_player_stats(self):
        """Test retrieving stats for non-existent player."""
        from database import init_db, HistoryManager

        init_db()

        stats = HistoryManager.get_player_stats('Ghost')
        assert stats is None

    def test_get_leaderboard(self):
        """Test getting leaderboard."""
        from database import init_db, HistoryManager

        init_db()

        # Create some players with different profits
        players = [
            ('Alice', 100),
            ('Bob', -50),
            ('Charlie', 200),
            ('Diana', 50)
        ]

        for name, profit in players:
            HistoryManager.record_hand(
                room_id='test-room',
                hand_number=1,
                pot_size=100,
                winners=[name] if profit > 0 else [],
                actions=[],
                player_results=[
                    {'player_name': name, 'starting_stack': 100,
                     'ending_stack': 100 + profit, 'profit': profit,
                     'is_winner': profit > 0}
                ]
            )

        leaderboard = HistoryManager.get_leaderboard(limit=3)

        assert len(leaderboard) == 3
        # Should be sorted by profit descending
        assert leaderboard[0]['player_name'] == 'Charlie'
        assert leaderboard[0]['total_profit'] == 200

    def test_get_all_stats(self):
        """Test getting all player stats."""
        from database import init_db, HistoryManager

        init_db()

        # Record hands for multiple players
        HistoryManager.record_hand(
            room_id='test-room',
            hand_number=1,
            pot_size=100,
            winners=['Alice'],
            actions=[],
            player_results=[
                {'player_name': 'Alice', 'starting_stack': 100, 'ending_stack': 150,
                 'profit': 50, 'is_winner': True},
                {'player_name': 'Bob', 'starting_stack': 100, 'ending_stack': 50,
                 'profit': -50, 'is_winner': False}
            ]
        )

        all_stats = HistoryManager.get_all_stats()

        assert len(all_stats) == 2
        names = [s['player_name'] for s in all_stats]
        assert 'Alice' in names
        assert 'Bob' in names
