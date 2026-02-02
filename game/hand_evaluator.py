"""Hand evaluation for Texas Hold'em poker."""

from collections import Counter
from itertools import combinations
from typing import List, Tuple
from .poker import Card


class HandRank:
    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10

    NAMES = {
        1: "High Card",
        2: "Pair",
        3: "Two Pair",
        4: "Three of a Kind",
        5: "Straight",
        6: "Flush",
        7: "Full House",
        8: "Four of a Kind",
        9: "Straight Flush",
        10: "Royal Flush"
    }


class HandEvaluator:
    """Evaluates poker hands and determines winners."""

    @staticmethod
    def evaluate(cards: List[Card]) -> Tuple[int, List[int], str]:
        """
        Evaluate a 5-card hand.
        Returns: (rank, tiebreakers, description)
        """
        if len(cards) != 5:
            raise ValueError("Hand must contain exactly 5 cards")

        values = sorted([c.value for c in cards], reverse=True)
        suits = [c.suit for c in cards]
        value_counts = Counter(values)

        is_flush = len(set(suits)) == 1
        is_straight, straight_high = HandEvaluator._check_straight(values)

        # Check for straight flush / royal flush
        if is_flush and is_straight:
            if straight_high == 14:
                return (HandRank.ROYAL_FLUSH, [14], "Royal Flush")
            return (HandRank.STRAIGHT_FLUSH, [straight_high], f"Straight Flush, {HandEvaluator._value_name(straight_high)} high")

        # Four of a kind
        if 4 in value_counts.values():
            quad = [v for v, c in value_counts.items() if c == 4][0]
            kicker = [v for v, c in value_counts.items() if c == 1][0]
            return (HandRank.FOUR_OF_A_KIND, [quad, kicker], f"Four of a Kind, {HandEvaluator._value_name(quad)}s")

        # Full house
        if 3 in value_counts.values() and 2 in value_counts.values():
            trips = [v for v, c in value_counts.items() if c == 3][0]
            pair = [v for v, c in value_counts.items() if c == 2][0]
            return (HandRank.FULL_HOUSE, [trips, pair], f"Full House, {HandEvaluator._value_name(trips)}s full of {HandEvaluator._value_name(pair)}s")

        # Flush
        if is_flush:
            return (HandRank.FLUSH, values, f"Flush, {HandEvaluator._value_name(values[0])} high")

        # Straight
        if is_straight:
            return (HandRank.STRAIGHT, [straight_high], f"Straight, {HandEvaluator._value_name(straight_high)} high")

        # Three of a kind
        if 3 in value_counts.values():
            trips = [v for v, c in value_counts.items() if c == 3][0]
            kickers = sorted([v for v, c in value_counts.items() if c == 1], reverse=True)
            return (HandRank.THREE_OF_A_KIND, [trips] + kickers, f"Three of a Kind, {HandEvaluator._value_name(trips)}s")

        # Two pair
        if list(value_counts.values()).count(2) == 2:
            pairs = sorted([v for v, c in value_counts.items() if c == 2], reverse=True)
            kicker = [v for v, c in value_counts.items() if c == 1][0]
            return (HandRank.TWO_PAIR, pairs + [kicker], f"Two Pair, {HandEvaluator._value_name(pairs[0])}s and {HandEvaluator._value_name(pairs[1])}s")

        # One pair
        if 2 in value_counts.values():
            pair = [v for v, c in value_counts.items() if c == 2][0]
            kickers = sorted([v for v, c in value_counts.items() if c == 1], reverse=True)
            return (HandRank.PAIR, [pair] + kickers, f"Pair of {HandEvaluator._value_name(pair)}s")

        # High card
        return (HandRank.HIGH_CARD, values, f"High Card, {HandEvaluator._value_name(values[0])}")

    @staticmethod
    def _check_straight(values: List[int]) -> Tuple[bool, int]:
        """Check if values form a straight. Returns (is_straight, high_card)."""
        sorted_vals = sorted(set(values), reverse=True)
        if len(sorted_vals) != 5:
            return False, 0

        # Regular straight
        if sorted_vals[0] - sorted_vals[4] == 4:
            return True, sorted_vals[0]

        # Ace-low straight (A-2-3-4-5)
        if sorted_vals == [14, 5, 4, 3, 2]:
            return True, 5

        return False, 0

    @staticmethod
    def _value_name(value: int) -> str:
        """Convert card value to name."""
        names = {11: 'Jack', 12: 'Queen', 13: 'King', 14: 'Ace'}
        return names.get(value, str(value))

    @staticmethod
    def best_hand(hole_cards: List[Card], community_cards: List[Card]) -> Tuple[List[Card], int, List[int], str]:
        """
        Find the best 5-card hand from hole cards + community cards.
        Returns: (best_5_cards, rank, tiebreakers, description)
        """
        all_cards = hole_cards + community_cards
        if len(all_cards) < 5:
            raise ValueError("Need at least 5 cards to evaluate")

        best_hand = None
        best_rank = (0, [])
        best_desc = ""

        for combo in combinations(all_cards, 5):
            cards = list(combo)
            rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
            if (rank, tiebreakers) > best_rank:
                best_rank = (rank, tiebreakers)
                best_hand = cards
                best_desc = desc

        return best_hand, best_rank[0], best_rank[1], best_desc

    @staticmethod
    def compare_hands(hands: List[Tuple[List[Card], List[Card]]]) -> List[int]:
        """
        Compare multiple hands and return indices of winners.
        hands: List of (hole_cards, community_cards) tuples
        Returns: List of winner indices (can be multiple for ties)
        """
        if not hands:
            return []

        evaluations = []
        for hole, community in hands:
            _, rank, tiebreakers, _ = HandEvaluator.best_hand(hole, community)
            evaluations.append((rank, tiebreakers))

        max_eval = max(evaluations)
        return [i for i, e in enumerate(evaluations) if e == max_eval]
