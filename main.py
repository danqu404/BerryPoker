"""BerryPoker - Texas Hold'em Poker Server."""

import uuid
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from game.table import Table, GamePhase
from database import init_db, HistoryManager
from database.db import get_db, get_db_lock
from models.schemas import RoomSettings, CreateRoomRequest, CreateRoomResponse
import config

app = FastAPI(title="BerryPoker")

# CORS middleware for production deployment
if config.CORS_ALLOW_ALL:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Initialize database
init_db()

# Room management with locks
rooms: Dict[str, Table] = {}
room_locks: Dict[str, asyncio.Lock] = {}  # Per-room locks for concurrent access
room_connections: Dict[str, Dict[str, WebSocket]] = {}  # room_id -> {player_name: websocket}
player_stacks_before_hand: Dict[str, Dict[str, int]] = {}  # room_id -> {player_name: stack}

# Global lock for room creation/deletion
rooms_global_lock = asyncio.Lock()


def get_room_lock(room_id: str) -> asyncio.Lock:
    """Get or create a lock for a specific room."""
    if room_id not in room_locks:
        room_locks[room_id] = asyncio.Lock()
    return room_locks[room_id]


class RoomManager:
    """Manages poker rooms with persistence."""

    @staticmethod
    async def create_room(settings: Optional[RoomSettings] = None) -> str:
        """Create a new room and return its ID."""
        async with rooms_global_lock:
            room_id = str(uuid.uuid4())[:8]
            if settings is None:
                settings = RoomSettings()

            table = Table(
                room_id=room_id,
                small_blind=settings.small_blind,
                big_blind=settings.big_blind,
                min_buy_in=settings.min_buy_in,
                max_buy_in=settings.max_buy_in
            )

            rooms[room_id] = table
            room_locks[room_id] = asyncio.Lock()
            room_connections[room_id] = {}
            player_stacks_before_hand[room_id] = {}

            # Persist to database
            await RoomManager.persist_room(room_id)

            return room_id

    @staticmethod
    def get_room(room_id: str) -> Optional[Table]:
        """Get a room by ID."""
        return rooms.get(room_id)

    @staticmethod
    async def delete_room(room_id: str):
        """Delete a room."""
        async with rooms_global_lock:
            if room_id in rooms:
                del rooms[room_id]
            if room_id in room_locks:
                del room_locks[room_id]
            if room_id in room_connections:
                del room_connections[room_id]
            if room_id in player_stacks_before_hand:
                del player_stacks_before_hand[room_id]

            # Remove from database
            db_lock = get_db_lock()
            with db_lock:
                with get_db() as conn:
                    conn.execute("DELETE FROM rooms WHERE room_id = ?", (room_id,))
                    conn.commit()

    @staticmethod
    async def persist_room(room_id: str):
        """Persist room state to database."""
        table = rooms.get(room_id)
        if not table:
            return

        state = table.serialize()
        state_json = json.dumps(state)

        db_lock = get_db_lock()
        with db_lock:
            with get_db() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO rooms (room_id, state_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (room_id, state_json))
                conn.commit()

    @staticmethod
    async def load_rooms_from_db():
        """Load all persisted rooms from database on startup."""
        async with rooms_global_lock:
            with get_db() as conn:
                # Only load rooms updated within cleanup period
                cutoff = datetime.now() - timedelta(hours=config.ROOM_CLEANUP_HOURS)
                cursor = conn.execute(
                    "SELECT room_id, state_json FROM rooms WHERE updated_at > ?",
                    (cutoff.isoformat(),)
                )

                for row in cursor.fetchall():
                    try:
                        state = json.loads(row['state_json'])
                        table = Table.deserialize(state)
                        room_id = row['room_id']

                        rooms[room_id] = table
                        room_locks[room_id] = asyncio.Lock()
                        room_connections[room_id] = {}
                        player_stacks_before_hand[room_id] = {}

                        print(f"Restored room {room_id}")
                    except Exception as e:
                        print(f"Failed to restore room {row['room_id']}: {e}")

    @staticmethod
    async def cleanup_old_rooms():
        """Remove rooms that haven't been updated in a while."""
        db_lock = get_db_lock()
        cutoff = datetime.now() - timedelta(hours=config.ROOM_CLEANUP_HOURS)

        with db_lock:
            with get_db() as conn:
                conn.execute(
                    "DELETE FROM rooms WHERE updated_at < ?",
                    (cutoff.isoformat(),)
                )
                conn.commit()


