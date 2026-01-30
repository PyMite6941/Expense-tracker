# This is for calcualting the dates that are added in the add_expenses() function
from datetime import datetime
# This is used to process lists, especially writing and reading files as seen in the open_file() and write_file() functions
import json
# These are used to upgrade the CLI menu a lot and make it better
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
# This is used to process the API url to get the rates in the convert_currency() function
import requests

class ExpenseTracker():
    # Initialize class variables
    def __init__(self,filename='data.txt'):
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
        # Iterate through all the expenses
        for expense in expenseList:
            table.add_row(str(expense['id']),f"{expense['price']:.1f}",expense['purchased'],str(expense['category']).capitalize(),expense['date'],str(expense['currency']).upper())
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
        filter_choice = questionary.select(
            "What should be filtered?\nUse arrow keys to navigate",
            choices=[
                'Price',
                'Purchased',
                'Category',
                'Date of purchase',
            ],
            pointer='>'
        ).ask()
        # If choice is 'price' then ask for minimum and maximum price value
        if filter_choice == 'Price':
            min_value = questionary.text("What is the minimum value?\n> ").ask()
            max_value = questionary.text("What is the maximum value?\n> ").ask()
            filter_min_value = float(min_value) if min_value else 0.0
            filter_max_value = float(max_value) if max_value else filter_min_value+1
        # If choice is 'purchased' then ask for what item
        elif filter_choice == 'Purchased':
            filter_item = questionary.text("What was the item purchased?\n> ").ask()
        # If choice is 'category' then as for what category
        elif filter_choice == 'Category':
            filter_category = questionary.text("What is the category?\n> ").ask().lower()
        # If choice is 'date of purchase' then ask for the date range
        elif filter_choice == 'Date of purchase':
            filter_min_date = questionary.text("Enter the start range (yyyy-mm-dd):\n> ").ask()
            filter_max_date = questionary.text("Enter the end range (yyyy-mm-dd):\n> ").ask()
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
        elif filter_choice == 'Category':
            for expense in expenseList:
                if filter_category == expense['category'].lower():
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
        table.add_column("Category",style='magenta')
        table.add_column("Date of Purchase",style='blue')
        table.add_column("Currency",style='red')
        # Iterate through all the expenses
        for expense in filteredExpenses:
            table.add_row(str(expense['id']),f"{self.format_currency_output(expense['price'],expense['currency'])}",expense['purchased'],str(expense['category']).capitalize(),expense['date'],str(expense['currency']).upper())
        console.print(table)

    # Add new expenses
    def add_expenses(self,currency:str='usd',date=None)-> str:
        try:
            # Check and validate price
            price = float(questionary.text("How much was spent?\n> ").ask())
            if not price > 0:
                return "[bold yellow]Price must be positive[/bold yellow]."
            # Check and validate the purchased variable
            purchased = str(questionary.text("What was purchased?\n> ").ask())
            if not purchased.strip():
                return "[bold yellow]Cannot leave item purchased empty[/bold yellow]."
            # Check the other variables
            category = str(questionary.text("What category (i.e. bills, food, etc; default is 'other') ?\n> ").ask())
            if not category.strip():
                category = 'other'
            currency = str(questionary.text("In which currency (i.e. USD, EUR; default is 'USD') ?\n> ").ask()).lower()
            if not currency.strip():
                currency = 'usd'
            date = str(questionary.text("What is the date of purchase (default is the current date) ?\n> ").ask())
            # Check for date; if not defined find current date and use it
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            # Varaibles in the list format
            expense = {
                'id': self.assign_id(),
                'price': price,
                'purchased': purchased,
                'category': category,
                'date': date,
                'currency': currency.lower(),
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
            expense_id = int(questionary.text("Enter the id of the expense you want to edit:\n> ").ask())
            # Get user input from a questionary menu
            choice = questionary.select(
                "What do you want to edit?\nUse arrow keys to navigate",
                choices=[
                    'Price',
                    'Purchased',
                    'Category',
                    'Date of purchase',
                    'Currency',
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
                        expense['price'] = float(questionary.text("Enter the new price:\n> ").ask())
                    # Change the item purchased if choice == 'Purchased'
                    elif choice =='Purchased':
                        expense['purchased'] = str(questionary.text("Enter the new purchased item:\n> ").ask())
                    # Change the category of the expense if choice == 'Category'
                    elif choice == 'Category':
                        expense['category'] = str(questionary.text("Enter the new category:\n> ").ask())
                    # Change the date of purchase if choice == 'Date of purchase'
                    elif choice == 'Date of purchase':
                        expense['date'] = str(questionary.text("Enter the new date (yyyy-mm-dd):\n> ").ask())
                    # Change the currency and price if choice == 'Currency'
                    elif choice == 'Currency':
                        from_curr = expense['currency']
                        price = expense['price']
                        expense['currency'] = str(questionary.text("Enter the currency to change this expense to:\n> ").ask())
                        expense['price'] = self.convert_currency(price,from_curr,expense['currency'])
                        if not expense['price']:
                            return f"[bold red]Error converting {from_curr} -> {expense['currency']}[/bold red]."
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
            expense_id = int(questionary.text("Enter the id of the expense you want to delete:\n> ").ask())
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
            file.write("id,price,purchased,category,date,currency\n")
            # Loop through expenses
            for expense in expenseList:
                file.write(f"{expense['id']},{expense['price']},{expense['purchased']},{expense['category']},{expense['date']},{expense['currency']}\n")
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
        currency = str(questionary.text("What currency should be displayed (default is 'USD') ?\n> ").ask()).lower()
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
    console.print(Panel("[bold white]This is my APCSP Project, an expense tracker. I wanted (and have) created a project that doesn't just look good for my GitHub it also works for my APCSP project!\nIn this project I learned basic CLI styling as well as list management, making this the best way to learn new information.",title="[bold cyan]--- Expense Tracker ---[/bold cyan]",border_style='blue'))
    # Get user input from a questionary menu
    choice = questionary.select(
        "What function do you want to perform?\nUse arrow keys to navigate",
        choices=[
            'View total expenses',
            'Filter total expenses',
            'Add expenses',
            'Edit expenses',
            'Delete expenses',
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
    # Get the function for adding expenses with the parameters
    elif choice == 'Add expenses':
        console.print(tracker.add_expenses())
    # Get the function to edit expenses
    elif choice == 'Edit expenses':
        console.print(tracker.edit_expenses())
    # Get the function to delete expenses
    elif choice == 'Delete expenses':
        console.print(tracker.delete_expenses())
    # Get the function to export the expenses to a .csv
    elif choice == 'Export expenses to a .csv file':
        console.print(tracker.export_to_csv())
    # Get the function to graph the expense data in the CLI
    elif choice == 'Show expense data on a bar graph':
        tracker.show_data_in_graph()
    # Get the function to convert expenses to a different currency
    elif choice == 'Convert expenses to a different currency':
        to_currency = str(questionary.text("Enter the currency you want to convert all expenses to (e.g. USD, EUR):\n> ").ask()).lower().strip()
        console.print(tracker.convert_prices_to_currency(to_currency))
    # Get the exit command
    elif choice == 'Exit':
        console.print("Goodbye.")
        running = False
    # If ctrl+c pressed then exit
    elif choice is None:
        console.print("Farewell.")
        running = False