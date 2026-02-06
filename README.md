## ABOUT ##
This is a program that helps keep track of inputted expenses.
You can filter and view expenses as well using the main.py file.

## IMPORTANT ##
Read the license for rules about using this program properly.

## IMPORTANT FEATURE INSTRUCTIONS ##
Any files to be processed need to be put in the `files_to_process` directory.

## SETUP THE CLI INTERFACE APP ##

First run the virtual environment (venv) setup:
python -m venv {your_venv_directory_name}

Then, if Windows is being used run:
{your_venv_directory_name}\Scripts\python.exe

If you are on Mac or Linux run:
source {your_venv_directory_name}\bin\activate

Finally you are ready to run the file using the following command:
python cli_app.py

## SETUP THE WEB INTERFACE APP ##

First run the virtual environment (venv) setup:
python -m venv {your_venv_directory_name}

Then, if Windows is being used run:
{your_venv_directory_name}\Scripts\python.exe

If you are on Mac or Linux run:
source {your_venv_directory_name}\bin\activate

Finally, you are ready to run the file using the following command:
streamlit run streamlit_app.py

## POSSIBLE ERRORS ##
If there are packages that need to be installed, use this command to install them:
pip install datetime json pandas pillow questionary requests rich streamlit