"""Integration tests for the FastAPI server and WebSocket communication."""

import os
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def test_db():
    """Set up a temporary database for tests."""
    temp_dir = tempfile.mkdtemp()
    test_db_path = Path(temp_dir) / "test_berrypoker.db"

    import database.db as db_module
    original_path = db_module.DATABASE_PATH
    db_module.DATABASE_PATH = test_db_path

    # Re-initialize database
    from database import init_db
    init_db()

    yield test_db_path

    # Cleanup
    db_module.DATABASE_PATH = original_path
    if test_db_path.exists():
        os.remove(test_db_path)
    os.rmdir(temp_dir)


@pytest.fixture
def client(test_db):
    """Create a test client."""
    from main import app
    return TestClient(app)


class TestRoomAPI:
    """Tests for room-related API endpoints."""

    def test_create_room(self, client):
        """Test creating a room via API."""
        response = client.post("/api/rooms", json={
            "settings": {
                "small_blind": 5,
                "big_blind": 10,
                "min_buy_in": 100,
                "max_buy_in": 500
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert 'room_id' in data
        assert data['settings']['small_blind'] == 5
        assert data['settings']['big_blind'] == 10

    def test_create_room_default_settings(self, client):
        """Test creating a room with default settings."""
        response = client.post("/api/rooms", json={})

        assert response.status_code == 200
        data = response.json()
        assert 'room_id' in data
        assert data['settings']['small_blind'] == 1
        assert data['settings']['big_blind'] == 2

    def test_get_room_info(self, client):
        """Test getting room information."""
        # First create a room
        create_response = client.post("/api/rooms", json={})
        room_id = create_response.json()['room_id']

        # Then get its info
        response = client.get(f"/api/rooms/{room_id}")

        assert response.status_code == 200
        data = response.json()
        assert data['room_id'] == room_id
        assert data['phase'] == 'waiting'

    def test_get_nonexistent_room(self, client):
        """Test getting non-existent room returns 404."""
        response = client.get("/api/rooms/nonexistent")
        assert response.status_code == 404


class TestWebSocket:
    """Tests for WebSocket functionality."""

    def test_websocket_connect_invalid_room(self, client):
        """Test connecting to non-existent room."""
        with client.websocket_connect("/ws/invalid-room") as websocket:
            data = websocket.receive_json()
            assert data['type'] == 'error'
            assert 'not found' in data['data']['message'].lower()

    def test_websocket_join_room(self, client):
        """Test joining a room via WebSocket with seat selection."""
        # Create room first
        create_response = client.post("/api/rooms", json={})
        room_id = create_response.json()['room_id']

        with client.websocket_connect(f"/ws/{room_id}") as websocket:
            # First, spectate to see the room
            websocket.send_json({
                "type": "spectate",
                "data": {
                    "player_name": "TestPlayer"
                }
            })

            # Should receive spectating confirmation
            data = websocket.receive_json()
            assert data['type'] == 'spectating'

            # Should receive game state
            data = websocket.receive_json()
            assert data['type'] == 'game_state'

            # Now join with a specific seat
            websocket.send_json({
                "type": "join",
                "data": {
                    "player_name": "TestPlayer",
                    "stack": 100,
                    "seat": 0
                }
            })

            # Should receive joined confirmation
            data = websocket.receive_json()
            assert data['type'] == 'joined'
            assert data['data']['player_name'] == 'TestPlayer'
            assert data['data']['seat'] == 0

            # Should receive game state
            data = websocket.receive_json()
            assert data['type'] == 'game_state'

    def test_websocket_join_empty_name(self, client):
        """Test joining with empty name fails."""
        create_response = client.post("/api/rooms", json={})
        room_id = create_response.json()['room_id']

        with client.websocket_connect(f"/ws/{room_id}") as websocket:
            websocket.send_json({
                "type": "join",
                "data": {
                    "player_name": "",
                    "stack": 100
                }
            })

            data = websocket.receive_json()
            assert data['type'] == 'error'

    def test_websocket_start_game_not_enough_players(self, client):
        """Test starting game with insufficient players."""
        create_response = client.post("/api/rooms", json={})
        room_id = create_response.json()['room_id']

        with client.websocket_connect(f"/ws/{room_id}") as websocket:
            # Spectate first
            websocket.send_json({
                "type": "spectate",
                "data": {"player_name": "Solo"}
            })
            websocket.receive_json()  # spectating
            websocket.receive_json()  # game_state

            # Join as single player with seat
            websocket.send_json({
                "type": "join",
                "data": {"player_name": "Solo", "stack": 100, "seat": 0}
            })
            websocket.receive_json()  # joined
            websocket.receive_json()  # game_state

            # Try to start game
            websocket.send_json({"type": "start_game"})

            data = websocket.receive_json()
            assert data['type'] == 'error'
            assert 'at least 2' in data['data']['message'].lower()

    def test_websocket_chat(self, client):
        """Test chat functionality."""
        create_response = client.post("/api/rooms", json={})
        room_id = create_response.json()['room_id']

        with client.websocket_connect(f"/ws/{room_id}") as websocket:
            # Spectate first
            websocket.send_json({
                "type": "spectate",
                "data": {"player_name": "Chatter"}
            })
            websocket.receive_json()  # spectating
            websocket.receive_json()  # game_state

            # Join with seat
            websocket.send_json({
                "type": "join",
                "data": {"player_name": "Chatter", "stack": 100, "seat": 0}
            })
            websocket.receive_json()  # joined
            websocket.receive_json()  # game_state

            # Send chat
            websocket.send_json({
                "type": "chat",
                "data": {"message": "Hello!"}
            })

            # Should receive chat broadcast
            data = websocket.receive_json()
            assert data['type'] == 'chat'
            assert data['data']['player_name'] == 'Chatter'
            assert data['data']['message'] == 'Hello!'


class TestMultiPlayerGame:
    """Tests for multi-player game scenarios."""

    def test_two_player_game_flow(self, client):
        """Test a basic two-player game flow."""
        # Create room
        create_response = client.post("/api/rooms", json={
            "settings": {"small_blind": 1, "big_blind": 2}
        })
        room_id = create_response.json()['room_id']

        # Connect two players
        with client.websocket_connect(f"/ws/{room_id}") as ws1:
            # Alice spectates then joins
            ws1.send_json({
                "type": "spectate",
                "data": {"player_name": "Alice"}
            })
            ws1.receive_json()  # spectating
            ws1.receive_json()  # game_state

            ws1.send_json({
                "type": "join",
                "data": {"player_name": "Alice", "stack": 100, "seat": 0}
            })
            ws1.receive_json()  # joined
            ws1.receive_json()  # game_state

            with client.websocket_connect(f"/ws/{room_id}") as ws2:
                # Bob spectates then joins
                ws2.send_json({
                    "type": "spectate",
                    "data": {"player_name": "Bob"}
                })
                ws2.receive_json()  # spectating
                ws2.receive_json()  # game_state

                ws2.send_json({
                    "type": "join",
                    "data": {"player_name": "Bob", "stack": 100, "seat": 1}
                })
                ws2.receive_json()  # joined

                # Alice should get player_joined notification
                alice_msg = ws1.receive_json()
                assert alice_msg['type'] == 'player_joined'

                # Both get game_state
                ws1.receive_json()
                ws2.receive_json()

                # Start game
                ws1.send_json({"type": "start_game"})

                # Both should receive hand_started
                msg1 = ws1.receive_json()
                msg2 = ws2.receive_json()
                assert msg1['type'] == 'hand_started'
                assert msg2['type'] == 'hand_started'


class TestStatsAPI:
    """Tests for statistics API endpoints."""

    def test_get_player_stats_new_player(self, client):
        """Test getting stats for a player with no history."""
        response = client.get("/api/stats/NewPlayer")

        assert response.status_code == 200
        data = response.json()
        assert data['player_name'] == 'NewPlayer'
        assert data['hands_played'] == 0

    def test_get_leaderboard(self, client):
        """Test getting the leaderboard."""
        response = client.get("/api/leaderboard")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestRoomManager:
    """Tests for RoomManager functionality."""

    def test_room_manager_create_and_get(self):
        """Test creating and retrieving rooms via RoomManager."""
        from main import RoomManager
        from models.schemas import RoomSettings

        settings = RoomSettings(small_blind=5, big_blind=10)
        room_id = RoomManager.create_room(settings)

        assert room_id is not None
        room = RoomManager.get_room(room_id)
        assert room is not None
        assert room.small_blind == 5
        assert room.big_blind == 10

    def test_room_manager_delete(self):
        """Test deleting a room."""
        from main import RoomManager

        room_id = RoomManager.create_room()
        assert RoomManager.get_room(room_id) is not None

        RoomManager.delete_room(room_id)
        assert RoomManager.get_room(room_id) is None
