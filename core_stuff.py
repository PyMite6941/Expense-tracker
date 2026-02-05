# This is for calcualting the dates that are added in the add_expenses() function
from datetime import datetime
# This is used to process lists, especially writing and reading files as seen in the open_file() and write_file() functions
import json
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
    def assign_id(self,lst:list) -> int:
        # If there aren't any previous items then assign '1'
        if len(lst) == 0:
            return 1
        # IF there are previous items then calculate the next id value
        else:
            max_id = max(item['id'] for item in lst)
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
        data = self.open_file()
        expenseList = data['expenses']
        # If expenseList is empty do not continue
        if not expenseList:
            {'success':False,'message':'No expenses found.'}
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
    def view_filtered_expenses(self,min_value:float=None,max_value:float=None,item:float=None,min_date:str=None,max_date:str=None)-> list:
        # Define the list to be processed
        data = self.open_file()
        expenseList = data['expenses']
        # If expenseList is empty do not continue
        if not expenseList:
            return {'success':False,'message':'No expenses found[/bold yellow].'}
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
        # Define the list to process
        data = self.open_file()
        expenseList = data['expenses']
        try:
            # Varaibles in the list format
            expense = {
                'id':self.assign_id(expenseList),
                'price':price,
                'purchased':purchased,
                'tags':tags,
                'date':date,
                'currency':currency.lower(),
                'notes':notes,
            }
            expenseList.append(expense)
            self.write_file(expenseList)
            return "[bold green]Expense properly added[/bold green]."
        except ValueError:
            return ""

    # Edit an expense
    def edit_expenses(self)-> str:
        try:
            # Define the list to process
            data = self.open_file()
            expenseList = data['expenses']
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
                        expense['price'] = float(questionary.text("Enter the new price:\n> ").ask())
                    # Change the item purchased if choice == 'Purchased'
                    elif choice =='Purchased':
                        expense['purchased'] = str(questionary.text("Enter the new purchased item:\n> ").ask())
                    # Change the category of the expense if choice == 'Category'
                    elif choice == 'Tags':
                        expense['tags'] = str(questionary.text("Enter the new tags:\n> ").ask())
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
                    elif choice == 'Notes':
                        expense['notes'] = str(questionary.text("Enter the new notes:\n> ").ask())
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
            data = self.open_file()
            expenseList = data['expenses']
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
        
    # View all income
    def view_income(self):
        # Define the list to process
        data = self.open_file()
        incomeList = data['income']
        # Create a nice table to display all of the income logged
        table = Table(title="All Income",header_style='blue')
        table.add_column("ID",justify='right',style='cyan')
        table.add_column("Amount",style='white')
        table.add_column("Source",style='magenta')
        table.add_column("Date of Purchase",style='blue')
        table.add_column("Currency",style='red')
        table.add_column("Notes",style='orange')
        # Iterate through the logged income
        for item in incomeList:
            table.add_row(str(item['id']),f"{self.format_currency_output(item['amount'],item['currency'])}",str(item['source']).capitalize(),item['date'],str(item['currency']).upper(),str(item['notes']))
        console.print(table) 

    # View filtered income
    def view_filtered_income(self):
        # Define the list to process
        data = self.open_file()
        incomeList = data['income']
        
    # Add income data
    def add_income(self,amount:float,source:str,currency:str='usd',date:str=None,notes:str=None):
        # Define the list to process
        data = self.open_file()
        incomeList = data['income']
        # Format for new income
        if date == None:
            date = datetime.strftime('%Y-%m-%d')
        new_income = {
            'id':self.assign_id(incomeList),
            'amount':amount,
            'source':source,
            'date':date,
            'currency':currency,
            'notes':notes,
        }
        # Add and write new income
        incomeList.append(new_income)
        self.write_file(data)
        return "[bold green]Income added successfully[/bold green]."

    # Edit income data
    def edit_income(self,):
        # Define the list to process
        data = self.open_file()
        incomeList = data['income']
        if not incomeList:
            return {'success':False,'message':'No income to process.'}
        
    # Create a budget
    def create_budget(self,newBudgets:list) -> str:
        # Define the list to process
        data = self.open_file()
        budgetList = []
        # Loop through all budgets in newBudgets
        for budget in newBudgets:
            newBudget = {
                'category':budget['category'],
                'amount':budget['amount'],
            }
            budgetList.append(newBudget)
        # Save the budget in the data file
        data['budget'] = budgetList
        self.write_file(data)
        return {'success':True,'message':'Created budget category successfully.'}

    # Update budget
    def update_budget(self,budgetCategory:str,category:str=None,amount:float=None) -> str:
        # Define the list to process
        data = self.open_file()
        budgetList = data['budget']
        if not budgetCategory in budgetList:
            return {'success':False,'message':'Budget category not found.'}
        # Use stuff to change the budget
        for budget in budgetList:
            if budget['category'] == budgetCategory:
                if category != None:
                    budget['category'] = category
                elif amount != None:
                    budget['amount'] = amount
        self.write_file(data)
        return {'success':True,'message':'Edited the budget category successfully.'}
    
    # View total budget
    def view_all_budget(self):
        # Define the list to process
        data = self.open_file()
        budgetList = data['budget']
        return budgetList
    
    # Export expenses to a .csv file
    def export_to_csv(self,listName:str,filename='expenses.csv') -> str:
        # Define the list to process
        data = self.open_file()
        listToProcess = data[listName]
        # If listToProcess is empty do no continue
        if not listToProcess:
            return {'success':False,'message':'No expenses to process.'}
        # Write .csv file using the open() function
        with open(filename,'w') as file:
            # Create headers for the .csv to use
            file.write("id,price,purchased,tags,date,currency,notes\n")
            # Loop through items in the list
            for expense in listToProcess:
                file.write(f"{expense['id']},{expense['price']},{expense['purchased']},{expense['tags']},{expense['date']},{expense['currency']},{expense['notes']}\n")
        return {'success':True,'message':f'Wrote {listName} to .csv'}

    # Convert expenses to a different currency
    def convert_prices_to_currency(self,to_currency:str) -> str:
        # Define the list to process
        data = self.open_file()
        expenseList = data['expenses']
        # If expenseList is empty do not continue
        if not expenseList:
            return {'success':False,'message':'No expenses to process'}
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
            return {'success':False,'message':f'Failed to convert {from_currency} -> {to_currency}'}
        self.write_file(expenseList)
        return {'success':True,'message':f'Successfully converted {from_currency} -> {to_currency}'}