"""Table and player management for Texas Hold'em."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from .poker import Card, Deck
from .hand_evaluator import HandEvaluator


class GamePhase(Enum):
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    WAITING_RUN_TWICE = "waiting_run_twice"  # Waiting for run-it-twice choices


class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class Action:
    player_name: str
    action_type: ActionType
    amount: int = 0
    phase: str = ""

    def to_dict(self) -> dict:
        return {
            'player': self.player_name,
            'action': self.action_type.value,
            'amount': self.amount,
            'phase': self.phase
        }


@dataclass
class Player:
    name: str
    seat: int
    stack: int = 0
    hole_cards: List[Card] = field(default_factory=list)
    current_bet: int = 0  # Bet in current betting round
    total_bet: int = 0    # Total bet in current hand (for side pots)
    is_folded: bool = False
    is_all_in: bool = False
    is_sitting_out: bool = False

    def reset_for_hand(self):
        self.hole_cards = []
        self.current_bet = 0
        self.total_bet = 0
        self.is_folded = False
        self.is_all_in = False

    def to_dict(self, show_cards: bool = False) -> dict:
        data = {
            'name': self.name,
            'seat': self.seat,
            'stack': self.stack,
            'current_bet': self.current_bet,
            'total_bet': self.total_bet,
            'is_folded': self.is_folded,
            'is_all_in': self.is_all_in,
            'is_sitting_out': self.is_sitting_out,
            'has_cards': len(self.hole_cards) > 0
        }
        if show_cards and self.hole_cards:
            data['hole_cards'] = [c.to_dict() for c in self.hole_cards]
        return data


@dataclass
class Pot:
    """Represents a pot (main or side) with eligible players."""
    amount: int = 0
    eligible_players: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'amount': self.amount,
            'eligible_players': self.eligible_players
        }


class Table:
    def __init__(self, room_id: str, small_blind: int = 1, big_blind: int = 2,
                 min_buy_in: int = 40, max_buy_in: int = 200):
        self.room_id = room_id
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.min_buy_in = min_buy_in
        self.max_buy_in = max_buy_in

        self.players: Dict[int, Player] = {}  # seat -> Player
        self.deck = Deck()
        self.community_cards: List[Card] = []
        self.pots: List[Pot] = []  # Main pot + side pots

        self.phase = GamePhase.WAITING
        self.dealer_seat: Optional[int] = None
        self.current_player_seat: Optional[int] = None
        self.last_aggressor_seat: Optional[int] = None  # Last player who bet/raised
        self.current_bet = 0
        self.last_raise_amount = 0  # Track the last raise increment for min-raise rule

        self.hand_number = 0
        self.action_history: List[Action] = []
        self._last_hand_result: Optional[dict] = None
        self._bb_has_option: bool = False  # Track if BB still has option to raise preflop

        # Run it twice state
        self._run_twice_eligible: bool = False
        self._run_twice_choices: Dict[str, bool] = {}  # player_name -> wants_twice
        self._run_twice_players: List[str] = []  # All-in players who can choose
        self._saved_deck_state: Optional[List[Card]] = None  # Save deck for second run
        self._saved_community_cards: List[Card] = []  # Cards dealt before run-twice

    @property
    def pot(self) -> int:
        """Total pot amount (all pots combined)."""
        return sum(p.amount for p in self.pots)

    def add_player(self, name: str, stack: int, seat: Optional[int] = None) -> Optional[Player]:
        """Add a player to the table."""
        if len(self.players) >= 9:
            return None

        # Validate stack
        stack = max(self.min_buy_in, min(stack, self.max_buy_in))

        # Find available seat
        if seat is None:
            for s in range(9):
                if s not in self.players:
                    seat = s
                    break
        elif seat in self.players:
            return None

        if seat is None:
            return None

        player = Player(name=name, seat=seat, stack=stack)
        self.players[seat] = player
        return player

    def remove_player(self, name: str) -> bool:
        """Remove a player from the table."""
        for seat, player in list(self.players.items()):
            if player.name == name:
                del self.players[seat]
                return True
        return False

    def get_player_by_name(self, name: str) -> Optional[Player]:
        """Get player by name."""
        for player in self.players.values():
            if player.name == name:
                return player
        return None

    def get_active_players(self) -> List[Player]:
        """Get players who can participate in a new hand (have chips, not sitting out)."""
        return [p for p in self.players.values()
                if not p.is_sitting_out and p.stack > 0]

    def get_players_in_hand(self) -> List[Player]:
        """Get players still in the current hand (not folded)."""
        return [p for p in self.players.values()
                if not p.is_folded and not p.is_sitting_out and len(p.hole_cards) > 0]

    def get_players_who_contributed(self) -> List[Player]:
        """Get all players who contributed to the pot (including folded players)."""
        return [p for p in self.players.values()
                if p.total_bet > 0 or len(p.hole_cards) > 0]

    def _get_seats_in_order(self) -> List[int]:
        """Get all occupied seats in clockwise order starting from seat 0."""
        return sorted(self.players.keys())

    def _get_next_seat(self, current_seat: int, skip_folded: bool = True,
                       skip_all_in: bool = False, skip_sitting_out: bool = True) -> Optional[int]:
        """Get the next occupied seat after current_seat in clockwise order."""
        seats = self._get_seats_in_order()
        if not seats:
            return None

        # Find index of current seat or the next one
        current_idx = -1
        for i, s in enumerate(seats):
            if s == current_seat:
                current_idx = i
                break
            elif s > current_seat and current_idx == -1:
                current_idx = i - 1
                break

        if current_idx == -1:
            current_idx = len(seats) - 1

        # Search for next valid seat
        for i in range(1, len(seats) + 1):
            seat = seats[(current_idx + i) % len(seats)]
            player = self.players[seat]
            if skip_sitting_out and player.is_sitting_out:
                continue
            if skip_folded and player.is_folded:
                continue
            if skip_all_in and player.is_all_in:
                continue
            if seat != current_seat:
                return seat
        return None

    def _is_heads_up(self) -> bool:
        """Check if this is a heads-up (2 player) game."""
        return len(self.get_active_players()) == 2

    def _get_sb_seat(self) -> int:
        """Get small blind seat.

        Heads-up: Button is small blind.
        3+ players: First player left of button.
        """
        if self._is_heads_up():
            return self.dealer_seat
        return self._get_next_seat(self.dealer_seat, skip_folded=False, skip_all_in=False)

    def _get_bb_seat(self) -> int:
        """Get big blind seat.

        Always the first player left of small blind.
        """
        sb_seat = self._get_sb_seat()
        return self._get_next_seat(sb_seat, skip_folded=False, skip_all_in=False)

    def start_hand(self) -> bool:
        """Start a new hand."""
        active = self.get_active_players()
        if len(active) < 2:
            return False

        # Reset for new hand
        self.hand_number += 1
        self.deck.reset()
        self.community_cards = []
        self.pots = [Pot()]  # Start with empty main pot
        self.action_history = []
        self.current_bet = 0
        self.last_raise_amount = self.big_blind  # Initial min-raise is big blind
        self.last_aggressor_seat = None
        self._last_hand_result = None

        for player in self.players.values():
            player.reset_for_hand()

        # Move dealer button
        if self.dealer_seat is None:
            self.dealer_seat = active[0].seat
        else:
            next_dealer = self._get_next_seat(self.dealer_seat, skip_folded=False, skip_all_in=False)
            if next_dealer is not None:
                self.dealer_seat = next_dealer

        # Post blinds
        self._post_blinds()

        # Deal hole cards to active players
        for player in self.get_active_players():
            player.hole_cards = self.deck.deal(2)

        self.phase = GamePhase.PREFLOP

        # Set first player to act preflop
        self._set_first_to_act_preflop()

        return True

    def _post_blinds(self):
        """Post small and big blinds."""
        sb_seat = self._get_sb_seat()
        bb_seat = self._get_bb_seat()

        sb_player = self.players.get(sb_seat)
        bb_player = self.players.get(bb_seat)

        # Post small blind
        if sb_player:
            sb_amount = min(self.small_blind, sb_player.stack)
            sb_player.stack -= sb_amount
            sb_player.current_bet = sb_amount
            sb_player.total_bet = sb_amount
            self.pots[0].amount += sb_amount
            if sb_player.stack == 0:
                sb_player.is_all_in = True

        # Post big blind
        if bb_player:
            bb_amount = min(self.big_blind, bb_player.stack)
            bb_player.stack -= bb_amount
            bb_player.current_bet = bb_amount
            bb_player.total_bet = bb_amount
            self.pots[0].amount += bb_amount
            self.current_bet = bb_amount
            if bb_player.stack == 0:
                bb_player.is_all_in = True

        # Big blind has option to raise even if everyone just calls
        self._bb_has_option = True
        # Initially no aggressor (blinds don't count as aggression)
        self.last_aggressor_seat = None

    def _set_first_to_act_preflop(self):
        """Set the first player to act preflop.

        Heads-up: Small blind (button) acts first.
        3+ players: First player left of big blind (UTG).
        """
        if self._is_heads_up():
            # Heads-up: SB (button) acts first preflop
            self.current_player_seat = self._get_sb_seat()
            # Skip if all-in from blind
            if self.players[self.current_player_seat].is_all_in:
                self.current_player_seat = self._get_next_seat(
                    self.current_player_seat, skip_all_in=True
                )
        else:
            # 3+ players: UTG (left of BB) acts first
            bb_seat = self._get_bb_seat()
            self.current_player_seat = self._get_next_seat(bb_seat, skip_all_in=True)

    def _set_first_to_act_postflop(self):
        """Set the first player to act postflop.

        Heads-up: Big blind acts first.
        3+ players: First active player left of button.
        """
        if self._is_heads_up():
            # Heads-up: BB acts first postflop
            bb_seat = self._get_bb_seat()
            if not self.players[bb_seat].is_folded and not self.players[bb_seat].is_all_in:
                self.current_player_seat = bb_seat
            else:
                self.current_player_seat = self._get_next_seat(
                    self.dealer_seat, skip_all_in=True
                )
        else:
            # 3+ players: First active player left of button
            self.current_player_seat = self._get_next_seat(
                self.dealer_seat, skip_all_in=True
            )

        self.last_aggressor_seat = self.current_player_seat

    def process_action(self, player_name: str, action_type: str, amount: int = 0) -> dict:
        """Process a player's action."""
        player = self.get_player_by_name(player_name)
        if not player:
            return {'success': False, 'error': 'Player not found'}

        if player.seat != self.current_player_seat:
            return {'success': False, 'error': 'Not your turn'}

        if player.is_folded or player.is_all_in:
            return {'success': False, 'error': 'Cannot act'}

        # Clear BB option when BB acts in preflop
        if self.phase == GamePhase.PREFLOP and self._bb_has_option:
            bb_seat = self._get_bb_seat()
            if player.seat == bb_seat:
                self._bb_has_option = False

        action = ActionType(action_type)
        result = {'success': True}
        action_amount = 0

        if action == ActionType.FOLD:
            player.is_folded = True

        elif action == ActionType.CHECK:
            if player.current_bet < self.current_bet:
                return {'success': False, 'error': 'Cannot check, must call or raise'}

        elif action == ActionType.CALL:
            call_amount = min(self.current_bet - player.current_bet, player.stack)
            player.stack -= call_amount
            player.current_bet += call_amount
            player.total_bet += call_amount
            self.pots[0].amount += call_amount
            action_amount = call_amount
            if player.stack == 0:
                player.is_all_in = True
                action = ActionType.ALL_IN

        elif action == ActionType.RAISE:
            raise_to = amount
            raise_increment = raise_to - self.current_bet

            # Validate minimum raise (must be at least the last raise amount)
            # Exception: if player doesn't have enough for min-raise, they can still all-in
            min_raise_to = self.current_bet + self.last_raise_amount
            chips_needed = raise_to - player.current_bet

            if raise_increment < self.last_raise_amount and player.stack > chips_needed:
                return {'success': False, 'error': f'Minimum raise to {min_raise_to}'}

            if chips_needed >= player.stack:
                # All-in for less than min-raise is allowed
                chips_needed = player.stack
                raise_to = player.current_bet + chips_needed
                raise_increment = raise_to - self.current_bet
                player.is_all_in = True
                action = ActionType.ALL_IN

            player.stack -= chips_needed
            player.current_bet += chips_needed
            player.total_bet += chips_needed
            self.pots[0].amount += chips_needed
            action_amount = raise_to

            # Update betting state
            if raise_to > self.current_bet:
                if raise_increment >= self.last_raise_amount:
                    self.last_raise_amount = raise_increment
                self.current_bet = raise_to
                self.last_aggressor_seat = player.seat

        elif action == ActionType.ALL_IN:
            all_in_amount = player.stack
            player.current_bet += all_in_amount
            player.total_bet += all_in_amount
            self.pots[0].amount += all_in_amount
            player.stack = 0
            player.is_all_in = True
            action_amount = player.current_bet

            if player.current_bet > self.current_bet:
                raise_increment = player.current_bet - self.current_bet
                if raise_increment >= self.last_raise_amount:
                    self.last_raise_amount = raise_increment
                    self.last_aggressor_seat = player.seat
                self.current_bet = player.current_bet

        # Record action
        self.action_history.append(Action(
            player_name=player_name,
            action_type=action,
            amount=action_amount,
            phase=self.phase.value
        ))

        # Advance to next player or phase
        self._advance_game()

        return result

    def _advance_game(self):
        """Advance the game to next player or phase."""
        players_in_hand = self.get_players_in_hand()

        # Check if hand is over (only one player left)
        if len(players_in_hand) <= 1:
            self._calculate_side_pots()
            self._end_hand_single_winner()
            return

        # Check if betting round is complete
        active_players = [p for p in players_in_hand if not p.is_all_in]

        # Find next player to act
        next_seat = self._get_next_seat(self.current_player_seat, skip_all_in=True)

        # Check if all remaining players have matched the bet or are all-in
        all_bets_matched = all(
            p.current_bet == self.current_bet or p.is_all_in
            for p in players_in_hand
        )

        if len(active_players) <= 1 and all_bets_matched:
            # Everyone is all-in or folded except maybe one, and bets are settled
            # Calculate side pots and run out the board
            self._calculate_side_pots()
            self._run_out_board()
            return

        if len(active_players) == 0:
            # Everyone is all-in, run out the board
            self._calculate_side_pots()
            self._run_out_board()
            return

        # Check if betting round is complete
        if self._is_betting_round_complete(next_seat):
            self._calculate_side_pots()
            self._next_phase()
        else:
            self.current_player_seat = next_seat

    def _is_betting_round_complete(self, next_seat: Optional[int]) -> bool:
        """Check if the current betting round is complete."""
        if next_seat is None:
            return True

        players_in_hand = self.get_players_in_hand()

        # All active players must have matched the current bet
        all_matched = all(
            p.current_bet == self.current_bet or p.is_all_in
            for p in players_in_hand
        )

        if not all_matched:
            return False

        # In preflop, BB must have option to act even if everyone just called
        if self.phase == GamePhase.PREFLOP and self._bb_has_option:
            bb_seat = self._get_bb_seat()
            bb_player = self.players.get(bb_seat)
            if bb_player and not bb_player.is_folded and not bb_player.is_all_in:
                # BB still has option, don't end round until BB acts
                return False

        # If there's a last aggressor, round ends when action returns to them
        if self.last_aggressor_seat is not None:
            return next_seat == self.last_aggressor_seat

        # No aggressor (everyone checked/called) - round complete when everyone has matched
        return True

    def _calculate_side_pots(self):
        """Calculate main pot and side pots based on all-in amounts.

        Important: Pot amounts include contributions from ALL players (including folded),
        but only non-folded players are eligible to win.
        """
        # Get ALL players who contributed (including folded)
        all_contributors = self.get_players_who_contributed()
        players_in_hand = self.get_players_in_hand()  # Non-folded only, for eligibility

        if not all_contributors:
            return

        # Collect all unique bet amounts from players who went all-in (and are not folded)
        # We use non-folded all-in players to determine pot levels
        all_in_amounts = sorted(set(
            p.total_bet for p in all_contributors if p.is_all_in and not p.is_folded
        ))

        if not all_in_amounts:
            # No side pots needed, just set eligible players for main pot
            total = sum(p.total_bet for p in all_contributors)
            self.pots = [Pot(
                amount=total,
                eligible_players=[p.name for p in players_in_hand]
            )]
            return

        # Calculate pots - include ALL contributors for amounts, but only non-folded for eligibility
        new_pots = []
        prev_level = 0

        for level in all_in_amounts:
            pot_amount = 0
            eligible = []

            for p in all_contributors:
                if p.total_bet >= level:
                    # Player contributed at least up to this level
                    contribution = level - prev_level
                    pot_amount += contribution
                    # Only non-folded players are eligible to win
                    if not p.is_folded:
                        eligible.append(p.name)
                elif p.total_bet > prev_level:
                    # Player contributed partially to this level
                    contribution = p.total_bet - prev_level
                    pot_amount += contribution
                    # Folded players still don't get added to eligible

            if pot_amount > 0:
                new_pots.append(Pot(amount=pot_amount, eligible_players=eligible))

            prev_level = level

        # Add remaining contributions (from players who bet more than highest all-in)
        max_all_in = all_in_amounts[-1] if all_in_amounts else 0
        final_pot_amount = 0
        eligible = []

        for p in all_contributors:
            if p.total_bet > max_all_in:
                contribution = p.total_bet - max_all_in
                final_pot_amount += contribution
                if not p.is_folded:
                    eligible.append(p.name)

        if final_pot_amount > 0:
            new_pots.append(Pot(amount=final_pot_amount, eligible_players=eligible))

        # If no pots were created, create a single pot
        if not new_pots:
            total = sum(p.total_bet for p in all_contributors)
            new_pots = [Pot(
                amount=total,
                eligible_players=[p.name for p in players_in_hand]
            )]

        self.pots = new_pots

    def _next_phase(self):
        """Move to next betting phase."""
        # Reset for new betting round
        for player in self.players.values():
            player.current_bet = 0
        self.current_bet = 0
        self.last_raise_amount = self.big_blind  # Reset min-raise
        self.last_aggressor_seat = None  # Reset aggressor for new round
        self._bb_has_option = False  # BB option only applies to preflop

        if self.phase == GamePhase.PREFLOP:
            self.community_cards.extend(self.deck.deal(3))
            self.phase = GamePhase.FLOP
        elif self.phase == GamePhase.FLOP:
            self.community_cards.extend(self.deck.deal(1))
            self.phase = GamePhase.TURN
        elif self.phase == GamePhase.TURN:
            self.community_cards.extend(self.deck.deal(1))
            self.phase = GamePhase.RIVER
        elif self.phase == GamePhase.RIVER:
            self._showdown()
            return

        # Set first player to act postflop
        self._set_first_to_act_postflop()

        # If only one player can act, go to showdown
        active_players = [p for p in self.get_players_in_hand() if not p.is_all_in]
        if len(active_players) <= 1:
            self._run_out_board()

    def _run_out_board(self):
        """Deal remaining community cards when no more betting possible."""
        # Check if run-it-twice is eligible (2+ players all-in)
        all_in_players = [p for p in self.get_players_in_hand() if p.is_all_in]

        if len(all_in_players) >= 2 and len(self.community_cards) < 5:
            # Save state for potential run-twice
            self._run_twice_eligible = True
            self._run_twice_choices = {}
            self._run_twice_players = [p.name for p in all_in_players]
            self._saved_community_cards = self.community_cards.copy()
            self._saved_deck_state = self.deck.cards.copy()  # Save deck state

            # Enter waiting for run-twice choices
            self.phase = GamePhase.WAITING_RUN_TWICE
            return

        self._deal_remaining_and_showdown()

    def _deal_remaining_and_showdown(self, is_second_run: bool = False):
        """Deal remaining cards and go to showdown."""
        while len(self.community_cards) < 5:
            if len(self.community_cards) == 0:
                self.community_cards.extend(self.deck.deal(3))
                self.phase = GamePhase.FLOP
            else:
                self.community_cards.extend(self.deck.deal(1))
                if len(self.community_cards) == 4:
                    self.phase = GamePhase.TURN
                elif len(self.community_cards) == 5:
                    self.phase = GamePhase.RIVER

        if is_second_run:
            self._showdown_second_run()
        else:
            self._showdown()

    def process_run_twice_choice(self, player_name: str, wants_twice: bool) -> dict:
        """Process a player's run-it-twice choice."""
        if self.phase != GamePhase.WAITING_RUN_TWICE:
            return {'success': False, 'error': 'Not waiting for run-twice choice'}

        if player_name not in self._run_twice_players:
            return {'success': False, 'error': 'You are not eligible for run-twice choice'}

        if player_name in self._run_twice_choices:
            return {'success': False, 'error': 'You already made your choice'}

        self._run_twice_choices[player_name] = wants_twice

        # Check if all players have chosen
        if len(self._run_twice_choices) == len(self._run_twice_players):
            self._execute_run_twice_decision()

        return {'success': True, 'waiting': len(self._run_twice_choices) < len(self._run_twice_players)}

    def _execute_run_twice_decision(self):
        """Execute the run-twice decision after all players have chosen."""
        # If anyone chose "once", run once. Otherwise run twice.
        run_twice = all(self._run_twice_choices.values())

        if run_twice:
            self._run_it_twice()
        else:
            # Run once - continue with normal showdown
            self._run_twice_eligible = False
            self._deal_remaining_and_showdown()

    def _run_it_twice(self):
        """Run the board twice and split pot based on results."""
        players_in_hand = self.get_players_in_hand()

        # First run - use current deck state
        self._deal_remaining_and_showdown(is_second_run=False)

        # Store first run results (winners are already determined in showdown)
        first_run_winners = set(self._last_hand_result.get('winners', []))
        first_community = self.community_cards.copy()

        # Second run - restore deck and deal new cards
        self.deck.cards = self._saved_deck_state.copy()
        self.community_cards = self._saved_community_cards.copy()

        # Shuffle remaining deck for second run
        import random
        remaining_cards = self.deck.cards
        random.shuffle(remaining_cards)
        self.deck.cards = remaining_cards

        # Deal second run
        second_community = self._saved_community_cards.copy()
        while len(second_community) < 5:
            second_community.extend(self.deck.deal(1))

        # Evaluate second run
        second_winners = self._evaluate_hands_for_community(players_in_hand, second_community)

        # Determine final pot distribution
        self._distribute_run_twice_pots(first_run_winners, second_winners, first_community, second_community)

    def _evaluate_hands_for_community(self, players: List[Player], community: List[Card]) -> set:
        """Evaluate hands for given community cards and return winner names."""
        hand_results = []
        for player in players:
            if player.is_folded:
                continue
            best_cards, rank, tiebreakers, desc = HandEvaluator.best_hand(
                player.hole_cards, community
            )
            hand_results.append({
                'player': player,
                'rank': rank,
                'tiebreakers': tiebreakers
            })

        if not hand_results:
            return set()

        # Find best hand
        hand_results.sort(key=lambda x: (x['rank'], x['tiebreakers']), reverse=True)
        best = (hand_results[0]['rank'], hand_results[0]['tiebreakers'])
        winners = {
            r['player'].name for r in hand_results
            if (r['rank'], r['tiebreakers']) == best
        }
        return winners

    def _distribute_run_twice_pots(self, first_winners: set, second_winners: set,
                                    first_community: List[Card], second_community: List[Card]):
        """Distribute pots based on run-twice results."""
        players_in_hand = self.get_players_in_hand()

        if first_winners == second_winners:
            # Same winner(s) both times - they get full pot
            all_winners = first_winners
            for pot in self.pots:
                if pot.amount == 0:
                    continue
                eligible_winners = [p for p in players_in_hand
                                   if p.name in pot.eligible_players and p.name in all_winners]
                if eligible_winners:
                    share = pot.amount // len(eligible_winners)
                    remainder = pot.amount % len(eligible_winners)
                    for i, winner in enumerate(eligible_winners):
                        winner.stack += share + (1 if i < remainder else 0)
        else:
            # Different winners - split each pot 50/50
            for pot in self.pots:
                if pot.amount == 0:
                    continue

                first_half = pot.amount // 2
                second_half = pot.amount - first_half

                # First half to first run winners
                first_eligible = [p for p in players_in_hand
                                 if p.name in pot.eligible_players and p.name in first_winners]
                if first_eligible:
                    share = first_half // len(first_eligible)
                    remainder = first_half % len(first_eligible)
                    for i, winner in enumerate(first_eligible):
                        winner.stack += share + (1 if i < remainder else 0)

                # Second half to second run winners
                second_eligible = [p for p in players_in_hand
                                  if p.name in pot.eligible_players and p.name in second_winners]
                if second_eligible:
                    share = second_half // len(second_eligible)
                    remainder = second_half % len(second_eligible)
                    for i, winner in enumerate(second_eligible):
                        winner.stack += share + (1 if i < remainder else 0)

        # End hand
        self._last_hand_result = {
            'winners': list(first_winners | second_winners),
            'pot': sum(p.amount for p in self.pots),
            'run_twice': True,
            'first_run': {
                'winners': list(first_winners),
                'community': [c.to_dict() for c in first_community]
            },
            'second_run': {
                'winners': list(second_winners),
                'community': [c.to_dict() for c in second_community]
            }
        }
        self.phase = GamePhase.WAITING
        self.current_player_seat = None
        self._run_twice_eligible = False

    def _showdown_second_run(self):
        """Placeholder - actual second run handling is in _run_it_twice."""
        pass

    def _end_hand_single_winner(self):
        """End hand when only one player remains (others folded)."""
        players_in_hand = self.get_players_in_hand()
        if len(players_in_hand) == 1:
            winner = players_in_hand[0]
            total_won = sum(p.amount for p in self.pots)
            winner.stack += total_won
            self._end_hand([winner.name])
        else:
            # Shouldn't happen, but handle gracefully
            self._showdown()

    def _showdown(self):
        """Determine winner(s) and distribute pots."""
        self.phase = GamePhase.SHOWDOWN
        self.current_player_seat = None

        players_in_hand = self.get_players_in_hand()

        if len(players_in_hand) == 1:
            # Only one player left
            winner = players_in_hand[0]
            total_won = sum(p.amount for p in self.pots)
            winner.stack += total_won
            self._end_hand([winner.name])
            return

        # Evaluate all hands
        hand_results = []
        for player in players_in_hand:
            best_cards, rank, tiebreakers, desc = HandEvaluator.best_hand(
                player.hole_cards, self.community_cards
            )
            hand_results.append({
                'player': player,
                'rank': rank,
                'tiebreakers': tiebreakers,
                'description': desc,
                'best_cards': best_cards
            })

        # Distribute each pot
        all_winners = set()
        for pot in self.pots:
            if pot.amount == 0:
                continue

            # Find eligible players for this pot
            eligible_results = [
                r for r in hand_results
                if r['player'].name in pot.eligible_players
            ]

            if not eligible_results:
                continue

            # Find best hand among eligible players
            eligible_results.sort(
                key=lambda x: (x['rank'], x['tiebreakers']),
                reverse=True
            )
            best = (eligible_results[0]['rank'], eligible_results[0]['tiebreakers'])
            pot_winners = [
                r['player'] for r in eligible_results
                if (r['rank'], r['tiebreakers']) == best
            ]

            # Distribute pot among winners
            share = pot.amount // len(pot_winners)
            remainder = pot.amount % len(pot_winners)
            for i, winner in enumerate(pot_winners):
                winner.stack += share + (1 if i < remainder else 0)
                all_winners.add(winner.name)

        self._end_hand(list(all_winners), hand_results)

    def _end_hand(self, winners: List[str] = None, hand_results: List[dict] = None):
        """End the current hand."""
        self.phase = GamePhase.WAITING
        self.current_player_seat = None

        # Calculate total pot for result
        total_pot = sum(p.amount for p in self.pots)

        # Store results for history, including updated player stacks
        self._last_hand_result = {
            'winners': winners or [],
            'pot': total_pot,
            'pots': [p.to_dict() for p in self.pots],
            'player_stacks': {p.name: p.stack for p in self.players.values()},
            'hand_results': [
                {
                    'player_name': r['player'].name,
                    'rank': r['rank'],
                    'description': r['description'],
                    'best_cards': [c.to_dict() for c in r['best_cards']]
                }
                for r in (hand_results or [])
            ] if hand_results else None
        }

    def get_valid_actions(self, player_name: str) -> List[dict]:
        """Get valid actions for a player."""
        player = self.get_player_by_name(player_name)
        if not player or player.seat != self.current_player_seat:
            return []

        if player.is_folded or player.is_all_in:
            return []

        actions = []
        to_call = self.current_bet - player.current_bet

        # Fold is always valid
        actions.append({'action': 'fold'})

        if to_call == 0:
            actions.append({'action': 'check'})
        else:
            # Call (or all-in if not enough chips)
            call_amount = min(to_call, player.stack)
            actions.append({'action': 'call', 'amount': call_amount})

        # Raise (if player has chips beyond calling)
        if player.stack > to_call:
            min_raise_to = self.current_bet + self.last_raise_amount
            max_raise_to = player.current_bet + player.stack

            # If min raise is more than player can afford, they can still all-in
            if min_raise_to > max_raise_to:
                min_raise_to = max_raise_to

            actions.append({
                'action': 'raise',
                'min': min_raise_to,
                'max': max_raise_to
            })

        # All-in
        if player.stack > 0:
            actions.append({'action': 'all_in', 'amount': player.stack})

        return actions

    def get_position_name(self, seat: int) -> str:
        """Get the position name for a seat.

        Position names:
        - BTN: Button (Dealer)
        - SB: Small Blind
        - BB: Big Blind
        - UTG: Under the Gun (first to act preflop)
        - UTG+1: Second under the gun
        - MP: Middle Position
        - MP+1: Middle Position +1
        - HJ: Hijack (2 seats before button)
        - CO: Cutoff (1 seat before button)
        """
        if self.dealer_seat is None:
            return ""

        active_seats = sorted([
            s for s, p in self.players.items()
            if not p.is_sitting_out
        ])

        if not active_seats or seat not in active_seats:
            return ""

        num_players = len(active_seats)
        if num_players < 2:
            return ""

        # Find dealer index in active seats
        dealer_idx = active_seats.index(self.dealer_seat) if self.dealer_seat in active_seats else 0
        seat_idx = active_seats.index(seat)

        # Calculate position relative to dealer (0 = dealer, 1 = SB, 2 = BB, etc.)
        relative_pos = (seat_idx - dealer_idx) % num_players

        # Heads-up special case
        if num_players == 2:
            if relative_pos == 0:
                return "BTN"  # Button is also SB in heads-up
            else:
                return "BB"

        # 3+ players
        if relative_pos == 0:
            return "BTN"
        elif relative_pos == 1:
            return "SB"
        elif relative_pos == 2:
            return "BB"

        # Positions after BB (counting from BB as position 0)
        pos_after_bb = relative_pos - 2
        positions_after_bb = num_players - 3  # Exclude BTN, SB, BB

        if positions_after_bb <= 0:
            return ""

        # For different table sizes, assign position names
        # Last position before BTN is CO, before that is HJ
        if pos_after_bb == positions_after_bb:
            return "CO"  # Cutoff (last before button)

        if positions_after_bb >= 2 and pos_after_bb == positions_after_bb - 1:
            return "HJ"  # Hijack (2nd last before button)

        # UTG positions (first positions after BB)
        if pos_after_bb == 1:
            return "UTG"
        elif pos_after_bb == 2 and positions_after_bb >= 4:
            return "UTG+1"

        # Middle positions
        if positions_after_bb >= 5 and pos_after_bb == 3:
            return "MP"
        if positions_after_bb >= 6 and pos_after_bb == 4:
            return "MP+1"

        # Fallback for edge cases
        return f"MP"

    def get_game_state(self, for_player: str = None) -> dict:
        """Get the current game state."""
        players_data = []
        for seat in sorted(self.players.keys()):
            player = self.players[seat]
            show_cards = (
                self.phase == GamePhase.SHOWDOWN or
                (for_player and player.name == for_player)
            )
            player_dict = player.to_dict(show_cards=show_cards)
            player_dict['position'] = self.get_position_name(seat)
            players_data.append(player_dict)

        state = {
            'room_id': self.room_id,
            'phase': self.phase.value,
            'hand_number': self.hand_number,
            'pot': self.pot,
            'pots': [p.to_dict() for p in self.pots],
            'community_cards': [c.to_dict() for c in self.community_cards],
            'players': players_data,
            'dealer_seat': self.dealer_seat,
            'current_player_seat': self.current_player_seat,
            'current_bet': self.current_bet,
            'last_raise_amount': self.last_raise_amount,
            'small_blind': self.small_blind,
            'big_blind': self.big_blind,
            'min_buy_in': self.min_buy_in,
            'max_buy_in': self.max_buy_in
        }

        if for_player:
            state['valid_actions'] = self.get_valid_actions(for_player)

        if self._last_hand_result and self.phase == GamePhase.WAITING:
            state['last_hand_result'] = self._last_hand_result

        return state

    def get_action_history(self) -> List[dict]:
        """Get the action history for current hand."""
        return [a.to_dict() for a in self.action_history]

    def serialize(self) -> dict:
        """Serialize table state to dict for persistence."""
        return {
            'room_id': self.room_id,
            'small_blind': self.small_blind,
            'big_blind': self.big_blind,
            'min_buy_in': self.min_buy_in,
            'max_buy_in': self.max_buy_in,
            'phase': self.phase.value,
            'dealer_seat': self.dealer_seat,
            'current_player_seat': self.current_player_seat,
            'last_aggressor_seat': self.last_aggressor_seat,
            'current_bet': self.current_bet,
            'last_raise_amount': self.last_raise_amount,
            'hand_number': self.hand_number,
            '_bb_has_option': self._bb_has_option,
            'community_cards': [c.to_dict() for c in self.community_cards],
            'pots': [{'amount': p.amount, 'eligible_players': p.eligible_players} for p in self.pots],
            'players': {
                str(seat): {
                    'name': p.name,
                    'seat': p.seat,
                    'stack': p.stack,
                    'current_bet': p.current_bet,
                    'total_bet': p.total_bet,
                    'is_folded': p.is_folded,
                    'is_all_in': p.is_all_in,
                    'is_sitting_out': p.is_sitting_out,
                    'hole_cards': [c.to_dict() for c in p.hole_cards]
                }
                for seat, p in self.players.items()
            },
            'action_history': [a.to_dict() for a in self.action_history],
            '_last_hand_result': self._last_hand_result
        }

    @classmethod
    def deserialize(cls, data: dict) -> 'Table':
        """Deserialize table state from dict."""
        table = cls(
            room_id=data['room_id'],
            small_blind=data['small_blind'],
            big_blind=data['big_blind'],
            min_buy_in=data['min_buy_in'],
            max_buy_in=data['max_buy_in']
        )

        table.phase = GamePhase(data['phase'])
        table.dealer_seat = data['dealer_seat']
        table.current_player_seat = data['current_player_seat']
        table.last_aggressor_seat = data['last_aggressor_seat']
        table.current_bet = data['current_bet']
        table.last_raise_amount = data['last_raise_amount']
        table.hand_number = data['hand_number']
        table._bb_has_option = data.get('_bb_has_option', False)
        table._last_hand_result = data.get('_last_hand_result')

        # Restore community cards
        table.community_cards = [
            Card(c['suit'], c['rank']) for c in data.get('community_cards', [])
        ]

        # Restore pots
        table.pots = [
            Pot(amount=p['amount'], eligible_players=p['eligible_players'])
            for p in data.get('pots', [{'amount': 0, 'eligible_players': []}])
        ]

        # Restore players
        for seat_str, pdata in data.get('players', {}).items():
            seat = int(seat_str)
            player = Player(
                name=pdata['name'],
                seat=pdata['seat'],
                stack=pdata['stack']
            )
            player.current_bet = pdata['current_bet']
            player.total_bet = pdata['total_bet']
            player.is_folded = pdata['is_folded']
            player.is_all_in = pdata['is_all_in']
            player.is_sitting_out = pdata['is_sitting_out']
            player.hole_cards = [
                Card(c['suit'], c['rank']) for c in pdata.get('hole_cards', [])
            ]
            table.players[seat] = player

        # Restore action history
        table.action_history = [
            Action(
                player_name=a['player'],
                action_type=ActionType(a['action']),
                amount=a['amount'],
                phase=a['phase']
            )
            for a in data.get('action_history', [])
        ]

        return table
