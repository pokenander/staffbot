import discord
import logging
from datetime import datetime

class LeaderboardManager:
    def __init__(self, bot):
        self.bot = bot

    async def get_leaderboard_embed(self, guild: discord.Guild, period: str = "total", page: int = 1) -> discord.Embed:
        """Generate leaderboard embed for a specific period with pagination."""

        period_names = {
            "daily": "Daily",
            "weekly": "Weekly", 
            "total": "All Time"
        }

        period_name = period_names.get(period, "All Time")

        # Get leaderboard data
        leaderboard_data = self.bot.database.get_leaderboard(guild.id, period)

        if not leaderboard_data:
            embed = discord.Embed(
                title=f"🏆 {period_name} Ticket Claims Leaderboard",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            embed.description = "No claims recorded yet."
            embed.add_field(
                name="Getting Started",
                value="Use `?claim @user` to start claiming tickets and earning points!",
                inline=False
            )
            return embed

        # Pagination settings
        per_page = 10
        total_pages = (len(leaderboard_data) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))

        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        page_data = leaderboard_data[start_index:end_index]

        embed = discord.Embed(
            title=f"🏆 {period_name} Ticket Claims Leaderboard",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        leaderboard_text = ""
        medals = ["🥇", "🥈", "🥉"]

        for i, (user_id, claims) in enumerate(page_data):
            actual_rank = start_index + i + 1
            try:
                user = guild.get_member(user_id) or await self.bot.fetch_user(user_id)
                username = user.mention
            except Exception:
                username = f"User {user_id}"

            medal = medals[actual_rank - 1] if actual_rank <= 3 else f"{actual_rank}."
            leaderboard_text += f"{medal} {username} - {claims} claims\n"

        embed.description = leaderboard_text

        footer_text = f"Page {page}/{total_pages} • " if total_pages > 1 else ""

        if period == "daily":
            footer_text += "Daily leaderboard resets at 00:00 GMT+2"
        elif period == "weekly":
            footer_text += "Weekly leaderboard resets every Monday at 00:00 GMT+2"
        else:
            footer_text += "All-time statistics • Use ?help for more commands"

        embed.set_footer(text=footer_text)

        return embed

    async def send_leaderboard(self, channel: discord.TextChannel, period: str = "total", page: int = 1):
        """Send leaderboard to a channel with pagination."""
        try:
            embed = await self.get_leaderboard_embed(channel.guild, period, page)
            await channel.send(embed=embed)
        except Exception as e:
            logging.error(f"Error sending leaderboard to {channel.id}: {e}")
            await channel.send("❌ Error generating leaderboard.")

    async def send_daily_leaderboard(self, channel: discord.TextChannel, page: int = 1):
        """Send daily leaderboard."""
        await self.send_leaderboard(channel, "daily", page)

    async def send_weekly_leaderboard(self, channel: discord.TextChannel, page: int = 1):
        """Send weekly leaderboard."""
        await self.send_leaderboard(channel, "weekly", page)

    async def send_total_leaderboard(self, channel: discord.TextChannel, page: int = 1):
        """Send total leaderboard."""
        await self.send_leaderboard(channel, "total", page)

    async def send_combined_leaderboard(self, channel: discord.TextChannel):
        """Send all three leaderboards in one message."""
        try:
            embed = discord.Embed(
                title="🏆 Ticket Claims Leaderboards",
                description="Top performers across all time periods",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )

            periods = [("daily", "📅 Daily"), ("weekly", "📊 Weekly"), ("total", "🌟 All Time")]

            for period, period_emoji in periods:
                leaderboard_data = self.bot.database.get_leaderboard(channel.guild.id, period)

                if leaderboard_data:
                    field_text = ""
                    for i, (user_id, claims) in enumerate(leaderboard_data[:5]):
                        try:
                            user = channel.guild.get_member(user_id) or await self.bot.fetch_user(user_id)
                            username = user.mention
                        except Exception:
                            username = f"User {user_id}"
                        medal = "🥇🥈🥉"[i] if i < 3 else f"{i + 1}."
