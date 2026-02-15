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
                data = json.load(file)
            # If not organized right then organize it right
            if not isinstance(data,dict):
                data = {'expenses':[],'income':[],'budget':[]}
            # If not data list then create it
            else:
                if 'expenses' not in data:
                    data['expenses'] = []
                if 'income' not in data:
                    data['income'] = []
                if 'budget' not in data:
                    data['budget'] = []
            return {'success':True,'data':data}
        # If FileNotFound or JSONDecodeError then return empty list
        except FileNotFoundError:
            data = {'expenses':[],'income':[],'budget':[]}
            self.write_file(data)
            return {'success':True,'data':data}
        except json.JSONDecodeError:
            data = {'expenses':[],'income':[],'budget':[]}
            self.write_file(data)
            return {'success':True,'data':data}
    
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
    def view_total_expenses(self) -> list:
        # Define and return list
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
        if not data['expenses']:
            return {'success':False,'message':'No expenses found.'}
        expenseList = data['expenses']
        # If expenseList is empty do not continue
        if not expenseList:
            return {'success':False,'message':'No expenses found.'}
        return {'success':True,'data':expenseList}

    # View filtered expenses
    def view_filtered_expenses(self,search_content:str) -> list:
        # Define the list to be processed
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
        expenseList = data['expenses']
        # If expenseList is empty do not continue
        if not expenseList:
            return {'success':False,'message':'No expenses found.'}
        # Loop through all expenses if the filter pertains to price
        filteredExpenses = [expense for expense in expenseList if search_content]
        return {'success':True,'data':filteredExpenses}

    # Add new expenses
    def add_expenses(self,price:float,purchased:str,tags:str,currency:str,date,notes:str) -> list:        
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
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
            data['expenses'] = expenseList
            self.write_file(data)
            return {'success':True,'message':'Expense properly added.'}
        except ValueError:
            return {'success':False,'message':'Variables not proper types.'}

    # Edit an expense
    def edit_expenses(self,expense_id,price:float=None,purchased:str=None,tags:str=None,date:str=None,currency:str=None,notes:str=None)-> list:
        try:
            # Define the list to process
            result = self.open_file()
            if not result['success']:
                return {'success':False,'message':'File not found'}
            data = result['data']
            expenseList = data['expenses']
            # If the expenseList is empty do not continue
            if not expenseList:
                return {'success':True,'message':'No expenses to process.'}
            # Set counter to count how many times the expense['id'] is found
            count = 0
            # Loop through all of the expenses in the list
            for expense in expenseList:
                if expense['id'] == expense_id:
                    count += 1
                    # Change the price if price != None
                    if price is not None:
                        expense['price'] = price
                    # Change the item purchased if purchased != None
                    elif purchased is not None:
                        expense['purchased'] = purchased
                    # Change the category of the expense if tags != None
                    elif tags is not None:
                        expense['tags'] = tags
                    # Change the date of purchase if date != None
                    elif date is not None:
                        expense['date'] = date
                    # Change the currency and price if currency != None
                    elif currency is not None:
                        from_curr = expense['currency']
                        price = expense['price']
                        expense['currency'] = currency
                        expense['price'] = self.convert_currency(price,from_curr,expense['currency'])
                        if not expense['price']:
                            return f"[bold red]Error converting {from_curr} -> {expense['currency']}[/bold red]."
                    # Change the notes if notes != None
                    elif notes != None:
                        expense['notes'] = notes
            # If expense not found
            if count < 1:
                return {'success':False,'message':'Expense not found.'}
            self.write_file(data)
            return {'success':True,'message':'Expense edited successfully.'}
        except ValueError:
            return {'success':False,'message':'Invalid Expense ID.'}

    # Delete an expense
    def delete_expenses(self,expense_id) -> list:
        try:
            # Define the list to process
            result = self.open_file()
            if not result['success']:
                return {'success':False,'message':'File not found'}
            data = result['data']
            expenseList = data['expenses']
            # If expenseList is empty do not continue
            if not expenseList:
                return {'success':False,'message':'No expenses to process.'}
            deleteExpense = ''
            # Loop through all of the expenses in the list
            for expense in expenseList:
                # If the expense id matches delete the expenses from the list
                if expense['id'] == expense_id:
                    deleteExpense = expense
            # If deleteExpense == '' after the loop then return error
            if deleteExpense == '':
                return {'success':False,'message':'Expense not found'}
            expenseList.remove(deleteExpense)
            data['expenses'] = expenseList
            self.write_file(data)
            return {'success':True,'message':'Expense deleted successfully'}
        except ValueError:
            return {'success':False,'message':'Invalid ID format'}
        except FileNotFoundError:
            return {'success':False,'message':'File not found'}
        
    # View all income
    def view_income(self) -> list:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
        if not data['income']:
            return {'success':False,'message':'No income found.'}
        incomeList = data['income']
        return {'success':True,'data':incomeList}

    # View filtered income
    def view_filtered_income(self) -> list:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
        income_list = data['income']
        filter_list = []
        return filter_list
        
    # Add income data
    def add_income(self,amount:float,source:str,date:str,currency:str='usd',notes:str=None) -> list:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
        incomeList = data['income']
        # Format for new income
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
        return {'success':True,'message':'Income recorded successfully'}

    # Edit income data
    def edit_income(self,expense_id,price:float=None,purchased:str=None,tags:str=None,date:str=None,currency:str=None,notes:str=None)-> list:
        try:
            # Define the list to process
            result = self.open_file()
            if not result['success']:
                return {'success':False,'message':'File not found'}
            data = result['data']
            incomeList = data['income']
            if not incomeList:
                return {'success':False,'message':'No income to process.'}
            count = 0
            for income in incomeList:
                if income['id'] == expense_id:
                    count += 1
                    if price is not None:
                        income['amount'] = price
                    elif purchased is not None:
                        income['source'] = purchased
                    elif date is not None:
                        income['date'] = date
                    elif currency is not None:
                        from_curr = income['currency']
                        amount = income['amount']
                        income['currency'] = currency
                        income['amount'] = self.convert_currency(amount,from_curr,income['currency'])
                        if not income['amount']:
                            return f"[bold red]Error converting {from_curr} -> {income['currency']}[/bold red]."
                    elif notes is not None:
                        income['notes'] = notes
            if count < 1:
                return {'success':False,'message':'Income not found.'}
            self.write_file(data)
            return {'success':True,'message':'Income edited successfully.'}
        except ValueError:
            return {'success':False,'message':'Invalid Income ID.'}
        
    # Create a budget
    def create_budget(self,category:str,amount:float) -> list:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
        budgetList = data['budget']
        newBudget = {
            'category':category,
            'amount':amount,
        }
        budgetList.append(newBudget)
        # Save the budget in the data file
        data['budget'] = budgetList
        self.write_file(data)
        return {'success':True,'message':'Created budget category successfully.'}

    # Update budget
    def update_budget(self,budgetCategory:str,category:str=None,amount:float=None) -> list:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
        budgetList = data['budget']
        if not budgetCategory in budgetList:
            return {'success':False,'message':'Budget category not found.'}
        # Use stuff to change the budget
        for budget in budgetList:
            if budget['category'] == budgetCategory:
                if category is not None:
                    budget['category'] = category
                elif amount is not None:
                    budget['amount'] = amount
        self.write_file(data)
        return {'success':True,'message':'Edited the budget category successfully.'}

    def check_budget_status(self) -> list:
        data = self.open_file()
        if not data['success']:
            return {'success':False,'message':'File not found'}
        budgetList = data['budget']
        if not budgetList:
            return {'success':False,'message':'No budget categories found.'}
        expenseList = data['expenses']
        if not expenseList:
            return {'success':False,'message':'No expenses to process.'}
    
    # View total budget
    def view_all_budget(self) -> list:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
        budgetList = data['budget']
        return budgetList
    
    # Export expenses to a .csv file
    def export_to_csv(self,listName:str,filename:str) -> list:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
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
    def convert_prices_to_currency(self,to_currency:str) -> list:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':'File not found'}
        data = result['data']
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