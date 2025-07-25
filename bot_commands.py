import discord
from discord.ext import commands
import logging
from config import CLAIM_MESSAGE

class TicketCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_ticket_channel(self, channel):
        """Check if channel is a ticket channel."""
        ticket_keywords = ['ticket', 'support', 'help']
        channel_name = channel.name.lower()
        
        # Check if channel name contains ticket-related keywords
        for keyword in ticket_keywords:
            if keyword in channel_name:
                return True
        
        # Check channel category
        if channel.category:
            category_name = channel.category.name.lower()
            for keyword in ticket_keywords:
                if keyword in category_name:
                    return True
        
        return False

    @commands.command(name='lb', aliases=['leaderboard'])
    async def show_leaderboard(self, ctx, period: str = "total", page: int = 1):
        """Show leaderboard. Usage: ?lb [daily/weekly/total] [page]"""
    
        try:
        if period.lower() == "daily":
            await self.bot.leaderboard_manager.send_daily_leaderboard(ctx.channel, page)
        elif period.lower() == "weekly":
            await self.bot.leaderboard_manager.send_weekly_leaderboard(ctx.channel, page)
        else:
            await self.bot.leaderboard_manager.send_total_leaderboard(ctx.channel, page)
    except Exception as e:
        logging.error(f"Error showing leaderboard: {e}")
        await ctx.send("❌ An error occurred while fetching the leaderboard.")

    @commands.command(name='leaderboardchannel')
    @commands.has_permissions(administrator=True)
    async def set_leaderboard_channel(self, ctx, channel: discord.TextChannel = None):
        """Set channel for automatic leaderboard posting. Usage: ?leaderboardchannel #channel"""
    
    if not channel:
        channel = ctx.channel
    
    self.bot.database.set_guild_config(ctx.guild.id, leaderboard_channel_id=channel.id)
    await ctx.send(f"✅ Leaderboard channel set to {channel.mention}")
    logging.info(f"Leaderboard channel set to {channel.id} in guild {ctx.guild.id}")

    @commands.command(name='testtimeout')
    @commands.has_permissions(administrator=True)
    async def test_timeout(self, ctx, minutes: int = 1):
        """Test timeout functionality. Usage: ?testtimeout [minutes]"""
    
    if not self._is_ticket_channel(ctx.channel):
        await ctx.send("❌ This command can only be used in ticket channels.")
        return
    
    # Check if there's an active timeout
    timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
    if not timeout_info:
        await ctx.send("❌ This ticket is not currently claimed.")
        return
    
    # Modify timeout for testing
    import datetime
    new_timeout = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    
    await ctx.send(f"⏰ Timeout set to {minutes} minute(s) for testing.")
    logging.info(f"Test timeout set for {minutes} minutes in channel {ctx.channel.id}")

    @commands.command(name='readperms')
    @commands.has_permissions(administrator=True)
    async def set_staff_role(self, ctx, role: discord.Role = None, role_type: str = None):
        """Set staff or officer role. Usage: ?readperms @role or ?readperms @role officer"""
    
    if not role:
        await ctx.send("❌ Please mention a role.\n**Usage:** `?readperms @role` or `?readperms @role officer`")
        return
    
    if role_type and role_type.lower() == "officer":
        # Set officer role
        self.bot.database.set_guild_config(ctx.guild.id, officer_role_id=role.id)
        await ctx.send(f"✅ Officer role set to **{role.name}**")
        logging.info(f"Officer role set to {role.id} in guild {ctx.guild.id}")
    else:
        # Set staff role (default)
        self.bot.database.set_guild_config(ctx.guild.id, staff_role_id=role.id)
        await ctx.send(f"✅ Staff role set to **{role.name}**")
        logging.info(f"Staff role set to {role.id} in guild {ctx.guild.id}")

    @commands.command(name='addcat')
    @commands.has_permissions(administrator=True) 
    async def add_category(self, ctx, *, category_name=None):
        """Add a category where ticket commands can be used. Usage: ?addcat category-name"""
    
    if not category_name:
        await ctx.send("❌ Please specify a category name.\n**Usage:** `?addcat category-name`")
        return
    
    # Find category by name
    category = discord.utils.get(ctx.guild.categories, name=category_name)
    
    if not category:
        await ctx.send(f"❌ Category '{category_name}' not found.")
        return
        
    # Add category to allowed list
    self.bot.database.add_allowed_category(ctx.guild.id, category.id)
    await ctx.send(f"✅ Category **{category.name}** added to allowed ticket categories.")
    logging.info(f"Category {category.id} added to guild {ctx.guild.id}")

    @commands.command(name='removecat')
    @commands.has_permissions(administrator=True)
    async def remove_category(self, ctx, category: discord.CategoryChannel = None):
        """Remove a category from allowed ticket categories. Usage: ?removecat #category"""
        
        if not category:
            await ctx.send("❌ Please mention a category.\n**Usage:** `?removecat #category-name`")
            return
            
        # Remove category from allowed list
        self.bot.database.remove_allowed_category(ctx.guild.id, category.id)
        await ctx.send(f"✅ Category **{category.name}** removed from allowed ticket categories.")
        logging.info(f"Category {category.id} removed from guild {ctx.guild.id}")

    @commands.command(name='help')
    async def help_command(self, ctx):
        """Show available commands."""
        
        embed = discord.Embed(title="🎫 Ticket Bot Commands", color=0x00ff00)
        
        # Admin commands
        admin_commands = """
        `?readperms @role` - Set staff role
        `?readperms officer @role` - Set officer role  
        `?addcat #category` - Add allowed ticket category
        `?removecat #category` - Remove allowed category
        """
        embed.add_field(name="🔧 Admin Commands", value=admin_commands, inline=False)
        
        # Ticket commands
        ticket_commands = """
        `?claim @user` - Claim a ticket
        `?unclaim` - Unclaim current ticket
        `?reclaim @user` - Reclaim timed out ticket
        `?ticketholder @user` - Set ticket holder
        `?officer` - Invite officers to help
        """
        embed.add_field(name="🎫 Ticket Commands", value=ticket_commands, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name='claim')
    async def claim_ticket(self, ctx, member: discord.Member = None):
        """Claim a ticket and restrict permissions. Usage: ?claim @user"""
        
        # Get guild configuration
        staff_role_id, _, allowed_category_id, _ = self.bot.database.get_guild_config(ctx.guild.id)
        
        if not staff_role_id:
            await ctx.send("❌ No staff role configured. Use `?readperms @role` to set it.")
            return
        
        # Check if user has staff role
        if not self.bot.permission_manager.has_staff_role(ctx.author, staff_role_id):
            await ctx.send("❌ You don't have permission to claim tickets.")
            return
        
        # Check if category restriction is set and channel is in allowed category
        allowed_category_ids = self.bot.database.get_allowed_categories(ctx.guild.id)
        if allowed_category_ids and (not ctx.channel.category or ctx.channel.category.id not in allowed_category_ids):
            await ctx.send("❌ This command can only be used in the configured ticket category.")
            return
        
        # Check if this is a ticket channel
        if not self._is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in ticket channels.")
            return
        
        # Check if member was mentioned
        if not member:
            await ctx.send("❌ Please mention the ticket holder.\n**Usage:** `?claim @user`")
            return
        
        # Check if mentioned user is a bot
        if member.bot:
            await ctx.send("❌ You cannot claim a ticket for a bot.")
            return
        
        # Check if ticket is already claimed
        timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
        if timeout_info:
            await ctx.send("❌ This ticket has already been claimed.")
            return
        
        # Set the ticket holder in database
        self.bot.database.set_ticket_holder(ctx.channel.id, member.id, ctx.author.id)
        
        # Get staff role
        staff_role = ctx.guild.get_role(staff_role_id)
        if not staff_role:
            await ctx.send("❌ Staff role not found.")
            return
        
        try:
            # Restrict channel permissions
            original_permissions = await self.bot.permission_manager.restrict_channel_permissions(
                ctx.channel, member, ctx.author, staff_role
            )
            
            # Create claim record
            self.bot.database.create_claim(ctx.guild.id, ctx.channel.id, ctx.author.id)
            
            # Save timeout information
            self.bot.database.save_timeout(
                ctx.channel.id, ctx.author.id, member.id, original_permissions
            )
            
            # Start timeout monitoring
            await self.bot.timeout_manager.start_timeout_monitoring(ctx.channel.id)
            
            # Send claim message
            claim_msg = CLAIM_MESSAGE.format(username=ctx.author.display_name)
            await ctx.send(claim_msg)
            
            logging.info(f"Ticket {ctx.channel.id} claimed by {ctx.author.id} for {member.id}")
            
        except Exception as e:
            logging.error(f"Error claiming ticket {ctx.channel.id}: {e}")
            await ctx.send("❌ An error occurred while claiming the ticket.")

    @commands.command(name='reclaim')
    async def reclaim_ticket(self, ctx, member: discord.Member = None):
        """Reclaim a ticket that has timed out. Usage: ?reclaim @user"""
        
        # Get guild configuration
        staff_role_id, _, allowed_category_id, _ = self.bot.database.get_guild_config(ctx.guild.id)
        
        if not staff_role_id:
            await ctx.send("❌ No staff role configured. Use `?readperms @role` to set it.")
            return
        
        # Check if user has staff role
        if not self.bot.permission_manager.has_staff_role(ctx.author, staff_role_id):
            await ctx.send("❌ You don't have permission to claim tickets.")
            return
        
        # Check if category restriction is set and channel is in allowed category
        if allowed_category_id and (not ctx.channel.category or ctx.channel.category.id != allowed_category_id):
            await ctx.send("❌ This command can only be used in the configured ticket category.")
            return
        
        # Check if this is a ticket channel
        if not self._is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in ticket channels.")
            return
        
        # Check if member was mentioned
        if not member:
            # Try to get existing ticket holder
            ticket_holder_id = self.bot.database.get_ticket_holder(ctx.channel.id)
            if ticket_holder_id:
                member = ctx.guild.get_member(ticket_holder_id)
            
            if not member:
                await ctx.send("❌ Please mention the ticket holder.\n**Usage:** `?reclaim @user`")
                return
        
        # Check if mentioned user is a bot
        if member.bot:
            await ctx.send("❌ You cannot claim a ticket for a bot.")
            return
        
        # Check if ticket is currently claimed (should not be for reclaim)
        timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
        if timeout_info:
            await ctx.send("❌ This ticket is currently claimed. Use `?claim` for new claims or wait for timeout.")
            return
        
        # Set/update the ticket holder in database
        self.bot.database.set_ticket_holder(ctx.channel.id, member.id, ctx.author.id)
        
        # Get staff role
        staff_role = ctx.guild.get_role(staff_role_id)
        if not staff_role:
            await ctx.send("❌ Staff role not found.")
            return
        
        try:
            # Restrict channel permissions
            original_permissions = await self.bot.permission_manager.restrict_channel_permissions(
                ctx.channel, member, ctx.author, staff_role
            )
            
            # Create claim record
            self.bot.database.create_claim(ctx.guild.id, ctx.channel.id, ctx.author.id)
            
            # Save timeout information
            self.bot.database.save_timeout(
                ctx.channel.id, ctx.author.id, member.id, original_permissions
            )
            
            # Start timeout monitoring
            await self.bot.timeout_manager.start_timeout_monitoring(ctx.channel.id)
            
            # Send reclaim message
            claim_msg = f"✅ **{ctx.author.display_name}** has reclaimed this ticket for **{member.display_name}**.\n\n⏰ Timeout will occur after **15 minutes** of inactivity."
            await ctx.send(claim_msg)
            
            logging.info(f"Ticket {ctx.channel.id} reclaimed by {ctx.author.id} for {member.id}")
            
        except Exception as e:
            logging.error(f"Error reclaiming ticket {ctx.channel.id}: {e}")
            await ctx.send("❌ An error occurred while reclaiming the ticket.")

    @commands.command(name='ticketholder')
    async def set_ticket_holder(self, ctx, member: discord.Member = None):
        """Set or change the ticket holder. Usage: ?ticketholder @user"""
        
        # Get guild configuration
        staff_role_id, _, allowed_category_id, _ = self.bot.database.get_guild_config(ctx.guild.id)
        
        if not staff_role_id:
            await ctx.send("❌ No staff role configured. Use `?readperms @role` to set it.")
            return
        
        # Check if user has staff role
        if not self.bot.permission_manager.has_staff_role(ctx.author, staff_role_id):
            await ctx.send("❌ You don't have permission to set ticket holders.")
            return
        
        # Check if category restriction is set and channel is in allowed category
        if allowed_category_id and (not ctx.channel.category or ctx.channel.category.id != allowed_category_id):
            await ctx.send("❌ This command can only be used in the configured ticket category.")
            return
        
        # Check if this is a ticket channel
        if not self._is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in ticket channels.")
            return
        
        # Check if member was mentioned
        if not member:
            await ctx.send("❌ Please mention the ticket holder.\n**Usage:** `?ticketholder @user`")
            return
        
        # Check if mentioned user is a bot
        if member.bot:
            await ctx.send("❌ You cannot set a bot as ticket holder.")
            return
        
        # Set the ticket holder in database
        self.bot.database.set_ticket_holder(ctx.channel.id, member.id, ctx.author.id)
        
        await ctx.send(f"✅ Ticket holder set to **{member.display_name}**.")
        logging.info(f"Ticket holder for {ctx.channel.id} set to {member.id} by {ctx.author.id}")

    @commands.command(name='unclaim')
    async def unclaim_ticket(self, ctx):
        """Unclaim a ticket and restore permissions."""
        
        # Check if ticket is claimed
        timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
        if not timeout_info:
            await ctx.send("❌ This ticket is not currently claimed.")
            return
        
        claimer_id = timeout_info[0]
        
        # Check if user is the claimer or has manage channels permission
        if ctx.author.id != claimer_id and not ctx.author.guild_permissions.manage_channels:
            await ctx.send("❌ Only the ticket claimer or administrators can unclaim tickets.")
            return
        
        try:
            # Get original permissions and officer usage status
            original_permissions = timeout_info[5]
            officer_used = timeout_info[6] if len(timeout_info) > 6 else False
            ticket_holder_id = timeout_info[1]
            
            # Restore permissions
            await self.bot.permission_manager.restore_permissions(ctx.channel, original_permissions)
            
            # Award points based on new criteria - only award if not already awarded by ?officer command
            if officer_used:
                # Points already awarded when ?officer was used - no additional points needed
                logging.info(f"Ticket {ctx.channel.id} unclaimed - points already awarded via officer command")
            else:
                # Award point to claimer only - they completed the ticket manually
                self.bot.database.award_score(ctx.guild.id, claimer_id)
                logging.info(f"Ticket {ctx.channel.id} unclaimed - point awarded to claimer {claimer_id}")
            
            # Complete claim
            self.bot.database.complete_claim(ctx.channel.id)
            
            # Remove timeout tracking
            self.bot.database.remove_timeout(ctx.channel.id)
            await self.bot.timeout_manager.stop_timeout_monitoring(ctx.channel.id)
            
            await ctx.send("✅ Ticket unclaimed and permissions restored.")
            logging.info(f"Ticket {ctx.channel.id} unclaimed by {ctx.author.id}")
            
        except Exception as e:
            logging.error(f"Error unclaiming ticket {ctx.channel.id}: {e}")
            await ctx.send("❌ An error occurred while unclaiming the ticket.")

    @commands.command(name='officer')
    async def invite_officers(self, ctx):
        """Invite officers to help with the ticket."""
        
        # Get guild configuration
        _, officer_role_id, allowed_category_id, _ = self.bot.database.get_guild_config(ctx.guild.id)
        
        # Check if category restriction is set and channel is in allowed category
        if allowed_category_id and (not ctx.channel.category or ctx.channel.category.id != allowed_category_id):
            await ctx.send("❌ This command can only be used in the configured ticket category.")
            return
        
        # Check if this is a ticket channel
        if not self._is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in ticket channels.")
            return
        
        # Check if ticket is claimed
        timeout_info = self.bot.database.get_timeout_info(ctx.channel.id)
        if not timeout_info:
            await ctx.send("❌ This ticket is not currently claimed.")
            return
        
        claimer_id = timeout_info[0]
        
        # Check if user is the claimer
        if ctx.author.id != claimer_id:
            await ctx.send("❌ Only the ticket claimer can invite officers.")
            return
        
        # Check if officer role is configured
        if not officer_role_id:
            await ctx.send("❌ No officer role configured. Ask an administrator to set it up.")
            return
        
        # Get officer role
        officer_role = ctx.guild.get_role(officer_role_id)
        if not officer_role:
            await ctx.send("❌ Officer role not found.")
            return
        
        try:
            # Add officer permissions to channel
            await self.bot.permission_manager.add_officer_permissions(ctx.channel, officer_role)
            
            # Mark officer as used in database
            self.bot.database.mark_officer_used(ctx.channel.id)
            
            # Award points to claimer immediately when officers are called
            self.bot.database.award_score(ctx.guild.id, claimer_id)
            
            await ctx.send(f"✅ **Officers** ({officer_role.mention}) have been invited to help with this ticket!\n"
                          f"🎯 **{ctx.author.display_name}** has been awarded **1 point** for escalating the ticket.")
            
            logging.info(f"Officers invited to ticket {ctx.channel.id} by {ctx.author.id} - point awarded")
            
        except Exception as e:
            logging.error(f"Error inviting officers to ticket {ctx.channel.id}: {e}")
            await ctx.send("❌ An error occurred while inviting officers.")

    @commands.command(name='addcategory')
    @commands.has_permissions(manage_channels=True)
    async def add_allowed_category(self, ctx, category: discord.CategoryChannel):
    self.bot.database.add_allowed_category(ctx.guild.id, category.id)
    await ctx.send(f"✅ Added allowed category: **{category.name}**")

    @commands.command(name='removecategory')
    @commands.has_permissions(manage_channels=True)
    async def remove_allowed_category(self, ctx, category: discord.CategoryChannel):
    self.bot.database.remove_allowed_category(ctx.guild.id, category.id)
    await ctx.send(f"❌ Removed category: **{category.name}**")

    @commands.command(name='listcategories')
    @commands.has_permissions(manage_channels=True)
    async def list_allowed_categories(self, ctx):
    ids = self.bot.database.get_allowed_categories(ctx.guild.id)
    if not ids:
        return await ctx.send("ℹ️ No allowed categories set.")
    names = []
    for cat_id in ids:
        cat = ctx.guild.get_channel(cat_id)
        names.append(f"- {cat.name if cat else f'Unknown ({cat_id})'}")
    await ctx.send("📂 Allowed Ticket Categories:\n" + "\n".join(names))

    @commands.command(name='test')
    @commands.has_permissions(administrator=True)
    async def test_timeout(self, ctx, channel_id: int = None):
        """Admin-only command to accelerate timeout for testing. Usage: ?test <channel_id>"""
        
        if channel_id is None:
            channel_id = ctx.channel.id
        
        # Check if timeout info exists for the channel
        timeout_info = self.bot.database.get_timeout_info(channel_id)
        if not timeout_info:
            await ctx.send(f"❌ No active timeout found for channel {channel_id}.")
            return
        
        try:
            # Set accelerated timeout (1 second) for this channel
            self.bot.timeout_manager.set_test_timeout(channel_id, 1)
            
            # Restart timeout monitoring with accelerated timer
            await self.bot.timeout_manager.stop_timeout_monitoring(channel_id)
            await self.bot.timeout_manager.start_timeout_monitoring(channel_id)
            
            await ctx.send(f"⚡ **Test mode activated** for channel <#{channel_id}>!\n"
                          f"Timeout accelerated to **1 second** for testing purposes.")
            
            logging.info(f"Test timeout activated for channel {channel_id} by admin {ctx.author.id}")
            
        except Exception as e:
            logging.error(f"Error setting test timeout for channel {channel_id}: {e}")
            await ctx.send("❌ An error occurred while setting test timeout.")

    @commands.command(name='readperms')
    @commands.has_permissions(manage_roles=True)
    async def set_staff_role(self, ctx, role: discord.Role):
        """Set the staff role that can claim tickets. Usage: ?readperms @role"""
        
        self.bot.database.set_staff_role(ctx.guild.id, role.id)
        await ctx.send(f"✅ Staff role set to **{role.name}**.")
        logging.info(f"Staff role set to {role.id} for guild {ctx.guild.id}")

    @commands.command(name='officerrole')
    @commands.has_permissions(manage_roles=True)
    async def set_officer_role(self, ctx, role: discord.Role):
        """Set the officer role for ticket escalation. Usage: ?officerrole @role"""
        
        self.bot.database.set_officer_role(ctx.guild.id, role.id)
        await ctx.send(f"✅ Officer role set to **{role.name}**.")
        logging.info(f"Officer role set to {role.id} for guild {ctx.guild.id}")

    @commands.command(name='category')
    @commands.has_permissions(manage_channels=True)
    async def set_allowed_category(self, ctx, category: discord.CategoryChannel):
        """Set the category where ticket commands can be used. Usage: ?category #category"""
        
        self.bot.database.set_allowed_category(ctx.guild.id, category.id)
        await ctx.send(f"✅ Ticket commands restricted to **{category.name}** category.")
        logging.info(f"Allowed category set to {category.id} for guild {ctx.guild.id}")

    @commands.command(name='leaderboardchannel')
    @commands.has_permissions(manage_channels=True)
    async def set_leaderboard_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel for automatic leaderboard updates. Usage: ?leaderboardchannel #channel"""
        
        if not channel:
            channel = ctx.channel
        
        self.bot.database.set_leaderboard_channel(ctx.guild.id, channel.id)
        await ctx.send(f"✅ Automatic leaderboard updates will be sent to {channel.mention}.")
        logging.info(f"Leaderboard channel set to {channel.id} for guild {ctx.guild.id}")

    @commands.command(name='lb', aliases=['leaderboard'])
    async def show_leaderboard(self, ctx, period: str = "total", page: str = "1"):
        """Show leaderboard with pagination. Usage: ?lb [daily|weekly|total] [page]"""
        
        valid_periods = ["daily", "weekly", "total"]
        if period.lower() not in valid_periods:
            await ctx.send(f"❌ Invalid period. Use: {', '.join(valid_periods)}")
            return
        
        # Parse page number
        try:
            page_num = int(page)
            if page_num < 1:
                page_num = 1
        except (ValueError, TypeError):
            page_num = 1
        
        await self.bot.leaderboard_manager.send_leaderboard(ctx.channel, period.lower(), page_num)

    @commands.command(name='help')
    async def help_command(self, ctx):
        """Show bot help information."""
        
        embed = discord.Embed(
            title="🎫 Ticket Bot Commands",
            description="Manage tickets and track leaderboards",
            color=discord.Color.blue()
        )
        
        # Ticket commands
        embed.add_field(
            name="🎯 Ticket Commands",
            value=(
                "`?claim @user` - Claim a ticket for a user\n"
                "`?reclaim @user` - Reclaim a timed-out ticket\n"
                "`?unclaim` - Unclaim your ticket\n"
                "`?officer` - Invite officers to help\n"
                "`?ticketholder @user` - Set ticket holder"
            ),
            inline=False
        )
        
        # Leaderboard commands
        embed.add_field(
            name="🏆 Leaderboard Commands",
            value=(
                "`?lb daily` - Show daily leaderboard\n"
                "`?lb weekly` - Show weekly leaderboard\n"
                "`?lb total` - Show all-time leaderboard\n"
                "`?lb [period] [page]` - Show specific page (10 per page)"
            ),
            inline=False
        )
        
        # Admin commands
        embed.add_field(
            name="⚙️ Admin Commands",
            value=(
                "`?readperms @role` - Set staff role\n"
                "`?officerrole @role` - Set officer role\n"
                "`?category #category` - Set allowed category\n"
                "`?leaderboardchannel #channel` - Set leaderboard channel\n"
                "`?test <channel_id>` - Test timeout (admins only)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Information",
            value=(
                "• Timeouts occur after 15 minutes of inactivity\n"
                "• Points are awarded for successful ticket completion\n"
                "• Daily leaderboard resets at 00:00 GMT+2\n"
                "• Weekly leaderboard resets every Monday"
            ),
            inline=False
        )
        
        embed.set_footer(text="Need help? Contact your server administrators.")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TicketCommands(bot))
