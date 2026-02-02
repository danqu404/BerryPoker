# BerryPoker Design Document

## Overview

BerryPoker is a web-based Texas Hold'em poker game supporting 2-9 players over a local network. The application provides real-time multiplayer gameplay with proper poker rules, hand history tracking, and player statistics.

## Goals

- Support 2-9 player No-Limit Texas Hold'em
- Real-time game state synchronization via WebSocket
- Proper implementation of poker rules (blinds, betting rounds, side pots)
- Player seat selection and dynamic join/leave
- Persistent game history and statistics
- Simple, responsive web interface

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  index.html │  │  style.css  │  │      game.js        │  │
│  │  (UI Layout)│  │  (Styling)  │  │  (WebSocket Client) │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │ WebSocket (JSON)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                     main.py                           │   │
│  │  - HTTP endpoints (REST API)                          │   │
│  │  - WebSocket handler                                  │   │
│  │  - Room management                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│         ┌────────────────┼────────────────┐                 │
│         ▼                ▼                ▼                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐        │
│  │   game/    │  │  models/   │  │   database/    │        │
│  │  poker.py  │  │ schemas.py │  │    db.py       │        │
│  │  table.py  │  │            │  │  history.py    │        │
│  │ evaluator  │  │            │  │                │        │
│  └────────────┘  └────────────┘  └───────┬────────┘        │
└──────────────────────────────────────────┼──────────────────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │   SQLite    │
                                    │ berrypoker  │
                                    │    .db      │
                                    └─────────────┘
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Backend | Python 3.10+ / FastAPI | Async support, WebSocket, type hints |
| Real-time | WebSocket | Bidirectional, low-latency communication |
| Frontend | Vanilla HTML/CSS/JS | Simple, no build step required |
| Database | SQLite | Lightweight, zero configuration |
| Testing | pytest | Standard Python testing framework |

## Project Structure

```
BerryPoker/
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration (env variables)
├── game/
│   ├── poker.py            # Card and Deck classes
│   ├── table.py            # Table, Player, game logic
│   └── hand_evaluator.py   # Hand ranking evaluation
├── models/
│   └── schemas.py          # Pydantic data models
├── database/
│   ├── db.py               # Database connection
│   └── history.py          # History and statistics queries
├── static/
│   ├── index.html          # Game UI
│   ├── style.css           # Styling
│   └── game.js             # Frontend logic
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # API and WebSocket tests
└── requirements.txt        # Python dependencies
```

## Game Logic

### Texas Hold'em Rules

#### Game Flow
```
[Waiting] → [Pre-flop] → [Flop] → [Turn] → [River] → [Showdown]
                ↓           ↓        ↓         ↓
           [Betting]   [Betting] [Betting] [Betting]
```

#### Position and Blinds

**Heads-up (2 players):**
- Button = Small Blind (acts first pre-flop)
- Other player = Big Blind (acts first post-flop)

**3+ players:**
- Small Blind: Left of button
- Big Blind: Left of small blind
- Pre-flop: UTG (left of BB) acts first
- Post-flop: First active player left of button acts first

#### Position Names
| Players | Positions |
|---------|-----------|
| 2 | BTN/SB, BB |
| 3 | BTN, SB, BB |
| 4 | BTN, SB, BB, UTG |
| 5 | BTN, SB, BB, UTG, CO |
| 6 | BTN, SB, BB, UTG, HJ, CO |
| 7 | BTN, SB, BB, UTG, UTG+1, HJ, CO |
| 8 | BTN, SB, BB, UTG, UTG+1, MP, HJ, CO |
| 9 | BTN, SB, BB, UTG, UTG+1, MP, MP+1, HJ, CO |

#### Player Actions
| Action | Description |
|--------|-------------|
| Fold | Discard hand, forfeit pot |
| Check | Pass action (only if no bet to call) |
| Call | Match the current bet |
| Raise | Increase the bet (min raise = last raise amount) |
| All-in | Bet all remaining chips |

#### Big Blind Option
When all players call the big blind (limp), the BB has the option to raise before the flop ends.

#### Side Pots
When a player goes all-in for less than the full bet, a side pot is created. Players can only win from pots they have contributed to.

### Hand Rankings (High to Low)
1. Royal Flush (A-K-Q-J-10 suited)
2. Straight Flush (5 consecutive cards, same suit)
3. Four of a Kind (4 cards same rank)
4. Full House (3 of a kind + pair)
5. Flush (5 cards same suit)
6. Straight (5 consecutive cards)
7. Three of a Kind (3 cards same rank)
8. Two Pair (2 different pairs)
9. One Pair (2 cards same rank)
10. High Card (highest card wins)

