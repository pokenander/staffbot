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

@app.route('/health')
def health():
    return 'OK', 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))  # Render sets this dynamically
    app.run(host='0.0.0.0', port=port, debug=False)

async def start_bot():
    """Starts the Discord bot."""
    bot_token = os.getenv('DISCORD_TOKEN')
    
    if not bot_token:
        logging.error("ERROR: DISCORD_TOKEN not found in environment variables")
        logging.error("Please set your Discord bot token in Render's environment variables")
        return

    logging.info("Starting Discord bot...")
    bot = TicketBot()

    try:
        await bot.start(bot_token)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Bot crashed: {e}")
        raise
    finally:
        logging.info("Closing bot connection...")
        await bot.close()

def main():
    # Check for required environment variables
    if not os.getenv('DISCORD_TOKEN'):
        logging.error("DISCORD_TOKEN environment variable not set!")
        logging.error("Please add your Discord bot token to Render's environment variables")
        return

    logging.info("Starting Flask web server...")
    # Start Flask app in a background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    logging.info("Starting Discord bot...")
    # Run the bot in the main thread's event loop
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logging.info("Application stopped by user")
    except Exception as e:
        logging.error(f"Application crashed: {e}")
        raise

if __name__ == "__main__":
    main()
