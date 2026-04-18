# These are used to upgrade the CLI menu a lot and make it better
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
# For the CLI graphs / charts
import plotext as plt
# For the date inputs
from datetime import datetime

# Import data from the core python file
from CLI.core.core_stuff import ExpenseTracker,check_for_updates,validate_update,start_update

class Run:
    def __init__(self):
        # Initiate needed modules
        tracker = ExpenseTracker()
        console = Console()
        running = True
        while running:
            # Check for duplicates everytime the file is rerun and delete the duplicates
            result = tracker.open_file()
            data = result['data']
            types = ['expenses','income','budget','subscriptions','goals']
            for i in range(len(types)):
                tracker.check_for_duplicates(data[types[i]])
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
                    questionary.Choice('View all budgets'),
                    questionary.Choice('View filtered budgets'),
                    questionary.Choice('Delete budgets'),
                    questionary.Separator('--- Subscriptions ---'),
                    questionary.Choice('Add a subscription'),
                    questionary.Choice('Edit a subscription'),
                    questionary.Choice('View all subscriptions'),
                    questionary.Choice('View filtered subscriptions'),
                    questionary.Choice('Delete a subscription'),
                    questionary.Choice('--- Goals ---'),
                    questionary.Choice('Add a goal'),
                    questionary.Choice('Edit a goal'),
                    questionary.Choice('View all goals'),
                    questionary.Choice('View filtered goals'),
                    questionary.Choice('View total goal progress'),
                    questionary.Choice('Delete goals'),
                    questionary.Separator('--- Cool Functions ---'),
                    questionary.Choice('Import data from a .csv file'),
                    questionary.Choice('Export data to a .csv file'),
                    questionary.Choice('Show data on graphs and charts'),
                    questionary.Choice('Convert money to a different currency'),
                    questionary.Separator('--- Program Functions ---'),
                    questionary.Choice('Update Software'),
                    questionary.Choice('Exit'),
                ],
                pointer='>'
            ).ask()
            # Get the function for viewing total expenses
            if choice == 'View total expenses':
                result = tracker.view_total_expenses()
                if not result['success']:
                    console.print(f"[bold red]{result['message']}[/bold red].")
                    continue
                if not result['data']:
                    console.print(f"[bold red]Data not found[/bold red].")
                    continue
                # Create a table to put data into
                table = Table(title="Total Expenses",header_style='blue')
                table.add_column("ID",justify='right',style='cyan')
                table.add_column("Price",style='white')
                table.add_column("Purchased",style='green')
                table.add_column("Tags",style="magenta")
                table.add_column("Date of Purchase",style='blue')
                table.add_column("Currency",style='red')
                table.add_column("Notes",style='blue')
                for expense in result['data']:
                    table.add_row(str(expense['id']),str(expense['price']),expense['purchased'],expense['tags'],expense['date'],expense['currency'],expense['notes'])
                console.print(table)
            # Get the function for filtering total expenses
            elif choice == 'Filter total expenses':
                filter_choice = questionary.checkbox(
                    "What should be filtered?\nUse [space] to select options and [enter] to confirm your choice.",
                    choices=[
                        'Price',
                        'Purchased',
                        'Category',
                        'Date of Purchase',
                        'Currency',
                        'Notes',
                    ],
                ).ask()
                if 'Price' in filter_choice:
                    price = float(questionary.text("How much was spent?\n> ").ask())
                if 'Purchased' in filter_choice:
                    purchased = str(questionary.text("What was purchased?\n> ").ask())
                if 'Category' in filter_choice:
                    tags = str(questionary.text("What tags (i.e. bills, food, etc; default is 'other') ?\n> ").ask())
                    if not tags.strip():
                        tags = 'other'
                if 'Currency' in filter_choice:
                    currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
                    if not currency.strip():
                        currency = 'usd'
                if 'Date of Purchase' in filter_choice:
                    date = str(questionary.text("What is the date of purchase (default is the current date) ?\n> ").ask())
                    if not date:
                        date = str(datetime.now().strftime("%Y-%m-%d"))
                if 'Notes' in filter_choice:
                    notes = str(questionary.text("Enter any notes (default is ''):\n> ").ask())
                    if not notes.strip():
                        notes = None
                result = tracker.view_filtered_expenses(price=price if 'Price' in filter_choice else None,purchased=purchased if 'Purchased' in filter_choice else None,tags=tags if 'Category' in filter_choice else None,currency=currency if 'Currency' in filter_choice else None,date=date if 'Date of Purchase' in filter_choice else None)
                if not result['success']:
                    console.print(f"[bold red]{result['message']}[/bold red].")
                    continue
                expenses = result['data']
                if not expenses:
                    console.print(f"[bold red]Data not found[/bold red].")
                    continue
                # Create a table to put data into
                table = Table(title="Total Expenses",header_style='blue')
                table.add_column("ID",justify='right',style='cyan')
                table.add_column("Price",style='white')
                table.add_column("Purchased",style='green')
                table.add_column("Tags",style="magenta")
                table.add_column("Date of Purchase",style='blue')
                table.add_column("Currency",style='red')
                table.add_column("Notes",style='blue')
                # If data successfully retrieved
                if result['success']:
                    # Loop through data and organize it
                    for expense in result['data']:
                        table.add_row(str(expense['id']),str(expense['price']),str(expense['purchased']),str(expense['tags']),str(expense['date']),str(expense['currency']),str(expense['notes']))
                    console.print(table)
                else:
                    console.print(f"[bold red]{result['message']}[/bold red].")
            # Get the function for adding expenses
            elif choice == 'Add expenses':
                # Loop through the add expenses stuff for amount of expenses desired to be created
                amount_of_expenses = int(questionary.text("How many expenses do you want to add?\n> ").ask())
                for _ in range(amount_of_expenses):
                    # Check and validate price
                    price = float(questionary.text("How much was spent?\n> ").ask())
                    if not price > 0:
                        console.print("[bold yellow]Price must be positive[/bold yellow].")
                        continue
                    # Check and validate the purchased variable
                    purchased = str(questionary.text("What was purchased?\n> ").ask())
                    if not purchased.strip():
                        console.print("[bold yellow]Cannot leave item purchased empty[/bold yellow].")
                        continue
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
                        date = str(datetime.now().strftime("%Y-%m-%d"))
                    # Get notes if any
                    notes = str(questionary.text("Enter any notes (default is ''):\n> ").ask())
                    if not notes.strip():
                        notes = None
                    result = tracker.add_expenses(price,purchased,tags,currency,date,notes)
                    color = 'green' if result['success'] else 'red'
                    console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to edit expenses
            elif choice == 'Edit expenses':
                expense_id = int(questionary.text("What ID should be edited?\n> ").ask())
                choice = questionary.checkbox(
                    "What should be filtered?\nUse [space] to select options and [enter] to confirm your choice.",
                    choices=[
                        'Price',
                        'Purchased',
                        'Category',
                        'Date of Purchase',
                        'Currency',
                        'Notes',
                    ],
                    pointer='>',
                ).ask()
                price,purchased,tags,currency,date,notes = None,None,None,None,None,None
                if 'Price' in choice:
                    price = float(questionary.text("How much was spent?\n> ").ask())
                if 'Purchased' in choice:
                    purchased = str(questionary.text("What was purchased?\n> ").ask())
                if 'Category' in choice:
                    tags = str(questionary.text("What tags (i.e. bills, food, etc; default is 'other') ?\n> ").ask())
                    if not tags.strip():
                        tags = 'other'
                if 'Currency' in choice:
                    currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
                    if not currency.strip():
                        currency = 'usd'
                if 'Date of Purchase' in choice:
                    date = str(questionary.text("What is the date of purchase (default is the current date) ?\n> ").ask())
                    if not date:
                        date = str(datetime.now().strftime("%Y-%m-%d"))
                if 'Notes' in choice:
                    notes = str(questionary.text("Enter any notes (default is ''):\n> ").ask())
                    if not notes.strip():
                        notes = None
                result = tracker.edit_expenses(expense_id,price=price if 'Price' in choice else None,purchased=purchased if 'Purchased' in choice else None,tags=tags if 'Category' in choice else None,currency=currency if 'Currency' in choice else None,date=date if 'Date of Purchase' in choice else None,notes=notes if 'Notes' in choice else None)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to delete expenses
            elif choice == 'Delete expenses':
                expense_id = int(questionary.text("What ID should be deleted?\n> ").ask())
                result = tracker.delete_expenses(expense_id)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to view total income
            elif choice == 'View total Income':
                result = tracker.view_income()
                if not result['success']:
                    console.print(f"[bold red]{result['message']}[/bold red].")
                    continue
                incomeList = result['data']
                if not incomeList:
                    console.print("[bold red]No income data found[/bold red].")
                    continue
                table = Table(title="Total Income",header_style='blue')
                table.add_column("ID",justify='right',style='cyan')
                table.add_column("Amount",style='white')
                table.add_column("Source",style='green')
                table.add_column("Date",style='blue')
                table.add_column("Currency",style='red')
                table.add_column("Notes",style='blue')
                for income in incomeList:
                    table.add_row(str(income['id']),str(income['amount']),income['source'],str(income['date']),str(income['currency']).lower(),str(income['notes']))
                console.print(table)
            # Get the function to filter total income
            elif choice == 'Filter total Income':
                choice = questionary.checkbox(
                    "What should be filtered?\nUse [space] to select options and [enter] to confirm your choice.",
                    choices=[
                        'Amount',
                        'Source',
                        'Date',
                        'Currency',
                    ],
                ).ask()
                if 'Amount' in choice:
                    amount = float(questionary.text("How much was earned?\n> ").ask())
                if 'Source' in choice:
                    source = str(questionary.text("What was the source?\n> ").ask())
                if 'Currency' in choice:
                    currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
                    if not currency.strip():
                        currency = 'usd'
                if 'Date' in choice:
                    date = str(questionary.text("What is the date (default is the current date) ?\n> ").ask())
                    if not date:
                        date = str(datetime.now().strftime("%Y-%m-%d"))
                result = tracker.view_filtered_income(amount=amount if 'Amount' in choice else None,source=source if 'Source' in choice else None,currency=currency if 'Currency' in choice else None,date=date if 'Date' in choice else None)
                if not result['success']:
                    console.print(f"[bold red]{result['message']}[/bold red].")
                    continue
                incomeList = result['data']
                if not incomeList:
                    console.print("[bold red]No income data found[/bold red].")
                    continue
                table = Table(title="Filtered Income",header_style='blue')
                table.add_column("ID",justify='right',style='cyan')
                table.add_column("Amount",style='white')
                table.add_column("Source",style='green')
                table.add_column("Date",style='blue')
                table.add_column("Currency",style='red')
                table.add_column("Notes",style='blue')
                for income in incomeList:
                    table.add_row(str(income['id']),str(income['amount']),income['source'],str(income['date']),str(income['currency']).lower(),str(income['notes']))
                console.print(table)
            # Get the function to add income
            elif choice == 'Add Income':
                # Loop through the add expenses stuff for amount of expenses desired to be created
                amount_of_expenses = int(questionary.text("How many expenses do you want to add?\n> ").ask())
                for _ in range(amount_of_expenses):
                    # Check and validate amount
                    amount = float(questionary.text("How much was earned?\n> ").ask())
                    if not amount > 0:
                        console.print("[bold yellow]Income must be positive[/bold yellow].")
                        continue
                    # Check and validate the source
                    source = str(questionary.text("Where did the money come from (i.e. work, gift, etc; default is 'job') ?\n> ").ask())
                    if not source.strip():
                        source = 'job'
                    # Check and validate the currency
                    currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
                    if not currency.strip():
                        currency = 'usd'
                    # Check and validate the date
                    date = str(questionary.text("What is the date of purchase (default is the current date) ?\n> ").ask())
                    if not date:
                        date = str(datetime.now().strftime("%Y-%m-%d"))
                    # Get notes if any
                    notes = str(questionary.text("Enter any notes (default is ''):\n> ").ask())
                    if not notes.strip():
                        notes = None
                    result = tracker.add_income(amount,source,date,currency,notes)
                    console.print(f"[bold green]{result['message']}[/bold green].")
            # Get the function to edit income
            elif choice == 'Edit Income':
                expense_id = int(questionary.text("What ID should be edited?\n> ").ask())
                choice = questionary.checkbox(
                    "What should be filtered?\nUse [space] to select options and [enter] to confirm your choice.",
                    choices=[
                        'Amount',
                        'Source',
                        'Date',
                        'Currency',
                        'Notes',
                    ],
                ).ask()
                amount,source,tags,currency,date,notes = None,None,None,None,None,None
                if 'Amount' in choice:
                    amount = float(questionary.text("How much was earned?\n> ").ask())
                if 'Source' in choice:
                    source = str(questionary.text("What was the source?\n> ").ask())
                if 'Currency' in choice:
                    currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
                    if not currency.strip():
                        currency = 'usd'
                if 'Date' in choice:
                    date = str(questionary.text("What is the date (default is the current date) ?\n> ").ask())
                    if not date:
                        date = str(datetime.now().strftime("%Y-%m-%d"))
                if 'Notes' in choice:
                    notes = str(questionary.text("Enter any notes (default is ''):\n> ").ask())
                    if not notes.strip():
                        notes = None
                result = tracker.edit_income(expense_id,amount if amount is not None else None,source if source is not None else None,date if date is not None else None,currency if currency is not None else None,notes if notes is not None else None)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to delete income
            elif choice == 'Delete Income':
                income_id = int(questionary.text("What ID should be deleted?\n> ").ask())
                result = tracker.delete_income(income_id)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to create budgets
            elif choice == 'Create a budget':
                amount_of_budgets = int(questionary.text("How many budgets should be made?\n> ").ask())
                for _ in range(amount_of_budgets):
                    category = str(questionary.text("What category should be budgeted?\n> ").ask())
                    amount = float(questionary.text("How much should be budgeted?\n> ").ask())
                    currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
                    if not currency.strip():
                        currency = 'usd'
                    result = tracker.create_budget(category,amount,currency)
                    color = 'green' if result['success'] else 'red'
                    console.print(f"[bold {color}]{result['message']}[/bold {color}].\n")
            # Get the function to edit the budgets
            elif choice == 'Edit budget':
                budgetCategory = str(questionary.text("What category should be edited?\n> ").ask())
                newAmount = float(questionary.text("What is the new amount for the budget?\n> ").ask())
                result = tracker.update_budget(budgetCategory,amount=newAmount)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to view all budgets
            elif choice == 'View all budgets':
                result = tracker.view_all_budget()
                if not result['success']:
                    console.print(f"[bold red]{result['message']}[/bold red].")
                    continue
                budgetList = result['data']
                if not budgetList:
                    console.print("[bold red]No budget data found[/bold red].")
                    continue
                table = Table(title="Total Budgets",header_style='blue')
                table.add_column("Amount",style='white')
                table.add_column("Category",style='green')
                table.add_column("Currency",style='red')
                for budget in budgetList:
                    table.add_row(str(budget['amount']),budget['category'],str(budget['currency']).upper())
                console.print(table)
            # Get the function to delete budgets
            elif choice == 'Delete budgets':
                budget_category = str(questionary.text("What category should be deleted?\n> ").ask())
                result = tracker.delete_budget(budget_category)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to add subscriptions
            elif choice == 'Add a subscription':
                amount_of_subscriptions = int(questionary.text("How many subscriptions do you want to add?\n> ").ask())
                for _ in range(amount_of_subscriptions):
                    name = str(questionary.text("What is the name of the subscription?\n> ").ask())
                    price = float(questionary.text("How much is the subscription?\n> ").ask())
                    currency = str(questionary.text("What currency is the subscription in? (default is usd)\n> ").ask())
                    startDate = str(questionary.text("When did the subscription start? (yyyy-mm-dd)\n> ").ask())
                    result = tracker.add_subscriptions(name,price,currency,startDate)
            # Get the function to edit subscriptions
            elif choice == 'Edit a subscription':
                previous_name = str(questionary.text("What is the name of the subscription to be edited?\n> ").ask())
                choice = questionary.checkbox(
                    "What should be filtered?\nUse [space] to select options and [enter] to confirm your choice.",
                    choices=[
                        'Amount',
                        'Name',
                        'Start Date',
                        'Currency',
                    ],
                ).ask()
                amount,name,startDate,currency = None,None,None,None
                if 'Amount' in choice:
                    amount = float(questionary.text("How much is the new cost?\n> ").ask())
                if 'Name' in choice:
                    name = str(questionary.text("What is the new name of the subscription?\n> ").ask())
                if 'Start Date' in choice:
                    startDate = str(questionary.text("What is the new start date? (default is today)\n> ").ask())
                    if not startDate.strip():
                        startDate = datetime.now().strftime('%Y-%m-%d')
                if 'Currency' in choice:
                    currency = str(questionary.text("What is the currency the subscription is in? (default is USD)\n> ").ask())
                    if not currency.strip():
                        currency = 'usd'
                results = tracker.edit_subscription(previous_name,amount,name,currency,startDate)
                color = 'green' if results['success'] else 'red'
                console.print(f"[bold {color}]{results['message']}[/bold {color}].")
            # Get the function to view all subscriptions
            elif choice == 'View all subscriptions':
                result = tracker.view_subscriptions()
                if not result['success']:
                    console.print(f"[bold red]{result['message']}[/bold red].")
                    continue
                subscriptionList = result['data']
                if not subscriptionList:
                    console.print("[bold red]No subscription data found[/bold red].")
                    continue
                table = Table(title="Total Subscriptions",header_style='blue')
                table.add_column("Name",style="white")
                table.add_column("Price",style='gold')
                table.add_column("Start Date",style='green')
                table.add_column("Currency",style='red')
                for subscription in subscriptionList:
                    table.add_row(subscription['name'],str(subscription['price']),str(subscription['startDate']),str(subscription['currency']).upper())
                console.print(table)
            # Get the function to view filtered subscriptions
            elif choice == 'View filtered subscriptions':
                choice = questionary.checkbox(
                    "What should be filtered?\nUse [space] to select options and [enter] to confirm your choice.",
                    choices=[
                        "Name",
                        "Amount",
                        "Currency",
                    ],
                    pointer='>'                        
                ).ask()
                name,amount,currency = None,None,None
                if 'Name' in choice:
                    name = str(questionary.text("What is the name of the subscription?\n> ").ask())
                if 'Amount' in choice:
                    amount = float(questionary.text("What is the amount spent?\n> ").ask())
                if 'Currency' in choice:
                    currency = str(questionary.text("What is the currency the subscription is in?\n> ").ask())
                results = tracker.view_filtered_subscriptions(name,amount,currency)
                if not results['success'] or not results['data']:
                    console.print(f"[bold red]{results['message']}[/bold red].")
                    continue
                table = Table(title="Total Subscriptions",header_style='blue')
                table.add_column("Name",style="white")
                table.add_column("Price",style='gold')
                table.add_column("Start Date",style='green')
                table.add_column("Currency",style='red')
                for subscription in results['data']:
                    table.add_row(subscription['name'],str(subscription['price']),str(subscription['startDate']),str(subscription['currency']).upper())
                console.print(table)
            # Get the function to delete a subscription
            elif choice == 'Delete a subscription':
                name = str(questionary.text("What is the name of the subscription?\n> ").ask())
                results = tracker.delete_subscription(name)
                color = 'green' if results['success'] else 'red'
                console.print(f"[bold {color}]{results['message']}[/bold {color}].")
            # Get the function to add a goal
            elif choice == 'Add a goal':
                amount_of_goals = int(questionary.text("How many goals do you want to create?\n> ").ask())
                for _ in range(amount_of_goals):
                    name = str(questionary.text("What is the name of the goal?\n> ").ask())
                    amount = float(questionary.text("What is the amount desired to earn in the goal?").ask())
                    startDate = str(questionary.text("What is the start date of this goal? (default is today)\n> ").ask())
                    monthContribution = float(questionary.text("What is the monthly contribution from the inputted income?\n> ").ask())
                    currency = str(questionary.text("What is the currency this goal uses?\n> ").ask())
                    results = tracker.create_goal(name,amount,startDate,monthContribution,currency)
                    color = 'green' if results['success'] else 'red'
                    console.print(f"[bold {color}]{results['message']}[/bold {color}].")
            # Get the function to edit a goal
            elif choice == 'Edit a goal':
                previous_name = str(questionary.text("What is the name of the subscription to be edited?\n> ").ask())
                choice = questionary.checkbox(
                    "What should be edited?\nUse [space] to select options and [enter] to confirm your choice.",
                    choices=[
                        'Name',
                        'Amount',
                        'Start Date',
                        'Monthly Contribution',
                        'Currency',
                    ],
                ).ask()
                amount,name,startDate,monthContribution,currency = None,None,None,None,None
                if 'Amount' in choice:
                    amount = float(questionary.text("How much is the new cost?\n> ").ask())
                if 'Name' in choice:
                    name = str(questionary.text("What is the new name of the goal?\n> ").ask())
                if 'Start Date' in choice:
                    startDate = str(questionary.text("What is the new start date? (default is today)\n> ").ask())
                    if not startDate.strip():
                        startDate = datetime.now().strftime('%Y-%m-%d')
                if 'Monthly Contribution' in choice:
                    monthContribution = float(questionary.text("What is the new monthly contribution?\n> ").ask())
                if 'Currency' in choice:
                    currency = str(questionary.text("What is the currency the goal is in? (default is USD)\n> ").ask())
                    if not currency.strip():
                        currency = 'usd'
                results = tracker.edit_goal(previous_name,name,amount,startDate,monthContribution,currency)
                color = 'green' if results['success'] else 'red'
                console.print(f"[bold {color}]{results['message']}[/bold {color}].")
            # Get the function to view all goals
            elif choice == 'View all goals':
                results = tracker.view_all_goals()
                if not results['success']:
                    console.print(f"[bold red]{results['message']}[/bold red].")
                    continue
                table = Table(title="Total Goals",header_style='blue')
                table.add_column("Name",style="white")
                table.add_column("Amount",style='gold')
                table.add_column("Start Date",style='green')
                table.add_column("Monthly Contribution",style="orange")
                table.add_column("Currency",style='red')
                for goal in results['data']:
                    table.add_row(goal['name'],str(goal['amount']),goal['startDate'],str(goal['monthContribution']),str(goal['currency']).upper())
                console.print(table)
            # Get the function to view filtered goals
            elif choice == 'View filtered goals':
                choice = questionary.checkbox(
                    "What should be filtered?\nUse [space] to select options and [enter] to confirm your choice.",
                    choices=[
                        'Name',
                        'Amount',
                        'Start Date',
                        'Monthly Contribution',
                        'Currency',
                    ],
                ).ask()
                name,amount,startDate,monthContribution,currency = None,None,None,None,None
                if 'Name' in choice:
                    name = str(questionary.text("What is the name of the goal?\n> ").ask())
                if 'Amount' in choice:
                    amount = float(questionary.text("What is the amount of the goal?\n> ").ask())
                if 'Start Date' in choice:
                    startDate = str(questionary.text("What is the goal's start date? (yyyy-mm-dd)\n> ").ask())
                if 'Monthly Contribution' in choice:
                    monthContribution = float(questionary.text("What amount is the monthly contribution?\n> ").ask())
                results = tracker.view_filtered_goals(name,amount,startDate,monthContribution,currency)
                if not results['success'] or not results['data']:
                    console.print(f"[bold red]{results['message']}[/bold red].")
                    continue
                table = Table(title="Total Goals",header_style='blue')
                table.add_column("Name",style="white")
                table.add_column("Amount",style='gold')
                table.add_column("Start Date",style='green')
                table.add_column("Monthly Contribution",style="orange")
                table.add_column("Currency",style='red')
                for goal in results['data']:
                    table.add_row(goal['name'],str(goal['amount']),goal['startDate'],str(goal['monthContribution']),str(goal['currency']).upper())
                console.print(table)
            # Get the function to view total goal progress
            elif choice == 'View total goal progress':
                pass
            # Get the function to delete a goal
            elif choice == 'Delete goals':
                goal_id = int(questionary.text("What is the id of the goal?\n> ").ask())
                results = tracker.delete_goals(goal_id)
                color = 'green' if results['success'] else 'red'
                console.print(f"[bold {color}]{results['message']}[/bold {color}].")
            # Get the function to import expenses from a .csv file
            elif choice == 'Import data from a .csv file':
                filename = str(questionary.text("What is the file name (including .csv) ?\n> ").ask())
                choice = questionary.select(
                    "What should be imported?",
                    instructions="Use arrow keys to navigate.",
                    choices=[
                        'Expenses',
                        'Income',
                    ],
                    pointer='>',
                ).ask()
                if choice == 'Expenses':
                    result = tracker.import_from_csv('expenses',filename)
                elif choice == 'Income':
                    result = tracker.import_from_csv('income',filename)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to export the expenses to a .csv
            elif choice == 'Export data to a .csv file':
                filename = str(questionary.text("What is the desired file name (default is expenses.csv) ?\n> ").ask())
                if not filename.strip():
                    filename = 'expenses'
                choice = questionary.select(
                    "What should be exported?",
                    instructions="Use arrow keys to navigate.",
                    choices=[
                        'Expenses',
                        'Income',
                    ],
                    pointer='>',
                ).ask()
                results = tracker.open_file()
                if not results['success']:
                    console.print(f"[bold red]{results['message']}[/bold red].")
                    continue
                data = results['data']
                if choice == 'Expenses':
                    result = tracker.export_to_csv('expenses',filename)
                elif choice == 'Income':
                    result = tracker.export_to_csv('income',filename)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to graph the expense data in the CLI
            elif choice == 'Show data on graphs and charts':
                result = tracker.open_file()
                if not result['success']:
                    console.print(f"[bold red]{result['message']}[/bold red].")
                data = result['data']
                choice = questionary.select(
                    "What should be graphed?",
                    instructions="Use arrow keys to navigate.",
                    choices=[
                        'Expenses',
                        'Income',
                        'Budget',
                        'Subscriptions',
                        'Goals',
                    ],
                    pointer='>',
                ).ask()
                if choice == 'Expenses':
                    tracker.create_graphs('expenses','pie')
                elif choice == 'Income':
                    tracker.create_graphs('income','pie')
                elif choice == 'Budget':
                    tracker.create_graphs('budget','pie')
                elif choice == 'Subscriptions':
                    tracker.create_graphs('subscriptions','pie')
                elif choice == 'Goals':
                    tracker.create_graphs('goals','bar')
            # Get the function to remove duplicate entries
            elif choice == 'Delete duplicates':
                list_choice = questionary.select(
                    "What list should be checked?",
                    choices=[
                        "Expenses",
                        "Income",
                        "Budget",
                        "Subscriptions",
                    ],
                    pointer='>',
                ).ask()
                result = tracker.check_for_duplicates(list_choice.lower())
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the function to convert expenses to a different currency
            elif choice == 'Convert money to a different currency':
                to_currency = str(questionary.text("Enter the currency you want to convert all expenses to (e.g. USD, EUR):\n> ").ask()).lower().strip()
                result = tracker.convert_prices_to_currency(to_currency)
                color = 'green' if result['success'] else 'red'
                console.print(f"[bold {color}]{result['message']}[/bold {color}].")
            # Get the functions to update software
            elif choice == 'Update Software':
                result = check_for_updates()
                if result['success']:
                    results = validate_update(result['version'])
                    if results['update']:
                        console.print('[bold yellow]Updating ...[/bold yellow]')
                        start_update()
                        console.print('[bold green]Update Completed[/bold green].')
                    else:
                        console.print('[bold green]All up to date[/bold green].')
                else:
                    console.print(f"[bold red]{result['message']}[/bold red].")
            # Get the exit command
            elif choice == 'Exit':
                console.print("[bold orange]Goodbye[/bold orange].")
                running = False
            # If ctrl+c pressed then exit
            elif choice is None:
                console.print("[bold orange]Farewell[/bold orange].")
                running = False