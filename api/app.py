# import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import os
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use the 'Agg' backend for non-interactive plotting
import seaborn as sns
import pandas as pd
from io import BytesIO
from flask import send_file
from datetime import date
import base64
from flask import make_response
import time
from collections import defaultdict
from flask import send_file
import io
# from flask import flash

app = Flask(__name__)
# app.secret_key = 'your_secret_key_here'  # Required for flash messages to work
app.debug = True

# Initialize global variable for Excel DataFrame
global_columns = ['name', 'frequency', 'description', 'goal', 'time_of_day']
global_excel_df = pd.DataFrame(columns=global_columns)

# print(global_excel_df)

# Register datetime globally
app.jinja_env.globals['datetime'] = datetime


# def db_to_excel_format(task_times):
#     # Convert to DataFrame for easier manipulation
#     df = pd.DataFrame(task_times)
#     df.columns = ['date', 'num_timeUnits', 'time_of_day', 'task_value', 'name', 'frequency', 'description', 'goal']

#     # Pivot the DataFrame
#     # ['name', 'time_of_day', 'description', 'frequency'])
#     pivoted_df = df.pivot_table(
#         index=global_columns,  # Rows: task Name, Time of Day, frequency, and description
#         columns='date',                # Columns: Dates
#         values='task_value',          # Values: task Values
#     )

#     return pivoted_df


# def excel_to_db_format(df):

#     # Melt the DataFrame to long format
#     df_long = df.melt(id_vars=['name', 'time_of_day', 'frequency', 'description', 'goal'], var_name='date', value_name='task_value')
#     df_long['date'] = df_long['date'].astype(str)

#     # Drop rows with missing task values
#     # df_long = df_long.dropna(subset=['task_value'])

#     # Convert DataFrame to list of tuples
#     task_time_table = [
#         (row['name'], row['date'], row['time_of_day'], row['task_value'], row['frequency'], row['description'], row['goal'])
#         for _, row in df_long.iterrows()
#     ]

#     # print(df_long)
#     # print(task_time_table)

#     return task_time_table


# Function to manually check if the date is within range
def is_within_pandas_range(date_str):
    try:
        # Convert to datetime object
        date_obj = pd.to_datetime(date_str)
        # Check if the date is within the acceptable range
        if pd.Timestamp.min <= date_obj <= pd.Timestamp.max:
            return True
        else:
            return False
    except Exception as e:
        # Catch any errors that occur during the conversion
        return False


def sort_by_time_of_day(df):
    time_of_day_order = ['morning', 'midday', 'night']
    df['time_of_day'] = pd.Categorical(df['time_of_day'], categories=time_of_day_order, ordered=True)
    df = df.sort_values(by=['time_of_day'])
    df['time_of_day'] = df['time_of_day'].astype(str)
    df = df.reset_index(drop=True)

    return df


@app.route('/')
def task_tracker():

    global global_excel_df
    
    if global_excel_df.empty:
        name_description_frequency_goal_s = global_excel_df[['name', 'frequency', 'description', 'goal']].to_dict(orient='records')
    else:
        name_description_frequency_goal_s = global_excel_df.groupby('time_of_day').get_group('morning')[['name', 'frequency', 'description', 'goal']].to_dict(orient='records')

    # Transform data for display
    table_data = global_excel_df.to_dict('records')
    # pivoted_data, dates = transform_data(task_times)

    # Render the index.html template with the task_times data
    return render_template('index.html', name_description_frequency_goal_s=name_description_frequency_goal_s, table_data=table_data, columns=global_excel_df.columns.tolist())


@app.route('/favicon.ico')
def favicon(): 
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon'


