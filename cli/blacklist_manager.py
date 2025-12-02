"""
Blacklist Manager CLI Module

This module provides a CLI interface for managing the user blacklist,
including listing, adding, removing, checking, and clearing blacklisted users.
"""

import asyncio
from typing import Optional
from datetime import datetime
from rich.console import Console
from telegram_manager.blacklist import BlocklistManager
from cli.ui_components import UIComponents


class BlacklistManagerCLI:
    """CLI interface for blacklist management"""
    
    def __init__(self, blacklist_manager: BlocklistManager, console: Optional[Console] = None):
        """
        Initialize Blacklist Manager CLI
        
        Args:
            blacklist_manager: BlocklistManager instance
            console: Optional Rich Console instance
        """
        self.blacklist_manager = blacklist_manager
        self.console = console or Console()
        self.ui = UIComponents(self.console)
    
    async def list_blacklist(self):
        """
        Display blacklist in a formatted table
        
        Shows user ID, timestamp, reason, and session name for each entry.
        Requirements: 6.4
        """
        try:
            # Get all blacklist entries
            entries = await self.blacklist_manager.get_all()
            
            if not entries:
                self.ui.show_info("Blacklist is empty")
                return
            
            # Prepare table data
            rows = []
            for entry in entries:
                # Format timestamp as readable date
                timestamp = datetime.fromtimestamp(entry['timestamp'])
                formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                
                # Get session name or show "N/A"
                session = entry['session_name'] or "N/A"
                
                rows.append([
                    entry['user_id'],
                    formatted_time,
                    entry['reason'],
                    session
                ])
            
            # Display table
            columns = ["User ID", "Added At", "Reason", "Detected By"]
            self.ui.display_table("Blacklisted Users", columns, rows)
            
            # Show summary
            self.console.print(f"\n[bold]Total blacklisted users:[/bold] {len(entries)}")
            
        except Exception as e:
            self.ui.show_error(f"Failed to list blacklist: {e}")
    
    async def add_user(self):
        """
        Add user to blacklist with interactive prompt and validation
        
        Prompts for user ID and reason, validates input, and adds to blacklist.
        Requirements: 6.2
        """
        try:
            # Prompt for user ID
            user_id = await self.ui.prompt_input_async("Enter user ID or username to blacklist")
            
            if not user_id:
                self.ui.show_error("User ID cannot be empty")
                return
            
            # Remove @ prefix if present
            if user_id.startswith('@'):
                user_id = user_id[1:]
            
            # Check if already blacklisted
            is_blacklisted = await self.blacklist_manager.is_blacklisted(user_id)
            if is_blacklisted:
                self.ui.show_warning(f"User '{user_id}' is already blacklisted")
                
                # Ask if they want to update
                update = await self.ui.prompt_confirm_async("Do you want to update the entry?", default=False)
                if not update:
                    return
            
            # Prompt for reason
            reason_choices = [
                "manual",
                "spam",
                "abusive_behavior",
                "block_detected",
                "other"
            ]
            
            reason = await self.ui.prompt_choice_async(
                "Select reason for blacklisting:",
                reason_choices,
                default="manual"
            )
            
            # If "other", prompt for custom reason
            if reason == "other":
                reason = await self.ui.prompt_input_async("Enter custom reason", default="manual")
            
            # Add to blacklist
            await self.blacklist_manager.add(user_id, reason=reason, session_name=None)
            
            self.ui.show_success(f"User '{user_id}' added to blacklist (reason: {reason})")
            
        except KeyboardInterrupt:
            self.console.print("\n")
            self.ui.show_warning("Operation cancelled")
        except Exception as e:
            self.ui.show_error(f"Failed to add user to blacklist: {e}")
    
    async def remove_user(self):
        """
        Remove user from blacklist with interactive prompt and confirmation
        
        Prompts for user ID, confirms removal, and removes from blacklist.
        Requirements: 6.3
        """
        try:
            # Prompt for user ID
            user_id = await self.ui.prompt_input_async("Enter user ID or username to remove from blacklist")
            
            if not user_id:
                self.ui.show_error("User ID cannot be empty")
                return
            
            # Remove @ prefix if present
            if user_id.startswith('@'):
                user_id = user_id[1:]
            
            # Check if user is blacklisted
            is_blacklisted = await self.blacklist_manager.is_blacklisted(user_id)
            if not is_blacklisted:
                self.ui.show_warning(f"User '{user_id}' is not in the blacklist")
                return
            
            # Confirm removal
            confirm = await self.ui.prompt_confirm_async(
                f"Are you sure you want to remove '{user_id}' from the blacklist?",
                default=False
            )
            
            if not confirm:
                self.ui.show_info("Operation cancelled")
                return
            
            # Remove from blacklist
            removed = await self.blacklist_manager.remove(user_id)
            
            if removed:
                self.ui.show_success(f"User '{user_id}' removed from blacklist")
            else:
                self.ui.show_error(f"Failed to remove user '{user_id}' from blacklist")
            
        except KeyboardInterrupt:
            self.console.print("\n")
            self.ui.show_warning("Operation cancelled")
        except Exception as e:
            self.ui.show_error(f"Failed to remove user from blacklist: {e}")
    
    async def check_user(self):
        """
        Check if user is blacklisted and display status
        
        Prompts for user ID and displays whether they are blacklisted with details.
        Requirements: 6.4
        """
        try:
            # Prompt for user ID
            user_id = await self.ui.prompt_input_async("Enter user ID or username to check")
            
            if not user_id:
                self.ui.show_error("User ID cannot be empty")
                return
            
            # Remove @ prefix if present
            if user_id.startswith('@'):
                user_id = user_id[1:]
            
            # Check if blacklisted
            is_blacklisted = await self.blacklist_manager.is_blacklisted(user_id)
            
            if is_blacklisted:
                # Get all entries to find details
                entries = await self.blacklist_manager.get_all()
                entry = next((e for e in entries if e['user_id'] == user_id), None)
                
                if entry:
                    # Format timestamp
                    timestamp = datetime.fromtimestamp(entry['timestamp'])
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Display details in a panel
                    details = []
                    details.append(f"[bold red]✗ User is BLACKLISTED[/bold red]")
                    details.append(f"")
                    details.append(f"[bold]User ID:[/bold] {entry['user_id']}")
                    details.append(f"[bold]Added At:[/bold] {formatted_time}")
                    details.append(f"[bold]Reason:[/bold] {entry['reason']}")
                    details.append(f"[bold]Detected By:[/bold] {entry['session_name'] or 'N/A'}")
                    
                    content = "\n".join(details)
                    self.ui.show_panel(content, title=f"Blacklist Status: {user_id}", style="red")
                else:
                    self.ui.show_error(f"User '{user_id}' is blacklisted but details not found")
            else:
                self.ui.show_success(f"User '{user_id}' is NOT blacklisted")
            
        except KeyboardInterrupt:
            self.console.print("\n")
            self.ui.show_warning("Operation cancelled")
        except Exception as e:
            self.ui.show_error(f"Failed to check user status: {e}")
    
    async def clear_blacklist(self):
        """
        Clear entire blacklist with confirmation
        
        Prompts for confirmation and clears all entries from blacklist.
        Requirements: 6.5
        """
        try:
            # Get current count
            entries = await self.blacklist_manager.get_all()
            count = len(entries)
            
            if count == 0:
                self.ui.show_info("Blacklist is already empty")
                return
            
            # Show warning
            self.ui.show_warning(f"This will remove ALL {count} entries from the blacklist")
            
            # Confirm clearing
            confirm = await self.ui.prompt_confirm_async(
                "Are you sure you want to clear the entire blacklist? This cannot be undone.",
                default=False
            )
            
            if not confirm:
                self.ui.show_info("Operation cancelled")
                return
            
            # Double confirmation for safety
            double_confirm = await self.ui.prompt_confirm_async(
                "Please confirm again - this will permanently delete all blacklist entries.",
                default=False
            )
            
            if not double_confirm:
                self.ui.show_info("Operation cancelled")
                return
            
            # Clear blacklist
            removed_count = await self.blacklist_manager.clear()
            
            self.ui.show_success(f"Blacklist cleared - {removed_count} entries removed")
            
        except KeyboardInterrupt:
            self.console.print("\n")
            self.ui.show_warning("Operation cancelled")
        except Exception as e:
            self.ui.show_error(f"Failed to clear blacklist: {e}")
    
    async def show_menu(self):
        """
        Display blacklist management menu and handle user selection
        
        Requirements: 6.1, 7.2, 7.3
        """
        while True:
            self.console.print("\n[bold cyan]═══ Blacklist Management ═══[/bold cyan]\n")
            
            choices = [
                "List Blacklist",
                "Add User",
                "Remove User",
                "Check User",
                "Clear Blacklist",
                "Back to Main Menu"
            ]
            
            try:
                choice = await self.ui.prompt_choice_async("Select an option:", choices)
                
                if choice == "List Blacklist":
                    await self.list_blacklist()
                
                elif choice == "Add User":
                    await self.add_user()
                
                elif choice == "Remove User":
                    await self.remove_user()
                
                elif choice == "Check User":
                    await self.check_user()
                
                elif choice == "Clear Blacklist":
                    await self.clear_blacklist()
                
                elif choice == "Back to Main Menu":
                    break
                
            except KeyboardInterrupt:
                self.console.print("\n")
                break
            except Exception as e:
                self.ui.show_error(f"An error occurred: {e}")
                import traceback
                traceback.print_exc()
