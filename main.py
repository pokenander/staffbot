import os
import asyncio
import logging
import threading
from flask import Flask
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

# Minimal Flask app to bind a port (required for Render Web Service)
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is running!'

def run_flask():
    port = int(os.environ.get('PORT', 5000))  # Render sets this dynamically
    app.run(host='0.0.0.0', port=port)

async def start_bot():
    """Starts the Discord bot."""
    bot_token = os.getenv('DISCORD_BOT_TOKEN', 'your_bot_token_here')
    if not bot_token or bot_token == 'your_bot_token_here':
        logging.error("DISCORD_BOT_TOKEN environment variable not set")
        return

    bot = TicketBot()

    try:
        await bot.start(bot_token)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Bot crashed: {e}")
        raise
    finally:
        await bot.close()

def main():
    # Start Flask app in a background thread
    threading.Thread(target=run_flask).start()

    # Run the bot in the main thread's event loop
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
