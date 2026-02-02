"""Unit tests for hand_evaluator.py - Hand ranking logic."""

import pytest
from game.poker import Card
from game.hand_evaluator import HandEvaluator, HandRank


class TestHandEvaluator:
    """Tests for the HandEvaluator class."""

    def test_royal_flush(self):
        """Test royal flush detection."""
        cards = [
            Card('A', 'hearts'),
            Card('K', 'hearts'),
            Card('Q', 'hearts'),
            Card('J', 'hearts'),
            Card('10', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.ROYAL_FLUSH
        assert "Royal Flush" in desc

    def test_straight_flush(self):
        """Test straight flush detection."""
        cards = [
            Card('9', 'clubs'),
            Card('8', 'clubs'),
            Card('7', 'clubs'),
            Card('6', 'clubs'),
            Card('5', 'clubs')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.STRAIGHT_FLUSH
        assert "Straight Flush" in desc

    def test_four_of_a_kind(self):
        """Test four of a kind detection."""
        cards = [
            Card('K', 'hearts'),
            Card('K', 'diamonds'),
            Card('K', 'clubs'),
            Card('K', 'spades'),
            Card('5', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.FOUR_OF_A_KIND
        assert "Four of a Kind" in desc

    def test_full_house(self):
        """Test full house detection."""
        cards = [
            Card('Q', 'hearts'),
            Card('Q', 'diamonds'),
            Card('Q', 'clubs'),
            Card('7', 'spades'),
            Card('7', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.FULL_HOUSE
        assert "Full House" in desc

    def test_flush(self):
        """Test flush detection."""
        cards = [
            Card('A', 'diamonds'),
            Card('J', 'diamonds'),
            Card('8', 'diamonds'),
            Card('5', 'diamonds'),
            Card('2', 'diamonds')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.FLUSH
        assert "Flush" in desc

    def test_straight(self):
        """Test straight detection."""
        cards = [
            Card('9', 'hearts'),
            Card('8', 'diamonds'),
            Card('7', 'clubs'),
            Card('6', 'spades'),
            Card('5', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.STRAIGHT
        assert "Straight" in desc

    def test_ace_low_straight(self):
        """Test A-2-3-4-5 straight (wheel)."""
        cards = [
            Card('A', 'hearts'),
            Card('2', 'diamonds'),
            Card('3', 'clubs'),
            Card('4', 'spades'),
            Card('5', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.STRAIGHT
        assert tiebreakers == [5]  # 5-high straight

    def test_three_of_a_kind(self):
        """Test three of a kind detection."""
        cards = [
            Card('J', 'hearts'),
            Card('J', 'diamonds'),
            Card('J', 'clubs'),
            Card('9', 'spades'),
            Card('5', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.THREE_OF_A_KIND
        assert "Three of a Kind" in desc

    def test_two_pair(self):
        """Test two pair detection."""
        cards = [
            Card('K', 'hearts'),
            Card('K', 'diamonds'),
            Card('8', 'clubs'),
            Card('8', 'spades'),
            Card('3', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.TWO_PAIR
        assert "Two Pair" in desc

    def test_one_pair(self):
        """Test one pair detection."""
        cards = [
            Card('10', 'hearts'),
            Card('10', 'diamonds'),
            Card('A', 'clubs'),
            Card('7', 'spades'),
            Card('3', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.PAIR
        assert "Pair" in desc

    def test_high_card(self):
        """Test high card detection."""
        cards = [
            Card('A', 'hearts'),
            Card('J', 'diamonds'),
            Card('8', 'clubs'),
            Card('5', 'spades'),
            Card('2', 'hearts')
        ]
        rank, tiebreakers, desc = HandEvaluator.evaluate(cards)
        assert rank == HandRank.HIGH_CARD
        assert "High Card" in desc

    def test_evaluate_requires_five_cards(self):
        """Test that evaluate requires exactly 5 cards."""
        with pytest.raises(ValueError, match="exactly 5 cards"):
            HandEvaluator.evaluate([Card('A', 'hearts')])

    def test_best_hand_from_seven_cards(self):
        """Test finding best 5-card hand from 7 cards."""
        hole_cards = [Card('A', 'hearts'), Card('K', 'hearts')]
        community = [
            Card('Q', 'hearts'),
            Card('J', 'hearts'),
            Card('10', 'hearts'),
            Card('2', 'clubs'),
            Card('3', 'diamonds')
        ]
        best_cards, rank, tiebreakers, desc = HandEvaluator.best_hand(hole_cards, community)
        assert rank == HandRank.ROYAL_FLUSH
        assert len(best_cards) == 5

    def test_compare_hands_single_winner(self):
        """Test comparing hands with clear winner."""
        # Player 1: Pair of Aces
        hole1 = [Card('A', 'hearts'), Card('A', 'diamonds')]
        # Player 2: Pair of Kings
        hole2 = [Card('K', 'hearts'), Card('K', 'diamonds')]
        community = [
            Card('5', 'clubs'),
            Card('7', 'spades'),
            Card('9', 'hearts'),
            Card('2', 'clubs'),
            Card('3', 'diamonds')
        ]

        winners = HandEvaluator.compare_hands([
            (hole1, community),
            (hole2, community)
        ])
        assert winners == [0]  # Player 1 wins

    def test_compare_hands_tie(self):
        """Test comparing hands that result in a tie."""
        # Both players use same community straight
        hole1 = [Card('2', 'hearts'), Card('3', 'diamonds')]
        hole2 = [Card('2', 'clubs'), Card('3', 'spades')]
        community = [
            Card('4', 'clubs'),
            Card('5', 'spades'),
            Card('6', 'hearts'),
            Card('7', 'diamonds'),
            Card('8', 'clubs')
        ]

        winners = HandEvaluator.compare_hands([
            (hole1, community),
            (hole2, community)
        ])
        assert winners == [0, 1]  # Both tie

    def test_hand_ranking_order(self):
        """Test that hand rankings are in correct order."""
        # Create one hand of each type and verify ordering
        high_card = [Card('A', 'hearts'), Card('K', 'diamonds'), Card('J', 'clubs'),
                     Card('9', 'spades'), Card('7', 'hearts')]
        pair = [Card('A', 'hearts'), Card('A', 'diamonds'), Card('J', 'clubs'),
                Card('9', 'spades'), Card('7', 'hearts')]
        two_pair = [Card('A', 'hearts'), Card('A', 'diamonds'), Card('J', 'clubs'),
                    Card('J', 'spades'), Card('7', 'hearts')]
        trips = [Card('A', 'hearts'), Card('A', 'diamonds'), Card('A', 'clubs'),
                 Card('9', 'spades'), Card('7', 'hearts')]
        straight = [Card('9', 'hearts'), Card('8', 'diamonds'), Card('7', 'clubs'),
                    Card('6', 'spades'), Card('5', 'hearts')]
        flush = [Card('A', 'hearts'), Card('K', 'hearts'), Card('J', 'hearts'),
                 Card('9', 'hearts'), Card('2', 'hearts')]
        full_house = [Card('A', 'hearts'), Card('A', 'diamonds'), Card('A', 'clubs'),
                      Card('K', 'spades'), Card('K', 'hearts')]
        quads = [Card('A', 'hearts'), Card('A', 'diamonds'), Card('A', 'clubs'),
                 Card('A', 'spades'), Card('7', 'hearts')]
        straight_flush = [Card('9', 'hearts'), Card('8', 'hearts'), Card('7', 'hearts'),
                          Card('6', 'hearts'), Card('5', 'hearts')]
        royal_flush = [Card('A', 'hearts'), Card('K', 'hearts'), Card('Q', 'hearts'),
                       Card('J', 'hearts'), Card('10', 'hearts')]

        hands = [high_card, pair, two_pair, trips, straight, flush,
                 full_house, quads, straight_flush, royal_flush]

        ranks = [HandEvaluator.evaluate(h)[0] for h in hands]

        # Verify each hand ranks higher than the previous
        for i in range(1, len(ranks)):
            assert ranks[i] > ranks[i-1], f"Hand {i} should rank higher than hand {i-1}"
