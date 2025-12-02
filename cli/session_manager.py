"""
Session Manager CLI Module

This module provides a CLI interface for managing Telegram sessions,
including listing sessions, reloading sessions, and viewing session details.
"""

import asyncio
from typing import Optional, Dict
from rich.console import Console
from telegram_manager.manager import TelegramSessionManager
from cli.ui_components import UIComponents


class SessionManagerCLI:
    """CLI interface for session management"""
    
    def __init__(self, session_manager: TelegramSessionManager, console: Optional[Console] = None):
        """
        Initialize Session Manager CLI
        
        Args:
            session_manager: TelegramSessionManager instance
            console: Optional Rich Console instance
        """
        self.session_manager = session_manager
        self.console = console or Console()
        self.ui = UIComponents(self.console)
    
    async def list_sessions(self):
        """
        Display all sessions in a formatted table
        
        Shows session name, phone number, connection status, and active operations.
        Requirements: 1.4
        """
        if not self.session_manager.sessions:
            self.ui.show_warning("No sessions loaded")
            return
        
        # Prepare table data
        rows = []
        for session_name, session in self.session_manager.sessions.items():
            # Extract phone number from session file name
            phone = session_name.replace('+', '').replace('.session', '')
            
            # Get connection status
            status = "✓ Connected" if session.is_connected else "✗ Disconnected"
            status_style = "green" if session.is_connected else "red"
            
            # Get monitoring status
            monitoring = "Active" if session.is_monitoring else "Inactive"
            
            # Get active operations count
            active_ops = len(session.active_tasks)
            
            # Get current operation
            current_op = session.current_operation or "None"
            
            rows.append([
                session_name,
                phone,
                status,
                monitoring,
                active_ops,
                current_op
            ])
        
        # Display table
        columns = ["Session Name", "Phone", "Status", "Monitoring", "Active Tasks", "Current Operation"]
        self.ui.display_table("Telegram Sessions", columns, rows)
        
        # Show summary
        total = len(self.session_manager.sessions)
        connected = sum(1 for s in self.session_manager.sessions.values() if s.is_connected)
        monitoring = sum(1 for s in self.session_manager.sessions.values() if s.is_monitoring)
        
        self.console.print(f"\n[bold]Summary:[/bold] {connected}/{total} connected, {monitoring} monitoring")
    
    async def reload_sessions(self):
        """
        Reload sessions from database with progress indicator
        
        Requirements: 1.1, 1.5
        """
        self.ui.show_info("Reloading sessions from database...")
        
        # Create progress bar
        with self.ui.create_progress_bar(100, "Loading sessions") as progress:
            task = progress.add_task("Loading sessions...", total=100)
            
            # Start loading
            progress.update(task, advance=20, description="Connecting to database...")
            
            try:
                # Load sessions from database
                results = await self.session_manager.load_sessions_from_db()
                
                progress.update(task, advance=40, description="Initializing sessions...")
                
                # Wait a bit for connections to establish
                await asyncio.sleep(1)
                
                progress.update(task, advance=40, description="Complete!")
                
                # Show results
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                
                if success_count == total_count:
                    self.ui.show_success(f"Successfully loaded {success_count}/{total_count} sessions")
                elif success_count > 0:
                    self.ui.show_warning(f"Loaded {success_count}/{total_count} sessions (some failed)")
                else:
                    self.ui.show_error(f"Failed to load any sessions")
                
                # Show details of failed sessions
                failed_sessions = [name for name, success in results.items() if not success]
                if failed_sessions:
                    self.console.print("\n[bold red]Failed sessions:[/bold red]")
                    for name in failed_sessions:
                        self.console.print(f"  - {name}")
                
            except Exception as e:
                progress.update(task, advance=100, description="Failed!")
                self.ui.show_error(f"Failed to reload sessions: {e}")
    
    async def show_session_details(self, session_name: Optional[str] = None):
        """
        Show detailed information about a specific session
        
        Args:
            session_name: Name of the session to show details for.
                         If None, prompts user to select a session.
        
        Requirements: 1.4
        """
        # If no session name provided, prompt user to select one
        if session_name is None:
            if not self.session_manager.sessions:
                self.ui.show_warning("No sessions available")
                return
            
            session_names = list(self.session_manager.sessions.keys())
            session_name = await self.ui.prompt_choice_async(
                "Select a session to view details:",
                session_names
            )
        
        # Check if session exists
        if session_name not in self.session_manager.sessions:
            self.ui.show_error(f"Session '{session_name}' not found")
            return
        
        session = self.session_manager.sessions[session_name]
        
        # Get session status
        status = session.get_status()
        queue_depth = session.get_queue_depth()
        
        # Display session details in a panel
        details = []
        details.append(f"[bold]Session Name:[/bold] {session_name}")
        details.append(f"[bold]Session File:[/bold] {session.session_file}")
        details.append(f"[bold]Connected:[/bold] {'✓ Yes' if status['connected'] else '✗ No'}")
        details.append(f"[bold]Monitoring:[/bold] {'✓ Active' if status['monitoring'] else '✗ Inactive'}")
        details.append(f"[bold]Monitoring Targets:[/bold] {status['monitoring_targets_count']}")
        details.append(f"[bold]Active Tasks:[/bold] {status['active_tasks']}")
        details.append(f"[bold]Queue Depth:[/bold] {queue_depth}")
        details.append(f"[bold]Current Operation:[/bold] {status['current_operation'] or 'None'}")
        
        # Add operation timing if available
        if status['operation_start_time']:
            import time
            duration = time.time() - status['operation_start_time']
            details.append(f"[bold]Operation Duration:[/bold] {duration:.1f}s")
        
        # Display monitoring targets if any
        if status['monitoring'] and session.monitoring_targets:
            details.append(f"\n[bold]Monitoring Targets:[/bold]")
            for target_id, target in session.monitoring_targets.items():
                details.append(f"  - {target_id}")
        
        content = "\n".join(details)
        self.ui.show_panel(content, title=f"Session Details: {session_name}", style="cyan")
    
    async def show_menu(self):
        """
        Display session management menu and handle user selection
        
        Requirements: 1.3, 7.2, 7.3
        """
        while True:
            self.console.print("\n[bold cyan]═══ Session Management ═══[/bold cyan]\n")
            
            choices = [
                "List Sessions",
                "Reload Sessions",
                "Show Session Details",
                "Back to Main Menu"
            ]
            
            try:
                choice = await self.ui.prompt_choice_async("Select an option:", choices)
                
                if choice == "List Sessions":
                    await self.list_sessions()
                
                elif choice == "Reload Sessions":
                    await self.reload_sessions()
                
                elif choice == "Show Session Details":
                    await self.show_session_details()
                
                elif choice == "Back to Main Menu":
                    break
                
            except KeyboardInterrupt:
                self.console.print("\n")
                break
            except Exception as e:
                self.ui.show_error(f"An error occurred: {e}")
                import traceback
                traceback.print_exc()

