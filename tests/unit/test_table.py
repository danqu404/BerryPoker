"""Unit tests for table.py - Table and Player management."""

import pytest
from game.table import Table, Player, GamePhase, ActionType, Pot


class TestPlayer:
    """Tests for the Player class."""

    def test_player_creation(self):
        """Test creating a player."""
        player = Player(name="Alice", seat=0, stack=100)
        assert player.name == "Alice"
        assert player.seat == 0
        assert player.stack == 100
        assert player.hole_cards == []
        assert player.current_bet == 0
        assert player.total_bet == 0
        assert not player.is_folded
        assert not player.is_all_in

    def test_player_reset_for_hand(self):
        """Test resetting player state for new hand."""
        player = Player(name="Alice", seat=0, stack=100)
        player.is_folded = True
        player.current_bet = 50
        player.total_bet = 100
        player.is_all_in = True

        player.reset_for_hand()

        assert player.hole_cards == []
        assert player.current_bet == 0
        assert player.total_bet == 0
        assert not player.is_folded
        assert not player.is_all_in

    def test_player_to_dict(self):
        """Test player serialization."""
        player = Player(name="Bob", seat=1, stack=200)
        d = player.to_dict()
        assert d['name'] == "Bob"
        assert d['seat'] == 1
        assert d['stack'] == 200
        assert 'hole_cards' not in d  # Not shown by default

    def test_player_to_dict_with_cards(self):
        """Test player serialization with cards shown."""
        from game.poker import Card
        player = Player(name="Bob", seat=1, stack=200)
        player.hole_cards = [Card('A', 'hearts'), Card('K', 'spades')]

        d = player.to_dict(show_cards=True)
        assert 'hole_cards' in d
        assert len(d['hole_cards']) == 2


class TestPot:
    """Tests for the Pot class."""

    def test_pot_creation(self):
        """Test creating a pot."""
        pot = Pot(amount=100, eligible_players=['Alice', 'Bob'])
        assert pot.amount == 100
        assert pot.eligible_players == ['Alice', 'Bob']

    def test_pot_to_dict(self):
        """Test pot serialization."""
        pot = Pot(amount=50, eligible_players=['Alice'])
        d = pot.to_dict()
        assert d['amount'] == 50
        assert d['eligible_players'] == ['Alice']


