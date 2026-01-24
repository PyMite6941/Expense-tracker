from datetime import datetime
import json
import requests

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
            json.dump([],self.filename)
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

    def convert_currency(self,price:float,from_curr:str,to_curr:str) -> str:
        url = f"https://api.frankfurter.app/latest?from={from_curr}&to={to_curr}"
        response = requests.get(url)
        rate = response.json()['rates'][to_curr]
        return f"Conversion prive to {to_curr} : {price * rate}"

    def view_total_expenses(self)-> list:
        expenseList = self.open_file()
        return expenseList

    def view_filtered_expenses(self)-> list:
        expenseList = self.open_file()
        for expense in expenseList:
            if not expense:
                return "No expenses found."
        filter_choice = int(input("--- Filter Menu ---\n\n1. By Price\n2. By purchased item\n3. Date\nYour choice:\n> "))
        if filter_choice == 1:
            filter_min_value = float(input("Enter the minimum value:\n> "))
            filter_max_value = float(input("Enter the maximum value:\n> "))
        elif filter_choice == 2:
            filter_item = str(input("Enter the item purchased:\n> "))
        elif filter_choice == 3:
            filter_min_date = input("Enter the start range (yyyy-mm-dd):\n> ")
            filter_max_date = input("Enter the end range (yyyy-mm-dd):\n> ")
        else:
            print("Choose from the above menu")
        filteredExpenses = []
        if filter_choice == 1:
            for expense in expenseList:
                if filter_min_value <= expense['price'] <= filter_max_value:
                    filteredExpenses.append(expense)
        elif filter_choice == 2:
            for expense in expenseList:
                if filter_item == expense['purchased']:
                    filteredExpenses.append(expense)
        elif filter_choice == 3:
            for expense in expenseList:
                if filter_min_date <= expense['date'] <= filter_max_date:
                    filteredExpenses.append(expense)
        return filteredExpenses

    def add_expenses(self,price:float,purchased:str,currency:str='usd',date=f'{datetime.now().strftime("%Y-%m-%d")}')-> str:
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
        return "Expense properly added"

    def edit_expenses(self)-> str:
        expenseList = self.open_file()
        id = int(input("Enter the id of the expense you want to edit:\n> "))
        choice = int(input("What do you want to edit?\n1. Price\n2. Purchased\n3. Date of purchase\n> "))
        for expense in expenseList:
            if expense['id'] == id:
                if choice == 1:
                    new_price = float(input("Enter the new price:\n> "))
                    expense['price'] = new_price
                elif choice == 2:
                    new_purchased = str(input("Enter the new purchased item:\n> "))
                    expense['purchased'] = new_purchased
                elif choice == 3:
                    new_date = str(input("Enter the new date (yyyy-mm-dd):\n> "))
                    expense['date'] = new_date
        self.write_file(expenseList)
        return "Expense edited successfully."
    
    def delete_expenses(self)-> str:
        try:
            expenseList = self.open_file()
            id = int(input("Enter the id of the expense you want to delete:\n> "))
            for expense in expenseList:
                if expense['id'] == id:
                    expenseList.pop(expense)
            self.write_file(expense)
            return "Expense deleted successfully."
        except FileNotFoundError:
            return "File not found."
    
    def export_to_csv(self,filename='expenses.csv')-> str:
        expenseList = self.open_file()
        if not expense in expenseList:
            return "No expenses to process."
        with open(filename,'w') as file:
            file.write("id,price,purchased,date,currency\n")
            for expense in expenseList:
                file.write(f"{expense['id']},{expense['price']},{expense['purchased']},{expense['date']},{expense['currency']}\n")
        return "Expenses exported successfully."

    def convert_prices_to_currency(self,to_currency:str)-> str:
        expenseList = self.open_file()
        if not expense in expenseList:
            return "No expenses to convert."
        for expense in expenseList:
            from_currency = expense['currency']
            price_in_new_currency = self.convert_currency(expense['price'],from_currency,to_currency)
            expense['price'] = round(price_in_new_currency,2)
            expense['currency'] = to_currency.lower()
        self.write_file(expenseList)
        return "All expenses converted successfully."

tracker = ExpenseTracker()
running = True
while running:
    choice = int(input("--- Menu ---\n\n1. View total expenses\n2. Filter total expenses\n3. Add expenses\n4. Edit expenses\n5. Delete expenses\n6. Export expenses to a .csv file\n7. Convert expenses to a different currency\n0. Exit\nYour choice:\n> "))
    if choice == 1:
        tracker.view_total_expenses()
    elif choice == 2:
        tracker.view_filtered_expenses()
    elif choice == 3:
        price = float(input("How much was spent?\n> "))
        purchased = input("What was purchased?\n> ")
        currency = str(input("In which currency?\n> "))
        tracker.add_expenses(price,purchased,currency)
    elif choice == 4:
        print(tracker.edit_expenses())
    elif choice == 5:
        print(tracker.delete_expenses())
    elif choice == 6:
        print(tracker.export_to_csv())
    elif choice == 7:
        to_currency = str(input("Enter the currency you want to convert all expenses to (e.g. USD, EUR):\n> "))
        print(tracker.convert_prices_to_currency(to_currency))
    elif choice == 0:
        running = False