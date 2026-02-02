"""Pydantic models for BerryPoker."""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class CardModel(BaseModel):
    rank: str
    suit: str


class PlayerInfo(BaseModel):
    name: str
    seat: int
    stack: int
    current_bet: int = 0
    is_folded: bool = False
    is_all_in: bool = False
    is_sitting_out: bool = False
    has_cards: bool = False
    hole_cards: Optional[List[CardModel]] = None


class RoomSettings(BaseModel):
    small_blind: int = Field(default=1, ge=1)
    big_blind: int = Field(default=2, ge=1)
    min_buy_in: int = Field(default=40, ge=1)
    max_buy_in: int = Field(default=200, ge=1)


class JoinRequest(BaseModel):
    player_name: str
    stack: int = Field(default=100, ge=1)
    seat: Optional[int] = None


class ActionRequest(BaseModel):
    action: str  # fold, check, call, raise, all_in
    amount: Optional[int] = None


class ValidAction(BaseModel):
    action: str
    amount: Optional[int] = None
    min: Optional[int] = None
    max: Optional[int] = None


class GameState(BaseModel):
    room_id: str
    phase: str
    hand_number: int
    pot: int
    community_cards: List[CardModel]
    players: List[PlayerInfo]
    dealer_seat: Optional[int]
    current_player_seat: Optional[int]
    current_bet: int
    small_blind: int
    big_blind: int
    min_buy_in: int
    max_buy_in: int
    valid_actions: Optional[List[ValidAction]] = None
    last_hand_result: Optional[Dict[str, Any]] = None


class WebSocketMessage(BaseModel):
    type: str
    data: Optional[Dict[str, Any]] = None


class CreateRoomRequest(BaseModel):
    settings: Optional[RoomSettings] = None


class CreateRoomResponse(BaseModel):
    room_id: str
    settings: RoomSettings


class ActionHistoryItem(BaseModel):
    player: str
    action: str
    amount: int
    phase: str


class HandRecord(BaseModel):
    id: int
    room_id: str
    hand_number: int
    pot_size: int
    winner_names: str
    actions: str
    created_at: str


class PlayerStats(BaseModel):
    player_name: str
    hands_played: int
    hands_won: int
    total_profit: int