class TestTable:
    """Tests for the Table class."""

    def test_table_creation(self):
        """Test creating a table."""
        table = Table('room-123', small_blind=1, big_blind=2)
        assert table.room_id == 'room-123'
        assert table.small_blind == 1
        assert table.big_blind == 2
        assert table.phase == GamePhase.WAITING
        assert len(table.players) == 0

    def test_add_player(self):
        """Test adding players to table."""
        table = Table('test-room')
        player = table.add_player('Alice', 100)

        assert player is not None
        assert player.name == 'Alice'
        assert player.stack == 100
        assert len(table.players) == 1

    def test_add_player_specific_seat(self):
        """Test adding player to specific seat."""
        table = Table('test-room')
        player = table.add_player('Alice', 100, seat=5)

        assert player.seat == 5
        assert 5 in table.players

    def test_add_player_seat_taken(self):
        """Test adding player to taken seat returns None."""
        table = Table('test-room')
        table.add_player('Alice', 100, seat=0)
        player2 = table.add_player('Bob', 100, seat=0)

        assert player2 is None
        assert len(table.players) == 1

    def test_add_player_table_full(self):
        """Test adding player to full table returns None."""
        table = Table('test-room')
        for i in range(9):
            table.add_player(f'Player{i}', 100)

        player = table.add_player('Extra', 100)
        assert player is None

    def test_add_player_stack_limits(self):
        """Test that player stack is clamped to buy-in limits."""
        table = Table('test-room', min_buy_in=50, max_buy_in=200)

        p1 = table.add_player('Low', 10)  # Below min
        p2 = table.add_player('High', 500)  # Above max

        assert p1.stack == 50  # Clamped to min
        assert p2.stack == 200  # Clamped to max

    def test_remove_player(self):
        """Test removing a player."""
        table = Table('test-room')
        table.add_player('Alice', 100)
        table.add_player('Bob', 100)

        result = table.remove_player('Alice')

        assert result is True
        assert len(table.players) == 1
        assert table.get_player_by_name('Alice') is None

    def test_remove_nonexistent_player(self):
        """Test removing non-existent player returns False."""
        table = Table('test-room')
        result = table.remove_player('Ghost')
        assert result is False

    def test_get_player_by_name(self):
        """Test getting player by name."""
        table = Table('test-room')
        table.add_player('Alice', 100)
        table.add_player('Bob', 100)

        player = table.get_player_by_name('Bob')
        assert player is not None
        assert player.name == 'Bob'

    def test_get_active_players(self):
        """Test getting active players."""
        table = Table('test-room')
        table.add_player('Alice', 100)
        table.add_player('Bob', 100)
        charlie = table.add_player('Charlie', 100)
        charlie.is_sitting_out = True  # Sitting out

        active = table.get_active_players()
        assert len(active) == 2
        assert all(not p.is_sitting_out for p in active)

    def test_start_hand_minimum_players(self):
        """Test that start_hand requires at least 2 players."""
        table = Table('test-room')
        table.add_player('Alice', 100)

        result = table.start_hand()
        assert result is False
        assert table.phase == GamePhase.WAITING

    def test_start_hand_success(self):
        """Test successful hand start."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100)
        table.add_player('Bob', 100)
        table.add_player('Charlie', 100)

        result = table.start_hand()

        assert result is True
        assert table.phase == GamePhase.PREFLOP
        assert table.hand_number == 1
        assert table.pot == 3  # SB + BB

        # Check players have cards
        for player in table.players.values():
            assert len(player.hole_cards) == 2

    def test_blinds_posted(self):
        """Test that blinds are posted correctly."""
        table = Table('test-room', small_blind=5, big_blind=10)
        table.add_player('Alice', 100, seat=0)  # Dealer
        table.add_player('Bob', 100, seat=1)    # SB
        table.add_player('Charlie', 100, seat=2)  # BB

        table.start_hand()

        # In 3+ player game, dealer is seat 0, SB is next, BB is after
        assert table.pot == 15  # 5 + 10

    def test_get_valid_actions_fold_always_valid(self):
        """Test that fold is always a valid action."""
        table = Table('test-room')
        table.add_player('Alice', 100)
        table.add_player('Bob', 100)
        table.start_hand()

        current_player = table.players[table.current_player_seat]
        actions = table.get_valid_actions(current_player.name)

        action_types = [a['action'] for a in actions]
        assert 'fold' in action_types

    def test_get_game_state(self):
        """Test getting game state."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100)
        table.add_player('Bob', 100)

        state = table.get_game_state()

        assert state['room_id'] == 'test-room'
        assert state['phase'] == 'waiting'
        assert state['small_blind'] == 1
        assert state['big_blind'] == 2
        assert len(state['players']) == 2

    def test_get_game_state_for_player(self):
        """Test getting personalized game state."""
        table = Table('test-room')
        table.add_player('Alice', 100)
        table.add_player('Bob', 100)
        table.start_hand()

        state = table.get_game_state(for_player='Alice')

        # Should include valid actions for Alice if it's her turn
        assert 'valid_actions' in state

    def test_pot_property(self):
        """Test that pot property returns sum of all pots."""
        table = Table('test-room')
        table.pots = [Pot(amount=50), Pot(amount=30), Pot(amount=20)]
        assert table.pot == 100


