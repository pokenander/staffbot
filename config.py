import os

# Bot configuration
BOT_PREFIX = "?"
TIMEZONE = "Europe/Berlin"  # GMT+2
TIMEOUT_MINUTES = 15

# Database configuration
DATABASE_PATH = "ticket_bot.db"

# Environment variables
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', 'your_bot_token_here')

# Default messages
CLAIM_MESSAGE = "✅ **{username}** has claimed this ticket.\n\n⏰ Timeout will occur after **15 minutes** of inactivity from either party."
TIMEOUT_MESSAGE = "⏰ Ticket timeout reached. Permissions have been restored."
RECLAIM_MESSAGE = "⏰ This ticket is now available for claiming again due to staff timeout."

# Web monitor configuration
WEB_PORT = 5000
WEB_HOST = "0.0.0.0"