@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    global global_excel_df
    global global_columns

    if 'file' not in request.files:
        # flash("No file part", "error")
        return redirect(url_for('task_tracker'))

    file = request.files['file']

    if file.filename == '':
        # flash("No file selected", "error")
        return redirect(url_for('task_tracker'))

    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            # Read the Excel file into a Pandas DataFrame
            df = pd.read_excel(file)

            # Validate the first len(global_columns) - 1 column names
            required_columns = global_columns[:-1]
            if not all(column in df.columns[:len(required_columns)] for column in required_columns):
                print("Invalid column headers", "error")
                return redirect(url_for('task_tracker'))

            # Check if the total number of columns is valid
            if len(df.columns) < len(global_columns):
                print("Insufficient columns", "error")
                return redirect(url_for('task_tracker'))

            # Validate 'name' column: every 3 rows should have the same name, but it must change between chunks
            names = df['name'].tolist()
            for i in range(0, len(names), 3):
                if len(set(names[i:i + 3])) != 1:
                    print("Invalid 'name' column: names must be consistent in chunks of 3", "error")
                    return redirect(url_for('task_tracker'))
            if len(set(names)) != len(names) // 3:
                print("Invalid 'name' column: repeated names between chunks", "error")
                return redirect(url_for('task_tracker'))

            # Validate 'time_of_day' column: each chunk of 3 rows must have 'morning', 'midday', 'night'
            expected_time_of_day = ['morning', 'midday', 'night']
            time_of_day = df['time_of_day'].tolist()
            for i in range(0, len(time_of_day), 3):
                if set(time_of_day[i:i + 3]) != set(expected_time_of_day):
                    print("Invalid 'time_of_day' column", "error")
                    return redirect(url_for('task_tracker'))

            # Validate 'goal' column: all values should be strings that can convert to integers
            try:
                df['goal'].astype(int)
            except ValueError:
                print("Invalid 'goal' column: values must be integers or convertible to integers", "error")
                return redirect(url_for('task_tracker'))

            # Validate 'frequency' column: values must be 'daily', 'weekly', 'monthly', or 'yearly'
            if not all(freq in ['daily', 'weekly', 'monthly', 'yearly'] for freq in df['frequency']):
                print("Invalid 'frequency' column: values must be 'daily', 'weekly', 'monthly', or 'yearly'", "error")
                return redirect(url_for('task_tracker'))

            # Validate 'description' column: all entries must be strings
            if not all(isinstance(desc, str) for desc in df['description']):
                print("Invalid 'description' column: values must be strings", "error")
                return redirect(url_for('task_tracker'))

            # Validate additional columns (dates)
            for col in df.columns[len(global_columns):]:
                try:
                    pd.to_datetime(col, format='%Y-%m-%d')
                except ValueError:
                    print(f"Invalid date format in column: {col}. Must be YYYY-MM-DD", "error")
                    return redirect(url_for('task_tracker'))

                # Check column values
                if not all(val in ['', '-1', '0', '1'] for val in df[col].astype(str)):
                    print(f"Invalid values in column: {col}. Allowed values are '', '-1', '0', or '1'", "error")
                    return redirect(url_for('task_tracker'))

            # If all validations pass, assign df to global_excel_df
            global_excel_df = df
            print("File uploaded successfully", "success")
        except Exception as e:
            print(f"An error occurred: {str(e)}", "error")
            return redirect(url_for('task_tracker'))

    else:
        print("Invalid file type. Only .xlsx and .xls files are allowed", "error")
    
    # order the time of day values as 'morning' then 'midday' then 'night'
    global_excel_df = sort_by_time_of_day(global_excel_df)
    
    return redirect(url_for('task_tracker'))



@app.route('/add_date_column', methods=['GET', 'POST'])
def add_date_column():

    # Default date: today's date unless specified
    selected_date = request.args.get('new_date', date.today().strftime('%Y-%m-%d'))

    if request.method == 'POST':
        # Get the date to add as a new column
        new_date = request.form['new_date']

        # Check if new date is within allowable pandas datetime range
        if not is_within_pandas_range(new_date):
            return redirect(url_for('add_date_column'))

        # Check if the date is not already a column
        if new_date not in global_excel_df.columns:
            # Add the new date column with empty values (or set it to NaN)
            global_excel_df[new_date] = ''  # Or set to pd.NA or any default value
        # else:
            # If the column already exists, you can display a message or handle accordingly
            # flash(f"Column for {new_date} already exists!", 'error')

        # Redirect back to the update_tasks page after adding the column
        return redirect(url_for('task_tracker'))

    return render_template('add_date_column.html', selected_date=selected_date)


