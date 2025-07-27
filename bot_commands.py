import discord
from discord.ext import commands
import logging
from datetime import datetime, timedelta
import asyncio

class BotCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='help')
    async def help_command(self, ctx):
        """Display all available commands with proper formatting."""
        embed = discord.Embed(
            title="🎫 Ticket Bot Commands",
            description="Manage tickets and track leaderboards",
            color=discord.Color.blue()
        )

        # Ticket Commands
        ticket_commands = (
            "?claim @user - Claim a ticket for a user\n"
            "?reclaim @user - Reclaim a timed-out ticket\n"
            "?unclaim - Unclaim your ticket\n"
            "?officer - Invite officers to help\n"
            "?ticketholder @user - Set ticket holder"
        )
        embed.add_field(
            name="🎫 Ticket Commands",
            value=ticket_commands,
            inline=False
        )

        # Leaderboard Commands
        leaderboard_commands = (
            "?lb daily - Show daily leaderboard\n"
            "?lb weekly - Show weekly leaderboard\n"
            "?lb total - Show all-time leaderboard\n"
            "?lb [period] [page] - Show specific page (10 per page)"
        )
        embed.add_field(
            name="🏆 Leaderboard Commands",
            value=leaderboard_commands,
            inline=False
        )

        # Admin Commands
        admin_commands = (
            "?readperms @role - Set staff role\n"
            "?officerrole @role - Set officer role\n"
            "?category #category - Set allowed category\n"
            "?leaderboardchannel #channel - Set leaderboard channel\n"
            "?test <channel_id> - Test timeout (admins only)"
        )
        embed.add_field(
            name="⚙️ Admin Commands",
            value=admin_commands,
            inline=False
        )

        # Information
        information = (
            "• Timeouts occur after 15 minutes of inactivity\n"
            "• Points are awarded for successful ticket completion\n"
            "• Daily leaderboard resets at 00:00 GMT+2\n"
            "• Weekly leaderboard resets every Monday"
        )
        embed.add_field(
            name="ℹ️ Information",
            value=information,
            inline=False
        )

        embed.set_footer(text="Need help? Contact your server administrators.")
        await ctx.send(embed=embed)

    @commands.command(name='claim')
    async def claim_ticket(self, ctx, user: discord.Member = None):
        """Claim a ticket for yourself or another user."""
        try:
            # Get guild configuration
            staff_role_id, officer_role_id, allowed_category_id, leaderboard_channel_id = self.bot.database.get_guild_config(ctx.guild.id)
            
            if not staff_role_id:
                await ctx.send("❌ Staff role not configured. Use `?readperms @role` to set it.")
                return

            # Check if user has staff role
            if not self.bot.permissions.has_staff_role(ctx.author, staff_role_id):
                await ctx.send("❌ You don't have permission to use this command.")
                return

            # Check if in allowed category
            if allowed_category_id and ctx.channel.category_id != allowed_category_id:
                # Also check allowed categories list
                allowed_categories = self.bot.database.get_allowed_categories(ctx.guild.id)
                if ctx.channel.category_id not in allowed_categories:
                    await ctx.send("❌ This command can only be used in allowed ticket categories.")
                    return

            # FIX #1: CHECK FOR EXISTING ACTIVE CLAIM - Prevent duplicate claims
            existing_claim = self.bot.database.get_active_claim(ctx.channel.id)
            if existing_claim:
                claimer_id = existing_claim[0]
                claimer = ctx.guild.get_member(claimer_id)
                claimer_mention = claimer.mention if claimer else f"<@{claimer_id}>"
                await ctx.send(f"❌ This ticket is already claimed by {claimer_mention}. Use `?unclaim` to release it first.")
                return

            # Get staff role
            staff_role = ctx.guild.get_role(staff_role_id)
            if not staff_role:
                await ctx.send("❌ Staff role not found.")
                return

            # Set ticket holder
            if user:
                ticket_holder = user
                self.bot.database.set_ticket_holder(ctx.channel.id, user.id, ctx.author.id)
            else:
                # Get existing ticket holder or use command author
                holder_id = self.bot.database.get_ticket_holder(ctx.channel.id)
                if holder_id:
                    ticket_holder = ctx.guild.get_member(holder_id)
                    if not ticket_holder:
                        await ctx.send("❌ Previous ticket holder not found. Please specify a user.")
                        return
                else:
                    ticket_holder = ctx.author
                    self.bot.database.set_ticket_holder(ctx.channel.id, ctx.author.id, ctx.author.id)

            # Create claim record
            self.bot.database.create_claim(ctx.guild.id, ctx.channel.id, ctx.author.id)

            # Restrict permissions
            original_permissions = await self.bot.permissions.restrict_channel_permissions(
                ctx.channel, ticket_holder, ctx.author, staff_role
            )

            # Save timeout info
            self.bot.database.save_timeout(
                ctx.channel.id, ctx.author.id, ticket_holder.id, original_permissions
            )

            # Send confirmation
            embed = discord.Embed(
                title="✅ Ticket Claimed",
                description=f"**Claimer:** {ctx.author.mention}\n**Ticket Holder:** {ticket_holder.mention}",
                color=discord.Color.green()
            )
            embed.add_field(
                name="⏰ Timeout Warning",
                value="15 minutes of inactivity will trigger automatic timeout.",
                inline=False
            )
            await ctx.send(embed=embed)

            logging.info(f"Ticket claimed by {ctx.author.id} for holder {ticket_holder.id} in channel {ctx.channel.id}")

        except Exception as e:
            logging.error(f"Error in claim command: {e}")
            await ctx.send("❌ An error occurred while claiming the ticket.")

    @commands.command(name='unclaim')
    async def unclaim_ticket(self, ctx):
        """Release a ticket claim."""
        try:
            # Get timeout info
            timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
            if not timeout_info:
                await ctx.send("❌ No active claim found for this channel.")
                return

            claimer_id, ticket_holder_id, claim_time, last_staff_msg, last_holder_msg, original_permissions, officer_used = timeout_info

            # Check if user is the claimer or has admin permissions
            if ctx.author.id != claimer_id and not ctx.author.guild_permissions.administrator:
                await ctx.send("❌ You can only unclaim tickets you have claimed.")
                return

            # Restore permissions
            await self.bot.permissions.restore_channel_permissions(ctx.channel, original_permissions)

            # Complete the claim (successful completion) - FIXED: removed duplicate call
            self.bot.database.complete_claim(ctx.channel.id, timeout_occurred=False, officer_used=officer_used)

            # Remove timeout info
            self.bot.database.remove_timeout(ctx.channel.id)

            # Send confirmation
            embed = discord.Embed(
                title="✅ Ticket Unclaimed",
                description="Permissions restored and claim completed successfully.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

            logging.info(f"Ticket unclaimed by {ctx.author.id} in channel {ctx.channel.id}")

        except Exception as e:
            logging.error(f"Error in unclaim command: {e}")
            await ctx.send("❌ An error occurred while unclaiming the ticket.")

    @commands.command(name='reclaim')
    async def reclaim_ticket(self, ctx, user: discord.Member = None):
        """Reclaim a timed-out ticket."""
        try:
            # Get guild configuration
            staff_role_id, officer_role_id, allowed_category_id, leaderboard_channel_id = self.bot.database.get_guild_config(ctx.guild.id)
            
            if not staff_role_id:
                await ctx.send("❌ Staff role not configured.")
                return

            # Check if user has staff role
            if not self.bot.permissions.has_staff_role(ctx.author, staff_role_id):
                await ctx.send("❌ You don't have permission to use this command.")
                return

            # Get timeout info to check if there was a timeout
            timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
            if not timeout_info:
                await ctx.send("❌ No timeout found for this channel.")
                return

            claimer_id, ticket_holder_id, claim_time, last_staff_msg, last_holder_msg, original_permissions, officer_used = timeout_info

            # Get ticket holder
            if user:
                ticket_holder = user
                self.bot.database.set_ticket_holder(ctx.channel.id, user.id, ctx.author.id)
            else:
                ticket_holder = ctx.guild.get_member(ticket_holder_id)
                if not ticket_holder:
                    await ctx.send("❌ Original ticket holder not found. Please specify a user.")
                    return

            # Get staff role
            staff_role = ctx.guild.get_role(staff_role_id)
            if not staff_role:
                await ctx.send("❌ Staff role not found.")
                return

            # Create new claim record
            self.bot.database.create_claim(ctx.guild.id, ctx.channel.id, ctx.author.id)

            # Restrict permissions again
            new_original_permissions = await self.bot.permissions.restrict_channel_permissions(
                ctx.channel, ticket_holder, ctx.author, staff_role
            )

            # Update timeout info
            self.bot.database.save_timeout(
                ctx.channel.id, ctx.author.id, ticket_holder.id, new_original_permissions
            )

            # Send confirmation
            embed = discord.Embed(
                title="✅ Ticket Reclaimed",
                description=f"**New Claimer:** {ctx.author.mention}\n**Ticket Holder:** {ticket_holder.mention}",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)

            logging.info(f"Ticket reclaimed by {ctx.author.id} for holder {ticket_holder.id} in channel {ctx.channel.id}")

        except Exception as e:
            logging.error(f"Error in reclaim command: {e}")
            await ctx.send("❌ An error occurred while reclaiming the ticket.")

    @commands.command(name='holder', aliases=['ticketholder'])
    async def set_ticket_holder(self, ctx, user: discord.Member):
        """Set the ticket holder for this channel."""
        try:
            # Get guild configuration
            staff_role_id, officer_role_id, allowed_category_id, leaderboard_channel_id = self.bot.database.get_guild_config(ctx.guild.id)
            
            if not staff_role_id:
                await ctx.send("❌ Staff role not configured.")
                return

            # Check if user has staff role
            if not self.bot.permissions.has_staff_role(ctx.author, staff_role_id):
                await ctx.send("❌ You don't have permission to use this command.")
                return

            # Set ticket holder
            self.bot.database.set_ticket_holder(ctx.channel.id, user.id, ctx.author.id)

            embed = discord.Embed(
                title="✅ Ticket Holder Set",
                description=f"Ticket holder set to {user.mention}",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

            logging.info(f"Ticket holder set to {user.id} by {ctx.author.id} in channel {ctx.channel.id}")

        except Exception as e:
            logging.error(f"Error in holder command: {e}")
            await ctx.send("❌ An error occurred while setting ticket holder.")

    @commands.command(name='officer')
    async def officer_help(self, ctx):
        """Allow officers to help with tickets and complete them."""
        try:
            # Get guild configuration
            staff_role_id, officer_role_id, allowed_category_id, leaderboard_channel_id = self.bot.database.get_guild_config(ctx.guild.id)
            
            if not officer_role_id:
                await ctx.send("❌ Officer role not configured. Use `?officerrole @role` to set it.")
                return

            # Check if user has officer role
            if not self.bot.permissions.has_officer_role(ctx.author, officer_role_id):
                await ctx.send("❌ You don't have permission to use this command.")
                return

            # Get timeout info
            timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
            if not timeout_info:
                await ctx.send("❌ No active claim found for this channel.")
                return

            claimer_id, ticket_holder_id, claim_time, last_staff_msg, last_holder_msg, original_permissions, officer_used = timeout_info

            # Mark that officer was used
            self.bot.database.mark_officer_used(ctx.channel.id)

            # Restore permissions
            await self.bot.permissions.restore_channel_permissions(ctx.channel, original_permissions)

            # Complete the claim (officer forced completion) - FIXED: officer_used=True
            self.bot.database.complete_claim(ctx.channel.id, timeout_occurred=True, officer_used=True)

            # Remove timeout info
            self.bot.database.remove_timeout(ctx.channel.id)

            # Get claimer info for notification
            claimer = ctx.guild.get_member(claimer_id)
            claimer_mention = claimer.mention if claimer else f"<@{claimer_id}>"

            # Send confirmation
            embed = discord.Embed(
                title="👮‍♂️ Officer Intervention",
                description=f"Officer {ctx.author.mention} has completed this ticket.\n**Original Claimer:** {claimer_mention}",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="✅ Actions Taken",
                value="• Permissions restored\n• Claim marked as completed\n• Points awarded to original claimer",
                inline=False
            )
            await ctx.send(embed=embed)

            logging.info(f"Officer {ctx.author.id} completed ticket for claimer {claimer_id} in channel {ctx.channel.id}")

        except Exception as e:
            logging.error(f"Error in officer command: {e}")
            await ctx.send("❌ An error occurred while processing officer intervention.")

    @commands.command(name='lb', aliases=['leaderboard'])
    async def show_leaderboard(self, ctx, period: str = "total", page: int = 1):
        """Show leaderboard for different time periods."""
        try:
            if period.lower() not in ["daily", "weekly", "total"]:
                await ctx.send("❌ Invalid period. Use: daily, weekly, or total")
                return

            # Get leaderboard data
            leaderboard_data = self.bot.database.get_leaderboard(ctx.guild.id, period.lower())
            
            if not leaderboard_data:
                await ctx.send(f"📊 No data available for {period} leaderboard.")
                return

            # Pagination
            items_per_page = 10
            total_pages = (len(leaderboard_data) + items_per_page - 1) // items_per_page
            
            if page < 1 or page > total_pages:
                await ctx.send(f"❌ Invalid page number. Available pages: 1-{total_pages}")
                return

            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            page_data = leaderboard_data[start_index:end_index]

            # Create embed
            embed = discord.Embed(
                title=f"🏆 {period.capitalize()} Leaderboard",
                color=discord.Color.gold()
            )

            leaderboard_text = ""
            for i, (user_id, score) in enumerate(page_data, start=start_index + 1):
                user = ctx.guild.get_member(user_id)
                username = user.display_name if user else f"Unknown User ({user_id})"
                
                # Add medal emojis for top 3
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                else:
                    medal = f"{i}."
                
                leaderboard_text += f"{medal} **{username}** - {score} point{'s' if score != 1 else ''}\n"

            embed.description = leaderboard_text
            embed.set_footer(text=f"Page {page}/{total_pages} • Total entries: {len(leaderboard_data)}")

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Error in leaderboard command: {e}")
            await ctx.send("❌ An error occurred while fetching the leaderboard.")

    @commands.command(name='readperms')
    @commands.has_permissions(administrator=True)
    async def set_staff_role(self, ctx, role: discord.Role):
        """Set the staff role for ticket management."""
        try:
            self.bot.database.set_staff_role(ctx.guild.id, role.id)
            
            embed = discord.Embed(
                title="✅ Staff Role Set",
                description=f"Staff role set to {role.mention}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

            logging.info(f"Staff role set to {role.id} by {ctx.author.id} in guild {ctx.guild.id}")

        except Exception as e:
            logging.error(f"Error in readperms command: {e}")
            await ctx.send("❌ An error occurred while setting staff role.")

    @commands.command(name='officerrole')
    @commands.has_permissions(administrator=True)
    async def set_officer_role(self, ctx, role: discord.Role):
        """Set the officer role for ticket management."""
        try:
            self.bot.database.set_officer_role(ctx.guild.id, role.id)
            
            embed = discord.Embed(
                title="✅ Officer Role Set",
                description=f"Officer role set to {role.mention}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

            logging.info(f"Officer role set to {role.id} by {ctx.author.id} in guild {ctx.guild.id}")

        except Exception as e:
            logging.error(f"Error in officerrole command: {e}")
            await ctx.send("❌ An error occurred while setting officer role.")

    @commands.command(name='category')
    @commands.has_permissions(administrator=True)
    async def set_allowed_category(self, ctx, category: discord.CategoryChannel):
        """Set the allowed category for ticket commands."""
        try:
            self.bot.database.set_allowed_category(ctx.guild.id, category.id)
            
            embed = discord.Embed(
                title="✅ Allowed Category Set",
                description=f"Allowed category set to {category.name}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

            logging.info(f"Allowed category set to {category.id} by {ctx.author.id} in guild {ctx.guild.id}")

        except Exception as e:
            logging.error(f"Error in category command: {e}")
            await ctx.send("❌ An error occurred while setting allowed category.")

    @commands.command(name='leaderboardchannel')
    @commands.has_permissions(administrator=True)
    async def set_leaderboard_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for automatic leaderboard updates."""
        try:
            self.bot.database.set_leaderboard_channel(ctx.guild.id, channel.id)
            
            embed = discord.Embed(
                title="✅ Leaderboard Channel Set",
                description=f"Leaderboard channel set to {channel.mention}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

            logging.info(f"Leaderboard channel set to {channel.id} by {ctx.author.id} in guild {ctx.guild.id}")

        except Exception as e:
            logging.error(f"Error in leaderboardchannel command: {e}")
            await ctx.send("❌ An error occurred while setting leaderboard channel.")

    @commands.command(name='test')
    @commands.has_permissions(administrator=True)
    async def test_timeout(self, ctx, channel_id: int = None):
        """Test timeout functionality (admin only)."""
        try:
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    await ctx.send("❌ Channel not found.")
                    return
            else:
                channel = ctx.channel

            # Trigger timeout check for the specified channel
            timeout_task = self.bot.timeout_handler.check_single_timeout(channel.id)
            if timeout_task:
                await timeout_task
                await ctx.send(f"✅ Timeout check completed for {channel.mention}")
            else:
                await ctx.send(f"❌ No active timeout found for {channel.mention}")

        except Exception as e:
            logging.error(f"Error in test command: {e}")
            await ctx.send("❌ An error occurred while testing timeout.")

    # FIXED: Proper error handlers
    @set_staff_role.error
    @set_officer_role.error
    @set_allowed_category.error
    @set_leaderboard_channel.error
    @test_timeout.error
    async def admin_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need administrator permissions to use this command.")
        else:
            logging.error(f"Admin command error: {error}")
            await ctx.send("❌ An error occurred while executing the command.")

async def setup(bot):
    await bot.add_cog(BotCommands(bot))
