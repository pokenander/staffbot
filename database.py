import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Guild configurations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id INTEGER PRIMARY KEY,
                    staff_role_id INTEGER,
                    officer_role_id INTEGER,
                    allowed_category_id INTEGER,
                    leaderboard_channel_id INTEGER
                )
            ''')
            
            # Check if new columns exist, add them if they don't
            cursor.execute("PRAGMA table_info(guild_config)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'allowed_category_id' not in columns:
                cursor.execute('ALTER TABLE guild_config ADD COLUMN allowed_category_id INTEGER')
                logging.info("Added allowed_category_id column to guild_config table")
            
            if 'leaderboard_channel_id' not in columns:
                cursor.execute('ALTER TABLE guild_config ADD COLUMN leaderboard_channel_id INTEGER')
                logging.info("Added leaderboard_channel_id column to guild_config table")
            
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
            
            # Ticket holders table  
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ticket_holders (
                    channel_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    set_by INTEGER,
                    set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            
            # Check if officer_used column exists, add it if it doesn't
            cursor.execute("PRAGMA table_info(active_timeouts)")
            timeout_columns = [column[1] for column in cursor.fetchall()]
            
            if 'officer_used' not in timeout_columns:
                cursor.execute('ALTER TABLE active_timeouts ADD COLUMN officer_used BOOLEAN DEFAULT FALSE')
                logging.info("Added officer_used column to active_timeouts table")
            
            # Allowed categories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS allowed_categories (
                    guild_id INTEGER,
                    category_id INTEGER,
                    UNIQUE(guild_id, category_id)
                )
            ''')
            
            conn.commit()
    
    def set_staff_role(self, guild_id: int, role_id: int):
        """Set the staff role for a guild."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO guild_config (guild_id, staff_role_id)
                VALUES (?, ?)
            ''', (guild_id, role_id))
            conn.commit()
    
    def set_officer_role(self, guild_id: int, role_id: int):
        """Set the officer role for a guild."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)
            ''', (guild_id,))
            cursor.execute('''
                UPDATE guild_config SET officer_role_id = ? WHERE guild_id = ?
            ''', (role_id, guild_id))
            conn.commit()

    def set_allowed_category(self, guild_id: int, category_id: int):
        """Set the main allowed category for a guild (single category)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)
            ''', (guild_id,))
            cursor.execute('''
                UPDATE guild_config SET allowed_category_id = ? WHERE guild_id = ?
            ''', (category_id, guild_id))
            conn.commit()
    
    def add_allowed_category(self, guild_id, category_id):
        """Add a category to allowed categories list."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO allowed_categories (guild_id, category_id)
                VALUES (?, ?)
            ''', (guild_id, category_id))
            conn.commit()

    def remove_allowed_category(self, guild_id, category_id):
        """Remove a category from allowed categories list."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM allowed_categories WHERE guild_id = ? AND category_id = ?
            ''', (guild_id, category_id))
            conn.commit()

    def get_allowed_categories(self, guild_id):
        """Get all allowed categories for a guild."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category_id FROM allowed_categories WHERE guild_id = ?
            ''', (guild_id,))
            return [row[0] for row in cursor.fetchall()]

    def set_leaderboard_channel(self, guild_id: int, channel_id: int):
        """Set the leaderboard channel for automatic updates."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)
            ''', (guild_id,))
            cursor.execute('''
                UPDATE guild_config SET leaderboard_channel_id = ? WHERE guild_id = ?
            ''', (channel_id, guild_id))
            conn.commit()

    def get_all_leaderboard_channels(self):
        """Get all leaderboard channels across all guilds."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT guild_id, leaderboard_channel_id FROM guild_config 
                WHERE leaderboard_channel_id IS NOT NULL
            ''')
            return cursor.fetchall()

    def set_guild_config(self, guild_id: int, staff_role_id=None, officer_role_id=None, leaderboard_channel_id=None):
        """Set guild configuration parameters."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
        
            # Insert guild if it doesn't exist
            cursor.execute('''
                INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)
            ''', (guild_id,))
            
            # Update the specified fields
            if staff_role_id is not None:
                cursor.execute('''
                    UPDATE guild_config SET staff_role_id = ? WHERE guild_id = ?
                ''', (staff_role_id, guild_id))
            
            if officer_role_id is not None:
                cursor.execute('''
                    UPDATE guild_config SET officer_role_id = ? WHERE guild_id = ?
                ''', (officer_role_id, guild_id))
            
            if leaderboard_channel_id is not None:
                cursor.execute('''
                    UPDATE guild_config SET leaderboard_channel_id = ? WHERE guild_id = ?
                ''', (leaderboard_channel_id, guild_id))
            
            conn.commit()

    def get_guild_config(self, guild_id: int) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
        """Get guild configuration: staff_role_id, officer_role_id, allowed_category_id, leaderboard_channel_id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT staff_role_id, officer_role_id, allowed_category_id, leaderboard_channel_id
                FROM guild_config WHERE guild_id = ?
            ''', (guild_id,))
            result = cursor.fetchone()
            return result if result else (None, None, None, None)

    def create_claim(self, guild_id: int, channel_id: int, user_id: int):
        """Create a new ticket claim record."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ticket_claims (guild_id, channel_id, user_id, claimed_at)
                VALUES (?, ?, ?, ?)
            ''', (guild_id, channel_id, user_id, datetime.now().isoformat()))
            conn.commit()

    def get_active_claim(self, channel_id: int):
        """FIX #1: Get active claim for a channel to prevent duplicate claims."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, claimed_at FROM ticket_claims 
                WHERE channel_id = ? AND completed = FALSE 
                ORDER BY claimed_at DESC LIMIT 1
            ''', (channel_id,))
            return cursor.fetchone()

    def complete_claim(self, channel_id: int, timeout_occurred: bool = False, officer_used: bool = False):
        """FIX #2: Mark a claim as completed and award score - Fixed officer logic for point awarding."""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.cursor()
            
            # Get the most recent claim for this channel
            cursor.execute('''
                SELECT guild_id, user_id, score_awarded FROM ticket_claims 
                WHERE channel_id = ? AND completed = FALSE 
                ORDER BY claimed_at DESC LIMIT 1
            ''', (channel_id,))
            result = cursor.fetchone()
            
            if result:
                guild_id, user_id, score_awarded = result
                
                # Mark as completed
                cursor.execute('''
                    UPDATE ticket_claims 
                    SET completed = TRUE, timeout_occurred = ?, score_awarded = TRUE
                    WHERE channel_id = ? AND user_id = ? AND completed = FALSE
                ''', (timeout_occurred, channel_id, user_id))

                # FIXED: Award score logic - Points awarded even if officer was used
                # - Not already awarded
                # - Not a timeout (unless it's a holder timeout where staff was active)
                # - Points should be awarded regardless of officer_used status
                if not score_awarded and not timeout_occurred:
                    self.award_score(guild_id, user_id)
                    logging.info(f"Point awarded to user {user_id} for completing ticket in channel {channel_id} (officer_used: {officer_used})")
                
                # Award score if not already awarded and not a timeout
                if not score_awarded and not timeout_occurred:
                    self.award_score(guild_id, user_id)
                
                conn.commit()

    def award_score(self, guild_id: int, user_id: int):
        """Award a point to a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create or update leaderboard entry
            cursor.execute('''
                INSERT OR IGNORE INTO leaderboard (guild_id, user_id) VALUES (?, ?)
            ''', (guild_id, user_id))
            
            cursor.execute('''
                UPDATE leaderboard 
                SET daily_claims = daily_claims + 1,
                    weekly_claims = weekly_claims + 1,
                    total_claims = total_claims + 1
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id))
            
            conn.commit()

    def get_leaderboard(self, guild_id: int, period: str = "total"):
        """Get leaderboard data for a specific period."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if period == "daily":
                cursor.execute('''
                    SELECT user_id, daily_claims FROM leaderboard 
                    WHERE guild_id = ? AND daily_claims > 0
                    ORDER BY daily_claims DESC, user_id ASC
                ''', (guild_id,))
            elif period == "weekly":
                cursor.execute('''
                    SELECT user_id, weekly_claims FROM leaderboard 
                    WHERE guild_id = ? AND weekly_claims > 0
                    ORDER BY weekly_claims DESC, user_id ASC
                ''', (guild_id,))
            else:  # total
                cursor.execute('''
                    SELECT user_id, total_claims FROM leaderboard 
                    WHERE guild_id = ? AND total_claims > 0
                    ORDER BY total_claims DESC, user_id ASC
                ''', (guild_id,))
            
            return cursor.fetchall()

    def reset_daily_leaderboard(self):
        """Reset all daily leaderboard scores."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE leaderboard SET daily_claims = 0, last_daily_reset = CURRENT_DATE
            ''')
            conn.commit()

    def reset_weekly_leaderboard(self):
        """Reset all weekly leaderboard scores."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE leaderboard SET weekly_claims = 0, last_weekly_reset = CURRENT_DATE
            ''')
            conn.commit()

    def set_ticket_holder(self, channel_id: int, user_id: int, set_by: int):
        """Set or update the ticket holder for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO ticket_holders (channel_id, user_id, set_by, set_at)
                VALUES (?, ?, ?, ?)
            ''', (channel_id, user_id, set_by, datetime.now().isoformat()))
            conn.commit()

    def get_ticket_holder(self, channel_id: int) -> Optional[int]:
        """Get the ticket holder for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id FROM ticket_holders WHERE channel_id = ?
            ''', (channel_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def save_timeout(self, channel_id: int, claimer_id: int, ticket_holder_id: int, original_permissions: str):
        """Save timeout information for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            cursor.execute('''
                INSERT OR REPLACE INTO active_timeouts 
                (channel_id, claimer_id, ticket_holder_id, claim_time, last_staff_message, last_holder_message, original_permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (channel_id, claimer_id, ticket_holder_id, current_time, current_time, current_time, original_permissions))
            conn.commit()

    def get_timeout_info(self, channel_id: int):
        """Get timeout information for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT claimer_id, ticket_holder_id, claim_time, last_staff_message, 
                       last_holder_message, original_permissions, officer_used
                FROM active_timeouts WHERE channel_id = ?
            ''', (channel_id,))
            return cursor.fetchone()

    def get_all_active_timeouts(self):
        """Get all active timeouts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT channel_id FROM active_timeouts')
            return cursor.fetchall()

    def remove_timeout(self, channel_id: int):
        """Remove timeout information for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM active_timeouts WHERE channel_id = ?', (channel_id,))
            conn.commit()

    def update_last_message(self, channel_id: int, user_id: int):
        """Update last message time for timeout tracking."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            
            # Check if this is an active timeout
            cursor.execute('SELECT claimer_id, ticket_holder_id FROM active_timeouts WHERE channel_id = ?', (channel_id,))
            timeout_info = cursor.fetchone()
            
            if timeout_info:
                claimer_id, ticket_holder_id = timeout_info
                
                if user_id == claimer_id:
                    # Update staff message time
                    cursor.execute('''
                        UPDATE active_timeouts SET last_staff_message = ? WHERE channel_id = ?
                    ''', (current_time, channel_id))
                elif user_id == ticket_holder_id:
                    # Update holder message time
                    cursor.execute('''
                        UPDATE active_timeouts SET last_holder_message = ? WHERE channel_id = ?
                    ''', (current_time, channel_id))
                
                conn.commit()

    def mark_officer_used(self, channel_id: int):
        """Mark that officer command was used for this ticket."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE active_timeouts SET officer_used = TRUE WHERE channel_id = ?
            ''', (channel_id,))
            conn.commit()