@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':

        global global_excel_df
        global global_columns

        # Retrieve data from the form
        name = request.form['name']
        description = request.form.get('description')  # Optional
        frequency = request.form.get('frequency')  # Must be either "daily", "weekly", "monthly", or "yearly"

        existing_task = False

        if name in global_excel_df['name'].tolist():
            existing_task = True
        
        if existing_task:
            # If task name already exists, show an error message
            return render_template('add_task.html', error_message="Error: task name already exists! Please choose a different name.")

        # Validate frequency (should be 'daily', 'weekly', 'monthly', or 'yearly')
        if frequency not in ['daily', 'weekly', 'monthly', 'yearly']:
            return render_template('add_task.html', error_message="Error: Frequency must be either 'daily' or 'weekly'.")

        for time_of_day in ['morning', 'midday', 'night']:
            # ['date', 'num_timeUnits', 'time_of_day', 'task_value', 'name', 'frequency', 'description']
            # global_columns = ['name', 'frequency', 'description', 'time_of_day']
            global_excel_df.loc[len(global_excel_df), global_columns] = [name, frequency, description, '', time_of_day]
        
        if global_excel_df.shape[1] == 5:
            return redirect(url_for('add_date_column'))

        global_excel_df = global_excel_df.fillna('')

        # Redirect to the homepage or another page
        return redirect(url_for('task_tracker'))  # Assuming you want to go back to the tracker page

    return render_template('add_task.html')


@app.route('/edit_task', methods=['GET', 'POST'])
def edit_task():
    global global_excel_df

    if request.method == 'POST':
        action = request.form.get('action')  # Check which button was pressed

        if action == 'submit':
            # Get selected task and new details from the form
            current_name = request.form.get('current_name')
            new_name = request.form.get('new_name')
            new_description = request.form.get('new_description')
            new_frequency = request.form.get('new_frequency')

            # print(global_excel_df)
            # print(global_excel_df['name'].unique().tolist())

            # Update the task details in the DataFrame
            if current_name in global_excel_df['name'].unique().tolist():
                global_excel_df.loc[global_excel_df['name'] == current_name, 'name'] = new_name
                # Update description (allow empty)
                global_excel_df.loc[global_excel_df['name'] == new_name, 'description'] = (
                    new_description if new_description is not None else ""
                )
                global_excel_df.loc[global_excel_df['name'] == new_name, 'frequency'] = new_frequency
                # flash("task updated successfully!", "success")
            # else:
                # flash("The selected task does not exist.", "error")
        elif action == 'load':
            current_name = request.form.get('current_name')
            return redirect(url_for('edit_task', task=current_name))

        return redirect(url_for('task_tracker'))

    # GET: Preload the list of tasks and their details
    tasks = global_excel_df['name'].unique().tolist()
    selected_task = request.args.get('task', tasks[0] if tasks else None)
    task_details = (
        global_excel_df[global_excel_df['name'] == selected_task].iloc[0]
        if selected_task else None
    )

    return render_template(
        'edit_task.html',
        tasks=tasks,
        selected_task=selected_task,
        task_details=task_details
    )


@app.route('/remove_task/<string:name>', methods=['POST'])
def remove_task(name):

    global global_excel_df
    global_excel_df = global_excel_df.loc[global_excel_df['name'] != name]

    # Redirect back to the task tracker page
    return redirect(url_for('task_tracker'))