## API Design

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/rooms` | Create a new room |
| GET | `/api/rooms/{room_id}` | Get room information |
| GET | `/api/stats/{player_name}` | Get player statistics |
| GET | `/api/leaderboard` | Get top players |

#### Create Room Request
```json
{
  "settings": {
    "small_blind": 1,
    "big_blind": 2,
    "min_buy_in": 40,
    "max_buy_in": 200
  }
}
```

#### Create Room Response
```json
{
  "room_id": "abc123",
  "settings": {
    "small_blind": 1,
    "big_blind": 2,
    "min_buy_in": 40,
    "max_buy_in": 200
  }
}
```

### WebSocket Protocol

Connection: `ws://host:port/ws/{room_id}`

#### Client → Server Messages

| Type | Data | Description |
|------|------|-------------|
| `spectate` | `{player_name}` | Enter room as spectator |
| `join` | `{player_name, stack, seat}` | Sit at table |
| `leave` | `{}` | Leave the table |
| `start_game` | `{}` | Start the game (host only) |
| `action` | `{action, amount?}` | Player action |
| `chat` | `{message}` | Send chat message |

#### Server → Client Messages

| Type | Data | Description |
|------|------|-------------|
| `spectating` | `{player_name}` | Confirmed spectating |
| `joined` | `{player_name, seat, stack}` | Confirmed join |
| `player_joined` | `{player_name, seat}` | Another player joined |
| `player_left` | `{player_name, seat}` | Player left |
| `game_state` | `{...}` | Full game state update |
| `hand_started` | `{hand_number}` | New hand started |
| `action_performed` | `{player, action, amount}` | Action broadcast |
| `phase_changed` | `{phase, community_cards}` | New betting round |
| `hand_complete` | `{winners, pots}` | Hand finished |
| `chat` | `{player_name, message}` | Chat message |
| `error` | `{message}` | Error occurred |

#### Game State Structure
```json
{
  "room_id": "abc123",
  "phase": "flop",
  "community_cards": ["Ah", "Kd", "7c"],
  "pot": 150,
  "current_bet": 20,
  "current_player_seat": 2,
  "dealer_seat": 0,
  "players": [
    {
      "seat": 0,
      "name": "Alice",
      "stack": 980,
      "bet": 10,
      "folded": false,
      "all_in": false,
      "position": "BTN"
    }
  ],
  "your_cards": ["As", "Ks"],
  "valid_actions": ["fold", "call", "raise", "all_in"],
  "min_raise": 20,
  "call_amount": 10
}
```

## Data Models

### Player
```python
@dataclass
class Player:
    name: str
    seat: int
    stack: int
    cards: List[Card]
    bet: int = 0
    folded: bool = False
    all_in: bool = False
    acted_this_round: bool = False
```

### Table
```python
class Table:
    room_id: str
    small_blind: int
    big_blind: int
    max_players: int = 9
    players: Dict[int, Player]  # seat -> Player
    deck: Deck
    community_cards: List[Card]
    pot: int
    current_bet: int
    phase: GamePhase
    dealer_seat: int
    current_player_seat: int
    hand_number: int
```

### Pot (for side pots)
```python
@dataclass
class Pot:
    amount: int
    eligible_players: Set[int]  # seats
```

## Concurrency Control

### Why Locks Are Needed

Multiple WebSocket connections can process messages concurrently in FastAPI's async environment. Without locks, race conditions can occur:

- Two players acting simultaneously could corrupt game state
- Room creation/deletion during iteration could cause errors
- Database writes could conflict

### Lock Architecture

```
┌─────────────────────────────────────────────────────┐
│                  rooms_global_lock                   │
│   (asyncio.Lock for room creation/deletion)         │
└─────────────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ room_lock_1 │  │ room_lock_2 │  │ room_lock_3 │
│ (per-room)  │  │ (per-room)  │  │ (per-room)  │
└─────────────┘  └─────────────┘  └─────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │    _db_lock         │
              │ (threading.Lock for │
              │  SQLite writes)     │
              └─────────────────────┘
```

### Lock Types

| Lock | Type | Purpose |
|------|------|---------|
| `rooms_global_lock` | `asyncio.Lock` | Room creation/deletion |
| `room_locks[room_id]` | `asyncio.Lock` | Per-room game state modifications |
| `_db_lock` | `threading.Lock` | SQLite write operations |

