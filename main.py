# This is for calcualting the dates that are added in the add_expenses() function
from datetime import datetime
# This is used to process lists, especially writing and reading files as seen in the open_file() and write_file() functions
import json
# These are used to upgrade the CLI menu a lot and make it better
from questionary import text,select
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
# This is used to process the API url to get the rates in the convert_currency() function
import requests

class ExpenseTracker():
    # Initialize class variables
    def __init__(self,filename='data.json'):
        self.filename = filename
        self.currency_symbols = {'usd':'$','eur':'€','gbp':'£','jpy':'¥','cny':'¥','inr':'₹','krw':'₩','thb':'฿','aud':'A$','cad':'C$','chf':'Fr','sgd':'S$','hkd':'HK$','nzd':'NZ$','sek':'kr','nok':'kr','dkk':'kr','rub':'₽','mxn':'Mex$','brl':'R$','zar':'R','czk':'Kč','pln':'zł','huf':'Ft','ron':'lei','bgn':'лв','try':'₺','myr':'RM','php':'₱','idr':'Rp','ils':'₪','isk':'kr','hrk':'kn',}

    # Read data file
    def open_file(self) -> list:
        try:
            # Read the file using open() function
            with open(self.filename,'r') as file:
                expenseList = json.load(file)
            return expenseList
        # If FileNotFound then return empty list
        except FileNotFoundError:
            return []
    
    # Update data file
    def write_file(self,list:list):
        try:
            # Overwrite all data to self.filename using open() function
            with open(self.filename,'w') as file:
                json.dump(list,file)
        # If FileNotFound then create the data file
        except FileNotFoundError:
            with open(self.filename,'w') as file:
                json.dump([],file)

    # Assign the id to the expense for better organization
    def assign_id(self) -> int:
        # Define the list to be processed
        expenseList = self.open_file()
        # If there aren't any previous expenses then assign '1'
        if len(expenseList) == 0:
            return 1
        # IF there are previous expenses then calculate the next id value
        else:
            max_id = max(expense['id'] for expense in expenseList)
            return max_id + 1
        
    # Get the currency symbol from self.currency_symbols
    def get_currency_symbols(self,currency:str) -> str:
        return self.currency_symbols.get(currency.lower(),currency.upper())
    
    # Format a string with the correct price and currency format
    def format_currency_output(self,price:float,currency:str) -> str:
        currency_symbol = self.get_currency_symbols(currency)
        return f"{currency_symbol}{price}"

    # Backbone of converting currency function
    def convert_currency(self,price:float,from_curr:str,to_curr:str) -> float:
        try:
            # API url
            url = f"https://api.frankfurter.app/latest?from={from_curr.upper()}&to={to_curr.upper()}"
            response = requests.get(url)
            # Get rate to return the improved price
            rate = response.json()['rates'][to_curr.upper()]
            return rate*price
        # If cannot connection to the API website the return None
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            return None
        # If bad/wrong variables to be processed then return None
        except KeyError:
            return None

    # View all expenses
    def view_total_expenses(self)-> list:
        # Define and return list
        expenseList = self.open_file()
        # If expenseList is empty do not continue
        if not expenseList:
            console.print("[bold yellow]No expenses found[/bold yellow].")
            return
        # Create a nice table to display all the expenses found
        table = Table(title="Total Expenses",header_style='blue')
        table.add_column("ID",justify='right',style='cyan')
        table.add_column("Price",style='white')
        table.add_column("Purchased",style='green')
        table.add_column("Category",style="magenta")
        table.add_column("Date of Purchase",style='blue')
        table.add_column("Currency",style='red')
        table.add_column("Notes",style='orange')
        # Iterate through all the expenses
        for expense in expenseList:
            table.add_row(str(expense['id']),f"{expense['price']:.1f}",expense['purchased'],str(expense['category']).capitalize(),expense['date'],str(expense['currency']).upper(),str(expense['notes']))
        console.print(table)

    # View filtered expenses
    def view_filtered_expenses(self)-> list:
        # Define the list to be processed
        expenseList = self.open_file()
        # If expenseList is empty do not continue
        if not expenseList:
            console.print("[bold yellow]No expenses found[/bold yellow].")
            return
        # Get user input from a questionary menu
        filter_choice = select(
            "What should be filtered?\nUse arrow keys to navigate",
            choices=[
                'Price',
                'Purchased',
                'Tags',
                'Date of purchase',
            ],
            pointer='>'
        ).ask()
        # If choice is 'price' then ask for minimum and maximum price value
        if filter_choice == 'Price':
            min_value = text("What is the minimum value?\n> ").ask()
            max_value = text("What is the maximum value?\n> ").ask()
            filter_min_value = float(min_value) if min_value else 0.0
            filter_max_value = float(max_value) if max_value else filter_min_value+1
        # If choice is 'purchased' then ask for what item
        elif filter_choice == 'Purchased':
            filter_item = text("What was the item purchased?\n> ").ask()
        # If choice is 'tags' then as for what category
        elif filter_choice == 'Tags':
            filter_tags = text("What are the tags?\n> ").ask().lower()
        # If choice is 'date of purchase' then ask for the date range
        elif filter_choice == 'Date of purchase':
            filter_min_date = text("Enter the start range (yyyy-mm-dd):\n> ").ask()
            filter_max_date = text("Enter the end range (yyyy-mm-dd):\n> ").ask()
        # Create filteredExpenses list
        filteredExpenses = []
        # Loop through all expenses if the filter_choice == 'Price'
        if filter_choice == 'Price':
            for expense in expenseList:
                if filter_min_value <= expense['price'] <= filter_max_value:
                    filteredExpenses.append(expense)
        # Loop through all expenses if the filter_choice == 'Purchased'
        elif filter_choice == 'Purchased':
            for expense in expenseList:
                if filter_item == expense['purchased']:
                    filteredExpenses.append(expense)
        # Loop through all expenses if the filter_choice == 'Category'
        elif filter_choice == 'Tags':
            for expense in expenseList:
                if filter_tags == expense['tags'].lower():
                    filteredExpenses.append(expense)
        # Loop through all expenses if the filter_choice == 'Date of purchase'
        elif filter_choice == 'Date of purchase':
            for expense in expenseList:
                if filter_min_date <= expense['date'] <= filter_max_date:
                    filteredExpenses.append(expense)
        # Create a nice table to display all the expenses found
        table = Table(title="Filtered Expenses",header_style='blue')
        table.add_column("ID",justify='right',style='cyan')
        table.add_column("Price",style='white')
        table.add_column("Purchased",style='green')
        table.add_column("Tags",style='magenta')
        table.add_column("Date of Purchase",style='blue')
        table.add_column("Currency",style='red')
        table.add_column("Notes",style='orange')
        # Iterate through all the expenses
        for expense in filteredExpenses:
            table.add_row(str(expense['id']),f"{self.format_currency_output(expense['price'],expense['currency'])}",expense['purchased'],str(expense['tags']).capitalize(),expense['date'],str(expense['currency']).upper(),str(expense['notes']))
        console.print(table)

    # Add new expenses
    def add_expenses(self,price:float,purchased:str,tags:str,currency:str,date,notes:str)-> str:
        try:
            # Varaibles in the list format
            expense = {
                'id': self.assign_id(),
                'price': price,
                'purchased': purchased,
                'tags': tags,
                'date': date,
                'currency': currency.lower(),
                'notes': notes,
            }
            # Define the list to process
            expenseList = self.open_file()
            expenseList.append(expense)
            self.write_file(expenseList)
            return "[bold green]Expense properly added[/bold green]."
        except ValueError:
            return ""

    # Edit an expense
    def edit_expenses(self)-> str:
        try:
            # Define the list to process
            expenseList = self.open_file()
            # If the expenseList is empty do not continue
            if not expenseList:
                return "[bold red]No expenses to process[/bold red]."
            expense_id = int(text("Enter the id of the expense you want to edit:\n> ").ask())
            # Get user input from a questionary menu
            choice = select(
                "What do you want to edit?\nUse arrow keys to navigate",
                choices=[
                    'Price',
                    'Purchased',
                    'Tags',
                    'Date of purchase',
                    'Currency',
                    'Notes',
                ],
                pointer='>'
            ).ask()
            # Set counter to count how many times the expense['id'] is found
            count = 0
            # Loop through all of the expenses in the list
            for expense in expenseList:
                if expense['id'] == expense_id:
                    count += 1
                    # Change the price if choice === 'Price'
                    if choice == 'Price':
                        expense['price'] = float(text("Enter the new price:\n> ").ask())
                    # Change the item purchased if choice == 'Purchased'
                    elif choice =='Purchased':
                        expense['purchased'] = str(text("Enter the new purchased item:\n> ").ask())
                    # Change the category of the expense if choice == 'Category'
                    elif choice == 'Tags':
                        expense['tags'] = str(text("Enter the new tags:\n> ").ask())
                    # Change the date of purchase if choice == 'Date of purchase'
                    elif choice == 'Date of purchase':
                        expense['date'] = str(text("Enter the new date (yyyy-mm-dd):\n> ").ask())
                    # Change the currency and price if choice == 'Currency'
                    elif choice == 'Currency':
                        from_curr = expense['currency']
                        price = expense['price']
                        expense['currency'] = str(text("Enter the currency to change this expense to:\n> ").ask())
                        expense['price'] = self.convert_currency(price,from_curr,expense['currency'])
                        if not expense['price']:
                            return f"[bold red]Error converting {from_curr} -> {expense['currency']}[/bold red]."
                    elif choice == 'Notes':
                        expense['notes'] = str(text("Enter the new notes:\n> ").ask())
            # If expense not found
            if count < 1:
                return "[bold red]Expense not found[/bold red]."
            self.write_file(expenseList)
            return "[bold green]Expense edited successfully[/bold green]."
        except ValueError:
            return "[bold red]Invalid Expense ID[/bold red]."
    
    # Delete an expense
    def delete_expenses(self)-> str:
        try:
            # Define the list to process
            expenseList = self.open_file()
            # If expenseList is empty do not continue
            if not expenseList:
                return "[bold red]No expenses to process[/bold red]."
            expense_id = int(text("Enter the id of the expense you want to delete:\n> ").ask())
            deleteExpense = ''
            # Loop through all of the expenses in the list
            for expense in expenseList:
                # If the expense id matches delete the expenses from the list
                if expense['id'] == expense_id:
                    deleteExpense = expense
            # If deleteExpense == '' after the loop then return error
            if deleteExpense == '':
                return "[bold red]Expense not found[/bold red]."
            expenseList.remove(deleteExpense)
            self.write_file(expenseList)
            return "[bold green]Expense deleted successfully[/bold green]."
        except ValueError:
            return "[bold red]Invalid Expense ID[/bold red]."
        except FileNotFoundError:
            return "[bold red]File not found[/bold red]."
        
    # Create a budget
    def create_budget(self) -> str:
        budget_data = self.open_file()
    
    # Export expenses to a .csv file
    def export_to_csv(self,filename='expenses.csv')-> str:
        # Define the list to process
        expenseList = self.open_file()
        # If expenseList is empty do no continue
        if not expenseList:
            return "[bold red]No expenses to process[/bold red]."
        # Write .csv file using the open() function
        with open(filename,'w') as file:
            # Create headers for the .csv to use
            file.write("id,price,purchased,tags,date,currency,notes\n")
            # Loop through expenses
            for expense in expenseList:
                file.write(f"{expense['id']},{expense['price']},{expense['purchased']},{expense['tags']},{expense['date']},{expense['currency']},{expense['notes']}\n")
        return "[bold green]Expenses exported successfully[/bold green]."

    # Convert expenses to a different currency
    def convert_prices_to_currency(self,to_currency:str)-> str:
        # Define the list to process
        expenseList = self.open_file()
        # If expenseList is empty do not continue
        if not expenseList:
            return "[bold red]No expenses to convert[/bold red]."
        try:
            # Loop through the expenseList list
            for expense in expenseList:
                # Only change the currency if the expense['currency'] doesn't match the to_currency
                if expense['currency'] != to_currency:
                    from_currency = expense['currency']
                    price_in_new_currency = self.convert_currency(expense['price'],from_currency,to_currency)
                    expense['price'] = round(price_in_new_currency,2)
                    expense['currency'] = to_currency.lower()
        # If price_in_new_currency returns 'None' (implying an error) then stop and return error statement
        except TypeError:
            return f"[bold red]Failed to convert {from_currency} -> {to_currency}[/bold red]."
        self.write_file(expenseList)
        return "[bold green]All expenses converted successfully[/bold green]."
    
    # Convert data into a graph
    def show_data_in_graph(self):
        # Define the list to process
        expenseList = self.open_file()
        # If expenseList is empty do not continue
        if not expenseList:
            console.print("[bold red]No expenses to process[/bold red].")
            return
        # Ask for what currency to graph everything in
        currency = str(text("What currency should be displayed (default is 'USD') ?\n> ").ask()).lower()
        if not currency:
            currency = 'usd'
        # Calculate spending to process in bar graph and save in variables to be referenced later
        category_totals = {}
        total = 0
        # Convert all the expenses to one currency and sort prices by category
        for expense in expenseList:
            expense['price'] = self.convert_currency(expense['price'],expense['currency'],currency)
            if expense['price'] is None:
                console.print(f"[bold red]Failed to convert {expense['currency']} -> {currency}[/bold red].")
                return
            category = expense.get('category','other')
            total += expense['price']
            # Save the price of the expense in a category under the category name for reference later
            category_totals[category] = category_totals.get(category,0)+expense['price']
        console.print()
        console.print(Panel("--- Expense Bar Graph ---"))
        # Calculate the bar length given amount of each 
        for category,amount in category_totals.items():
            percent = float((amount/total)*100)
            bar_length = int(percent/2)
            bar = "█"*bar_length
            console.print(f"{category} : {self.format_currency_output(amount,currency)} ({percent:.2f}%) | {bar}")
        console.print(f"Total Expenses : {total:.2f}")

