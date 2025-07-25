import discord
from discord.ext import commands
import asyncio
import logging
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from database import Database
from permissions import PermissionManager
from timeouts import TimeoutManager
from leaderboard import LeaderboardManager
from config import BOT_PREFIX, DATABASE_PATH, TIMEZONE

# === Flask server to keep Render Web Service alive ===
from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def index():
    return 'Bot is running!', 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# =====================================================

class TicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = False  # Don't require privileged member intent
        
        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            help_command=None
        )
        
        # Initialize components
        self.database = Database(DATABASE_PATH)
        self.permission_manager = PermissionManager(self)
        self.timeout_manager = TimeoutManager(self)
        self.leaderboard_manager = LeaderboardManager(self)
        
        # Initialize scheduler
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
        
    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        try:
            # Load commands
            await self.load_extension('bot_commands')
            # Setup scheduled tasks
            self._setup_scheduler()
            logging.info("Bot setup completed successfully")
        except Exception as e:
            logging.error(f"Error during bot setup: {e}")
    
    def _setup_scheduler(self):
        """Setup scheduled tasks for leaderboard resets."""
        
        # Daily reset at 00:00 GMT+2
        self.scheduler.add_job(
            self._daily_reset,
            CronTrigger(hour=0, minute=0, timezone=pytz.timezone(TIMEZONE)),
            id='daily_reset'
        )
        
        # Weekly reset every Monday at 00:00 GMT+2
        self.scheduler.add_job(
            self._weekly_reset,
            CronTrigger(day_of_week=0, hour=0, minute=0, timezone=pytz.timezone(TIMEZONE)),
            id='weekly_reset'
        )
        
        self.scheduler.start()
        logging.info("Scheduler started successfully")
    
    async def _daily_reset(self):
        """Daily leaderboard reset task."""
        try:
            # Send leaderboards to configured channels before reset
            await self._send_daily_leaderboards()
            
            # Reset daily leaderboard
            self.leaderboard_manager.reset_daily_leaderboard()
            logging.info("Daily leaderboard reset completed")
        except Exception as e:
            logging.error(f"Error in daily reset: {e}")
    
    async def _send_daily_leaderboards(self):
        """Send daily leaderboards to configured channels."""
        try:
            leaderboard_channels = self.database.get_all_leaderboard_channels()
            
            for guild_id, channel_id in leaderboard_channels:
                channel = self.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    await self.leaderboard_manager.send_combined_leaderboard(channel)
                    logging.info(f"Sent daily leaderboard to channel {channel_id}")
                else:
                    logging.warning(f"Leaderboard channel {channel_id} not found or invalid, cleaning up config")
                    # Clean up invalid channel from database
                    with sqlite3.connect(self.database.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE guild_config SET leaderboard_channel_id = NULL WHERE guild_id = ?
                        ''', (guild_id,))
                        conn.commit()
        except Exception as e:
            logging.error(f"Error sending daily leaderboards: {e}")
    
    async def _weekly_reset(self):
        """Weekly leaderboard reset task."""
        try:
            self.leaderboard_manager.reset_weekly_leaderboard()
            logging.info("Weekly leaderboard reset completed")
        except Exception as e:
            logging.error(f"Error in weekly reset: {e}")
    
    async def on_ready(self):
        """Event fired when bot is ready."""
        logging.info(f'{self.user} has connected to Discord!')
        logging.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Resume timeout monitoring for any active timeouts
        await self._resume_timeout_monitoring()
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for ticket claims | ?help"
            )
        )
    
    async def _resume_timeout_monitoring(self):
        """Resume timeout monitoring for active timeouts."""
        try:
            active_timeouts = self.database.get_all_active_timeouts()
            
            for timeout_info in active_timeouts:
                channel_id = timeout_info[0]
                
                # Verify channel still exists
                channel = self.get_channel(channel_id)
                if channel:
                    await self.timeout_manager.start_timeout_monitoring(channel_id)
                    logging.info(f"Resumed timeout monitoring for channel {channel_id}")
                else:
                    # Clean up stale timeout data
                    self.database.remove_timeout(channel_id)
                    logging.info(f"Cleaned up stale timeout data for channel {channel_id}")
        
        except Exception as e:
            logging.error(f"Error resuming timeout monitoring: {e}")
    
    async def on_guild_join(self, guild):
        """Event fired when bot joins a guild."""
        logging.info(f"Joined guild: {guild.name} (ID: {guild.id})")
    
    async def on_guild_remove(self, guild):
        """Event fired when bot leaves a guild."""
        logging.info(f"Left guild: {guild.name} (ID: {guild.id})")
    
    async def on_message(self, message):
        """Event fired when a message is sent."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Update last message time for timeout tracking
        if message.channel.id:
            self.database.update_last_message(message.channel.id, message.author.id)
        
        # Process commands
        await self.process_commands(message)
    
    async def on_command_error(self, ctx, error):
        """Global error handler for commands."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
        
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param}")
        
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided.")
        
        else:
            logging.error(f"Unhandled command error in {ctx.command}: {error}")
            await ctx.send("❌ An unexpected error occurred.")
    
    async def close(self):
        """Clean shutdown of the bot."""
        try:
            # Stop scheduler
            if hasattr(self, 'scheduler') and self.scheduler.running:
                self.scheduler.shutdown()
            
            # Cancel all timeout tasks
            for channel_id in list(self.timeout_manager.timeout_tasks.keys()):
                await self.timeout_manager.stop_timeout_monitoring(channel_id)
            
            logging.info("Bot shutdown completed")
            
        except Exception as e:
            logging.error(f"Error during bot shutdown: {e}")
        
        finally:
            await super().close()

# === Main runner ===
if __name__ == "__main__":
    # Start web server in background thread
    threading.Thread(target=run_web_server).start()

    # Start the Discord bot
    bot = TicketBot()
    token = os.environ.get("DISCORD_TOKEN")
if not token:
    print("ERROR: DISCORD_TOKEN environment variable not set!")
    exit(1)
bot.run(token)