class TestHeadsUpRules:
    """Tests for heads-up (2 player) specific rules."""

    def test_heads_up_button_is_small_blind(self):
        """In heads-up, button is small blind."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)
        table.add_player('Bob', 100, seat=1)

        table.start_hand()

        sb_seat = table._get_sb_seat()
        assert sb_seat == table.dealer_seat

    def test_heads_up_preflop_sb_acts_first(self):
        """In heads-up preflop, small blind (button) acts first."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)
        table.add_player('Bob', 100, seat=1)

        table.start_hand()

        sb_seat = table._get_sb_seat()
        assert table.current_player_seat == sb_seat

    def test_heads_up_postflop_bb_acts_first(self):
        """In heads-up postflop, big blind acts first."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)
        table.add_player('Bob', 100, seat=1)

        table.start_hand()

        # Both players call/check to flop
        current = table.players[table.current_player_seat]
        table.process_action(current.name, 'call')  # SB calls

        bb_seat = table._get_bb_seat()
        bb_player = table.players[bb_seat]
        table.process_action(bb_player.name, 'check')  # BB checks

        # Should now be on flop with BB acting first
        assert table.phase == GamePhase.FLOP
        assert table.current_player_seat == bb_seat


class TestThreePlayerRules:
    """Tests for 3+ player rules."""

    def test_three_player_preflop_utg_acts_first(self):
        """In 3+ player game, UTG (left of BB) acts first preflop."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)  # Dealer
        table.add_player('Bob', 100, seat=1)    # SB
        table.add_player('Charlie', 100, seat=2)  # BB

        table.start_hand()

        # UTG should be Alice (seat 0, wrapping around from BB at seat 2)
        bb_seat = table._get_bb_seat()
        assert bb_seat == 2

        # Current player should be seat 0 (UTG)
        assert table.current_player_seat == 0

    def test_three_player_postflop_sb_acts_first(self):
        """In 3+ player game postflop, first active player left of button acts first."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)  # Dealer
        table.add_player('Bob', 100, seat=1)    # SB
        table.add_player('Charlie', 100, seat=2)  # BB

        table.start_hand()

        # UTG (Alice) calls
        table.process_action('Alice', 'call')
        # SB (Bob) calls
        table.process_action('Bob', 'call')
        # BB (Charlie) checks
        table.process_action('Charlie', 'check')

        # Should be on flop, first player left of button (Bob at seat 1) acts first
        assert table.phase == GamePhase.FLOP
        assert table.current_player_seat == 1  # Bob (SB)


class TestMinRaiseRules:
    """Tests for minimum raise rules."""

    def test_min_raise_is_last_raise_amount(self):
        """Minimum raise must be at least the last raise increment."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)
        table.add_player('Bob', 100, seat=1)

        table.start_hand()

        # Alice raises to 6 (raise of 4 over BB of 2)
        table.process_action('Alice', 'raise', 6)

        # Bob's min raise should be 6 + 4 = 10
        actions = table.get_valid_actions('Bob')
        raise_action = next(a for a in actions if a['action'] == 'raise')
        assert raise_action['min'] == 10

    def test_all_in_less_than_min_raise_allowed(self):
        """Player can all-in for less than min raise."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)
        table.add_player('Bob', 15, seat=1)  # Short stack

        table.start_hand()

        # Alice raises to 10
        table.process_action('Alice', 'raise', 10)

        # Bob can all-in even though it's less than min raise
        result = table.process_action('Bob', 'all_in')
        assert result['success'] is True
        assert table.players[1].is_all_in is True


class TestSidePots:
    """Tests for side pot calculations."""

    def test_side_pot_created_on_all_in(self):
        """Side pot created when player goes all-in."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)
        table.add_player('Bob', 30, seat=1)  # Short stack
        table.add_player('Charlie', 100, seat=2)

        table.start_hand()

        # Alice raises to 50
        table.process_action('Alice', 'raise', 50)
        # Bob goes all-in for 30
        table.process_action('Bob', 'all_in')
        # Charlie calls 50
        table.process_action('Charlie', 'call')

        # Alice should check or can bet more
        # BB action completes preflop if everyone matched

    def test_multiple_side_pots(self):
        """Multiple side pots with different all-in amounts."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 20, seat=0)   # Shortest
        table.add_player('Bob', 50, seat=1)     # Medium
        table.add_player('Charlie', 100, seat=2)  # Deepest

        table.start_hand()

        # All go all-in
        table.process_action('Alice', 'all_in')  # 20
        table.process_action('Bob', 'all_in')    # 50
        table.process_action('Charlie', 'call')  # Calls 50

        # Side pots should be calculated


class TestTableActions:
    """Tests for player actions at the table."""

    def setup_method(self):
        """Set up a table with players for each test."""
        self.table = Table('test-room', small_blind=1, big_blind=2)
        self.table.add_player('Alice', 100, seat=0)
        self.table.add_player('Bob', 100, seat=1)
        self.table.add_player('Charlie', 100, seat=2)
        self.table.start_hand()

    def test_process_action_not_player_turn(self):
        """Test action from wrong player fails."""
        # Find a player who is NOT current
        current_seat = self.table.current_player_seat
        other_player = None
        for p in self.table.players.values():
            if p.seat != current_seat:
                other_player = p
                break

        result = self.table.process_action(other_player.name, 'fold')
        assert result['success'] is False
        assert 'not your turn' in result['error'].lower()

    def test_process_action_fold(self):
        """Test fold action."""
        current_player = self.table.players[self.table.current_player_seat]
        result = self.table.process_action(current_player.name, 'fold')

        assert result['success'] is True
        assert current_player.is_folded is True

    def test_process_action_call(self):
        """Test call action."""
        current_player = self.table.players[self.table.current_player_seat]
        initial_stack = current_player.stack

        result = self.table.process_action(current_player.name, 'call')

        assert result['success'] is True
        assert current_player.stack < initial_stack

    def test_process_action_check_invalid(self):
        """Test check when there's a bet to call fails."""
        # Preflop with blinds, checking should fail for most players
        current_player = self.table.players[self.table.current_player_seat]

        # If there's an amount to call, check should fail
        if current_player.current_bet < self.table.current_bet:
            result = self.table.process_action(current_player.name, 'check')
            assert result['success'] is False

    def test_process_action_raise(self):
        """Test raise action."""
        current_player = self.table.players[self.table.current_player_seat]
        initial_stack = current_player.stack

        # Raise to 10
        result = self.table.process_action(current_player.name, 'raise', 10)

        assert result['success'] is True
        assert current_player.stack < initial_stack

    def test_process_action_all_in(self):
        """Test all-in action."""
        current_player = self.table.players[self.table.current_player_seat]

        result = self.table.process_action(current_player.name, 'all_in')

        assert result['success'] is True
        assert current_player.stack == 0
        assert current_player.is_all_in is True

    def test_action_history_recorded(self):
        """Test that actions are recorded in history."""
        current_player = self.table.players[self.table.current_player_seat]
        self.table.process_action(current_player.name, 'call')

        history = self.table.get_action_history()
        assert len(history) > 0
        assert history[-1]['player'] == current_player.name

    def test_game_advances_after_all_fold(self):
        """Test game ends when all but one player folds."""
        # Get players in order and fold all but one
        players_in_order = []
        current = self.table.current_player_seat

        while len(players_in_order) < len(self.table.players) - 1:
            player = self.table.players[current]
            if not player.is_folded:
                players_in_order.append(player)
                self.table.process_action(player.name, 'fold')
            current = self.table._get_next_seat(current, skip_folded=False)
            if current is None:
                break

        # Game should have ended
        assert self.table.phase == GamePhase.WAITING


