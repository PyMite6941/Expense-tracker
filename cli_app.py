# These are used to upgrade the CLI menu a lot and make it better
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Import data from the core python file
from core_stuff import ExpenseTracker

# Initiate needed modules
tracker = ExpenseTracker()
console = Console()
running = True
while running:
    # Display a description of my project
    console.print(Panel("[bold white]This was my APCSP Project, an expense tracker. I wanted (and have) created a project that doesn't just look good for my GitHub it also works for my APCSP project!\nWho cares what I've learned, I've learned to create a valuable product.",title="[bold cyan]--- Expense Tracker ---[/bold cyan]",border_style='blue'))
    # Get user input from a questionary menu
    choice = questionary.select(
        "What function do you want to perform?",
        instruction="Use arrow keys to navigate.",
        choices=[
            questionary.Separator('--- Expenses ---'),
            questionary.Choice('View total expenses'),
            questionary.Choice('Filter total expenses'),
            questionary.Choice('Add expenses'),
            questionary.Choice('Edit expenses'),
            questionary.Choice('Delete expenses'),
            questionary.Separator('--- Income ---'),
            questionary.Choice('View total Income'),
            questionary.Choice('Filter total Income'),
            questionary.Choice('Add Income'),
            questionary.Choice('Edit Income'),
            questionary.Choice('Delete Income'),
            questionary.Separator('--- Budgeting ---'),
            questionary.Choice('Create a budget'),
            questionary.Choice('Edit budget'),
            questionary.Separator('--- Cool Functions ---'),
            questionary.Choice('Export expenses to a .csv file'),
            questionary.Choice('Calculate Taxes'),
            questionary.Choice('Show expense data on a bar graph'),
            questionary.Choice('Convert expenses to a different currency'),
            questionary.Choice('Exit'),
        ],
        pointer='>'
    ).ask()
    # Get the function for viewing total expenses
    if choice == 'View total expenses':
        tracker.view_total_expenses()
    # Get the function for filtering total expenses
    elif choice == 'Filter total expenses':
        # Create a table to put data into
        table = Table(title="Total Expenses",header_style='blue')
        table.add_column("ID",justify='right',style='cyan')
        table.add_column("Price",style='white')
        table.add_column("Purchased",style='green')
        table.add_column("Category",style="magenta")
        table.add_column("Date of Purchase",style='blue')
        table.add_column("Currency",style='red')
        table.add_column("Notes",style='orange')
        data = tracker.view_filtered_expenses()
        # If data successfully retrieved
        if data['success']:
            # Loop through data and organize it
            for expense in data['data']:
                table.add_row(str(expense['id']),expense['price'],str(expense['purchased']),str(expense['category']),str(expense['date']),str(expense['currency']),str(expense['notes']))
            console.print(table)
        else:
            console.print(f"[bold red]{data['message']}[/bold red].")
    # Get the function for adding expenses
    elif choice == 'Add expenses':
        # Loop through the add expenses stuff for amount of expenses desired to be created
        amount_of_expenses = int(questionary.text("How many expenses do you want to add?\n> ").ask())
        for _ in range(amount_of_expenses):
            # Check and validate price
            price = float(questionary.text("How much was spent?\n> ").ask())
            if not price > 0:
                console.print("[bold yellow]Price must be positive[/bold yellow].")
                break
            # Check and validate the purchased variable
            purchased = str(questionary.text("What was purchased?\n> ").ask())
            if not purchased.strip():
                console.print("[bold yellow]Cannot leave item purchased empty[/bold yellow].")
                break
            # Check and validate the category
            tags = str(questionary.text("What tags (i.e. bills, food, etc; default is 'other') ?\n> ").ask())
            if not tags.strip():
                tags = 'other'
            # Check and validate the currency
            currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
            if not currency.strip():
                currency = 'usd'
            # Check and validate the date
            date = str(questionary.text("What is the date of purchase (default is the current date) ?\n> ").ask())
            if not date:
                date = None
            # Get notes if any
            notes = str(questionary.text("Enter any notes (default is ''):\n> ").ask())
            if not notes.strip():
                notes = None
            result = tracker.add_expenses(price,purchased,tags,currency,date,notes)
            color = 'green' if result['success'] else 'red'
            console.print(f"[bold {color}]{result['message']}[/bold {color}].")
    # Get the function to edit expenses
    elif choice == 'Edit expenses':
        console.print(tracker.edit_expenses())
    # Get the function to delete expenses
    elif choice == 'Delete expenses':
        expense_id = int(questionary.text("What ID should be deleted?\n> ").ask())
        result = tracker.delete_expenses(expense_id)
        color = 'green' if result['success'] else 'red'
        console.print(f"[bold {color}]{result['message']}[/bold {color}].")
    # View total income
    elif choice == 'View total Income':
        questionary
    # Filter total income
    elif choice == 'Filter total Income':
        questionary
    # Add new income
    elif choice == 'Add Income':
        # Loop through the add expenses stuff for amount of expenses desired to be created
        amount_of_expenses = int(questionary.text("How many expenses do you want to add?\n> ").ask())
        for _ in range(amount_of_expenses):
            # Check and validate amount
            amount = float(questionary.text("How much was spent?\n> ").ask())
            if not amount > 0:
                console.print("[bold yellow]Income must be positive[/bold yellow].")
                break
            # Check and validate the source
            source = str(questionary.text("What tags (i.e. bills, food, etc; default is 'other') ?\n> ").ask())
            if not source.strip():
                console.print("[bold yellow]Cannot leave source of income empty[/bold yellow].")
                break
            # Check and validate the currency
            currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
            if not currency.strip():
                currency = 'usd'
            # Check and validate the date
            date = str(questionary.text("What is the date of purchase (default is the current date) ?\n> ").ask())
            if not date:
                date = None
            # Get notes if any
            notes = str(questionary.text("Enter any notes (default is ''):\n> ").ask())
            if not notes.strip():
                notes = None
            result = tracker.add_income(amount,source,currency,date,notes)
            console.print(f"[bold green]{result['message']}[/bold green].")
    # Edit income
    elif choice == 'Edit Income':
        console.print(tracker.edit_income())
    # Delete income
    elif choice == 'Delete Income':
        result = tracker.delete_income()
        color = 'green' if result['success'] else 'red'
        console.print(f"[bold {color}]{result['message']}[/bold {color}].")
    # Get the function to create budgets
    elif choice == 'Create a budget':
        amount_of_budgets = int(questionary.text("How many budgets should be made?\n> ").ask())
        for _ in range(amount_of_budgets):
            category = str(questionary.text("What category should be budgeted?\n> ").ask())
            amount = str(questionary.text("How much should be budgeted?\n> ").ask())
            result = tracker.create_budget(category,amount)
            color = 'green' if result['success'] else 'red'
            console.print(f"[bold {color}]{result['message']}[/bold {color}].\n")
    # Get the function to export the expenses to a .csv
    elif choice == 'Export expenses to a .csv file':
        filename = str(questionary.text("What is the desired file name (default is expenses.csv) ?\n> ").ask())
        if not filename.strip():
            filename = 'expenses'
        choice = questionary.select(
            "What should be exported?",
            instructions="Use arrow keys to navigate.",
            choices=[
                'Expenses',
                'Income'
            ],
            pointer='>',
        ).ask()
        data = tracker.open_file()
        if choice == 'Expenses':
            result = tracker.export_to_csv(data['expenses'],filename)
        elif choice == 'Income':
            result = tracker.export_to_csv(data['income'],filename)
        color = 'green' if result['success'] else 'red'
        console.print(f"[bold {color}]{result['message']}[/bold {color}].")
    # Get the function to graph the expense data in the CLI
    elif choice == 'Show expense data on a bar graph':
        tracker.show_data_in_graph()
    # Get the function to convert expenses to a different currency
    elif choice == 'Convert expenses to a different currency':
        to_currency = str(questionary.text("Enter the currency you want to convert all expenses to (e.g. USD, EUR):\n> ").ask()).lower().strip()
        result = tracker.convert_prices_to_currency(to_currency)
        color = 'green' if result['success'] else 'red'
        console.print(f"[bold {color}]{result['message']}[/bold {color}].")
    # Get the exit command
    elif choice == 'Exit':
        console.print("Goodbye.")
        running = False
    # If ctrl+c pressed then exit
    elif choice is None:
        console.print("Farewell.")
        running = False