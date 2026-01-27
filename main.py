from datetime import datetime
import json
import questionary
import requests
from rich.console import Console

class ExpenseTracker():
    def __init__(self,filename='data.txt'):
        self.filename = filename

    def open_file(self) -> list:
        try:
            with open(self.filename,'r') as file:
                expenseList = json.load(file)
            return expenseList
        except FileNotFoundError:
            print("File doesn't exist, creating ...")
            with open(self.filename,'w') as file:
                json.dump([],file)
            return []
    
    def write_file(self,list:list):
        try:
            with open(self.filename,'w') as file:
                json.dump(list,file)
        except FileNotFoundError:
            with open(self.filename,'w') as file:
                json.dump([],file)

    def assign_id(self) -> int:
        totalExpenseList = self.open_file()
        if len(totalExpenseList) == 0:
            return 1
        else:
            max_id = max(expense['id'] for expense in totalExpenseList)
            return max_id + 1

    def convert_currency(self,price:float,from_curr:str,to_curr:str) -> float:
        url = f"https://api.frankfurter.app/latest?from={from_curr}&to={to_curr}"
        response = requests.get(url)
        rate = response.json()['rates'][to_curr]
        return rate*price

    def view_total_expenses(self)-> list:
        expenseList = self.open_file()
        return expenseList

    def view_filtered_expenses(self)-> list:
        expenseList = self.open_file()
        if not expenseList:
            return "[bold yellow]No expenses found[/bold yellow]."
        filter_choice = questionary.select(
            "What should be filtered?\nUse arrow keys to navigate",
            choices=[
                'Price',
                'Purchased',
                'Date of purchase',
            ],
            pointer='>'
        ).ask()
        if filter_choice == 'Price':
            filter_min_value = float(input("Enter the minimum value:\n> "))
            filter_max_value = float(input("Enter the maximum value:\n> "))
        elif filter_choice == 'Purchased':
            filter_item = str(input("Enter the item purchased:\n> "))
        elif filter_choice == 'Date of purchase':
            filter_min_date = input("Enter the start range (yyyy-mm-dd):\n> ")
            filter_max_date = input("Enter the end range (yyyy-mm-dd):\n> ")
        filteredExpenses = []
        if filter_choice == 'Price':
            for expense in expenseList:
                if filter_min_value <= expense['price'] <= filter_max_value:
                    filteredExpenses.append(expense)
        elif filter_choice == 'Purchased':
            for expense in expenseList:
                if filter_item == expense['purchased']:
                    filteredExpenses.append(expense)
        elif filter_choice == 'Date of purchase':
            for expense in expenseList:
                if filter_min_date <= expense['date'] <= filter_max_date:
                    filteredExpenses.append(expense)
        return filteredExpenses

    def add_expenses(self,price:float,purchased:str,currency:str='usd',date=None)-> str:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        expense = {
            'id': self.assign_id(),
            'price': price,
            'purchased': purchased,
            'date': date,
            'currency': currency.lower(),
        }
        expenseList = self.open_file()
        expenseList.append(expense)
        self.write_file(expenseList)
        return "[bold green]Expense properly added[/bold green]."

    def edit_expenses(self)-> str:
        expenseList = self.open_file()
        expense_id = int(input("Enter the id of the expense you want to edit:\n> "))
        choice = questionary.select(
            "What do you want to edit?\nUse arrow keys to navigate",
            choices=[
                'Price',
                'Purchased',
                'Date of purchase',
            ],
            pointer='>'
        ).ask()
        count = 0
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
        if count < 1:
            return "[bold red]Expense not found[/bold red]."
        self.write_file(expenseList)
        return "[bold green]Expense edited successfully[/bold green]."
    
    def delete_expenses(self)-> str:
        try:
            expenseList = self.open_file()
            id = int(input("Enter the id of the expense you want to delete:\n> "))
            for expense in expenseList:
                if expense['id'] == id:
                    expenseList.remove(expense)
            self.write_file(expenseList)
            return "[bold green]Expense deleted successfully[/bold green]."
        except FileNotFoundError:
            return "[bold red]File not found[/bold red]."
    
    def export_to_csv(self,filename='expenses.csv')-> str:
        expenseList = self.open_file()
        if not expenseList:
            return "[bold red]No expenses to process[/bold red]."
        with open(filename,'w') as file:
            file.write("id,price,purchased,date,currency\n")
            for expense in expenseList:
                file.write(f"{expense['id']},{expense['price']},{expense['purchased']},{expense['date']},{expense['currency']}\n")
        return "[bold green]Expenses exported successfully[/bold green]."

    def convert_prices_to_currency(self,to_currency:str)-> str:
        expenseList = self.open_file()
        if not expenseList:
            return "[bold red]No expenses to convert[/bold red]."
        for expense in expenseList:
            if not expense['currency'] == to_currency:
                from_currency = expense['currency']
                price_in_new_currency = self.convert_currency(expense['price'],from_currency,to_currency)
                expense['price'] = round(price_in_new_currency,2)
                expense['currency'] = to_currency.lower()
        self.write_file(expenseList)
        return "[bold green]All expenses converted successfully[/bold green]."

tracker = ExpenseTracker()
console = Console()
running = True
while running:
    print("\n--- Expense Tracker ---\nThis is my APCSP project that manages expenses inputted through lists saved to a .txt file.\nI created this to work well and also be practical.\n")
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
    if choice == 'View total expenses':
        console.print(tracker.view_total_expenses())
    elif choice == 'Filter total expenses':
        console.print(tracker.view_filtered_expenses())
    elif choice == 'Add expenses':
        price = float(input("How much was spent?\n> "))
        purchased = input("What was purchased?\n> ")
        currency = str(input("In which currency?\n> "))
        console.print(tracker.add_expenses(price,purchased,currency))
    elif choice == 'Edit expenses':
        console.print(tracker.edit_expenses())
    elif choice == 'Delete expenses':
        console.print(tracker.delete_expenses())
    elif choice == 'Export expenses to a .csv file':
        console.print(tracker.export_to_csv())
    elif choice == 'Convert expenses to a different currency':
        to_currency = str(input("Enter the currency you want to convert all expenses to (e.g. USD, EUR):\n> "))
        console.print(tracker.convert_prices_to_currency(to_currency))
    elif choice == 'Exit':
        print("Goodbye.")
        running = False