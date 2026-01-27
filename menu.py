import sys
import os
from colorama import Fore, Style, init
from math import ceil
from typing import List, Optional


class InteractiveMenu:
    """
    A responsive interactive menu system with keyboard navigation.
    Supports Windows (msvcrt) and macOS/Linux (tty/termios).
    """

    def __init__(self,
                 options: List[str],
                 cursor: str = "►",
                 highlight_color: str = Fore.GREEN,
                 items_per_page: int = 10,
                 title: str = "Menu"):
        """Initialize the interactive menu."""
        init(convert=True)
        self.original_options = [opt for opt in options if opt.strip()]
        self.cursor = cursor
        self.highlight_color = highlight_color
        self.items_per_page = items_per_page
        self.title = title
        self.current_index = 0
        self.current_page = 1
        self.total_pages = max(1, ceil(len(self.original_options) / items_per_page))

        self.can_navigate = False
        self._platform = None
        self.msvcrt = None
        self.tty = None
        self.termios = None
        if os.name == 'nt':
            try:
                import msvcrt
                self.msvcrt = msvcrt
                self.can_navigate = True
                self._platform = 'windows'
            except ImportError:
                pass
        else:
            try:
                import tty
                import termios
                self.tty = tty
                self.termios = termios
                self.can_navigate = True
                self._platform = 'unix'
            except ImportError:
                pass
    
    def _clear_screen(self) -> None:
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _get_key(self) -> Optional[str]:
        """Get a single keypress without Enter. Supports Windows and Unix."""
        if not self.can_navigate:
            return None

        if self._platform == 'windows' and self.msvcrt is not None:
            if self.msvcrt.kbhit():
                key = self.msvcrt.getch()
                if key == b'\xe0':  # Special key prefix on Windows
                    key = self.msvcrt.getch()
                    if key == b'H': return 'up'
                    elif key == b'P': return 'down'
                    elif key == b'K': return 'left'
                    elif key == b'M': return 'right'
                elif key == b'\r': return 'enter'
                elif key == b'\x1b': return 'escape'
                elif key.lower() == b'r': return 'reset'
                elif key.lower() == b'q': return 'quit'
        elif self._platform == 'unix':
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # Escape sequence
                seq = sys.stdin.read(2)
                if seq == '[A': return 'up'
                elif seq == '[B': return 'down'
                elif seq == '[C': return 'right'
                elif seq == '[D': return 'left'
                return 'escape'
            elif ch in ('\r', '\n'): return 'enter'
            elif ch.lower() == 'r': return 'reset'
            elif ch.lower() == 'q': return 'quit'
        return None
    
    def _get_page_options(self) -> List[str]:
        """Get options for the current page."""
        if len(self.original_options) <= self.items_per_page:
            return self.original_options
        
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.original_options))
        return self.original_options[start_idx:end_idx]
    
    def _get_display_index(self) -> int:
        """Get the display index for the current page."""
        if len(self.original_options) <= self.items_per_page:
            return self.current_index
        return self.current_index % self.items_per_page
    
    def _render_menu(self) -> None:
        """Render the menu to the terminal."""
        # Header
        print(f"{'─' * 20} {self.title} {'─' * 20}")
        
        # Page info for multi-page menus
        if self.total_pages > 1:
            print(f"Page [{self.current_page}/{self.total_pages}]")
        
        # Instructions
        if self.can_navigate:
            print("Use ↑↓ arrow keys to navigate | ENTER to select | ESC/Q to cancel | R to reset")
            if self.total_pages > 1:
                print("Use ←→ arrow keys to change pages")
        else:
            print("Interactive navigation not available.")
        
        print()  # Empty line before options
        
        # Render options
        page_options = self._get_page_options()
        display_index = self._get_display_index()
        
        for i, option in enumerate(page_options):
            if i == display_index:
                print(f"{self.highlight_color}{Style.BRIGHT}{self.cursor} {option}{Style.RESET_ALL}")
            else:
                print(f"  {option}")
        
        print()  # Empty line after options
        sys.stdout.flush()
    
    def show(self) -> Optional[str]:
        """Display the menu and return the selected option."""
        if not self.original_options:
            print("No options provided!")
            return None
        
        if not self.can_navigate:
            print("Interactive navigation not available.")
            return None

        old_settings = None
        if self._platform == 'unix' and self.termios is not None and self.tty is not None:
            old_settings = self.termios.tcgetattr(sys.stdin)
            self.tty.setcbreak(sys.stdin.fileno())

        try:
            # Initial render
            self._clear_screen()
            self._render_menu()

            while True:
                key = self._get_key()
                if key is None:
                    continue

                needs_refresh = False

                if key == 'up' and self.current_index > 0:
                    self.current_index -= 1
                    new_page = (self.current_index // self.items_per_page) + 1
                    if new_page != self.current_page:
                        self.current_page = new_page
                    needs_refresh = True

                elif key == 'down' and self.current_index < len(self.original_options) - 1:
                    self.current_index += 1
                    new_page = (self.current_index // self.items_per_page) + 1
                    if new_page != self.current_page:
                        self.current_page = new_page
                    needs_refresh = True

                elif key == 'left' and self.total_pages > 1 and self.current_page > 1:
                    self.current_page -= 1
                    self.current_index = (self.current_page - 1) * self.items_per_page
                    needs_refresh = True

                elif key == 'right' and self.total_pages > 1 and self.current_page < self.total_pages:
                    self.current_page += 1
                    self.current_index = min(
                        (self.current_page - 1) * self.items_per_page,
                        len(self.original_options) - 1
                    )
                    needs_refresh = True

                elif key == 'reset':
                    self.current_index = 0
                    self.current_page = 1
                    needs_refresh = True

                elif key == 'enter':
                    selected_option = self.original_options[self.current_index]
                    self._clear_screen()
                    return selected_option

                elif key in ['escape', 'quit']:
                    self._clear_screen()
                    return None

                # Only refresh if something changed
                if needs_refresh:
                    self._clear_screen()
                    self._render_menu()

        except KeyboardInterrupt:
            self._clear_screen()
            return None
        except Exception as e:
            self._clear_screen()
            print(f"Error: {e}")
            return None
        finally:
            if old_settings is not None and self.termios is not None:
                self.termios.tcsetattr(sys.stdin, self.termios.TCSADRAIN, old_settings)

if __name__ == '__main__':
    options = ["Test1", "Test2", "Balls"] + [f"Item {i}" for i in range(20)]
    menu = InteractiveMenu(options)
    result = menu.show()
    print(result)
