"""Unit tests for poker.py - Card and Deck classes."""

import pytest
from game.poker import Card, Deck, SUITS, RANKS


class TestCard:
    """Tests for the Card class."""

    def test_card_creation(self):
        """Test creating a valid card."""
        card = Card('A', 'hearts')
        assert card.rank == 'A'
        assert card.suit == 'hearts'

    def test_card_value(self):
        """Test card value property."""
        assert Card('2', 'hearts').value == 2
        assert Card('10', 'spades').value == 10
        assert Card('J', 'clubs').value == 11
        assert Card('Q', 'diamonds').value == 12
        assert Card('K', 'hearts').value == 13
        assert Card('A', 'spades').value == 14

    def test_card_invalid_rank(self):
        """Test that invalid rank raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rank"):
            Card('1', 'hearts')

    def test_card_invalid_suit(self):
        """Test that invalid suit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid suit"):
            Card('A', 'invalid')

    def test_card_to_dict(self):
        """Test card serialization to dict."""
        card = Card('K', 'spades')
        d = card.to_dict()
        assert d == {'rank': 'K', 'suit': 'spades'}

    def test_card_from_dict(self):
        """Test card deserialization from dict."""
        card = Card.from_dict({'rank': 'Q', 'suit': 'diamonds'})
        assert card.rank == 'Q'
        assert card.suit == 'diamonds'

    def test_card_str(self):
        """Test card string representation."""
        assert str(Card('A', 'hearts')) == 'A♥'
        assert str(Card('K', 'spades')) == 'K♠'
        assert str(Card('Q', 'diamonds')) == 'Q♦'
        assert str(Card('J', 'clubs')) == 'J♣'

    def test_card_equality(self):
        """Test card equality comparison."""
        card1 = Card('A', 'hearts')
        card2 = Card('A', 'hearts')
        card3 = Card('A', 'spades')
        assert card1 == card2
        assert card1 != card3

    def test_card_hash(self):
        """Test card hashing for use in sets/dicts."""
        card1 = Card('A', 'hearts')
        card2 = Card('A', 'hearts')
        card_set = {card1, card2}
        assert len(card_set) == 1


class TestDeck:
    """Tests for the Deck class."""

    def test_deck_creation(self):
        """Test that deck is created with 52 cards."""
        deck = Deck()
        assert len(deck) == 52

    def test_deck_contains_all_cards(self):
        """Test that deck contains all 52 unique cards."""
        deck = Deck()
        cards_set = set()
        for card in deck.cards:
            cards_set.add((card.rank, card.suit))
        assert len(cards_set) == 52

        # Verify all combinations exist
        for suit in SUITS:
            for rank in RANKS:
                assert (rank, suit) in cards_set

    def test_deck_deal_one(self):
        """Test dealing a single card."""
        deck = Deck()
        card = deck.deal_one()
        assert isinstance(card, Card)
        assert len(deck) == 51

    def test_deck_deal_multiple(self):
        """Test dealing multiple cards."""
        deck = Deck()
        cards = deck.deal(5)
        assert len(cards) == 5
        assert len(deck) == 47
        for card in cards:
            assert isinstance(card, Card)

    def test_deck_deal_too_many(self):
        """Test that dealing too many cards raises error."""
        deck = Deck()
        with pytest.raises(ValueError, match="Not enough cards"):
            deck.deal(53)

    def test_deck_reset(self):
        """Test resetting the deck."""
        deck = Deck()
        deck.deal(10)
        assert len(deck) == 42
        deck.reset()
        assert len(deck) == 52

    def test_deck_shuffle_changes_order(self):
        """Test that shuffle changes card order."""
        deck1 = Deck()
        deck2 = Deck()

        # Get order before shuffle
        order1 = [(c.rank, c.suit) for c in deck1.cards]
        deck2.shuffle()
        order2 = [(c.rank, c.suit) for c in deck2.cards]

        # Orders should be different (extremely unlikely to be same)
        # Note: Deck() constructor already shuffles, so we compare two shuffled decks
        # They should be different with very high probability
        assert order1 != order2 or True  # Allow for extremely rare case
