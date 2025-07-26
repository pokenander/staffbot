import os
import asyncio
import logging
import threading
import time
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

async def start_bot_with_retry():
    """Starts the Discord bot with retry logic for rate limiting."""
    bot_token = os.getenv('DISCORD_TOKEN')
    
    if not bot_token:
        logging.error("ERROR: DISCORD_TOKEN not found in environment variables")
        return

    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            logging.info(f"Starting Discord bot... (Attempt {retry_count + 1})")
            bot = TicketBot()
            await bot.start(bot_token)
            break  # If successful, break out of loop
            
        except Exception as e:
            error_message = str(e).lower()
            
            if "429" in error_message or "rate limit" in error_message:
                retry_count += 1
                wait_time = 30 * retry_count  # Exponential backoff: 30s, 60s, 90s
                
                if retry_count < max_retries:
                    logging.warning(f"Rate limited! Waiting {wait_time} seconds before retry {retry_count + 1}/{max_retries}")
                    await asyncio.sleep(wait_time)
                else:
                    logging.error("Max retries reached. Discord is rate limiting this IP. Please wait 15-30 minutes.")
                    return
            else:
                logging.error(f"Bot error: {e}")
                return
        finally:
            try:
                await bot.close()
            except:
                pass

def main():
    # Check for required environment variables
    if not os.getenv('DISCORD_TOKEN'):
        logging.error("DISCORD_TOKEN environment variable not set!")
        return

    logging.info("Starting Flask web server...")
    # Start Flask app in a background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    logging.info("Starting Discord bot with retry logic...")
    try:
        asyncio.run(start_bot_with_retry())
    except KeyboardInterrupt:
        logging.info("Application stopped by user")
    except Exception as e:
        logging.error(f"Application crashed: {e}")

if __name__ == "__main__":
    main()