@app.route('/update_tasks', methods=['GET', 'POST'])
def update_tasks():
    global global_excel_df
    global global_columns

    global_excel_df_long = global_excel_df.melt(id_vars=['name', 'time_of_day', 'frequency', 'description', 'goal'], var_name='date', value_name='task_value')

    # Default date: today's date unless specified
    selected_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))

    # Get unique tasks from the global DataFrame
    tasks = global_excel_df_long[['name', 'description', 'frequency']].drop_duplicates(subset=['name']).to_dict(orient='records')

    # Initialize task values as empty
    task_values = {}

    if request.method == 'POST':
        action = request.form.get('action')  # Determine which button was pressed

        if action == "Load tasks":
            # Load tasks for the user-specified date
            selected_date = request.form['date']
            task_times = global_excel_df_long[global_excel_df_long['date'] == selected_date]

            # Populate task_values dictionary for the form
            for _, row in task_times.iterrows():
                key = f"{row['name']}_{row['time_of_day']}"
                task_values[key] = row['task_value']

        elif action == "Update tasks":
            # Update tasks for the specified date
            date_of_task = request.form['date']

            # Check if selected date is within allowable pandas datetime range
            if not is_within_pandas_range(date_of_task):
                return redirect(url_for('update_tasks'))

            # Loop through all tasks and update the scores
            for task in tasks:
                task_name = task['name']

                # Retrieve scores for each time of day
                for time_of_day in ['morning', 'midday', 'night']:
                    score = request.form.get(f'{time_of_day}_score_{task_name}')
                    
                    # Update or add the entry in the global DataFrame
                    mask = (
                        (global_excel_df_long['name'] == task_name) &
                        (global_excel_df_long['date'] == date_of_task) &
                        (global_excel_df_long['time_of_day'] == time_of_day)
                    )
                    if mask.any():
                        # Update existing row
                        global_excel_df_long.loc[mask, 'task_value'] = score
                    else:
                        # Add new row
                        global_excel_df_long = pd.concat([global_excel_df_long, pd.DataFrame({
                            'name': [task_name],
                            'description': [task['description']],
                            'frequency': [task['frequency']],
                            'date': [date_of_task],
                            'time_of_day': [time_of_day],
                            'task_value': [score],
                            'goal': ['']
                        })], ignore_index=True)

            global_excel_df = global_excel_df_long.pivot_table(
                index=global_columns,  # Rows: task Name, Time of Day, frequency, and description
                columns='date',                # Columns: Dates
                values='task_value',          # Values: task Values
                aggfunc='first'
            ).reset_index()

            # print(global_excel_df)

            if global_excel_df.shape[1] == 5:
                return redirect(url_for('add_task'))

            # Redirect to the homepage
            return redirect(url_for('task_tracker'))

    # Render the form
    return render_template(
        'update_tasks.html',
        tasks=tasks,
        selected_date=selected_date,
        task_values=task_values,
    )


@app.route('/remove_date', methods=['GET', 'POST'])
def remove_date():
    if request.method == 'POST':
        global global_excel_df
        date_to_delete = request.form['date']  # The date entered by the user
        # print(global_excel_df)
        # print(type(date_to_delete))

        global_excel_df = global_excel_df.drop(columns=[date_to_delete])

        # Redirect to the homepage or a confirmation page
        return redirect(url_for('task_tracker'))  # Or you can redirect to a different page if desired

    return render_template('remove_date.html')


@app.route('/set_goals', methods=['GET', 'POST'])
def set_goals():
    global global_excel_df

    if request.method == 'POST':
        # Extract the submitted goal data from the form
        goals_data = request.form.to_dict()

        # Add a 'goal' column if it doesn't already exist
        if 'goal' not in global_excel_df.columns:
            global_excel_df['goal'] = ''

        # Validation limits based on frequency
        limits = {
            'daily': (-3, 3),
            'weekly': (-21, 21),
            'monthly': (-90, 90),
            'yearly': (-365 * 3, 365 * 3),
        }

        # Update the 'goal' column for each task
        for task_name, goal_value in goals_data.items():
            if task_name in global_excel_df['name'].unique():
                # Get the frequency of the task
                frequency = global_excel_df.loc[global_excel_df['name'] == task_name, 'frequency'].iloc[0]
                
                # Convert goal_value to integer and validate
                try:
                    goal_value = int(goal_value)
                except ValueError:
                    goal_value = ''  # Treat non-integer inputs as invalid

                # Check if the goal is within the allowed range for its frequency
                if frequency in limits and goal_value != '':
                    min_limit, max_limit = limits[frequency]
                    if min_limit <= goal_value <= max_limit:
                        global_excel_df.loc[global_excel_df['name'] == task_name, 'goal'] = goal_value
                    # else:
                        # flash(f"Goal for '{task_name}' must be between {min_limit} and {max_limit} for {frequency} frequency.")
                # else:
                    # flash(f"Invalid frequency or goal value for task '{task_name}'.")

        return redirect(url_for('task_tracker'))

    # Pass tasks and current goals to the form
    tasks = global_excel_df['name'].unique().tolist()
    current_goals = global_excel_df.set_index('name')['goal'].to_dict()  # Map task names to current goals
    return render_template('set_goals.html', tasks=tasks, current_goals=current_goals)



