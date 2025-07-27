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

            # Check for existing active claim
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

            # FIXED: Complete the claim with proper officer_used parameter (no points awarded here)
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
        """Allow officer role to access the ticket temporarily and award points based on responsiveness."""
        try:
            # Get guild configuration
            staff_role_id, officer_role_id, allowed_category_id, leaderboard_channel_id = self.bot.database.get_guild_config(ctx.guild.id)
            
            if not officer_role_id:
                await ctx.send("❌ Officer role not configured. Use `?officerrole @role` to set it.")
                return

            # Check if user has staff role
            if not self.bot.permissions.has_staff_role(ctx.author, staff_role_id):
                await ctx.send("❌ You don't have permission to use this command.")
                return

            # Get officer role
            officer_role = ctx.guild.get_role(officer_role_id)
            if not officer_role:
                await ctx.send("❌ Officer role not found.")
                return

            # Add officer permissions
            await self.bot.permissions.add_officer_permissions(ctx.channel, officer_role)

            # Mark officer as used
            self.bot.database.mark_officer_used(ctx.channel.id)
            
            # NEW: Analyze conversation and award points based on responsiveness
            points_awarded = self.bot.database.analyze_conversation_and_award_points(ctx.channel.id)

            # Send response
            embed = discord.Embed(
                title="✅ Officer Access Granted",
                description=f"Officer role {officer_role.mention} can now access this ticket and help resolve it.",
                color=discord.Color.purple()
            )
            
            if points_awarded:
                embed.add_field(
                    name="🏆 Points Awarded",
                    value="The ticket claimer has been awarded a point for being responsive!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="ℹ️ No Points Awarded", 
                    value="No points awarded - claimer was not sufficiently responsive.",
                    inline=False
                )
                
            await ctx.send(embed=embed)

            logging.info(f"Officer access granted by {ctx.author.id} in channel {ctx.channel.id}")

        except Exception as e:
            logging.error(f"Error in officer command: {e}")
            await ctx.send("❌ An error occurred while granting officer access.")

    @commands.command(name='readperms', aliases=['staffrole'])
    @commands.has_permissions(manage_roles=True)
    async def set_staff_role(self, ctx, role: discord.Role):
        """Set the staff role for ticket management."""
        self.bot.database.set_staff_role(ctx.guild.id, role.id)
        
        embed = discord.Embed(
            title="✅ Staff Role Set",
            description=f"Staff role set to {role.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        logging.info(f"Staff role set to {role.id} for guild {ctx.guild.id}")

    @commands.command(name='officerrole')
    @commands.has_permissions(manage_roles=True)
    async def set_officer_role(self, ctx, role: discord.Role):
        """Set the officer role for tickets."""
        self.bot.database.set_officer_role(ctx.guild.id, role.id)
        
        embed = discord.Embed(
            title="✅ Officer Role Set",
            description=f"Officer role set to {role.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        logging.info(f"Officer role set to {role.id} for guild {ctx.guild.id}")

    @commands.command(name='addcat')
    @commands.has_permissions(manage_channels=True)
    async def add_allowed_category_by_name(self, ctx, *, category_name: str):
        """Add allowed category by name for ticket commands."""
        
        # Find category by name
        category = discord.utils.get(ctx.guild.categories, name=category_name)
        if not category:
            await ctx.send(f"❌ Category '{category_name}' not found.")
            return
        
        self.bot.database.add_allowed_category(ctx.guild.id, category.id)
        await ctx.send(f"✅ Added allowed category: **{category.name}**")
        logging.info(f"Allowed category {category.id} added for guild {ctx.guild.id}")

    @commands.command(name='addcategory')
    @commands.has_permissions(manage_channels=True)
    async def add_allowed_category(self, ctx, category: discord.CategoryChannel):
        """Add allowed category for ticket commands."""
        
        self.bot.database.add_allowed_category(ctx.guild.id, category.id)
        await ctx.send(f"✅ Added allowed category: **{category.name}**")

    @commands.command(name='category')
    @commands.has_permissions(manage_channels=True)
    async def set_allowed_category(self, ctx, category: discord.CategoryChannel):
        """Set the category where ticket commands can be used. Usage: ?category #category"""
        
        self.bot.database.set_allowed_category(ctx.guild.id, category.id)
        await ctx.send(f"✅ Ticket commands restricted to **{category.name}** category.")
        logging.info(f"Allowed category set to {category.id} for guild {ctx.guild.id}")

    @commands.command(name='leaderboardchannel', aliases=['lbchannel'])
    @commands.has_permissions(manage_channels=True)
    async def set_leaderboard_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for automatic leaderboard updates."""
        self.bot.database.set_leaderboard_channel(ctx.guild.id, channel.id)
        
        embed = discord.Embed(
            title="✅ Leaderboard Channel Set",
            description=f"Leaderboard updates will be sent to {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        logging.info(f"Leaderboard channel set to {channel.id} for guild {ctx.guild.id}")

    @commands.command(name='lb', aliases=['leaderboard'])
    async def show_leaderboard(self, ctx, period: str = "total", page: int = 1):
        """Show leaderboard. Usage: ?lb [daily/weekly/total] [page]"""
        valid_periods = ["daily", "weekly", "total"]
        
        if period not in valid_periods:
            # If first argument is a number, treat it as page for total leaderboard
            try:
                page = int(period)
                period = "total"
            except ValueError:
                await ctx.send(f"❌ Invalid period. Use: {', '.join(valid_periods)}")
                return

        await self.bot.leaderboard.send_leaderboard(ctx.channel, period, page)

    @commands.command(name='stats')
    async def show_user_stats(self, ctx, user: discord.Member = None):
        """Show detailed statistics for a user."""
        if not user:
            user = ctx.author
        
        await self.bot.leaderboard.send_user_stats(ctx.channel, user)

    @commands.command(name='resetdaily')
    @commands.has_permissions(administrator=True)
    async def reset_daily_leaderboard(self, ctx):
        """Reset daily leaderboard scores."""
        self.bot.database.reset_daily_leaderboard()
        
        embed = discord.Embed(
            title="✅ Daily Leaderboard Reset",
            description="All daily scores have been reset to 0.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        logging.info(f"Daily leaderboard reset by {ctx.author.id}")

    @commands.command(name='resetweekly')
    @commands.has_permissions(administrator=True)
    async def reset_weekly_leaderboard(self, ctx):
        """Reset weekly leaderboard scores."""
        self.bot.database.reset_weekly_leaderboard()
        
        embed = discord.Embed(
            title="✅ Weekly Leaderboard Reset",
            description="All weekly scores have been reset to 0.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        logging.info(f"Weekly leaderboard reset by {ctx.author.id}")

    @commands.command(name='timeout')
    @commands.has_permissions(administrator=True)
    async def manual_timeout(self, ctx, user: discord.Member):
        """Manually trigger timeout for a user (admin only)."""
        try:
            timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
            if not timeout_info:
                await ctx.send("❌ No active timeout found for this channel.")
                return

            # Trigger timeout through timeout manager
            await self.bot.timeout_manager.handle_timeout(ctx.channel.id)
            
            embed = discord.Embed(
                title="⏰ Manual Timeout Triggered",
                description=f"Timeout manually triggered for {user.mention}",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Error in manual timeout: {e}")
            await ctx.send("❌ An error occurred while triggering timeout.")

    @commands.command(name='test')
    @commands.has_permissions(administrator=True)
    async def test_timeout(self, ctx, channel_id: int = None):
        """Test timeout functionality (admin only)."""
        test_channel_id = channel_id or ctx.channel.id
        
        timeout_info = self.bot.database.get_timeout_info(test_channel_id)
        if not timeout_info:
            await ctx.send(f"❌ No active timeout found for channel {test_channel_id}.")
            return

        await ctx.send(f"🧪 Testing timeout for channel {test_channel_id}...")
        
        try:
            await self.bot.timeout_manager.handle_timeout(test_channel_id)
            await ctx.send("✅ Timeout test completed.")
        except Exception as e:
            await ctx.send(f"❌ Timeout test failed: {str(e)}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Track messages for timeout system."""
        if message.author.bot:
            return
        
        # Update last message time for timeout tracking
        self.bot.database.update_last_message(message.channel.id, message.author.id)

async def setup(bot):
    await bot.add_cog(BotCommands(bot))
