import sqlite3
import logging
from datetime import datetime
from typing import List, Tuple, Optional

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Guild configuration table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id INTEGER PRIMARY KEY,
                    staff_role_id INTEGER,
                    officer_role_id INTEGER,
                    leaderboard_channel_id INTEGER
                )
            ''')

            # Allowed categories table (NEW)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS allowed_categories (
                    guild_id INTEGER,
                    category_id INTEGER,
                    PRIMARY KEY (guild_id, category_id)
                )
            ''')

            # Ticket claims table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ticket_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    user_id INTEGER,
                    claimed_at TIMESTAMP,
                    completed BOOLEAN DEFAULT FALSE,
                    timeout_occurred BOOLEAN DEFAULT FALSE,
                    score_awarded BOOLEAN DEFAULT FALSE
                )
            ''')

            # Ticket holders table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ticket_holders (
                    channel_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    set_by INTEGER,
                    set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Leaderboard table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leaderboard (
                    guild_id INTEGER,
                    user_id INTEGER,
                    daily_claims INTEGER DEFAULT 0,
                    weekly_claims INTEGER DEFAULT 0,
                    total_claims INTEGER DEFAULT 0,
                    last_daily_reset DATE,
                    last_weekly_reset DATE,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')

            # Active timeouts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_timeouts (
                    channel_id INTEGER PRIMARY KEY,
                    claimer_id INTEGER,
                    ticket_holder_id INTEGER,
                    claim_time TIMESTAMP,
                    last_staff_message TIMESTAMP,
                    last_holder_message TIMESTAMP,
                    original_permissions TEXT,
                    officer_used BOOLEAN DEFAULT FALSE
                )
            ''')

            conn.commit()

    # ---- NEW CATEGORY SUPPORT ----

    def add_allowed_category(self, guild_id: int, category_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO allowed_categories (guild_id, category_id)
                VALUES (?, ?)
            ''', (guild_id, category_id))
            conn.commit()

    def get_allowed_categories(self, guild_id: int) -> List[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category_id FROM allowed_categories WHERE guild_id = ?
            ''', (guild_id,))
            return [row[0] for row in cursor.fetchall()]

    # ---- GUILD CONFIG ----

    def set_staff_role(self, guild_id: int, role_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)
            ''', (guild_id,))
            cursor.execute('''
                UPDATE guild_config SET staff_role_id = ? WHERE guild_id = ?
            ''', (role_id, guild_id))
            conn.commit()

    def set_officer_role(self, guild_id: int, role_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)
            ''', (guild_id,))
            cursor.execute('''
                UPDATE guild_config SET officer_role_id = ? WHERE guild_id = ?
            ''', (role_id, guild_id))
            conn.commit()

    def set_leaderboard_channel(self, guild_id: int, channel_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)
            ''', (guild_id,))
            cursor.execute('''
                UPDATE guild_config SET leaderboard_channel_id = ? WHERE guild_id = ?
            ''', (channel_id, guild_id))
            conn.commit()

    def get_guild_config(self, guild_id: int) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT staff_role_id, officer_role_id, leaderboard_channel_id 
                FROM guild_config WHERE guild_id = ?
            ''', (guild_id,))
            result = cursor.fetchone()
            return result if result else (None, None, None)

    # ---- TICKET HOLDER ----

    def set_ticket_holder(self, channel_id: int, user_id: int, set_by: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO ticket_holders (channel_id, user_id, set_by)
                VALUES (?, ?, ?)
            ''', (channel_id, user_id, set_by))
            conn.commit()

    def get_ticket_holder(self, channel_id: int) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM ticket_holders WHERE channel_id = ?', (channel_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def remove_ticket_holder(self, channel_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ticket_holders WHERE channel_id = ?', (channel_id,))
            conn.commit()

    # ---- CLAIMING ----

    def create_claim(self, guild_id: int, channel_id: int, user_id: int) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ticket_claims (guild_id, channel_id, user_id, claimed_at)
                VALUES (?, ?, ?, ?)
            ''', (guild_id, channel_id, user_id, datetime.now()))
            conn.commit()
            return cursor.lastrowid or 0

    def complete_claim(self, channel_id: int, timeout_occurred: bool = False):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE ticket_claims 
                SET completed = TRUE, timeout_occurred = ?
                WHERE channel_id = ? AND completed = FALSE
            ''', (timeout_occurred, channel_id))
            conn.commit()

    def award_score(self, guild_id: int, user_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            today = datetime.now().date()

            cursor.execute('''
                INSERT OR IGNORE INTO leaderboard (guild_id, user_id, last_daily_reset, last_weekly_reset)
                VALUES (?, ?, ?, ?)
            ''', (guild_id, user_id, today, today))

            cursor.execute('''
                UPDATE leaderboard 
                SET daily_claims = daily_claims + 1,
                    weekly_claims = weekly_claims + 1,
                    total_claims = total_claims + 1
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id))

            cursor.execute('''
                SELECT id FROM ticket_claims 
                WHERE guild_id = ? AND user_id = ? AND score_awarded = FALSE
                ORDER BY claimed_at DESC LIMIT 1
            ''', (guild_id, user_id))
            result = cursor.fetchone()
            if result:
                cursor.execute('UPDATE ticket_claims SET score_awarded = TRUE WHERE id = ?', (result[0],))

            conn.commit()

    def remove_score(self, guild_id: int, user_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE leaderboard 
                SET daily_claims = MAX(0, daily_claims - 1),
                    weekly_claims = MAX(0, weekly_claims - 1),
                    total_claims = MAX(0, total_claims - 1)
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id))
            conn.commit()

    # ---- TIMEOUT ----

    def save_timeout(self, channel_id: int, claimer_id: int, ticket_holder_id: int, original_permissions: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now()
            cursor.execute('''
                INSERT OR REPLACE INTO active_timeouts 
                (channel_id, claimer_id, ticket_holder_id, claim_time, last_staff_message, last_holder_message, original_permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (channel_id, claimer_id, ticket_holder_id, now, now, now, original_permissions))
            conn.commit()

    def get_timeout_info(self, channel_id: int) -> Optional[tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT claimer_id, ticket_holder_id, claim_time, last_staff_message, 
                       last_holder_message, original_permissions, officer_used
                FROM active_timeouts WHERE channel_id = ?
            ''', (channel_id,))
            return cursor.fetchone()

    def remove_timeout(self, channel_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM active_timeouts WHERE channel_id = ?', (channel_id,))
            conn.commit()

    def mark_officer_used(self, channel_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE active_timeouts SET officer_used = TRUE WHERE channel_id = ?', (channel_id,))
            conn.commit()