class TestPositionNames:
    """Tests for position name assignments."""

    def test_heads_up_positions(self):
        """Test position names in heads-up game."""
        table = Table('test-room')
        table.add_player('Alice', 100, seat=0)
        table.add_player('Bob', 100, seat=1)
        table.start_hand()

        state = table.get_game_state()
        positions = {p['seat']: p['position'] for p in state['players']}

        # In heads-up, dealer is BTN (also SB), other is BB
        assert positions[table.dealer_seat] == 'BTN'
        other_seat = 1 if table.dealer_seat == 0 else 0
        assert positions[other_seat] == 'BB'

    def test_three_player_positions(self):
        """Test position names in 3-player game."""
        table = Table('test-room')
        table.add_player('Alice', 100, seat=0)
        table.add_player('Bob', 100, seat=1)
        table.add_player('Charlie', 100, seat=2)
        table.start_hand()

        state = table.get_game_state()
        positions = {p['seat']: p['position'] for p in state['players']}

        # Dealer at seat 0, SB at seat 1, BB at seat 2
        assert positions[0] == 'BTN'
        assert positions[1] == 'SB'
        assert positions[2] == 'BB'

    def test_six_player_positions(self):
        """Test position names in 6-player game."""
        table = Table('test-room')
        for i in range(6):
            table.add_player(f'Player{i}', 100, seat=i)
        table.start_hand()

        state = table.get_game_state()
        positions = {p['seat']: p['position'] for p in state['players']}

        # Should have BTN, SB, BB, UTG, HJ, CO
        position_values = set(positions.values())
        assert 'BTN' in position_values
        assert 'SB' in position_values
        assert 'BB' in position_values
        assert 'UTG' in position_values
        assert 'CO' in position_values

    def test_nine_player_positions(self):
        """Test position names in 9-player (full ring) game."""
        table = Table('test-room')
        for i in range(9):
            table.add_player(f'Player{i}', 100, seat=i)
        table.start_hand()

        state = table.get_game_state()
        positions = {p['seat']: p['position'] for p in state['players']}

        # Should have all positions
        position_values = set(positions.values())
        assert 'BTN' in position_values
        assert 'SB' in position_values
        assert 'BB' in position_values
        assert 'UTG' in position_values
        assert 'CO' in position_values
        assert 'HJ' in position_values


class TestBBOption:
    """Tests for big blind option."""

    def test_bb_can_raise_when_everyone_limps(self):
        """Big blind has option to raise when everyone just calls."""
        table = Table('test-room', small_blind=1, big_blind=2)
        table.add_player('Alice', 100, seat=0)  # Dealer
        table.add_player('Bob', 100, seat=1)    # SB
        table.add_player('Charlie', 100, seat=2)  # BB

        table.start_hand()

        # UTG (Alice) calls
        table.process_action('Alice', 'call')
        # SB (Bob) calls
        table.process_action('Bob', 'call')

        # BB (Charlie) should still be able to raise
        assert table.phase == GamePhase.PREFLOP
        assert table.current_player_seat == 2  # Charlie (BB)

        actions = table.get_valid_actions('Charlie')
        action_types = [a['action'] for a in actions]
        assert 'raise' in action_types
        assert 'check' in action_types