@app.route('/plot_task_scores_for_each_task', methods=['GET'])
def plot_task_scores_for_each_task():

    global global_excel_df
    global global_columns

    # Get width and height from query parameters, or use default values
    width = int(request.args.get('width', 10))  # Default to 10
    height = int(request.args.get('height', 7))  # Default to 7
    x_fontsize = int(request.args.get('x_fontsize', 14))  # Default to 14
    y_fontsize = int(request.args.get('y_fontsize', 14))  # Default to 14
    title_fontsize = int(request.args.get('title_fontsize', 16))  # Default to 16

    frequencies = ['daily', 'weekly', 'monthly', 'yearly']
    plots = {}

    if global_excel_df.shape[1] != len(global_columns):
        for freq in frequencies:
            buf = generate_timeUnitly_for_each_task_plots(freq, width, height, x_fontsize, y_fontsize, title_fontsize)
            # Encode plot to base64
            plots[freq] = base64.b64encode(buf.getvalue()).decode('utf-8')

    # Pass the plot data and other parameters to the template
    return render_template(
        'plot_task_scores_for_each_task.html',
        plots=plots,
        timestamp=int(time.time()),
        current_width=width,
        current_height=height,
        current_x_fontsize=x_fontsize,
        current_y_fontsize=y_fontsize,
        current_title_fontsize=title_fontsize
    )

def generate_timeUnitly_for_each_task_plots(frequency, width, height, x_fontsize, y_fontsize, title_fontsize):

    global global_excel_df

    df = global_excel_df.melt(id_vars=['name', 'time_of_day', 'frequency', 'description', 'goal'], var_name='date', value_name='task_value')
    df['date'] = pd.to_datetime(df['date'])  # Convert date to datetime format

    # Extract tracking start time
    start_date = df['date'][0].date()

    # Process df
    df = df.sort_values(by='date')
    df['num_days'] = df['date'] - df['date'][0]

    if frequency == 'daily':
        num_days_per_timeUnit = 1
    elif frequency == 'weekly':
        num_days_per_timeUnit = 7
    elif frequency == 'monthly':
        num_days_per_timeUnit = 30
    elif frequency == 'yearly':
        num_days_per_timeUnit = 365
    else:
        num_days_per_timeUnit = 0 # Intentionally raise an error

    df['num_timeUnits'] = df['num_days'] // num_days_per_timeUnit 
    df['task_value'] = df['task_value'].replace('', '0').astype(int)
    df = df.loc[df['frequency'] == frequency]
    timeUnitly_scores_for_each_task_df = df.groupby(['num_timeUnits', 'name'])['task_value'].sum().reset_index()
    timeUnitly_scores_for_each_task_df['num_timeUnits'] = timeUnitly_scores_for_each_task_df['num_timeUnits'].astype(int)

    # Convert the DataFrame to the plot_data dictionary
    timeUnitly_scores_for_each_task_groups = timeUnitly_scores_for_each_task_df.groupby('name')
    name_list = list(timeUnitly_scores_for_each_task_groups.groups.keys())
    plot_data = {}

    for name in name_list:
        df_at_name = timeUnitly_scores_for_each_task_groups.get_group(name)
        dates = df_at_name['num_timeUnits'].tolist()
        values = df_at_name['task_value'].tolist()
        plot_data[name] = {'dates': dates, 'values': values}

    # Create the plot
    num_tasks = len(plot_data)
    if num_tasks == 0:
        rows = 1
        cols = 1
    else:
        rows = int(num_tasks**0.5)
        cols = (num_tasks + rows - 1) // rows

    fig, axes = plt.subplots(rows, cols, figsize=(width, height), constrained_layout=True)
    if num_tasks > 1:
        axes = axes.flatten()

    for i, (task_name, data) in enumerate(plot_data.items()):
        if num_tasks != 1:
            ax = axes[i]
        else:
            ax = axes
        # Extract goal for task
        goal = global_excel_df.loc[global_excel_df['name'] == task_name]['goal'].tolist()[0]
        # Plot data
        ax.plot(data['dates'], data['values'], marker='o')
        # Plot a horizontal line at task goal
        ax.axhline(y=goal, color='red', linestyle='dotted', linewidth=2)
        ax.set_title(task_name, fontsize=title_fontsize)
        ax.set_xlabel('Time', fontsize=x_fontsize)
        ax.set_ylabel('Sum of Scores', fontsize=y_fontsize)
        ax.grid(True)

    # Remove unused subplots
    if num_tasks > 1:
        for j in range(i + 1, len(axes)):
            fig.delaxes(axes[j])

    # Save plot to buf
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return buf