### Lock Usage Pattern

```python
# Room-level operations
async with room_lock:
    result = table.process_action(player_name, action, amount)
    # ... handle result

# Global room operations
async with rooms_global_lock:
    room_id = create_new_room()

# Database writes
with _db_lock:
    conn.execute("INSERT ...")
    conn.commit()
```

## Data Persistence

### State Storage Strategy

| Data Type | Storage | Recovery |
|-----------|---------|----------|
| Hand history | SQLite (permanent) | Always available |
| Player statistics | SQLite (permanent) | Always available |
| Room state | SQLite (temporary) | Restored on server restart |
| WebSocket connections | Memory only | Players must reconnect |

### Room State Persistence

Room state is serialized to JSON and stored in the `rooms` table:

```python
# Serialize
state = table.serialize()  # Returns dict with all game state
state_json = json.dumps(state)

# Persist every 30 seconds + after each action
INSERT OR REPLACE INTO rooms (room_id, state_json, updated_at)
VALUES (?, ?, CURRENT_TIMESTAMP)
```

### What Gets Persisted

- Room settings (blinds, buy-ins)
- Player positions and stacks
- Current hand state (phase, bets, cards)
- Action history
- Pot calculations

### Startup Recovery

On server startup:
1. Load all rooms from database updated within 24 hours
2. Deserialize table state
3. Recreate in-memory structures
4. Players can reconnect to ongoing games

### Cleanup

- Rooms not updated in 24 hours are automatically deleted
- Configurable via `BERRYPOKER_ROOM_CLEANUP_HOURS`

## Database Schema

### Table: rooms (NEW - for persistence)
| Column | Type | Description |
|--------|------|-------------|
| room_id | TEXT | Primary key |
| state_json | TEXT | Serialized room state |
| created_at | TIMESTAMP | Room creation time |
| updated_at | TIMESTAMP | Last state update |

### Table: hands
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| room_id | TEXT | Room identifier |
| hand_number | INTEGER | Hand number in session |
| pot_size | INTEGER | Total pot size |
| winner_names | TEXT | Comma-separated winners |
| winning_hand | TEXT | Hand description |
| created_at | TIMESTAMP | When hand completed |

### Table: player_stats
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| player_name | TEXT | Player identifier (unique) |
| hands_played | INTEGER | Total hands played |
| hands_won | INTEGER | Hands won |
| total_profit | INTEGER | Net chips won/lost |
| biggest_pot | INTEGER | Largest pot won |
| updated_at | TIMESTAMP | Last update time |

### Table: action_history
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| hand_id | INTEGER | Foreign key to hands |
| player_name | TEXT | Acting player |
| action | TEXT | Action type |
| amount | INTEGER | Bet/raise amount |
| phase | TEXT | Game phase |
| sequence | INTEGER | Action order |

## Frontend Design

### UI Layout
```
┌─────────────────────────────────────────────────────────┐
│                    Community Cards                       │
│                  [  ] [  ] [  ] [  ] [  ]               │
│                       Pot: $150                          │
├─────────────────────────────────────────────────────────┤
│     [Seat 7]              [Seat 8]              [Seat 0]│
│      (CO)                  (BTN)                 (SB)   │
│                                                         │
│ [Seat 6]                                      [Seat 1]  │
│  (HJ)                                          (BB)     │
│                                                         │
│ [Seat 5]                                      [Seat 2]  │
│  (MP)                                          (UTG)    │
│                                                         │
│     [Seat 4]              [Seat 3]                      │
│     (UTG+1)                (UTG)                        │
├─────────────────────────────────────────────────────────┤
│  Your Cards: [As] [Ks]                                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────────┐  │
│  │ Fold │ │Check │ │ Call │ │Raise │ │   All-in     │  │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Seat Selection Flow
1. Player enters name and buy-in amount
2. Connects as spectator (sees table state)
3. Clicks on empty seat to join
4. Receives confirmation and game state updates

### Visual Indicators
- **Current player**: Highlighted border, timer
- **Dealer button**: "D" badge on seat
- **Position**: BTN/SB/BB/UTG etc. badge
- **All-in**: Red indicator
- **Folded**: Grayed out seat

## Testing Strategy

### Unit Tests
- `test_poker.py`: Card, Deck operations
- `test_hand_evaluator.py`: All hand rankings
- `test_table.py`: Game logic, betting rules
- `test_database.py`: Database operations

### Integration Tests
- `test_api.py`: REST endpoints, WebSocket flow

### Test Coverage
- Hand evaluation: All 10 hand types
- Betting rules: Min raise, BB option, all-in
- Position logic: Heads-up and multi-player
- Side pots: Multiple all-in scenarios

## Configuration

All settings can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BERRYPOKER_HOST` | `0.0.0.0` | Server bind address |
| `BERRYPOKER_PORT` | `8080` | Server port |
| `BERRYPOKER_CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `BERRYPOKER_DATABASE_PATH` | `./berrypoker.db` | SQLite database path |
| `BERRYPOKER_ROOM_CLEANUP_HOURS` | `24` | Hours before inactive rooms are deleted |
| `BERRYPOKER_PERSIST_INTERVAL` | `30` | Seconds between room state persistence |
| `BERRYPOKER_PRODUCTION` | `false` | Enable production mode |
| `BERRYPOKER_DEBUG` | `false` | Enable debug logging |

### Example Production Configuration

```bash
export BERRYPOKER_HOST=0.0.0.0
export BERRYPOKER_PORT=8080
export BERRYPOKER_CORS_ORIGINS=https://berrypoker.com,https://www.berrypoker.com
export BERRYPOKER_DATABASE_PATH=/var/lib/berrypoker/data.db
export BERRYPOKER_PRODUCTION=true
```

## Deployment

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --host 0.0.0.0 --port 8080

# Run tests
pytest tests/ -v
```

