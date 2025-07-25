import discord
import logging

class PermissionManager:
    def __init__(self, bot):
        self.bot = bot

    def has_staff_role(self, member, staff_role_id):
        """Check if member has the staff role."""
        if not staff_role_id:
            return False
        
        # Check if member has the specific staff role
        for role in member.roles:
            if role.id == staff_role_id:
                return True
        
        # Also allow administrators
        return member.guild_permissions.administrator

    async def restrict_channel_permissions(self, channel, ticket_holder, staff_member, staff_role):
        """Restrict channel permissions efficiently - only remove send_messages from staff role and give individual permission to claimer."""
        # Store original permissions for restoration
        original_permissions = {}
        
        try:
            # Store original staff role permissions if they had any
            staff_role_had_perms = staff_role in channel.overwrites
            if staff_role_had_perms:
                staff_perms = channel.overwrites_for(staff_role)
                original_permissions['staff_role'] = {
                    'view_channel': staff_perms.view_channel,
                    'send_messages': staff_perms.send_messages,
                    'read_message_history': staff_perms.read_message_history
                }
            else:
                original_permissions['staff_role'] = None
            
            # Store original staff member permissions if they had any
            staff_member_had_perms = staff_member in channel.overwrites
            if staff_member_had_perms:
                member_perms = channel.overwrites_for(staff_member)
                original_permissions['staff_member'] = {
                    'view_channel': member_perms.view_channel,
                    'send_messages': member_perms.send_messages,
                    'read_message_history': member_perms.read_message_history
                }
            else:
                original_permissions['staff_member'] = None
            
            # Remove send_messages permission from staff role but keep view access
            current_staff_perms = channel.overwrites_for(staff_role)
            await channel.set_permissions(
                staff_role,
                view_channel=True,  # Ensure staff can still view
                send_messages=False,  # Remove send permission
                read_message_history=True  # Ensure staff can read history
            )
            
            # Give individual send permission to the staff member who claimed
            await channel.set_permissions(
                staff_member,
                send_messages=True,
                view_channel=True,
                read_message_history=True
            )
            
            logging.info(f"Efficiently restricted permissions for channel {channel.id} - removed staff role send_messages, added individual permission for {staff_member.id}")
            return str(original_permissions)  # Convert to string for storage
            
        except Exception as e:
            logging.error(f"Error restricting channel permissions: {e}")
            raise

    async def restore_channel_permissions(self, channel, original_permissions_str):
        """Restore original channel permissions efficiently."""
        try:
            # Parse the original permissions string back to dict
            import ast
            original_permissions = ast.literal_eval(original_permissions_str)
            
            # Get current overwrites to identify the staff role and member to restore
            current_overwrites = channel.overwrites
            
            # Find and restore staff role permissions
            for target, overwrite in current_overwrites.items():
                if isinstance(target, discord.Role):
                    # Check if this role had original permissions stored
                    if 'staff_role' in original_permissions:
                        staff_role_perms = original_permissions['staff_role']
                        if staff_role_perms:
                            # Restore original permissions
                            await channel.set_permissions(
                                target,
                                view_channel=staff_role_perms.get('view_channel'),
                                send_messages=staff_role_perms.get('send_messages'),
                                read_message_history=staff_role_perms.get('read_message_history')
                            )
                        else:
                            # Remove override if role didn't have permissions originally
                            await channel.set_permissions(target, overwrite=None)
                        break
            
            # Find and restore staff member permissions
            for target, overwrite in current_overwrites.items():
                if isinstance(target, discord.Member):
                    # Check if this member had original permissions stored
                    if 'staff_member' in original_permissions:
                        staff_member_perms = original_permissions['staff_member']
                        if staff_member_perms:
                            # Restore original permissions
                            await channel.set_permissions(
                                target,
                                view_channel=staff_member_perms.get('view_channel'),
                                send_messages=staff_member_perms.get('send_messages'),
                                read_message_history=staff_member_perms.get('read_message_history')
                            )
                        else:
                            # Remove override if member didn't have permissions originally
                            await channel.set_permissions(target, overwrite=None)
                        break
            
            logging.info(f"Efficiently restored permissions for channel {channel.id}")
            
        except Exception as e:
            logging.error(f"Error restoring channel permissions: {e}")
            raise

    async def restore_permissions(self, channel, original_permissions):
        """Wrapper method to maintain compatibility."""
        return await self.restore_channel_permissions(channel, original_permissions)

    async def add_officer_permissions(self, channel, officer_role):
        """Add officer role permissions to channel."""
        try:
            await channel.set_permissions(
                officer_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
            logging.info(f"Added officer permissions for role {officer_role.id} in channel {channel.id}")
        except Exception as e:
            logging.error(f"Error adding officer permissions: {e}")
            raise

    async def add_user_to_ticket(self, channel, user, permission_level='view'):
        """Add a user to a ticket with specified permissions."""
        try:
            if permission_level == 'view':
                await channel.set_permissions(
                    user,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                )
            elif permission_level == 'interact':
                await channel.set_permissions(
                    user,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
            
            logging.info(f"Added user {user.id} to ticket {channel.id} with {permission_level} permissions")
            
        except Exception as e:
            logging.error(f"Error adding user to ticket: {e}")
            raise

    async def remove_user_from_ticket(self, channel, user):
        """Remove a user from a ticket."""
        try:
            await channel.set_permissions(user, overwrite=None)
            logging.info(f"Removed user {user.id} from ticket {channel.id}")
            
        except Exception as e:
            logging.error(f"Error removing user from ticket: {e}")
            raise

    def get_ticket_participants(self, channel):
        """Get list of users who can access the ticket channel."""
        participants = []
        
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member) and overwrite.view_channel:
                participants.append(target)
        
        return participants

    async def set_channel_read_only(self, channel, read_only=True):
        """Set channel to read-only mode."""
        try:
            everyone_role = channel.guild.default_role
            
            if read_only:
                await channel.set_permissions(
                    everyone_role,
                    send_messages=False,
                    add_reactions=False
                )
            else:
                await channel.set_permissions(
                    everyone_role,
                    send_messages=None,
                    add_reactions=None
                )
            
            logging.info(f"Set channel {channel.id} read-only: {read_only}")
            
        except Exception as e:
            logging.error(f"Error setting channel read-only mode: {e}")
            raise
