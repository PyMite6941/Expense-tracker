from datetime import datetime
import json
import requests

class ExpenseTracker():
    def __init__(self,filename='data.txt'):
        self.filename = filename

    def open_file(self) -> list:
        try:
            with open(self.filename, 'r') as file:
                data = json.load(file)
            return data
        except FileNotFoundError:
            print("File doesn't exist, creating ...")
            json.dump([],self.filename)
            return []
    
    def write_file(self,list:list):
        not_worked = True
        while not_worked:
            try:
                with open(self.filename, 'w') as file:
                    json.dump(list,file)
            except FileNotFoundError:
                print("File doesn't exist")

    def assign_id(self) -> int:
        expenses = self.open_file()
        if len(expenses) == 0:
            return 1
        else:
            max_id = max(expense['id'] for expense in expenses)
            return max_id + 1

    def convert_currency(self,price:float,from_curr:str,to_curr:str) -> float:
        url = f"https://api.frankfurter.app/latest?from={from_curr}&to={to_curr}"
        response = requests.get(url)
        rate = response.json()['rates'][to_curr]
        return price * rate

    def view_total_expenses(self):
        data = self.open_file()
        count = 1
        for item in data:
            print(f"\nExpense {count}\n\nPrice: {item['price']}\nPurchased: {item['purchased']}\nDate spent: {item['date']}")
            count += 1

    def view_filtered_expenses(self):
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
        data = self.open_file()
        if filter_choice == 1:
            for item in data:
                if filter_min_value <= item['price'] <= filter_max_value:
                    print(f"\nExpense {count}:\nPrice: {item['price']}\nPurchased: {item['purchased']}\nDate of expense: {item['date']}\n--------\n")
                    count += 1
        elif filter_choice == 2:
            count = 1
            for item in data:
                if filter_item == item['purchased']:
                    print(f"\nExpense {count}:\nPrice: {item['price']}\nPurchased: {item['purchased']}\nDate of expense: {item['date']}\n--------\n")
                    count += 1
        elif filter_choice == 3:
            count = 1
            for item in data:
                if filter_min_date <= item['date'] <= filter_max_date:
                    print(f"\nExpense {count}:\nPrice: {item['price']}\nPurchased: {item['purchased']}\nDate of expense: {item['date']}\n--------\n")
                    count += 1

    def add_expenses(self,price:float,purchased:str,currency:str,date=f'{datetime.now().strftime("%Y-%m-%d")}'):
        expense = {
            'id': self.assign_id(),
            'price': price,
            'purchased': purchased,
            'date': date,
            'currency': currency,
        }
        data = self.open_file()
        data.append(expense)
        self.write_file(data)

    def edit_expenses(self):
        expenses = self.open_file()
        id = int(input("Enter the id of the expense you want to edit:\n> "))
        choice = int(input("What do you want to edit?\n1. Price\n2. Purchased\n3. Date of purchase\n> "))
        for item in expenses:
            if item['id'] == id:
                if choice == 1:
                    new_price = float(input("Enter the new price:\n> "))
                    item['price'] = new_price
                elif choice == 2:
                    new_purchased = str(input("Enter the new purchased item:\n> "))
                    item['purchased'] = new_purchased
                elif choice == 3:
                    new_date = str(input("Enter the new date (yyyy-mm-dd):\n> "))
                    item['date'] = new_date
        self.write_file(expenses)
        return "Expense edited successfully."
    
    def delete_expenses(self):
        expenses = self.open_file()
        id = int(input("Enter the id of the expense you want to delete:\n> "))
        for item in expenses:
            if item['id'] == id:
                expenses.pop(item)
        self.write_file(expenses)
        return "Expense deleted successfully."
    
    def export_to_csv(self,filename='expenses.csv'):
        expenses = self.open_file()
        with open(filename, 'w') as file:
            file.write("id,price,purchased,date,currency\n")
            for item in expenses:
                file.write(f"{item['id']},{item['price']},{item['purchased']},{item['date']},{item['currency']}\n")
        return "Expenses exported successfully."

    def convert_prices_to_currency(self,to_currency:str):
        expenses = self.open_file()
        for item in expenses:
            from_currency = item['currency']
            price_in_new_currency = self.convert_currency(item['price'],from_currency,to_currency)
            item['price'] = round(price_in_new_currency,2)
            item['currency'] = to_currency
        self.write_file(expenses)
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
        added_expenses = tracker.add_expenses(price,purchased,currency)
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