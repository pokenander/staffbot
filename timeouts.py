import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import discord

class TimeoutManager:
    def __init__(self, bot):
        self.bot = bot
        self.timeout_tasks: Dict[int, asyncio.Task] = {}
        self.test_timeouts: Dict[int, int] = {}  # Channel ID -> test timeout in seconds
    
    def set_test_timeout(self, channel_id: int, timeout_seconds: int):
        """Set a test timeout for a specific channel."""
        self.test_timeouts[channel_id] = timeout_seconds
        logging.info(f"Test timeout set for channel {channel_id}: {timeout_seconds} seconds")
    
    def get_timeout_duration(self, channel_id: int) -> int:
        """Get timeout duration for a channel (test or default)."""
        if channel_id in self.test_timeouts:
            duration = self.test_timeouts[channel_id]
            # Remove test timeout after use (one-time only)
            del self.test_timeouts[channel_id]
            return duration
        return 15 * 60  # Default 15 minutes in seconds
    
    async def start_timeout_monitoring(self, channel_id: int):
        """Start timeout monitoring for a channel."""
        if channel_id in self.timeout_tasks:
            self.timeout_tasks[channel_id].cancel()
        
        task = asyncio.create_task(self._monitor_timeout(channel_id))
        self.timeout_tasks[channel_id] = task
        logging.info(f"Started timeout monitoring for channel {channel_id}")
    
    async def stop_timeout_monitoring(self, channel_id: int):
        """Stop timeout monitoring for a channel."""
        if channel_id in self.timeout_tasks:
            self.timeout_tasks[channel_id].cancel()
            del self.timeout_tasks[channel_id]
            logging.info(f"Stopped timeout monitoring for channel {channel_id}")
    
    async def _monitor_timeout(self, channel_id: int):
        """Monitor timeout for a specific channel."""
        try:
            # Get timeout duration (test or default)
            timeout_seconds = self.get_timeout_duration(channel_id)
            check_interval = min(60, timeout_seconds / 10)  # Check more frequently for test timeouts
            
            while True:
                await asyncio.sleep(check_interval)
                
                timeout_info = self.bot.database.get_timeout_info(channel_id)
                if not timeout_info:
                    logging.info(f"No timeout info found for channel {channel_id}, stopping monitoring")
                    break
                
                (claimer_id, ticket_holder_id, claim_time_str, 
                 last_staff_str, last_holder_str, original_permissions, officer_used) = timeout_info
                
                # Parse datetime strings
                try:
                    claim_time = datetime.fromisoformat(claim_time_str.replace('Z', '+00:00'))
                    last_staff = datetime.fromisoformat(last_staff_str.replace('Z', '+00:00'))
                    last_holder = datetime.fromisoformat(last_holder_str.replace('Z', '+00:00'))
                except ValueError:
                    # Handle different datetime formats
                    claim_time = datetime.strptime(claim_time_str, '%Y-%m-%d %H:%M:%S.%f')
                    last_staff = datetime.strptime(last_staff_str, '%Y-%m-%d %H:%M:%S.%f')
                    last_holder = datetime.strptime(last_holder_str, '%Y-%m-%d %H:%M:%S.%f')
                
                now = datetime.now()
                timeout_delta = timedelta(seconds=timeout_seconds)
                
                # Calculate inactive times
                staff_inactive_time = now - last_staff
                holder_inactive_time = now - last_holder
                
                # Check if enough time has passed since claim for timeout to occur
                if (now - claim_time) >= timeout_delta:
                    # Determine who was last active by comparing timestamps
                    if last_staff > last_holder:
                        # Staff was last active, so ticket holder should be timed out
                        if holder_inactive_time >= timeout_delta:
                            await self._handle_holder_timeout(channel_id, claimer_id, ticket_holder_id, original_permissions, officer_used)
                            break
                    else:
                        # Ticket holder was last active (or they were active at same time), so staff should be timed out
                        if staff_inactive_time >= timeout_delta:
                            await self._handle_staff_timeout(channel_id, claimer_id, original_permissions, officer_used)
                            break
        
        except asyncio.CancelledError:
            logging.info(f"Timeout monitoring cancelled for channel {channel_id}")
        except Exception as e:
            logging.error(f"Error in timeout monitoring for channel {channel_id}: {e}")
        finally:
            # Clean up task reference
            if channel_id in self.timeout_tasks:
                del self.timeout_tasks[channel_id]
    
    async def _handle_staff_timeout(self, channel_id: int, claimer_id: int, original_permissions: str, officer_used: bool):
        """Handle staff timeout - restore permissions and allow reclaiming."""
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                logging.warning(f"Channel {channel_id} not found for staff timeout")
                return
            
            # Restore original permissions
            await self.bot.permission_manager.restore_permissions(channel, original_permissions)
            
            # Mark claim as completed with timeout (no score changes)
            self.bot.database.complete_claim(channel_id, timeout_occurred=True)
            
            # Remove timeout tracking
            self.bot.database.remove_timeout(channel_id)
            
            # Send timeout message so others know ticket is reclaimable
            await channel.send(
                f"⏰ **Staff Timeout:** <@{claimer_id}> did not respond within the timeout period.\n"
                "This ticket is now **available for claiming again** using `?reclaim @user`."
            )
            
            logging.info(f"Staff timeout handled for channel {channel_id} - permissions restored and notification sent")
            
        except Exception as e:
            logging.error(f"Error handling staff timeout for channel {channel_id}: {e}")
    
    async def _handle_holder_timeout(self, channel_id: int, claimer_id: int, ticket_holder_id: int, original_permissions: str, officer_used: bool):
        """Handle ticket holder timeout - ping holder, award claimer point, restore permissions."""
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                logging.warning(f"Channel {channel_id} not found for holder timeout")
                return
            
            # Restore original permissions so others can help
            await self.bot.permission_manager.restore_permissions(channel, original_permissions)
            
            # Award point to claimer since they were active and it's not their fault
            self.bot.database.complete_claim(channel_id, timeout_occurred=False)  # Award point
            
            # Remove timeout tracking
            self.bot.database.remove_timeout(channel_id)
            
            # Send friendly message pinging the ticket holder
            await channel.send(
                f"👋 Hey <@{ticket_holder_id}>, please continue the conversation about your ticket so we can help you as quickly as possible! "
                f"Our staff member <@{claimer_id}> is ready to assist you. 😊"
            )
            
            logging.info(f"Holder timeout handled for channel {channel_id} - ticket holder pinged, claimer awarded point, permissions restored")
            
        except Exception as e:
            logging.error(f"Error handling holder timeout for channel {channel_id}: {e}")
    
    def update_last_message(self, channel_id: int, user_id: int):
        """Update last message time for timeout tracking."""
        try:
            self.bot.database.update_last_message(channel_id, user_id)
            logging.debug(f"Updated last message time for user {user_id} in channel {channel_id}")
        except Exception as e:
            logging.error(f"Error updating last message time: {e}")
    
    async def cleanup_timeouts(self):
        """Cleanup any stale timeout tasks."""
        current_channels = set()
        
        # Get all active timeout channels from database
        for timeout_info in self.bot.database.get_all_active_timeouts():
            channel_id = timeout_info[0]
            current_channels.add(channel_id)
        
        # Cancel tasks for channels no longer in database
        for channel_id in list(self.timeout_tasks.keys()):
            if channel_id not in current_channels:
                await self.stop_timeout_monitoring(channel_id)
                logging.info(f"Cleaned up stale timeout task for channel {channel_id}")
