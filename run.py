# For running commands to run the programs
import subprocess
# For creating the user interface
from rich.panel import Panel
from rich.console import Console
import questionary

from app.cli.cli_app import Run

console = Console()
console.print(Panel("[bold white]Expense Tracker[/bold white]",border_style='blue'))
choice = questionary.select(
    "How do you want to run this program?",
    choices=[
        "CLI",
        "Web UI",
        "Exit"
    ],
    pointer='>',
).ask()
if choice == "CLI":
    console.print("Beginning CLI ...")
    Run()
elif choice == "Web UI":
    console.print("Beginning Web UI Dashboard ...")
    subprocess.run(['streamlit','run','app/Dashboard.py'],check=True)
else:
    console.print("Farewell.")