### LAN Play
1. Start server on host machine
2. Find host's local IP (e.g., `192.168.1.100`)
3. Other players connect to `http://192.168.1.100:8080`

### Production Deployment (Domain)

#### Architecture for Public Internet
```
┌─────────────┐      ┌─────────────┐      ┌──────────────┐
│   Browser   │──────│   Nginx     │──────│  BerryPoker  │
│  (Client)   │ HTTPS│  (Reverse   │ HTTP │   (uvicorn)  │
│             │  WSS │   Proxy)    │  WS  │              │
└─────────────┘      └─────────────┘      └──────────────┘
                           │
                     ┌─────┴─────┐
                     │ SSL Cert  │
                     │(Let's Enc)│
                     └───────────┘
```

#### Option 1: Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  berrypoker:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
    environment:
      - BERRYPOKER_DATABASE_PATH=/app/data/berrypoker.db
      - BERRYPOKER_PRODUCTION=true
      - BERRYPOKER_CORS_ORIGINS=https://yourdomain.com
    restart: unless-stopped
```

#### Option 2: Systemd Service

```ini
# /etc/systemd/system/berrypoker.service
[Unit]
Description=BerryPoker Texas Hold'em Server
After=network.target

[Service]
Type=simple
User=berrypoker
WorkingDirectory=/opt/berrypoker
Environment=BERRYPOKER_PRODUCTION=true
Environment=BERRYPOKER_DATABASE_PATH=/var/lib/berrypoker/data.db
ExecStart=/opt/berrypoker/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Nginx Configuration (HTTPS + WebSocket)

```nginx
server {
    listen 80;
    server_name berrypoker.com www.berrypoker.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name berrypoker.com www.berrypoker.com;

    ssl_certificate /etc/letsencrypt/live/berrypoker.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/berrypoker.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

#### SSL Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d berrypoker.com -d www.berrypoker.com

# Auto-renewal (add to crontab)
0 0 * * * certbot renew --quiet
```

#### Cloud Platform Options

| Platform | Pros | Cons |
|----------|------|------|
| **DigitalOcean** | Simple, $5/mo droplet | Manual setup |
| **Railway** | Easy deploy, WebSocket support | May need paid plan |
| **Render** | Free tier, auto-deploy | Cold starts |
| **Fly.io** | Global edge, WebSocket native | Learning curve |
| **AWS EC2** | Full control | Complex setup |

#### Frontend WebSocket URL Update

For production, update `static/game.js` to detect protocol:

```javascript
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${window.location.host}/ws/${roomId}`;
```

### Health Check

Production deployments should use the health endpoint:

```bash
curl https://berrypoker.com/health
# {"status": "healthy", "rooms": 5}
```

## Future Enhancements

- [ ] Tournament mode (increasing blinds)
- [ ] Hand replay viewer
- [ ] Player avatars
- [ ] Sound effects
- [ ] Mobile-responsive design
- [ ] Reconnection handling
- [ ] Time bank for actions
- [ ] Pot odds calculator

## References

- [Texas Hold'em Rules](https://en.wikipedia.org/wiki/Texas_hold_%27em)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
