"""History recording and statistics."""

import json
from typing import List, Dict, Any, Optional
from .db import get_db


class HistoryManager:
    """Manages game history and player statistics."""

    @staticmethod
    def record_hand(room_id: str, hand_number: int, pot_size: int,
                    winners: List[str], actions: List[Dict],
                    player_results: List[Dict[str, Any]]) -> int:
        """
        Record a completed hand.

        player_results: List of dicts with keys:
            - player_name
            - starting_stack
            - ending_stack
            - profit
            - is_winner
            - hole_cards (optional)
        """
        with get_db() as conn:
            cursor = conn.cursor()

            # Insert hand record
            cursor.execute('''
                INSERT INTO hands (room_id, hand_number, pot_size, winner_names, actions)
                VALUES (?, ?, ?, ?, ?)
            ''', (room_id, hand_number, pot_size, ','.join(winners), json.dumps(actions)))

            hand_id = cursor.lastrowid

            # Insert player results
            for result in player_results:
                cursor.execute('''
                    INSERT INTO player_hand_results
                    (hand_id, player_name, starting_stack, ending_stack, profit, is_winner, hole_cards)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    hand_id,
                    result['player_name'],
                    result['starting_stack'],
                    result['ending_stack'],
                    result['profit'],
                    result['is_winner'],
                    json.dumps(result.get('hole_cards', []))
                ))

                # Update player stats
                cursor.execute('''
                    INSERT INTO player_stats (player_name, hands_played, hands_won, total_profit)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(player_name) DO UPDATE SET
                        hands_played = hands_played + 1,
                        hands_won = hands_won + ?,
                        total_profit = total_profit + ?
                ''', (
                    result['player_name'],
                    1 if result['is_winner'] else 0,
                    result['profit'],
                    1 if result['is_winner'] else 0,
                    result['profit']
                ))

            conn.commit()
            return hand_id

    @staticmethod
    def get_hand_history(room_id: str, limit: int = 50) -> List[Dict]:
        """Get recent hand history for a room."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, room_id, hand_number, pot_size, winner_names, actions, created_at
                FROM hands
                WHERE room_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (room_id, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_hand_details(hand_id: int) -> Optional[Dict]:
        """Get detailed information about a specific hand."""
        with get_db() as conn:
            cursor = conn.cursor()

            # Get hand info
            cursor.execute('''
                SELECT id, room_id, hand_number, pot_size, winner_names, actions, created_at
                FROM hands WHERE id = ?
            ''', (hand_id,))
            hand = cursor.fetchone()

            if not hand:
                return None

            result = dict(hand)
            result['actions'] = json.loads(result['actions'])

            # Get player results
            cursor.execute('''
                SELECT player_name, starting_stack, ending_stack, profit, is_winner, hole_cards
                FROM player_hand_results
                WHERE hand_id = ?
            ''', (hand_id,))

            result['player_results'] = []
            for row in cursor.fetchall():
                player_result = dict(row)
                player_result['hole_cards'] = json.loads(player_result['hole_cards'])
                result['player_results'].append(player_result)

            return result

    @staticmethod
    def get_player_stats(player_name: str) -> Optional[Dict]:
        """Get statistics for a player."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT player_name, hands_played, hands_won, total_profit
                FROM player_stats
                WHERE player_name = ?
            ''', (player_name,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def get_leaderboard(limit: int = 10) -> List[Dict]:
        """Get top players by profit."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT player_name, hands_played, hands_won, total_profit
                FROM player_stats
                ORDER BY total_profit DESC
                LIMIT ?
            ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_all_stats() -> List[Dict]:
        """Get all player statistics."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT player_name, hands_played, hands_won, total_profit
                FROM player_stats
                ORDER BY player_name
            ''')

            return [dict(row) for row in cursor.fetchall()]
