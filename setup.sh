#!/usr/bin/env bash
set -euo pipefail

echo "Setting up Expense Tracker..."

python3 -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f data.json ]; then
    echo '{"expenses":[],"income":[],"budget":[],"subscriptions":[],"goals":[],"recurring_expenses":[],"recurring_income":[]}' > data.json
    echo "Created data.json"
fi

echo "Done. Run 'python3 run.py' to start."
