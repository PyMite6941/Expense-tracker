# This is used to process lists, especially writing and reading files as seen in the open_file() and write_file() functions
import json
# This is for creating and using graphs effectively
import matplotlib.pyplot as plt
# This is to import and export .csv files easily
import pandas as pd
# This is used to export PDF documents nicely
from reportlab.pdfgen import canvas
# This is used to process the API url to get the rates in the convert_currency() function
import requests
# Add more time safety
from typing import Optional,List,Dict,Any

class ExpenseTracker():
    # Initialize class variables
    def __init__(self,filename:str='data.json') -> None:
        self.filename = filename
        self.currency_symbols = {'usd':'$','eur':'€','gbp':'£','jpy':'¥','cny':'¥','inr':'₹','krw':'₩','thb':'฿','aud':'A$','cad':'C$','chf':'Fr','sgd':'S$','hkd':'HK$','nzd':'NZ$','sek':'kr','nok':'kr','dkk':'kr','rub':'₽','mxn':'Mex$','brl':'R$','zar':'R','czk':'Kč','pln':'zł','huf':'Ft','ron':'lei','bgn':'лв','try':'₺','myr':'RM','php':'₱','idr':'Rp','ils':'₪','isk':'kr','hrk':'kn',}

    # Read data file
    def open_file(self) -> Dict[str,Any]:
        try:
            # Read the file using open() function
            with open(self.filename,'r') as file:
                data = json.load(file)
            # If not organized right then organize it right
            if not isinstance(data,dict):
                data = {'expenses':[],'income':[],'budget':[],'subscriptions':[],'goals':[],'recurring_expenses':[],'recurring_income':[],'assets':[],'liabilities':[]}
            # If not data list then create it
            else:
                if 'expenses' not in data:
                    data['expenses'] = []
                if 'income' not in data:
                    data['income'] = []
                if 'budget' not in data:
                    data['budget'] = []
                if 'subscriptions' not in data:
                    data['subscriptions'] = []
                if 'goals' not in data:
                    data['goals'] = []
                if 'recurring_expenses' not in data:
                    data['recurring_expenses'] = []
                if 'recurring_income' not in data:
                    data['recurring_income'] = []
                if 'assets' not in data:
                    data['assets'] = []
                if 'liabilities' not in data:
                    data['liabilities'] = []
            return {'success':True,'data':data}
        # If FileNotFound or JSONDecodeError then return empty list
        except (FileNotFoundError, json.JSONDecodeError):
            data = {'expenses':[],'income':[],'budget':[],'subscriptions':[],'goals':[],'recurring_expenses':[],'recurring_income':[],'assets':[],'liabilities':[]}
            self.write_file(data)
            return {'success':True,'data':data}
    
    # Update data file
    def write_file(self,data:dict) -> None:
        try:
            # Overwrite all data to self.filename using open() function
            with open(self.filename,'w') as file:
                json.dump(data,file)
        # If FileNotFound then create the data file
        except FileNotFoundError:
            with open(self.filename,'w') as file:
                json.dump(data,file)

    # Assign the id to the expense for better organization
    def assign_id(self,data:List[dict]) -> int:
        # If there aren't any previous items then assign '1'
        if len(data) == 0:
            return 1
        # IF there are previous items then calculate the next id value
        else:
            max_id = max(item['id'] for item in data)
            return max_id + 1
        
    # Create graphs
    def create_graphs(self,listName:str,graph_type:str) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        processList = data[listName]

        # If the list is empty, return an error
        if not processList:
            return {'success': False, 'message': f'No {listName} found to create graph'}

        # Set up graph components
        fig, ax = plt.subplots()

        # If pie chart
        if graph_type == 'pie':
            if listName == 'expenses':
                # Extract tags and prices for expenses
                tags = [item['tags'] for item in processList]
                prices = [item['price'] for item in processList]
                ax.pie(prices, labels=tags, autopct='%1.1f%%')
                ax.set_title(f'{listName} Pie Chart')
            elif listName == 'income':
                # Extract sources and amounts for income
                sources = [item['source'] for item in processList]
                amounts = [item['amount'] for item in processList]
                ax.pie(amounts, labels=sources, autopct='%1.1f%%')
                ax.set_title(f'{listName} Pie Chart')
            elif listName == 'budget':
                # Extract categories and amounts for budget
                categories = [item['category'] for item in processList]
                amounts = [item['amount'] for item in processList]
                ax.pie(amounts, labels=categories, autopct='%1.1f%%')
                ax.set_title(f'{listName} Pie Chart')
            else:
                return {'success': False, 'message': f'Pie chart not supported for {listName}'}

            return {'success': True, 'data': fig}
        
    # Get the currency symbol from self.currency_symbols
    def get_currency_symbols(self,currency:str) -> str:
        return self.currency_symbols.get(currency.lower(),currency.upper())
    
    # Format a string with the correct price and currency format
    def format_currency_output(self,price:float,currency:str) -> str:
        currency_symbol = self.get_currency_symbols(currency)
        return f"{currency_symbol}{price}"

    # Backbone of converting currency function
    def convert_currency(self,price:float,from_curr:str,to_curr:str) -> Dict[bool,Any]:
        try:
            # API url
            url = f"https://api.frankfurter.app/latest?from={from_curr.upper()}&to={to_curr.upper()}"
            response = requests.get(url,timeout=5)
            # Get rate to return the improved price
            rate = response.json()['rates'][to_curr.upper()]
            return {'success':True,'rate':rate*price}
        # If cannot connection to the API website the return None
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            return {'success':False,'message':'Could not connect to the Conversion API'}
        # If bad/wrong variables to be processed then return None
        except KeyError:
            return {'success':False,'message':'Bad variables'}

    # View all expenses
    def view_total_expenses(self) -> Dict[str,Any]:
        # Define and return list
        result = self.open_file()
        data = result['data']
        if not data['expenses']:
            return {'success':False,'message':'No expenses found.'}
        expenseList = data['expenses']
        # If expenseList is empty do not continue
        if not expenseList:
            return {'success':False,'message':'No expenses found.'}
        return {'success':True,'data':expenseList}

    # View filtered expenses
    def view_filtered_expenses(self,price:Optional[float]=None,purchased:Optional[str]=None,tags:Optional[str]=None,currency:Optional[str]=None,date:Optional[str]=None) -> Dict[str,Any]:
        # Define the list to be processed
        result = self.open_file()
        data = result['data']
        expenseList = data['expenses']
        # If expenseList is empty do not continue
        if not expenseList:
            return {'success':False,'message':'No expenses found'}
        # Loop through all expenses if the filter pertains to price
        filteredExpenses = [expense for expense in expenseList if (price is None or expense['price'] == price) and (purchased is None or expense['purchased'].lower() == purchased.lower()) and (tags is None or expense['tags'].lower() == tags.lower()) and (currency is None or expense['currency'].lower() == currency.lower()) and (date is None or expense['date'] == date)]
        if filteredExpenses:
            return {'success':True,'data':filteredExpenses}
        else:
            return {'success':False,'message':'Data not found'}

    # Add new expenses
    def add_expenses(self,price:float,purchased:str,tags:str,currency:str,date:str,notes:str) -> Dict[str,Any]:        
        # Define the list to process
        result = self.open_file()
        data = result['data']
        expenseList = data['expenses']
        # If not expenses
        if not expenseList:
            expenseList = []
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

    # Edit an expense
    def edit_expenses(self,expense_id:int,price:Optional[float]=None,purchased:Optional[str]=None,tags:Optional[str]=None,date:Optional[str]=None,currency:Optional[str]=None,notes:Optional[str]=None)-> Dict[str,Any]:
        try:
            # Define the list to process
            result = self.open_file()
            data = result['data']
            expenseList = data['expenses']
            # If the expenseList is empty do not continue
            if not expenseList:
                return {'success':False,'message':'No expenses to process.'}
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
                    if purchased is not None:
                        expense['purchased'] = purchased
                    # Change the category of the expense if tags != None
                    if tags is not None:
                        expense['tags'] = tags
                    # Change the date of purchase if date != None
                    if date is not None:
                        expense['date'] = date
                    # Change the currency and price if currency != None
                    if currency is not None:
                        from_curr = expense['currency']
                        expense['currency'] = currency
                        result = self.convert_currency(expense['price'],from_curr,expense['currency'])
                        if not result['success']:
                            return {'success':False,'message':result['message']}
                        expense['price'] = result['rate']
                    # Change the notes if notes != None
                    if notes != None:
                        expense['notes'] = notes
            # If expense not found
            if count < 1:
                return {'success':False,'message':'Expense not found'}
            self.write_file(data)
            return {'success':True,'message':'Expense edited successfully'}
        except ValueError:
            return {'success':False,'message':'Invalid Expense ID'}

    # Delete an expense
    def delete_expenses(self,expense_id:int) -> Dict[str,Any]:
        try:
            # Define the list to process
            result = self.open_file()
            data = result['data']
            expenseList = data['expenses']
            # If expenseList is empty do not continue
            if not expenseList:
                return {'success':False,'message':'No expenses to process'}
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
        
    # View all income
    def view_income(self) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        if not result['success']:
            return {'success':False,'message':result['message']}
        data = result['data']
        incomeList = data['income']
        return {'success':True,'data':incomeList}

    # View filtered income
    def view_filtered_income(self,amount:Optional[float]=None,source:Optional[str]=None,currency:Optional[str]=None,date:Optional[str]=None) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        incomeList = data['income']
        # Loop through all expenses if the filter pertains to price
        filteredIncome = [income for income in incomeList if (amount is None or income['amount'] == amount) and (source is None or income['source'].lower() == source.lower()) and (currency is None or income['currency'].lower() == currency.lower()) and (date is None or income['date'] == date)]
        if filteredIncome:
            return {'success':True,'data':filteredIncome}
        else:
            return {'success':False,'message':'Data not found'}
        
    # Add income data
    def add_income(self,amount:float,source:str,date:str,currency:str='usd',notes:Optional[str]=None) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        incomeList = data['income']
        # If not income
        if not incomeList:
            incomeList = []
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
        data['income'] = incomeList
        self.write_file(data)
        return {'success':True,'message':'Income recorded successfully'}

    # Edit income data
    def edit_income(self,income_id:int,amount:Optional[float]=None,source:Optional[str]=None,date:Optional[str]=None,currency:Optional[str]=None,notes:Optional[str]=None)-> Dict[str,Any]:
        try:
            # Define the list to process
            result = self.open_file()
            data = result['data']
            incomeList = data['income']
            if not incomeList:
                return {'success':False,'message':'No income to process.'}
            count = 0
            for income in incomeList:
                if income['id'] == income_id:
                    count += 1
                    if amount is not None:
                        income['amount'] = amount
                    if source is not None:
                        income['source'] = source
                    if date is not None:
                        income['date'] = date
                    if currency is not None:
                        from_curr = income['currency']
                        income['currency'] = currency
                        result = self.convert_currency(income['amount'],from_curr,income['currency'])
                        if not result['success']:
                            return {'success':False,'message':result['message']}
                        income['amount'] = result['rate']
                    if notes is not None:
                        income['notes'] = notes
            if count < 1:
                return {'success':False,'message':'Income not found'}
            self.write_file(data)
            return {'success':True,'message':'Income edited successfully'}
        except ValueError:
            return {'success':False,'message':'Invalid Income ID'}
        
    # Delete income
    def delete_income(self,income_id:int) -> Dict[str,Any]:
        try:
            # Define the list to process
            result = self.open_file()
            data = result['data']
            incomeList = data['income']
            # If incomeList is empty do not continue
            if not incomeList:
                return {'success':False,'message':'No income to process'}
            deleteIncome = ''
            # Loop through all of the income in the list
            for income in incomeList:
                # If the income id matches delete the income from the list
                if income['id'] == income_id:
                    deleteIncome = income
            # If deleteIncome == '' after the loop then return error
            if deleteIncome == '':
                return {'success':False,'message':'Income not found'}
            incomeList.remove(deleteIncome)
            data['income'] = incomeList
            self.write_file(data)
            return {'success':True,'message':'Income deleted successfully'}
        except ValueError:
            return {'success':False,'message':'Invalid ID format'}

    # Create a budget
    def create_budget(self,category:str,amount:float,currency:Optional[str]='usd') -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        budgetList = data['budget']
        # If not budget
        if not budgetList:
            budgetList = []
        # Create the new budget
        newBudget = {
            'id': self.assign_id(budgetList),
            'category':category,
            'amount':amount,
            'currency':currency,
        }
        budgetList.append(newBudget)
        # Save the budget in the data file
        data['budget'] = budgetList
        self.write_file(data)
        return {'success':True,'message':'Created budget category successfully'}

    # Update budget
    def update_budget(self,budgetCategory:str,category:Optional[str]=None,amount:Optional[float]=None,currency:Optional[str]=None) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        budgetList = data['budget']
        # Check to see if the budgetCategory is a created budget
        count = 0
        for budget in budgetList:
            if budget['category'] == budgetCategory:
                count += 1
        if count < 1:
            return {'success':False,'message':'Budget category not found'}
        # Use stuff to change the budget
        for budget in budgetList:
            if budget['category'] == budgetCategory:
                if category is not None:
                    budget['category'] = category
                if amount is not None:
                    budget['amount'] = amount
                if currency is not None:
                    from_curr = budget['currency']
                    budget['currency'] = currency
                    result = self.convert_currency(budget['amount'],from_curr,budget['currency'])
                    if not result['success']:
                        return {'success':False,'message':result['message']}
                    budget['amount'] = result['rate']
        self.write_file(data)
        return {'success':True,'message':'Edited the budget category successfully'}

    # Check the budget status
    def check_budget_status(self,budgetCategory:str) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        budgetList = data['budget']
        if not budgetList:
            return {'success':False,'message':'No budget categories found'}
        expenseList = data['expenses']
        if not expenseList:
            return {'success':False,'message':'No expenses to process'}
        # Find expenses in the budget and store to a list
        budgetExpenses = []
        for expense in expenseList:
            if expense['tags'] == budgetCategory:
                budgetExpenses.append(expense)
        return {'success':True,'data':budgetExpenses}
    
    # View total budget
    def view_all_budget(self) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        budgetList = data['budget']
        if not budgetList:
            return {'success':False,'message':'No budgets found'}
        return {'success':True,'data':budgetList}
    
    # Delete budget
    def delete_budget(self,budget_category:str) -> Dict[str,Any]:
        try:
            # Define the list to process
            result = self.open_file()
            data = result['data']
            budgetList = data['budget']
            # If budgetList is empty do not continue
            if not budgetList:
                return {'success':False,'message':'No budgets to process'}
            deleteBudget = ''
            # Loop through all of the budgets in the list
            for budget in budgetList:
                # If the budget category matches delete the budget from the list
                if budget['category'] == budget_category:
                    deleteBudget = budget
            # If deleteBudget == '' after the loop then return error
            if deleteBudget == '':
                return {'success':False,'message':'Budget not found'}
            budgetList.remove(deleteBudget)
            data['budget'] = budgetList
            self.write_file(data)
            return {'success':True,'message':'Budget deleted successfully'}
        except ValueError:
            return {'success':False,'message':'Invalid category format'}

    # Add subscriptions
    def add_subscriptions(self,subscription_name:Optional[str],subscription_price:float,currency:str,start_date:Optional[str]=None) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        subscriptionList = data['subscriptions']
        # If not subscriptions
        if not subscriptionList:
            subscriptionList = []
        # Add subscription
        subscription = {
            'id': self.assign_id(subscriptionList),
            'name': subscription_name,
            'price': subscription_price,
            'currency': currency,
            'startDate': start_date,
        }
        subscriptionList.append(subscription)
        data['subscriptions'] = subscriptionList
        self.write_file(data)
        return {'success':True,'message':'Subscription successfully added'}
    
    # Edit subscriptions
    def edit_subscription(self,previous_name:Optional[str],price:Optional[float]=None,name:Optional[str]=None,currency:Optional[str]=None,start_date:Optional[str]=None)-> Dict[str,Any]:
        try:
            # Define the list to process
            result = self.open_file()
            data = result['data']
            subscriptionList = data['subscriptions']
            # If subscriptionList is empty
            if not subscriptionList:
                return {'success':False,'message':'No subscriptions to process.'}
            count = 0
            for subscription in subscriptionList:
                if subscription['name'] == previous_name:
                    count += 1
                    if price is not None:
                        subscription['price'] = price
                    if name is not None:
                        subscription['name'] = name
                    if currency is not None:
                        from_curr = subscription['currency']
                        subscription['currency'] = currency
                        result = self.convert_currency(subscription['price'],from_curr,subscription['currency'])
                        if not result['success']:
                            return {'success':False,'message':result['message']}
                        subscription['price'] = result['rate']
                    if start_date is not None:
                        subscription['startDate'] = start_date
            if count < 1:
                return {'success':False,'message':'Subscription not found'}
            self.write_file(data)
            return {'success':True,'message':'Subscription edited successfully'}
        except ValueError:
            return {'success':False,'message':'Invalid Subscription'}

    # View subscriptions
    def view_subscriptions(self) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        subscriptionList = data['subscriptions']
        # View all subscriptions
        if not subscriptionList:
            return {'success':False,'message':'No subscriptions found'}
        return {'success':True,'data':subscriptionList}
    
    # Search subscriptions
    def view_filtered_subscriptions(self,subscriptionName:Optional[str]=None,subscriptionPrice:Optional[float]=None,subscriptionCurrency:Optional[str]=None) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        subscriptionList = data['subscriptions']
        if not subscriptionList:
            return {'success':False,'message':'No subscriptions found'}
        filtered_subscriptions = [subscription for subscription in subscriptionList if (subscriptionName is None or subscriptionName == subscription['name']) and (subscriptionPrice is None or subscriptionPrice == subscription['price']) and (subscriptionCurrency is None or subscriptionCurrency.upper() == subscription['currency'].upper())]
        if not filtered_subscriptions:
            return {'success':False,'message':'No subscriptions found'}
        else:
            return {'success':True,'data':filtered_subscriptions}
    
    # Delete subscriptions
    def delete_subscription(self,subscription_name:str) -> Dict[str,Any]:
        try:
            # Define the list to process
            result = self.open_file()
            data = result['data']
            subscriptionList = data['subscriptions']
            # If subscriptionList is empty do not continue
            if not subscriptionList:
                return {'success':False,'message':'No subscriptions to process'}
            deleteSubscription = ''
            # Loop through all of the subscriptions in the list
            for subscription in subscriptionList:
                # If the subscription name matches delete the subscription from the list
                if subscription['name'] == subscription_name:
                    deleteSubscription = subscription
            # If deleteSubscription == '' after the loop then return error
            if deleteSubscription == '':
                return {'success':False,'message':'Subscription not found'}
            subscriptionList.remove(deleteSubscription)
            data['subscriptions'] = subscriptionList
            self.write_file(data)
            return {'success':True,'message':'Subscription removed successfully'}
        except ValueError:
            return {'success':False,'message':'Invalid category format'}
    
    # Create a goal
    def create_goal(self,name:Optional[str],amount:Optional[float],startDate:Optional[str],monthContribution:Optional[float],currency:Optional[str]) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        goalList = data['goals']
        # If not goals
        if not goalList:
            goalList = []
        # Add goal
        goal = {
            'id':self.assign_id(goalList),
            'name':name,
            'amount':amount,
            'startDate':startDate,
            'monthContribution':monthContribution,
            'currency':currency,
        }
        goalList.append(goal)
        data['goals'] = goalList
        self.write_file(data)
        return {'success':True,'message':'Successfully created the goal'}
    
    # Edit a goal
    def edit_goal(self,name:Optional[str],new_name:Optional[str]=None,amount:Optional[float]=None,startDate:Optional[str]=None,monthContribution:Optional[float]=None,currency:Optional[str]=None) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        goalList = data['goals']
        # If not goals
        if not goalList:
            return {'success':False,'message':'No goals to edit'}
        # Search for the goal
        count = 0
        for item in goalList:
            if item['name'] == name:
                if new_name is not None:
                    item['name'] = new_name
                if amount is not None:
                    item['amount'] = amount
                if startDate is not None:
                    item['startDate'] = startDate
                if monthContribution is not None:
                    item['monthContribution'] = monthContribution
                if currency is not None:
                    item['currency'] = currency
                count += 1
        if count < 1:
            return {'success':False,'message':'No goal found'}
        data['goals'] = goalList
        self.write_file(data)
        return {'success':True,'message':'Successfully edited the goal'}
    
    # View all goals
    def view_all_goals(self) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        goalList = data['goals']
        # If goalList is empty
        if not goalList:
            return {'success':False,'message':'No goals found'}
        return {'success':True,'data':goalList}
    
    # View filtered goals
    def view_filtered_goals(self,name:Optional[str]=None,amount:Optional[float]=None,startDate:Optional[str]=None,monthContribution:Optional[float]=None,currency:Optional[str]=None) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        goalList = data['goals']
        # If not goals
        if not goalList:
            return {'success':False,'message':'No goals found'}
        filtered_goals = [goal for goal in goalList if (name is None or goal['name'] == name) and (amount is None or goal['amount'] == amount) and (startDate is None or goal['startDate'] == startDate) and (monthContribution is None or goal['monthContribution'] == monthContribution) and (currency is None or goal['currency'] == currency)]
        if not filtered_goals:
            return {'success':False,'message':'No goals found with these parameters'}
        return {'success':True,'data':filtered_goals}
    
    # Delete goals
    def delete_goals(self,id:int) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        goalList = data['goals']
        # If not goals
        if not goalList:
            return {'success':False,'message':'No goals to delete'}
        deleteGoal = ''
        for goal in goalList:
            if goal['id'] == id:
                deleteGoal = goal
        if deleteGoal == '':
            return {'success':False,'message':'No goal with this ID was found'}
        goalList.remove(deleteGoal)
        data['goals'] = goalList
        self.write_file(data)
        return {'success':True,'message':'Goal successfully deleted'}

    # Add recurring expense
    def add_recurring_expense(self,amount:float,purchased:str,tags:str,currency:str) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        recurringList = data['recurring_expenses']
        # Create recurring expense
        expense = {
            'amount': amount,
            'purchased': purchased,
            'tags': tags,
            'currency': currency,
        }
        recurringList.append(expense)
        data['recurring_expenses'] = recurringList
        self.write_file(data)
        return {'success':True,'message':'Successfully added recurring expense'}

    # View all recurring expenses
    def view_recurring_expenses(self) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        recurringList = data['recurring_expenses']
        return {'success':True,'data':recurringList}

    # Add recurring income
    def add_recurring_income(self,amount:float,source:str,currency:str) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        recurringList = data['recurring_income']
        # Create recurring income
        income = {
            'amount': amount,
            'source': source,
            'currency': currency,
        }
        recurringList.append(income)
        data['recurring_income'] = recurringList
        self.write_file(data)
        return {'success':True,'message':'Successfully added recurring income'}
    
    # View all recurring income
    def view_recurring_income(self) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        recurringList = data['recurring_income']
        return {'success':True,'data':recurringList}

    # Detect recurring expenses
    def detect_recurring_expenses(self, min_occurrences: int = 3, days_threshold: int = 30) -> Dict[str, Any]:
        """
        Detect recurring expenses based on similar transactions within a time threshold.

        Args:
            min_occurrences: Minimum number of occurrences to consider as recurring
            days_threshold: Maximum days between transactions to consider as the same recurring pattern

        Returns:
            Dictionary with success status and list of detected recurring expenses
        """
        try:
            result = self.open_file()
            data = result['data']
            expenses = data['expenses']

            if not expenses:
                return {'success': False, 'message': 'No expenses to analyze'}

            # Sort expenses by date
            expenses.sort(key=lambda x: x['date'])

            # Group expenses by similar characteristics (purchased item and amount)
            expense_groups = {}
            for expense in expenses:
                key = (expense['purchased'].lower(), expense['price'], expense['currency'].lower())
                if key not in expense_groups:
                    expense_groups[key] = []
                expense_groups[key].append(expense)

            # Detect recurring patterns
            recurring_expenses = []
            for key, group_expenses in expense_groups.items():
                if len(group_expenses) >= min_occurrences:
                    # Check if the expenses occur at regular intervals
                    dates = [pd.to_datetime(expense['date']) for expense in group_expenses]
                    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]

                    # Calculate average interval
                    avg_interval = sum(intervals) / len(intervals)

                    # Check if intervals are consistent (within threshold)
                    consistent = all(abs(interval - avg_interval) <= days_threshold for interval in intervals)

                    if consistent:
                        # Calculate next expected date
                        last_date = dates[-1]
                        next_expected_date = last_date + pd.Timedelta(days=avg_interval)

                        recurring_expenses.append({
                            'purchased': key[0],
                            'price': key[1],
                            'currency': key[2],
                            'frequency_days': round(avg_interval),
                            'occurrences': len(group_expenses),
                            'next_expected_date': next_expected_date.strftime('%Y-%m-%d'),
                            'last_date': last_date.strftime('%Y-%m-%d'),
                            'category': group_expenses[0]['tags']  # Use the category from the first occurrence
                        })

            return {'success': True, 'data': recurring_expenses}

        except Exception as e:
            return {'success': False, 'message': f'Error detecting recurring expenses: {str(e)}'}
    
    # ── Assets ────────────────────────────────────────────────────────────────

    ASSET_TYPES = ['liquid', 'investment', 'real_estate', 'vehicle', 'other']
    LIABILITY_TYPES = ['mortgage', 'student_loan', 'car_loan', 'credit_card', 'personal_loan', 'other']

    def view_assets(self) -> Dict[str, Any]:
        result = self.open_file()
        return {'success': True, 'data': result['data'].get('assets', [])}

    def add_asset(self, name: str, asset_type: str, value: float, currency: str = 'usd', notes: str = '') -> Dict[str, Any]:
        result = self.open_file()
        data = result['data']
        asset_id = self.assign_id(data['assets'])
        asset = {
            'id': asset_id,
            'name': name,
            'type': asset_type.lower(),
            'value': round(float(value), 2),
            'currency': currency.lower(),
            'notes': notes or '',
        }
        data['assets'].append(asset)
        self.write_file(data)
        return {'success': True, 'message': f'Asset "{name}" added successfully', 'data': asset}

    def edit_asset(self, asset_id: int, name: Optional[str] = None, asset_type: Optional[str] = None,
                   value: Optional[float] = None, currency: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        result = self.open_file()
        data = result['data']
        for asset in data['assets']:
            if asset['id'] == asset_id:
                if name is not None:
                    asset['name'] = name
                if asset_type is not None:
                    asset['type'] = asset_type.lower()
                if value is not None:
                    asset['value'] = round(float(value), 2)
                if currency is not None:
                    asset['currency'] = currency.lower()
                if notes is not None:
                    asset['notes'] = notes
                self.write_file(data)
                return {'success': True, 'message': f'Asset {asset_id} updated'}
        return {'success': False, 'message': f'Asset {asset_id} not found'}

    def delete_asset(self, asset_id: int) -> Dict[str, Any]:
        result = self.open_file()
        data = result['data']
        before = len(data['assets'])
        data['assets'] = [a for a in data['assets'] if a['id'] != asset_id]
        if len(data['assets']) == before:
            return {'success': False, 'message': f'Asset {asset_id} not found'}
        self.write_file(data)
        return {'success': True, 'message': f'Asset {asset_id} deleted'}

    # ── Liabilities ───────────────────────────────────────────────────────────

    def view_liabilities(self) -> Dict[str, Any]:
        result = self.open_file()
        return {'success': True, 'data': result['data'].get('liabilities', [])}

    def add_liability(self, name: str, liability_type: str, balance: float, currency: str = 'usd',
                      interest_rate: float = 0.0, notes: str = '') -> Dict[str, Any]:
        result = self.open_file()
        data = result['data']
        if 'liabilities' not in data:
            data['liabilities'] = []
        liability_id = self.assign_id(data['liabilities'])
        liability = {
            'id': liability_id,
            'name': name,
            'type': liability_type.lower(),
            'balance': round(float(balance), 2),
            'currency': currency.lower(),
            'interest_rate': round(float(interest_rate), 4),
            'notes': notes or '',
        }
        data['liabilities'].append(liability)
        self.write_file(data)
        return {'success': True, 'message': f'Liability "{name}" added', 'data': liability}

    def edit_liability(self, liability_id: int, name: Optional[str] = None, liability_type: Optional[str] = None,
                       balance: Optional[float] = None, currency: Optional[str] = None,
                       interest_rate: Optional[float] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        result = self.open_file()
        data = result['data']
        for lib in data.get('liabilities', []):
            if lib['id'] == liability_id:
                if name is not None: lib['name'] = name
                if liability_type is not None: lib['type'] = liability_type.lower()
                if balance is not None: lib['balance'] = round(float(balance), 2)
                if currency is not None: lib['currency'] = currency.lower()
                if interest_rate is not None: lib['interest_rate'] = round(float(interest_rate), 4)
                if notes is not None: lib['notes'] = notes
                self.write_file(data)
                return {'success': True, 'message': f'Liability {liability_id} updated'}
        return {'success': False, 'message': f'Liability {liability_id} not found'}

    def delete_liability(self, liability_id: int) -> Dict[str, Any]:
        result = self.open_file()
        data = result['data']
        before = len(data.get('liabilities', []))
        data['liabilities'] = [l for l in data.get('liabilities', []) if l['id'] != liability_id]
        if len(data['liabilities']) == before:
            return {'success': False, 'message': f'Liability {liability_id} not found'}
        self.write_file(data)
        return {'success': True, 'message': f'Liability {liability_id} deleted'}

    # Import from .csv file
    def import_from_csv(self,listName:Optional[str],filename:Optional[str]) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        listToProcess = data[listName]
        df = pd.read_csv(filename)
        # Drop any id column from CSV — we assign fresh IDs to avoid conflicts
        df = df.drop(columns=['id'], errors='ignore')
        newData = df.to_dict('records')
        max_id = max((item.get('id', 0) for item in listToProcess), default=0)
        for i, record in enumerate(newData, start=1):
            record['id'] = max_id + i
        listToProcess.extend(newData)
        data[listName] = listToProcess
        self.write_file(data)
        display_name = getattr(filename, 'name', filename)
        return {'success':True,'message':f'Imported {display_name} successfully'}

    # Export expenses to a .csv file
    def export_to_csv(self,listName:str,filename:str) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        listToProcess = data[listName]
        # If listToProcess is empty do no continue
        if not listToProcess:
            return {'success':False,'message':'No expenses to process'}
        # Write .csv file
        df = pd.DataFrame(listToProcess)
        df.to_csv(filename,index=False)
        return {'success':True,'message':f'Wrote {listName} to {filename}','data':df}

    # Export to PDF
    def export_to_pdf(self, listName: str, filename: str) -> Dict[str, Any]:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from datetime import datetime as _dt
        import io

        result = self.open_file()
        data = result['data']
        items = data.get(listName, [])
        if not items:
            return {'success': False, 'message': f'No {listName} to export'}

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(f'{listName.capitalize()} Report', styles['Title']))
        story.append(Paragraph(f'Generated: {_dt.now().strftime("%Y-%m-%d %H:%M")}', styles['Normal']))
        story.append(Spacer(1, 16))

        headers = list(items[0].keys())
        table_data = [headers] + [[str(row.get(h, '')) for h in headers] for row in items]
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F81BD')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EBF3FF')]),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

        doc.build(story)
        pdf_bytes = buf.getvalue()
        with open(filename, 'wb') as f:
            f.write(pdf_bytes)
        return {'success': True, 'message': f'PDF exported to {filename}', 'data': pdf_bytes}


    # Convert expenses to a different currency
    def convert_prices_to_currency(self,to_currency:str) -> Dict[str,Any]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        expenseList = data['expenses']
        # If expenseList is empty do not continue
        if not expenseList:
            return {'success':False,'message':'No expenses to process'}
        # Loop through the expenseList list
        for expense in expenseList:
            # Only change the currency if the expense['currency'] doesn't match the to_currency
            if expense['currency'] != to_currency:
                from_currency = expense['currency']
                result = self.convert_currency(expense['price'],from_currency,to_currency)
                if not result['success']:
                    return {'success':False,'message':result['message']}
                expense['price'] = round(result['rate'],2)
                expense['currency'] = to_currency.lower()
        self.write_file(data)
        return {'success':True,'message':f'Successfully converted to {to_currency.upper()}'}

    def check_for_duplicates(self,array:str) -> Dict[bool,str]:
        # Define the list to process
        result = self.open_file()
        data = result['data']
        processedList = data[array]
        # Look through the list for duplicates
        count = 0
        for item in processedList:
            for item2 in processedList:
                if item['id'] != item2['id'] and item['id'] < item2['id']:
                    if array == 'expenses':
                        if item['price'] == item2['price'] and item['purchased'] == item2['purchased'] and item['tags'] == item2['tags'] and item['date'] == item2['date'] and item['currency'] == item2['currency'] and item['notes'] == item2['notes']:
                            self.delete_expenses(item2['id'])
                            count += 1
                    elif array == 'income':
                        if item['amount'] == item2['amount'] and item['source'] == item2['source'] and item['date'] == item2['date'] and item['currency'] == item2['currency'] and item['notes'] == item2['notes']:
                            self.delete_income(item2['id'])
                            count += 1
                    elif array == 'budget':
                        if item['id'] != item2['id'] and item['category'] == item2['category'] and item['amount'] == item2['amount'] and item['currency'] == item2['currency']:
                            self.delete_budget(item2['category'])
                            count += 1
                    elif array == 'subscriptions':
                        if item['id'] != item2['id'] and item['price'] == item2['price'] and item['name'] == item2['name'] and item['currency'] == item2['currency'] and item['startDate'] == item2['startDate']:
                            self.delete_subscription(item2['name'])
                            count += 1
                    elif array == 'goals':
                        if item['id'] != item2['id'] and item['name'] == item2['name'] and item['amount'] == item2['amount'] and item['startDate'] == item2['startDate'] and item['monthContribution'] == item2['monthContribution'] and item['currency'] == item2['currency']:
                            self.delete_goals(item2['id'])
                            count += 1
        if count < 1:
            return {'success':False,'message':'No duplicates found'}
        return {'success':True,'message':f'Removed {count} duplicates'}


__version__ = "v1.5"

# For getting web pages such as the GitHub page for this project
import requests
# For checking for updates properly
from packaging.version import Version
# For running the updates properly
import subprocess
import sys
# Check the repo for the current version number
def check_for_updates(repo="PyMite6941/Expense-tracker"):
    try:
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        response = requests.get(url,timeout=5)
        response.raise_for_status()
        return {'success':True,'version':response.json()["tag_name"]}
    except Exception as e:
        return {'success':False,'message':f'{e}'}

# Validate the need for an update
def validate_update(latest_tag):
    latest = latest_tag.lstrip('v')
    current = __version__.lstrip('v')
    return {'update':Version(latest) > Version(current)}

# Start the update from GitHub
def start_update():
    subprocess.run(["git","pull"],check=True)
    subprocess.run([sys.executable,"-m","pip","install","-r","requirements.txt"],check=True)
    return {'success':True,'message':'Close the program to run with the new updates'}