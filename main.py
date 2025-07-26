import os
import asyncio
import logging
import threading
from flask import Flask
import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot test is running!'

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# Simple bot for testing
class TestBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
    
    async def on_ready(self):
        logging.info(f'✅ SUCCESS! Bot connected as {self.user}!')
        logging.info(f'✅ Bot ID: {self.user.id}')
        logging.info('✅ CONNECTION SUCCESSFUL - RATE LIMIT RESOLVED!')

async def test_connection():
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        logging.error("❌ DISCORD_TOKEN not found!")
        return
    
    logging.info(f"✅ Token found, length: {len(token)} characters")
    logging.info(f"✅ Token starts with: {token[:25]}...")
    
    bot = TestBot()
    
    try:
        logging.info("🔄 Attempting Discord connection...")
        await bot.start(token)
    except discord.LoginFailure:
        logging.error("❌ LOGIN FAILED - Invalid token!")
    except discord.HTTPException as e:
        if "429" in str(e):
            logging.error("❌ RATE LIMITED - Discord is blocking this IP")
            logging.error("❌ Try again in 1-2 hours, or try a different hosting provider")
        else:
            logging.error(f"❌ HTTP Error: {e}")
    except Exception as e:
        logging.error(f"❌ Unexpected error: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

def main():
    logging.info("🚀 Starting test bot...")
    
    # Start Flask
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Test Discord connection
    try:
        asyncio.run(test_connection())
    except KeyboardInterrupt:
        logging.info("Stopped by user")

if __name__ == "__main__":
    main()
