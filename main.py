import os
import asyncio
import logging
from bot import TicketBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

async def main():
    """Main entry point for the Discord bot."""
    # Get bot token from environment variable
    bot_token = os.getenv('DISCORD_BOT_TOKEN', 'your_bot_token_here')
    if not bot_token or bot_token == 'your_bot_token_here':
        logging.error("DISCORD_BOT_TOKEN environment variable not set")
        return

    # Initialize the bot
    bot = TicketBot()

    try:
        # Start the bot
        await bot.start(bot_token)

    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Bot crashed: {e}")
        raise
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