async def periodic_persist():
    """Periodically persist all room states."""
    while True:
        await asyncio.sleep(config.ROOM_PERSIST_INTERVAL_SECONDS)
        for room_id in list(rooms.keys()):
            try:
                await RoomManager.persist_room(room_id)
            except Exception as e:
                print(f"Failed to persist room {room_id}: {e}")


async def broadcast_to_room(room_id: str, message: dict, exclude: str = None):
    """Broadcast a message to all players in a room."""
    if room_id not in room_connections:
        return

    for player_name, ws in list(room_connections[room_id].items()):
        if exclude and player_name == exclude:
            continue
        try:
            await ws.send_json(message)
        except Exception:
            pass


async def send_game_state(room_id: str):
    """Send personalized game state to each player."""
    table = rooms.get(room_id)
    if not table:
        return

    for player_name, ws in list(room_connections[room_id].items()):
        try:
            state = table.get_game_state(for_player=player_name)
            await ws.send_json({
                'type': 'game_state',
                'data': state
            })
        except Exception:
            pass


def record_hand_result(room_id: str, table: Table):
    """Record hand result to database."""
    if not hasattr(table, '_last_hand_result'):
        return

    result = table._last_hand_result
    winners = result.get('winners', [])
    pot = result.get('pot', 0)

    # Calculate player results
    player_results = []
    stacks_before = player_stacks_before_hand.get(room_id, {})

    for player in table.players.values():
        starting = stacks_before.get(player.name, player.stack)
        profit = player.stack - starting
        player_results.append({
            'player_name': player.name,
            'starting_stack': starting,
            'ending_stack': player.stack,
            'profit': profit,
            'is_winner': player.name in winners,
            'hole_cards': [c.to_dict() for c in player.hole_cards] if player.hole_cards else []
        })

    # Record to database
    HistoryManager.record_hand(
        room_id=room_id,
        hand_number=table.hand_number,
        pot_size=pot,
        winners=winners,
        actions=table.get_action_history(),
        player_results=player_results
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Load persisted rooms and start background tasks."""
    await RoomManager.load_rooms_from_db()
    asyncio.create_task(periodic_persist())
    print(f"BerryPoker server starting on {config.HOST}:{config.PORT}")
    if config.PRODUCTION:
        print("Running in PRODUCTION mode")


# REST API Endpoints
@app.post("/api/rooms", response_model=CreateRoomResponse)
async def create_room(request: CreateRoomRequest = None):
    """Create a new poker room."""
    settings = request.settings if request and request.settings else RoomSettings()
    room_id = await RoomManager.create_room(settings)
    return CreateRoomResponse(room_id=room_id, settings=settings)


@app.get("/api/rooms/{room_id}")
async def get_room_info(room_id: str):
    """Get room information."""
    table = RoomManager.get_room(room_id)
    if not table:
        raise HTTPException(status_code=404, detail="Room not found")
    return table.get_game_state()


@app.get("/api/rooms/{room_id}/history")
async def get_room_history(room_id: str, limit: int = 50):
    """Get hand history for a room."""
    return HistoryManager.get_hand_history(room_id, limit)


@app.get("/api/hands/{hand_id}")
async def get_hand_details(hand_id: int):
    """Get detailed information about a specific hand."""
    details = HistoryManager.get_hand_details(hand_id)
    if not details:
        raise HTTPException(status_code=404, detail="Hand not found")
    return details


@app.get("/api/stats/{player_name}")
async def get_player_stats(player_name: str):
    """Get statistics for a player."""
    stats = HistoryManager.get_player_stats(player_name)
    if not stats:
        return {"player_name": player_name, "hands_played": 0, "hands_won": 0, "total_profit": 0}
    return stats


@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    """Get top players by profit."""
    return HistoryManager.get_leaderboard(limit)


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {"status": "healthy", "rooms": len(rooms)}


# WebSocket endpoint
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """WebSocket connection for real-time game updates."""
    await websocket.accept()

    table = RoomManager.get_room(room_id)
    if not table:
        await websocket.send_json({'type': 'error', 'data': {'message': 'Room not found'}})
        await websocket.close()
        return

    # Get the lock for this room
    room_lock = get_room_lock(room_id)

    player_name = None
    is_seated = False  # Track if player has chosen a seat
    spectator_name = None  # Name for spectators (not seated)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('type')
            msg_data = data.get('data', {})

            if msg_type == 'spectate':
                # Player enters room as spectator (can see table, choose seat)
                name = msg_data.get('player_name', '').strip()
                if not name:
                    await websocket.send_json({
                        'type': 'error',
                        'data': {'message': 'Player name is required'}
                    })
                    continue

                spectator_name = name

                async with room_lock:
                    # Check if already seated (reconnecting)
                    existing = table.get_player_by_name(name)
                    if existing:
                        player_name = name
                        is_seated = True
                        room_connections[room_id][player_name] = websocket
                        await websocket.send_json({
                            'type': 'joined',
                            'data': {'player_name': player_name, 'seat': existing.seat}
                        })
                    else:
                        # Send spectating confirmation
                        await websocket.send_json({
                            'type': 'spectating',
                            'data': {'player_name': name}
                        })

                    # Send current game state
                    state = table.get_game_state()
                    state['spectator_name'] = spectator_name
                    await websocket.send_json({
                        'type': 'game_state',
                        'data': state
                    })

            elif msg_type == 'join':
                # Player choosing a seat
                name = msg_data.get('player_name', '').strip() or spectator_name
                stack = msg_data.get('stack', 100)
                seat = msg_data.get('seat')

                if not name:
                    await websocket.send_json({
                        'type': 'error',
                        'data': {'message': 'Player name is required'}
                    })
                    continue

                if seat is None:
                    await websocket.send_json({
                        'type': 'error',
                        'data': {'message': 'Please select a seat'}
                    })
                    continue

                async with room_lock:
                    # Check if name is already taken by another player
                    existing = table.get_player_by_name(name)
                    if existing:
                        if existing.seat != seat:
                            await websocket.send_json({
                                'type': 'error',
                                'data': {'message': 'Name already taken'}
                            })
                            continue
                        # Reconnecting to same seat
                        player_name = name
                        is_seated = True
                        room_connections[room_id][player_name] = websocket
                    else:
                        # New player taking a seat
                        player = table.add_player(name, stack, seat)
                        if not player:
                            await websocket.send_json({
                                'type': 'error',
                                'data': {'message': 'Seat is taken or invalid'}
                            })
                            continue

                        player_name = name
                        is_seated = True
                        room_connections[room_id][player_name] = websocket

                    await websocket.send_json({
                        'type': 'joined',
                        'data': {'player_name': player_name, 'seat': seat}
                    })

                # Broadcast player update (outside lock to avoid deadlock)
                await broadcast_to_room(room_id, {
                    'type': 'player_joined',
                    'data': {'player_name': player_name, 'seat': seat}
                }, exclude=player_name)

                # Send game state to all
                await send_game_state(room_id)

                # Persist room state
                await RoomManager.persist_room(room_id)

            elif msg_type == 'leave':
                # Player leaving
                async with room_lock:
                    if player_name:
                        table.remove_player(player_name)
                        if player_name in room_connections[room_id]:
                            del room_connections[room_id][player_name]

                if player_name:
                    await broadcast_to_room(room_id, {
                        'type': 'player_left',
                        'data': {'player_name': player_name}
                    })
                    await send_game_state(room_id)
                    await RoomManager.persist_room(room_id)

                player_name = None

            elif msg_type == 'start_game':
                # Start a new hand
                async with room_lock:
                    if table.phase != GamePhase.WAITING:
                        await websocket.send_json({
                            'type': 'error',
                            'data': {'message': 'Game already in progress'}
                        })
                        continue

                    # Store stacks before hand
                    player_stacks_before_hand[room_id] = {
                        p.name: p.stack for p in table.players.values()
                    }

                    if table.start_hand():
                        await broadcast_to_room(room_id, {
                            'type': 'hand_started',
                            'data': {'hand_number': table.hand_number}
                        })
                        await send_game_state(room_id)
                        await RoomManager.persist_room(room_id)
                    else:
                        await websocket.send_json({
                            'type': 'error',
                            'data': {'message': 'Need at least 2 players to start'}
                        })

            elif msg_type == 'action':
                # Player action
                if not player_name:
                    await websocket.send_json({
                        'type': 'error',
                        'data': {'message': 'Not joined'}
                    })
                    continue

                action = msg_data.get('action')
                amount = msg_data.get('amount', 0)

                async with room_lock:
                    result = table.process_action(player_name, action, amount)

                    if not result['success']:
                        await websocket.send_json({
                            'type': 'error',
                            'data': {'message': result.get('error', 'Invalid action')}
                        })
                        continue

                    # Broadcast action
                    await broadcast_to_room(room_id, {
                        'type': 'player_action',
                        'data': {
                            'player_name': player_name,
                            'action': action,
                            'amount': amount
                        }
                    })

                    # Check if waiting for run-twice choice
                    if table.phase == GamePhase.WAITING_RUN_TWICE:
                        # Send prompt to eligible players
                        for eligible_player in table._run_twice_players:
                            if eligible_player in room_connections[room_id]:
                                try:
                                    await room_connections[room_id][eligible_player].send_json({
                                        'type': 'run_twice_prompt',
                                        'data': {
                                            'eligible_players': table._run_twice_players
                                        }
                                    })
                                except Exception:
                                    pass

                    # Check if hand ended
                    elif table.phase == GamePhase.WAITING:
                        # Record hand result
                        record_hand_result(room_id, table)

                        await broadcast_to_room(room_id, {
                            'type': 'hand_ended',
                            'data': table._last_hand_result if hasattr(table, '_last_hand_result') else {}
                        })

                    await send_game_state(room_id)
                    await RoomManager.persist_room(room_id)

            elif msg_type == 'chat':
                # Chat message
                if player_name:
                    await broadcast_to_room(room_id, {
                        'type': 'chat',
                        'data': {
                            'player_name': player_name,
                            'message': msg_data.get('message', '')
                        }
                    })

            elif msg_type == 'sit_out':
                # Toggle sit out
                async with room_lock:
                    if player_name:
                        player = table.get_player_by_name(player_name)
                        if player:
                            player.is_sitting_out = not player.is_sitting_out
                            await send_game_state(room_id)
                            await RoomManager.persist_room(room_id)

            elif msg_type == 'add_chips':
                # Add chips to stack (between hands only)
                async with room_lock:
                    if player_name and table.phase == GamePhase.WAITING:
                        player = table.get_player_by_name(player_name)
                        if player:
                            add_amount = msg_data.get('amount', 0)
                            new_total = player.stack + add_amount
                            if new_total <= table.max_buy_in:
                                player.stack = new_total
                                await send_game_state(room_id)
                                await RoomManager.persist_room(room_id)
                            else:
                                await websocket.send_json({
                                    'type': 'error',
                                    'data': {'message': f'Max stack is {table.max_buy_in}'}
                                })

            elif msg_type == 'run_twice_choice':
                # Handle run-it-twice choice
                if not player_name:
                    await websocket.send_json({
                        'type': 'error',
                        'data': {'message': 'Not joined'}
                    })
                    continue

                wants_twice = msg_data.get('run_twice', False)

                async with room_lock:
                    result = table.process_run_twice_choice(player_name, wants_twice)

                    if not result['success']:
                        await websocket.send_json({
                            'type': 'error',
                            'data': {'message': result.get('error', 'Invalid choice')}
                        })
                        continue

                    # Broadcast choice made
                    await broadcast_to_room(room_id, {
                        'type': 'run_twice_choice_made',
                        'data': {
                            'player_name': player_name,
                            'wants_twice': wants_twice,
                            'waiting_for': [p for p in table._run_twice_players
                                          if p not in table._run_twice_choices]
                        }
                    })

                    # Check if hand ended (all choices made)
                    if table.phase == GamePhase.WAITING:
                        # Record hand result
                        record_hand_result(room_id, table)

                        await broadcast_to_room(room_id, {
                            'type': 'hand_ended',
                            'data': table._last_hand_result if hasattr(table, '_last_hand_result') else {}
                        })

                    await send_game_state(room_id)
                    await RoomManager.persist_room(room_id)

    except WebSocketDisconnect:
        # Handle disconnect
        if player_name and room_id in room_connections:
            if player_name in room_connections[room_id]:
                del room_connections[room_id][player_name]

            # Don't remove player from table immediately (allow reconnect)
            await broadcast_to_room(room_id, {
                'type': 'player_disconnected',
                'data': {'player_name': player_name}
            })

    except Exception as e:
        print(f"WebSocket error: {e}")
        if player_name and room_id in room_connections:
            if player_name in room_connections[room_id]:
                del room_connections[room_id][player_name]


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the main game page."""
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
