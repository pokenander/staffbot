import discord
import logging
from datetime import datetime

class LeaderboardManager:
    def __init__(self, bot):
        self.bot = bot

    async def send_leaderboard(self, channel: discord.TextChannel, period: str = "total", page: int = 1):
        """Send leaderboard with pagination."""
        try:
            guild_id = channel.guild.id
            leaderboard_data = self.bot.database.get_leaderboard(guild_id, period)
            
            if not leaderboard_data:
                embed = discord.Embed(
                    title=f"🏆 {period.title()} Leaderboard",
                    description="No data available yet!",
                    color=discord.Color.blue()
                )
                await channel.send(embed=embed)
                return

            # Pagination
            items_per_page = 10
            total_pages = (len(leaderboard_data) - 1) // items_per_page + 1
            
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages

            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_data = leaderboard_data[start_idx:end_idx]

            # Create embed
            embed = discord.Embed(
                title=f"🏆 {period.title()} Leaderboard - Page {page}/{total_pages}",
                color=discord.Color.gold()
            )

            leaderboard_text = ""
            for i, (user_id, score) in enumerate(page_data):
                try:
                    user = self.bot.get_user(user_id)
                    if user:
                        username = user.display_name
                    else:
                        username = f"User {user_id}"
                    
                    rank = start_idx + i + 1
                    medal = "🥇🥈🥉"[i] if i < 3 and page == 1 else f"{rank}."
                    leaderboard_text += f"{medal} **{username}** - {score} claims\n"
                
                except Exception as e:
                    logging.error(f"Error processing leaderboard entry: {e}")
                    continue

            if not leaderboard_text:
                leaderboard_text = "No valid entries found."

            embed.description = leaderboard_text

            # Add pagination info if multiple pages
            if total_pages > 1:
                embed.set_footer(text=f"Page {page} of {total_pages}")

            await channel.send(embed=embed)

        except Exception as e:
            logging.error(f"Error sending leaderboard: {e}")
            await channel.send("❌ Error retrieving leaderboard data.")

    async def send_daily_leaderboard(self, channel: discord.TextChannel, page: int = 1):
        """Send daily leaderboard."""
        await self.send_leaderboard(channel, "daily", page)

    async def send_weekly_leaderboard(self, channel: discord.TextChannel, page: int = 1):
        """Send weekly leaderboard."""
        await self.send_leaderboard(channel, "weekly", page)

    async def send_total_leaderboard(self, channel: discord.TextChannel, page: int = 1):
        """Send total leaderboard."""
        await self.send_leaderboard(channel, "total", page)

    async def update_leaderboards(self):
        """Update leaderboards in all configured channels."""
        try:
            leaderboard_channels = self.bot.database.get_all_leaderboard_channels()
            
            for guild_id, channel_id in leaderboard_channels:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue
                    
                    # Send updated leaderboard
                    await self.send_leaderboard(channel, "total")
                    
                except Exception as e:
                    logging.error(f"Error updating leaderboard for guild {guild_id}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error in update_leaderboards: {e}")

    async def reset_daily_scores(self):
        """Reset daily leaderboard scores."""
        try:
            self.bot.database.reset_daily_leaderboard()
            logging.info("Daily leaderboard scores reset")
            
            # Optionally notify leaderboard channels
            leaderboard_channels = self.bot.database.get_all_leaderboard_channels()
            for guild_id, channel_id in leaderboard_channels:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        channel = guild.get_channel(channel_id)
                        if channel:
                            embed = discord.Embed(
                                title="🔄 Daily Reset",
                                description="Daily leaderboard has been reset!",
                                color=discord.Color.green()
                            )
                            await channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Error sending daily reset notification: {e}")
                    
        except Exception as e:
            logging.error(f"Error resetting daily scores: {e}")

    async def reset_weekly_scores(self):
        """Reset weekly leaderboard scores."""
        try:
            self.bot.database.reset_weekly_leaderboard()
            logging.info("Weekly leaderboard scores reset")
            
            # Optionally notify leaderboard channels
            leaderboard_channels = self.bot.database.get_all_leaderboard_channels()
            for guild_id, channel_id in leaderboard_channels:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        channel = guild.get_channel(channel_id)
                        if channel:
                            embed = discord.Embed(
                                title="🔄 Weekly Reset",
                                description="Weekly leaderboard has been reset!",
                                color=discord.Color.orange()
                            )
                            await channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Error sending weekly reset notification: {e}")
                    
        except Exception as e:
            logging.error(f"Error resetting weekly scores: {e}")

    def get_user_rank(self, guild_id: int, user_id: int, period: str = "total"):
        """Get a user's rank in the leaderboard."""
        try:
            leaderboard_data = self.bot.database.get_leaderboard(guild_id, period)
            
            for rank, (lb_user_id, score) in enumerate(leaderboard_data, 1):
                if lb_user_id == user_id:
                    return rank, score
            
            return None, 0  # User not in leaderboard
            
        except Exception as e:
            logging.error(f"Error getting user rank: {e}")
            return None, 0

    async def send_user_stats(self, channel: discord.TextChannel, user: discord.Member):
        """Send statistics for a specific user."""
        try:
            guild_id = channel.guild.id
            user_id = user.id
            
            # Get user's rank and score for each period
            daily_rank, daily_score = self.get_user_rank(guild_id, user_id, "daily")
            weekly_rank, weekly_score = self.get_user_rank(guild_id, user_id, "weekly")
            total_rank, total_score = self.get_user_rank(guild_id, user_id, "total")
            
            embed = discord.Embed(
                title=f"📊 Stats for {user.display_name}",
                color=discord.Color.blue()
            )
            
            # Add fields for each period
            embed.add_field(
                name="📅 Daily",
                value=f"Rank: {daily_rank or 'Unranked'}\nClaims: {daily_score}",
                inline=True
            )
            
            embed.add_field(
                name="📆 Weekly", 
                value=f"Rank: {weekly_rank or 'Unranked'}\nClaims: {weekly_score}",
                inline=True
            )
            
            embed.add_field(
                name="🏆 Total",
                value=f"Rank: {total_rank or 'Unranked'}\nClaims: {total_score}",
                inline=True
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.timestamp = datetime.now()
            
            await channel.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Error sending user stats: {e}")
            await channel.send("❌ Error retrieving user statistics.")