# Initiate needed modules
tracker = ExpenseTracker()
console = Console()
running = True
while running:
    # Display a description of my project
    console.print(Panel("[bold white]This was my APCSP Project, an expense tracker. I wanted (and have) created a project that doesn't just look good for my GitHub it also works for my APCSP project!\nWho cares what I've learned, I've learned to create a valuable product.",title="[bold cyan]--- Expense Tracker ---[/bold cyan]",border_style='blue'))
    # Get user input from a questionary menu
    choice = select(
        "What function do you want to perform?\nUse arrow keys to navigate",
        choices=[
            'View total expenses',
            'Filter total expenses',
            'Add expenses',
            'Edit expenses',
            'Delete expenses',
            'Create a budget',
            'Edit budget',
            'Export expenses to a .csv file',
            'Show expense data on a bar graph',
            'Convert expenses to a different currency',
            'Exit',
        ],
        pointer='>'
    ).ask()
    # Get the function for viewing total expenses
    if choice == 'View total expenses':
        tracker.view_total_expenses()
    # Get the function for fitlering total expenses
    elif choice == 'Filter total expenses':
        tracker.view_filtered_expenses()
    # Get the function for adding expenses
    elif choice == 'Add expenses':
        # Check and validate price
        price = float(text("How much was spent?\n> ").ask())
        if not price > 0:
            console.print("[bold yellow]Price must be positive[/bold yellow].")
        # Check and validate the purchased variable
        purchased = str(text("What was purchased?\n> ").ask())
        if not purchased.strip():
            console.print("[bold yellow]Cannot leave item purchased empty[/bold yellow].")
        # Check and validate the category
        tags = str(text("What tags (i.e. bills, food, etc; default is 'other') ?\n> ").ask())
        if not tags.strip():
            tags = 'other'
        # Check and validate the currency
        currency = str(text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
        if not currency.strip():
            currency = 'usd'
        # Check and validate the date
        date = str(text("What is the date of purchase (default is the current date) ?\n> ").ask())
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        # Get notes if any
        notes = str(text("Enter any notes (default is ''):\n> ").ask())
        if not notes.strip():
            notes = ''
        console.print(tracker.add_expenses(price,purchased,tags,currency,date,notes))
    # Get the function to edit expenses
    elif choice == 'Edit expenses':
        console.print(tracker.edit_expenses())
    # Get the function to delete expenses
    elif choice == 'Delete expenses':
        console.print(tracker.delete_expenses())
    # Get the function to create budgets
    elif choice == 'Create a budget':
        console.print(tracker.create_budget())
    # Get the function to export the expenses to a .csv
    elif choice == 'Export expenses to a .csv file':
        console.print(tracker.export_to_csv())
    # Get the function to graph the expense data in the CLI
    elif choice == 'Show expense data on a bar graph':
        tracker.show_data_in_graph()
    # Get the function to convert expenses to a different currency
    elif choice == 'Convert expenses to a different currency':
        to_currency = str(text("Enter the currency you want to convert all expenses to (e.g. USD, EUR):\n> ").ask()).lower().strip()
        console.print(tracker.convert_prices_to_currency(to_currency))
    # Get the exit command
    elif choice == 'Exit':
        console.print("Goodbye.")
        running = False
    # If ctrl+c pressed then exit
    elif choice is None:
        console.print("Farewell.")
        running = False