@app.route('/plot_task_scores')
def plot_task_scores():

    global global_excel_df
    global global_columns

    # Get width and height from query parameters, or use default values
    width = int(request.args.get('width', 10))  # Default to 10
    height = int(request.args.get('height', 7))  # Default to 7
    x_fontsize = int(request.args.get('x_fontsize', 14))  # Default to 14
    y_fontsize = int(request.args.get('y_fontsize', 14))  # Default to 14
    title_fontsize = int(request.args.get('title_fontsize', 16))  # Default to 16

    frequencies = ['daily', 'weekly', 'monthly', 'yearly']
    plots = {}

    if global_excel_df.shape[1] != len(global_columns):
        for freq in frequencies:
            buf = generate_timeUnitly_task_plot(freq, width, height, x_fontsize, y_fontsize, title_fontsize)
            # Encode plot to base64
            plots[freq] = base64.b64encode(buf.getvalue()).decode('utf-8')

    # Pass the plot data and other parameters to the template
    return render_template(
        'plot_task_scores.html',
        plots=plots,
        timestamp=int(time.time()),
        current_width=width,
        current_height=height,
        current_x_fontsize=x_fontsize,
        current_y_fontsize=y_fontsize,
        current_title_fontsize=title_fontsize
    )

def generate_timeUnitly_task_plot(frequency, width, height, x_fontsize, y_fontsize, title_fontsize):

    global global_excel_df
    global global_columns

    df = global_excel_df.melt(id_vars=global_columns, var_name='date', value_name='task_value')
    df['date'] = pd.to_datetime(df['date'])  # Convert date to datetime format

    # Extract tracking start time
    start_date = df['date'][0].date()

    # Process df
    df = df.sort_values(by='date')
    df['num_days'] = df['date'] - df['date'][0]

    if frequency == 'daily':
        num_days_per_timeUnit = 1
    elif frequency == 'weekly':
        num_days_per_timeUnit = 7
    elif frequency == 'monthly':
        num_days_per_timeUnit = 30
    elif frequency == 'yearly':
        num_days_per_timeUnit = 365
    else:
        num_days_per_timeUnit = 0 # Intentionally raise an error

    df['num_timeUnits'] = df['num_days'] // num_days_per_timeUnit 
    df['task_value'] = df['task_value'].replace('', '0').astype(int)
    df = df.loc[df['frequency'] == frequency]
    timeUnitly_scores = df.groupby('num_timeUnits')['task_value'].sum()
    timeUnitly_scores.index = timeUnitly_scores.index.astype(int)

    # Extract net goal for task score
    goal = sum(global_excel_df.loc[global_excel_df['time_of_day'] == 'morning', 'goal'].loc[global_excel_df['frequency'] == frequency].replace('', '0').astype(int).tolist())
    # print(goal)

    # Create the plot
    fig = plt.figure(figsize=(width, height))
    sns.lineplot(x=timeUnitly_scores.index.tolist(), y=timeUnitly_scores.values, marker='o')
    plt.axhline(y=goal, color='red', linestyle='dotted', linewidth=2)
    plt.title(f'Sum of {frequency} task Scores Over Time (Since {start_date})', fontsize=title_fontsize)
    plt.xlabel('Time', fontsize=x_fontsize)
    plt.ylabel('Total Score', fontsize=y_fontsize)
    plt.xticks(rotation=45)
    # plt.legend()
    plt.grid()

    # Save plot to buf
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return buf

@app.route('/download_excel', methods=['GET'])
def download_excel():
    global global_excel_df

    # Convert the DataFrame to an Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        global_excel_df.to_excel(writer, index=False, sheet_name='tasks')
        writer.close()

    output.seek(0)  # Go to the beginning of the stream

    # Send the Excel file to the user for download
    return send_file(
        output,
        as_attachment=True,
        download_name='periodic_task_tracker.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# if __name__ == '__main__':
#     app.run()
# #     app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
