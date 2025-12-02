"""
UI components module

This module provides reusable UI components for consistent formatting
including tables, progress bars, and styled messages.
"""

from typing import List, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import prompt
from prompt_toolkit.validation import Validator, ValidationError
import aioconsole


class UIComponents:
    """Reusable UI components for consistent formatting"""
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize UI components with a console instance"""
        self.console = console or Console()
    
    def create_table(self, title: str, columns: List[str], rows: List[List[Any]]) -> Table:
        """
        Create a formatted table with the given title, columns, and rows.
        
        Args:
            title: Table title
            columns: List of column headers
            rows: List of row data (each row is a list of values)
            
        Returns:
            Configured Table object
        """
        table = Table(title=title, show_header=True, header_style="bold magenta")
        
        # Add columns
        for column in columns:
            table.add_column(column, style="cyan", no_wrap=False)
        
        # Add rows
        for row in rows:
            # Convert all values to strings
            str_row = [str(value) for value in row]
            table.add_row(*str_row)
        
        return table
    
    def create_progress_bar(self, total: int, description: str = "Processing") -> Progress:
        """
        Create a progress bar for tracking operations.
        
        Args:
            total: Total number of items to process
            description: Description text for the progress bar
            
        Returns:
            Configured Progress object
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )
        return progress
    
    def show_success(self, message: str):
        """
        Display a success message with green color.
        
        Args:
            message: Success message to display
        """
        self.console.print(f"[bold green]✓[/bold green] {message}")
    
    def show_error(self, message: str):
        """
        Display an error message with red color.
        
        Args:
            message: Error message to display
        """
        self.console.print(f"[bold red]✗[/bold red] {message}")
    
    def show_warning(self, message: str):
        """
        Display a warning message with yellow color.
        
        Args:
            message: Warning message to display
        """
        self.console.print(f"[bold yellow]⚠[/bold yellow] {message}")
    
    def show_info(self, message: str):
        """
        Display an info message with blue color.
        
        Args:
            message: Info message to display
        """
        self.console.print(f"[bold blue]ℹ[/bold blue] {message}")
    
    def show_panel(self, content: str, title: str = "", style: str = ""):
        """
        Display content in a panel box.
        
        Args:
            content: Content to display in the panel
            title: Optional panel title
            style: Optional style (e.g., "green", "red", "yellow")
        """
        panel = Panel(content, title=title, border_style=style)
        self.console.print(panel)
    
    def show_keyboard_shortcuts(self):
        """
        Display available keyboard shortcuts
        """
        shortcuts = [
            ["Ctrl+C", "Interrupt current operation / Exit"],
            ["Ctrl+D", "Quick exit (in some menus)"],
            ["Enter", "Confirm / Use default value"],
            ["↑/↓", "Navigate history (in prompts)"],
            ["Tab", "Auto-complete (where available)"]
        ]
        
        self.console.print("\n[bold cyan]═══ Keyboard Shortcuts ═══[/bold cyan]\n")
        for key, description in shortcuts:
            self.console.print(f"  [bold yellow]{key:12}[/bold yellow] {description}")
        self.console.print()
    
    def show_status_bar(self, status_items: dict):
        """
        Display a status bar with key information
        
        Args:
            status_items: Dictionary of status items to display
        """
        status_parts = []
        for key, value in status_items.items():
            status_parts.append(f"[bold]{key}:[/bold] {value}")
        
        status_text = " | ".join(status_parts)
        self.console.print(f"\n[dim]{status_text}[/dim]\n")
    
    def prompt_input(self, prompt_text: str, default: Optional[str] = None, 
                     validator: Optional[Validator] = None) -> str:
        """
        Prompt for user input with optional default value and validation.
        
        Args:
            prompt_text: Prompt text to display
            default: Optional default value
            validator: Optional validator for input validation
            
        Returns:
            User input string
        """
        prompt_str = f"{prompt_text}"
        if default:
            prompt_str += f" [{default}]"
        prompt_str += ": "
        
        result = prompt(prompt_str, default=default or "", validator=validator)
        return result.strip()
    
    def prompt_confirm(self, prompt_text: str, default: bool = False) -> bool:
        """
        Prompt for yes/no confirmation.
        
        Args:
            prompt_text: Prompt text to display
            default: Default value if user just presses Enter
            
        Returns:
            True for yes, False for no
        """
        default_str = "Y/n" if default else "y/N"
        prompt_str = f"{prompt_text} [{default_str}]: "
        
        while True:
            response = prompt(prompt_str).strip().lower()
            
            if not response:
                return default
            
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                self.show_error("Please enter 'y' or 'n'")
    
    def prompt_choice(self, prompt_text: str, choices: List[str], 
                      default: Optional[str] = None) -> str:
        """
        Prompt for selection from a list of choices.
        
        Args:
            prompt_text: Prompt text to display
            choices: List of valid choices
            default: Optional default choice
            
        Returns:
            Selected choice
        """
        # Display choices
        self.console.print(f"\n[bold]{prompt_text}[/bold]")
        for i, choice in enumerate(choices, 1):
            default_marker = " (default)" if choice == default else ""
            self.console.print(f"  {i}. {choice}{default_marker}")
        
        # Create validator for choices
        class ChoiceValidator(Validator):
            def validate(self, document):
                text = document.text.strip()
                if not text and default:
                    return
                try:
                    choice_num = int(text)
                    if choice_num < 1 or choice_num > len(choices):
                        raise ValidationError(
                            message=f"Please enter a number between 1 and {len(choices)}"
                        )
                except ValueError:
                    raise ValidationError(
                        message="Please enter a valid number"
                    )
        
        # Prompt for selection
        prompt_str = "Enter choice number"
        if default:
            default_idx = str(choices.index(default) + 1) if default in choices else ""
            prompt_str += f" [{default_idx}]"
        prompt_str += ": "
        
        while True:
            try:
                response = prompt(prompt_str, validator=ChoiceValidator())
                if not response.strip() and default:
                    return default
                choice_num = int(response.strip())
                return choices[choice_num - 1]
            except (ValueError, IndexError):
                self.show_error(f"Please enter a number between 1 and {len(choices)}")
            except KeyboardInterrupt:
                raise
    
    def display_table(self, title: str, columns: List[str], rows: List[List[Any]]):
        """
        Create and display a formatted table.
        
        Args:
            title: Table title
            columns: List of column headers
            rows: List of row data
        """
        table = self.create_table(title, columns, rows)
        self.console.print(table)
    
    def clear_screen(self):
        """Clear the console screen"""
        self.console.clear()
    
    def print_separator(self, char: str = "─", style: str = "dim"):
        """
        Print a horizontal separator line.
        
        Args:
            char: Character to use for the separator
            style: Style for the separator
        """
        width = self.console.width
        self.console.print(char * width, style=style)
    
    # Async input methods for event loop compatibility
    
    async def prompt_input_async(self, prompt_text: str, default: Optional[str] = None) -> str:
        """
        Async prompt for user input with optional default value.
        
        This method uses aioconsole.ainput() to avoid event loop conflicts.
        It yields control to the event loop while waiting for input, allowing
        background operations to continue.
        
        Handles KeyboardInterrupt and EOFError gracefully to ensure the event
        loop continues running after input errors.
        
        Args:
            prompt_text: Prompt text to display
            default: Optional default value
            
        Returns:
            User input string
            
        Raises:
            KeyboardInterrupt: If user presses Ctrl+C (propagated for handling)
            EOFError: If user presses Ctrl+D (propagated for handling)
        """
        prompt_str = f"{prompt_text}"
        if default:
            prompt_str += f" [{default}]"
        prompt_str += ": "
        
        try:
            # Use aioconsole.ainput - async and yields control to event loop
            result = await aioconsole.ainput(prompt_str)
            result = result.strip()
            
            # Return default if empty and default is provided
            return result if result else (default or "")
            
        except KeyboardInterrupt:
            # User pressed Ctrl+C - propagate for higher-level handling
            raise
            
        except EOFError:
            # User pressed Ctrl+D - propagate for higher-level handling
            raise
            
        except Exception as e:
            # Handle any other unexpected errors gracefully
            self.show_error(f"Input error: {e}")
            # Return default or empty string to allow continuation
            return default or ""
    
    async def prompt_confirm_async(self, prompt_text: str, default: bool = False) -> bool:
        """
        Async prompt for yes/no confirmation.
        
        This method uses aioconsole.ainput() to avoid event loop conflicts.
        It yields control to the event loop while waiting for input.
        
        Handles KeyboardInterrupt and EOFError gracefully to ensure the event
        loop continues running after input errors.
        
        Args:
            prompt_text: Prompt text to display
            default: Default value if user just presses Enter
            
        Returns:
            True for yes, False for no
            
        Raises:
            KeyboardInterrupt: If user presses Ctrl+C (propagated for handling)
            EOFError: If user presses Ctrl+D (propagated for handling)
        """
        default_str = "Y/n" if default else "y/N"
        prompt_str = f"{prompt_text} [{default_str}]: "
        
        while True:
            try:
                response = await aioconsole.ainput(prompt_str)
                response = response.strip().lower()
                
                if not response:
                    return default
                
                if response in ['y', 'yes']:
                    return True
                elif response in ['n', 'no']:
                    return False
                else:
                    self.show_error("Please enter 'y' or 'n'")
                    
            except KeyboardInterrupt:
                # User pressed Ctrl+C - propagate for higher-level handling
                raise
                
            except EOFError:
                # User pressed Ctrl+D - propagate for higher-level handling
                raise
                
            except Exception as e:
                # Handle any other unexpected errors gracefully
                self.show_error(f"Input error: {e}")
                # Return default to allow continuation
                return default
    
    async def prompt_choice_async(self, prompt_text: str, choices: List[str], 
                                  default: Optional[str] = None) -> str:
        """
        Async prompt for selection from a list of choices.
        
        This method uses aioconsole.ainput() to avoid event loop conflicts.
        It yields control to the event loop while waiting for input.
        
        Handles KeyboardInterrupt and EOFError gracefully to ensure the event
        loop continues running after input errors.
        
        Args:
            prompt_text: Prompt text to display
            choices: List of valid choices
            default: Optional default choice
            
        Returns:
            Selected choice
            
        Raises:
            KeyboardInterrupt: If user presses Ctrl+C (propagated for handling)
            EOFError: If user presses Ctrl+D (propagated for handling)
        """
        # Display choices
        self.console.print(f"\n[bold]{prompt_text}[/bold]")
        for i, choice in enumerate(choices, 1):
            default_marker = " (default)" if choice == default else ""
            self.console.print(f"  {i}. {choice}{default_marker}")
        
        # Prompt for selection
        prompt_str = "Enter choice number"
        if default:
            default_idx = str(choices.index(default) + 1) if default in choices else ""
            prompt_str += f" [{default_idx}]"
        prompt_str += ": "
        
        while True:
            try:
                response = await aioconsole.ainput(prompt_str)
                if not response.strip() and default:
                    return default
                choice_num = int(response.strip())
                if 1 <= choice_num <= len(choices):
                    return choices[choice_num - 1]
                else:
                    self.show_error(f"Please enter a number between 1 and {len(choices)}")
                    
            except ValueError:
                self.show_error("Please enter a valid number")
                
            except KeyboardInterrupt:
                # User pressed Ctrl+C - propagate for higher-level handling
                raise
                
            except EOFError:
                # User pressed Ctrl+D - propagate for higher-level handling
                raise
                
            except Exception as e:
                # Handle any other unexpected errors gracefully
                self.show_error(f"Input error: {e}")
                # Return default if available, otherwise first choice
                return default if default else choices[0]
