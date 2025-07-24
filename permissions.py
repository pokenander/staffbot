import discord
import json
import logging
from typing import List, Optional, Dict, Any

class PermissionManager:
    def __init__(self, bot):
        self.bot = bot
    
    async def get_ticket_holder(self, channel: discord.TextChannel) -> Optional[discord.Member]:
        """Get the ticket holder from database (manually set by staff)."""
        try:
            # Check if ticket holder is already stored in database
            ticket_holder_id = self.bot.database.get_ticket_holder(channel.id)
            if ticket_holder_id:
                member = channel.guild.get_member(ticket_holder_id)
                if member:
                    logging.info(f"Found ticket holder from database: {member.display_name}")
                    return member
                else:
                    logging.warning(f"Stored ticket holder ID {ticket_holder_id} not found in guild")
            
            logging.warning(f"No ticket holder set for channel {channel.id}")
            return None
        except Exception as e:
            logging.error(f"Error getting ticket holder for {channel.id}: {e}")
            return None
    
    def has_staff_role(self, member: discord.Member, staff_role_id: int) -> bool:
        """Check if member has staff role or higher."""
        if not staff_role_id:
            return False
        
        staff_role = member.guild.get_role(staff_role_id)
        if not staff_role:
            return False
        
        # Check if member has staff role
        if staff_role in member.roles:
            return True
        
        # Check if member has higher role (administrator permissions)
        if member.guild_permissions.administrator:
            return True
        
        # Check if member has higher role by position
        for role in member.roles:
            if role.position > staff_role.position and not role.is_default():
                return True
        
        return False
    
    def get_higher_staff_roles(self, guild: discord.Guild, staff_role: discord.Role) -> List[discord.Role]:
        """Get all roles higher than the staff role in hierarchy."""
        higher_roles = []
        for role in guild.roles:
            if role.position > staff_role.position and not role.is_default():
                higher_roles.append(role)
        return higher_roles
    
    async def save_original_permissions(self, channel: discord.TextChannel) -> str:
        """Save the original channel permissions as JSON."""
        permissions_data = {}
        
        for target, overwrite in channel.overwrites.items():
            target_id = target.id
            target_type = "role" if isinstance(target, discord.Role) else "member"
            
            permissions_data[str(target_id)] = {
                "type": target_type,
                "allow": overwrite.pair()[0].value,
                "deny": overwrite.pair()[1].value
            }
        
        return json.dumps(permissions_data)
    
    async def restore_permissions(self, channel: discord.TextChannel, permissions_json: str):
        """Restore channel permissions from JSON data."""
        try:
            permissions_data = json.loads(permissions_json)
            
            # Clear all current overwrites
            for target in list(channel.overwrites.keys()):
                if isinstance(target, (discord.Role, discord.Member)):
                    await channel.set_permissions(target, overwrite=None)
            
            # Restore original permissions
            for target_id, perm_data in permissions_data.items():
                target_id = int(target_id)
                
                if perm_data["type"] == "role":
                    target = channel.guild.get_role(target_id)
                else:
                    target = channel.guild.get_member(target_id)
                
                if target and isinstance(target, (discord.Role, discord.Member)):
                    permissions = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(perm_data["allow"]),
                        discord.Permissions(perm_data["deny"])
                    )
                    
                    await channel.set_permissions(target, overwrite=permissions)
        
        except Exception as e:
            logging.error(f"Error restoring permissions for {channel.id}: {e}")
    
    async def restrict_channel_permissions(self, channel: discord.TextChannel, 
                                         ticket_holder: discord.Member,
                                         claimer: discord.Member,
                                         staff_role: discord.Role) -> str:
        """Restrict channel permissions and return original permissions JSON."""
        
        # Save original permissions
        original_permissions = await self.save_original_permissions(channel)
        
        try:
            # Get higher staff roles
            higher_roles = self.get_higher_staff_roles(channel.guild, staff_role)
            
            # Remove send message permissions for @everyone
            await channel.set_permissions(
                channel.guild.default_role,
                send_messages=False,
                view_channel=True  # Keep view permissions
            )
            
            # Remove send message permissions for staff role
            await channel.set_permissions(
                staff_role,
                send_messages=False,
                view_channel=True
            )
            
            # Allow ticket holder to send messages
            await channel.set_permissions(
                ticket_holder,
                send_messages=True,
                view_channel=True
            )
            
            # Allow claimer to send messages
            await channel.set_permissions(
                claimer,
                send_messages=True,
                view_channel=True
            )
            
            # Allow higher staff roles to send messages
            for role in higher_roles:
                await channel.set_permissions(
                    role,
                    send_messages=True,
                    view_channel=True
                )
            
            logging.info(f"Restricted permissions for channel {channel.id}")
            
        except Exception as e:
            logging.error(f"Error restricting permissions for {channel.id}: {e}")
        
        return original_permissions
    
    async def add_officer_permissions(self, channel: discord.TextChannel, officer_role: discord.Role):
        """Add send message permissions for officer role."""
        try:
            await channel.set_permissions(
                officer_role,
                send_messages=True,
                view_channel=True
            )
            logging.info(f"Added officer permissions for {officer_role.name} in {channel.id}")
        except Exception as e:
            logging.error(f"Error adding officer permissions: {e}")
