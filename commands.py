import discord
from discord.ext import commands
import logging

class TicketCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_ticket_channel(self, channel):
        ticket_keywords = ['ticket', 'support', 'help']
        name = channel.name.lower()
        if any(k in name for k in ticket_keywords):
            return True
        if channel.category:
            return any(k in channel.category.name.lower() for k in ticket_keywords)
        return False

    def _is_allowed_category(self, ctx):
        allowed_ids = self.bot.database.get_allowed_categories(ctx.guild.id)
        return ctx.channel.category and ctx.channel.category.id in allowed_ids

    @commands.command(name='category')
    @commands.has_permissions(manage_channels=True)
    async def add_allowed_category(self, ctx, category: discord.CategoryChannel):
        """Add an allowed ticket category (admins only)."""
        self.bot.database.add_allowed_category(ctx.guild.id, category.id)
        await ctx.send(f"✅ Added **{category.name}** to allowed ticket categories.")

    @commands.command(name='claim')
    async def claim_ticket(self, ctx, member: discord.Member = None):
        """Claim a ticket if in allowed category and channel."""
        staff_role_id, _, _ = self.bot.database.get_guild_config(ctx.guild.id)

        if not staff_role_id:
            await ctx.send("❌ No staff role configured. Use ?readperms @role to set it.")
            return

        if not self.bot.permission_manager.has_staff_role(ctx.author, staff_role_id):
            await ctx.send("❌ You don't have permission to claim tickets.")
            return

        if not self._is_allowed_category(ctx):
            await ctx.send("❌ This command can only be used in allowed ticket categories.")
            return

        if not self._is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in ticket channels.")
            return

        # Get the ticket holder (if none provided)
        if not member:
            member = await self.bot.utils.find_ticket_owner(ctx.channel)
            if not member:
                await ctx.send("❌ Could not find the ticket owner. Mention them or set with `?setuser`.")
                return

        # Check if a ticket is already claimed
        if self.bot.timeout_manager.is_channel_claimed(ctx.channel.id):
            await ctx.send("❌ This ticket is already being handled.")
            return

        # Set claim and track it
        self.bot.database.set_ticket_holder(ctx.channel.id, member.id, ctx.author.id)
        self.bot.database.create_claim(ctx.guild.id, ctx.channel.id, ctx.author.id)
        self.bot.timeout_manager.start_timeout(ctx.channel, ctx.author, member)

        await ctx.send(f"✅ Ticket claimed by {ctx.author.mention}. Ticket holder: {member.mention}")

    @commands.command(name='setuser')
    async def set_ticket_user(self, ctx, member: discord.Member):
        """Set the ticket owner manually if missing."""
        if not self._is_allowed_category(ctx) or not self._is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command must be used in a valid ticket channel and category.")
            return

        self.bot.database.set_ticket_holder(ctx.channel.id, member.id, ctx.author.id)
        await ctx.send(f"✅ Set {member.mention} as the ticket holder for this channel.")

    @commands.command(name='listcategories')
    @commands.has_permissions(manage_channels=True)
    async def list_categories(self, ctx):
        """List all allowed ticket categories for this server."""
        ids = self.bot.database.get_allowed_categories(ctx.guild.id)
        if not ids:
            await ctx.send("ℹ️ No allowed categories have been configured yet.")
            return

        names = []
        for cid in ids:
            category = ctx.guild.get_channel(cid)
            if isinstance(category, discord.CategoryChannel):
                names.append(f"- {category.name} (`{cid}`)")
            else:
                names.append(f"- Unknown Category (`{cid}`)")

        await ctx.send("✅ **Allowed ticket categories:**\n" + "\n".join(names))

async def setup(bot):
    await bot.add_cog(TicketCommands(bot))
