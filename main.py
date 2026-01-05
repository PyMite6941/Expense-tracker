from datetime import datetime
import json

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

    def view_total_expenses(self) -> list:
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
            return []
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

    def add_expenses(self,price:float,purchased:str,date=f'{datetime.now().strftime("%Y-%m-%d")}'):
        expense = {
            'price': price,
            'purchased': purchased,
            'date': date,
        }
        data = self.open_file()
        data.append(expense)
        self.write_file(data)

tracker = ExpenseTracker()
running = True
while running:
    choice = int(input("--- Menu ---\n\n1. View total expenses\n2. Filter total expenses\n3. Add expenses\n0. Exit\nYour choice:\n> "))
    if choice == 1:
        tracker.view_total_expenses()
    elif choice == 2:
        tracker.view_filtered_expenses()
    elif choice == 3:
        price = float(input("How much was spent?\n> "))
        purchased = input("What was purchased?\n> ")
        added_expenses = tracker.add_expenses(price,purchased)
    elif choice == 0:
        running = False