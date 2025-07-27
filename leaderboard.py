import discord
import logging
from datetime import datetime
from typing import List, Tuple

class Leaderboard:
    def __init__(self, bot, database):
        self.bot = bot
        self.database = database

    async def send_leaderboard(self, channel, period: str = "total", page: int = 1):
        """Send leaderboard to a channel with pagination."""
        try:
            guild_id = channel.guild.id
            guild = channel.guild
            
            # Get leaderboard data
            leaderboard_data = self.database.get_leaderboard(guild_id, period)
            
            if not leaderboard_data:
                embed = discord.Embed(
                    title=f"🏆 {period.title()} Leaderboard",
                    description="No data available yet. Start claiming tickets to appear on the leaderboard!",
                    color=discord.Color.blue()
                )
                await channel.send(embed=embed)
                return

            # Pagination
            items_per_page = 10
            total_pages = (len(leaderboard_data) + items_per_page - 1) // items_per_page
            page = max(1, min(page, total_pages))
            
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_data = leaderboard_data[start_idx:end_idx]

            # Create embed
            embed = discord.Embed(
                title=f"🏆 {period.title()} Leaderboard - Page {page}/{total_pages}",
                color=discord.Color.gold()
            )

            # Add leaderboard entries with user display names
            for i, (user_id, claims) in enumerate(page_data, start=start_idx + 1):
                # Get user object and create display name
                user = guild.get_member(user_id) or self.bot.get_user(user_id)
                if user:
                    user_display = f"@{user.display_name}"
                else:
                    user_display = f"User {user_id}"
                
                # Determine medal/emoji
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                else:
                    medal = f"{i}."

                embed.add_field(
                    name=f"{medal} {user_display}",
                    value=f"{claims} claims",
                    inline=False
                )

            # Add pagination info
            if total_pages > 1:
                embed.set_footer(text=f"Page {page}/{total_pages} • Use ?lb {period} {page+1} for next page")
            else:
                embed.set_footer(text=f"Total entries: {len(leaderboard_data)}")

            await channel.send(embed=embed)
            logging.info(f"Leaderboard sent to channel {channel.id}, period: {period}, page: {page}")

        except Exception as e:
            logging.error(f"Error sending leaderboard: {e}")
            await channel.send("❌ An error occurred while fetching the leaderboard.")

    async def send_user_stats(self, channel, user: discord.Member):
        """Send detailed statistics for a specific user."""
        try:
            guild_id = channel.guild.id
            
            # Get user's stats from database
            leaderboard_data = self.database.get_leaderboard(guild_id, "total")
            
            # Find user in leaderboard
            user_stats = None
            user_rank = None
            
            for i, (user_id, claims) in enumerate(leaderboard_data, 1):
                if user_id == user.id:
                    user_stats = claims
                    user_rank = i
                    break
            
            if user_stats is None:
                embed = discord.Embed(
                    title=f"📊 Statistics for {user.display_name}",
                    description="No ticket claims found for this user.",
                    color=discord.Color.blue()
                )
                await channel.send(embed=embed)
                return

            # Get detailed stats for all periods
            daily_data = self.database.get_leaderboard(guild_id, "daily")
            weekly_data = self.database.get_leaderboard(guild_id, "weekly")
            
            daily_claims = 0
            weekly_claims = 0
            
            for user_id, claims in daily_data:
                if user_id == user.id:
                    daily_claims = claims
                    break
                    
            for user_id, claims in weekly_data:
                if user_id == user.id:
                    weekly_claims = claims
                    break

            # Create stats embed
            embed = discord.Embed(
                title=f"📊 Statistics for @{user.display_name}",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="🏆 Total Claims",
                value=f"{user_stats} (Rank #{user_rank})",
                inline=True
            )
            
            embed.add_field(
                name="📅 Daily Claims",
                value=str(daily_claims),
                inline=True
            )
            
            embed.add_field(
                name="📊 Weekly Claims", 
                value=str(weekly_claims),
                inline=True
            )
            
            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            embed.set_footer(text=f"Statistics generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")

            await channel.send(embed=embed)
            logging.info(f"User stats sent for {user.id} in channel {channel.id}")

        except Exception as e:
            logging.error(f"Error sending user stats: {e}")
            await channel.send("❌ An error occurred while fetching user statistics.")

    async def update_leaderboard_channels(self):
        """Update all configured leaderboard channels."""
        try:
            channels = self.database.get_all_leaderboard_channels()
            
            for guild_id, channel_id in channels:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                        
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        logging.warning(f"Leaderboard channel {channel_id} not found in guild {guild_id}")
                        continue
                    
                    await self.send_leaderboard(channel, "daily")
                    logging.info(f"Updated leaderboard for guild {guild_id}")
                    
                except Exception as e:
                    logging.error(f"Error updating leaderboard for guild {guild_id}: {e}")
                    
        except Exception as e:
            logging.error(f"Error in update_leaderboard_channels: {e}")

    async def send_leaderboard_summary(self, channel):
        """Send a summary of all leaderboard periods."""
        try:
            guild_id = channel.guild.id
            guild = channel.guild
            
            # Get data for all periods
            daily_data = self.database.get_leaderboard(guild_id, "daily")
            weekly_data = self.database.get_leaderboard(guild_id, "weekly") 
            total_data = self.database.get_leaderboard(guild_id, "total")
            
            embed = discord.Embed(
                title="🏆 Leaderboard Summary",
                color=discord.Color.gold()
            )
            
            # Daily top 3
            daily_top = daily_data[:3] if daily_data else []
            daily_text = ""
            for i, (user_id, claims) in enumerate(daily_top, 1):
                user = guild.get_member(user_id) or self.bot.get_user(user_id)
                if user:
                    user_display = f"@{user.display_name}"
                else:
                    user_display = f"User {user_id}"
                medal = ["🥇", "🥈", "🥉"][i-1]
                daily_text += f"{medal} {user_display} - {claims}\n"
            
            if daily_text:
                embed.add_field(name="📅 Daily Top 3", value=daily_text, inline=True)
            
            # Weekly top 3
            weekly_top = weekly_data[:3] if weekly_data else []
            weekly_text = ""
            for i, (user_id, claims) in enumerate(weekly_top, 1):
                user = guild.get_member(user_id) or self.bot.get_user(user_id)
                if user:
                    user_display = f"@{user.display_name}"
                else:
                    user_display = f"User {user_id}"
                medal = ["🥇", "🥈", "🥉"][i-1]
                weekly_text += f"{medal} {user_display} - {claims}\n"
            
            if weekly_text:
                embed.add_field(name="📊 Weekly Top 3", value=weekly_text, inline=True)
            
            # Total top 3
            total_top = total_data[:3] if total_data else []
            total_text = ""
            for i, (user_id, claims) in enumerate(total_top, 1):
                user = guild.get_member(user_id) or self.bot.get_user(user_id)
                if user:
                    user_display = f"@{user.display_name}"
                else:
                    user_display = f"User {user_id}"
                medal = ["🥇", "🥈", "🥉"][i-1]
                total_text += f"{medal} {user_display} - {claims}\n"
            
            if total_text:
                embed.add_field(name="🏆 All-Time Top 3", value=total_text, inline=True)
            
            if not any([daily_text, weekly_text, total_text]):
                embed.description = "No leaderboard data available yet!"
            
            embed.set_footer(text=f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            await channel.send(embed=embed)
            logging.info(f"Leaderboard summary sent to channel {channel.id}")
            
        except Exception as e:
            logging.error(f"Error sending leaderboard summary: {e}")
            await channel.send("❌ An error occurred while fetching the leaderboard summary.")
