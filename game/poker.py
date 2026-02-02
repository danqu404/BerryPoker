"""Poker card and deck implementation."""

import random
from dataclasses import dataclass
from typing import List


SUITS = ['hearts', 'diamonds', 'clubs', 'spades']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {rank: i for i, rank in enumerate(RANKS, 2)}


@dataclass
class Card:
    rank: str
    suit: str

    def __post_init__(self):
        if self.rank not in RANKS:
            raise ValueError(f"Invalid rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"Invalid suit: {self.suit}")

    @property
    def value(self) -> int:
        return RANK_VALUES[self.rank]

    def to_dict(self) -> dict:
        return {'rank': self.rank, 'suit': self.suit}

    @classmethod
    def from_dict(cls, data: dict) -> 'Card':
        return cls(rank=data['rank'], suit=data['suit'])

    def __str__(self) -> str:
        suit_symbols = {
            'hearts': '♥',
            'diamonds': '♦',
            'clubs': '♣',
            'spades': '♠'
        }
        return f"{self.rank}{suit_symbols[self.suit]}"

    def __repr__(self) -> str:
        return str(self)

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit


class Deck:
    def __init__(self):
        self.cards: List[Card] = []
        self.reset()

    def reset(self):
        """Reset and shuffle the deck."""
        self.cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]
        self.shuffle()

    def shuffle(self):
        """Shuffle the deck."""
        random.shuffle(self.cards)

    def deal(self, count: int = 1) -> List[Card]:
        """Deal cards from the deck."""
        if count > len(self.cards):
            raise ValueError(f"Not enough cards in deck. Requested {count}, have {len(self.cards)}")
        dealt = self.cards[:count]
        self.cards = self.cards[count:]
        return dealt

    def deal_one(self) -> Card:
        """Deal a single card."""
        return self.deal(1)[0]

    def __len__(self) -> int:
        return len(self.cards)
