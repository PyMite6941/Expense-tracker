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
        # Create a nice table to display all the expenses found
        table = Table(title="Total Expenses",header_style='blue')
        table.add_column("ID",justify='right',style='cyan')
        table.add_column("Price",style='white')
        table.add_column("Purchased",style='green')
        table.add_column("Date of Purchase",style='blue')
        table.add_column("Currency",style='red')
        # Iterate through all the expenses
        for expense in expenseList:
            table.add_row(str(expense['id']),f"{expense['price']:.1f}",expense['purchased'],expense['date'],str(expense['currency']).upper())
        console.print(table)

    # View filtered expenses
    def view_filtered_expenses(self)-> list:
        # Define the list to be processed
        expenseList = self.open_file()
        # If expenseList is empty do not continue
        if not expenseList:
            return "[bold yellow]No expenses found[/bold yellow]."
        # Get user input from a questionary menu
        filter_choice = questionary.select(
            "What should be filtered?\nUse arrow keys to navigate",
            choices=[
                'Price',
                'Purchased',
                'Date of purchase',
            ],
            pointer='>'
        ).ask()
        # If choice is 'price' then ask for minimum and maximum price value
        if filter_choice == 'Price':
            filter_min_value = float(input("Enter the minimum value:\n> "))
            filter_max_value = float(input("Enter the maximum value:\n> "))
        # If choice is 'purchased' then ask for what item
        elif filter_choice == 'Purchased':
            filter_item = str(input("Enter the item purchased:\n> "))
        # If choice is 'date of purchase' then ask for the date range
        elif filter_choice == 'Date of purchase':
            filter_min_date = input("Enter the start range (yyyy-mm-dd):\n> ")
            filter_max_date = input("Enter the end range (yyyy-mm-dd):\n> ")
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
        table.add_column("Date of Purchase",style='blue')
        table.add_column("Currency",style='red')
        # Iterate through all the expenses
        for expense in filteredExpenses:
            table.add_row(str(expense['id']),f"{expense['price']:.1f}",expense['purchased'],expense['date'],str(expense['currency']).upper())
        console.print(table)

    # Add new expenses
    def add_expenses(self,price:float,purchased:str,currency:str='usd',date=None)-> str:
        # Check for date; if not defined find current date and use it
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        # Varaibles in the list format
        expense = {
            'id': self.assign_id(),
            'price': price,
            'purchased': purchased,
            'date': date,
            'currency': currency.lower(),
        }
        # Define the list to process
        expenseList = self.open_file()
        expenseList.append(expense)
        self.write_file(expenseList)
        return "[bold green]Expense properly added[/bold green]."

    # Edit an expense
    def edit_expenses(self)-> str:
        # Define the list to process
        expenseList = self.open_file()
        # If the expenseList is empty do not continue
        if not expenseList:
            return "[bold red]No expenses to process[/bold red]."
        expense_id = int(input("Enter the id of the expense you want to edit:\n> "))
        # Get user input from a questionary menu
        choice = questionary.select(
            "What do you want to edit?\nUse arrow keys to navigate",
            choices=[
                'Price',
                'Purchased',
                'Date of purchase',
            ],
            pointer='>'
        ).ask()
        # Set counter to count how many times the expense['id'] is found
        count = 0
        # Loop through all of the expenses in the list
        for expense in expenseList:
            if expense['id'] == expense_id:
                count += 1
                if choice == 'Price':
                    new_price = float(input("Enter the new price:\n> "))
                    expense['price'] = new_price
                elif choice =='Purchased':
                    new_purchased = str(input("Enter the new purchased item:\n> "))
                    expense['purchased'] = new_purchased
                elif choice == 'Date of purchase':
                    new_date = str(input("Enter the new date (yyyy-mm-dd):\n> "))
                    expense['date'] = new_date
        # If expense not found
        if count < 1:
            return "[bold red]Expense not found[/bold red]."
        self.write_file(expenseList)
        return "[bold green]Expense edited successfully[/bold green]."
    
    # Delete an expense
    def delete_expenses(self)-> str:
        try:
            # Define the list to process
            expenseList = self.open_file()
            # If expenseList is empty do not continue
            if not expenseList:
                return "[bold red]No expenses to process[/bold red]."
            id = int(input("Enter the id of the expense you want to delete:\n> "))
            deleteExpense = ''
            # Loop through all of the expenses in the list
            for expense in expenseList:
                # If the expense id matches delete the expenses from the list
                if expense['id'] == id:
                    deleteExpense = expense
            # If deleteExpense == '' after the loop then return error
            if deleteExpense == '':
                return "[bold red]Expense not found[/bold red]."
            expenseList.remove(deleteExpense)
            self.write_file(expenseList)
            return "[bold green]Expense deleted successfully[/bold green]."
        # If FileNotFound then return
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
            file.write("id,price,purchased,date,currency\n")
            # Loop through expenses
            for expense in expenseList:
                file.write(f"{expense['id']},{expense['price']},{expense['purchased']},{expense['date']},{expense['currency']}\n")
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
                if not expense['currency'] == to_currency:
                    from_currency = expense['currency']
                    price_in_new_currency = self.convert_currency(expense['price'],from_currency,to_currency)
                    expense['price'] = round(price_in_new_currency,2)
                    expense['currency'] = to_currency.lower()
        # If price_in_new_currency returns 'None' (implying an error) then stop and return error statement
        except TypeError:
            return f"[bold red]Failed to convert {from_currency} -> {to_currency}[/bold red]."
        self.write_file(expenseList)
        return "[bold green]All expenses converted successfully[/bold green]."

# Initiate needed modules
tracker = ExpenseTracker()
console = Console()
running = True
while running:
    # Display a description of my project
    console.print(Panel("[bold white]This is my APCSP Project, an expense tracker. I wanted (and have) created a project that doesn't just look good for my GitHub it also works for my APCSP project!\nIn this project I learned basic CLI styling as well as list management,making this the best way to learn new information.",title="[bold cyan]--- Expense Tracker ---[/bold cyan]",border_style='blue'))
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
        price = float(input("How much was spent?\n> "))
        purchased = str(input("What was purchased?\n> "))
        currency = str(input("In which currency?\n> ")).lower().strip()
        console.print(tracker.add_expenses(price,purchased,currency))
    # Get the function to edit expenses
    elif choice == 'Edit expenses':
        console.print(tracker.edit_expenses())
    # Get the function to delete expenses
    elif choice == 'Delete expenses':
        console.print(tracker.delete_expenses())
    # Get the function to export the expenses to a .csv
    elif choice == 'Export expenses to a .csv file':
        console.print(tracker.export_to_csv())
    # Get the function to convert expenses to a different currency
    elif choice == 'Convert expenses to a different currency':
        to_currency = str(input("Enter the currency you want to convert all expenses to (e.g. USD, EUR):\n> ")).lower().strip()
        console.print(tracker.convert_prices_to_currency(to_currency))
    # Get the exit command
    elif choice == 'Exit':
        print("Goodbye.")
        running = False
    # If ctrl+c pressed then exit
    elif choice is None:
        print("Farewell.")
        running = False