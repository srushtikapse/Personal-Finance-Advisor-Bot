import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai

from config import Config
from models import db, User, Income, Expense
import time

def get_ai_recommendation(income_total, expense_total, expenses):
    api_key = app.config.get('GEMINI_API_KEY')
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        return "Gemini API key is not configured. Add your API key to environment variables."

    expense_summary = ", ".join([f"{e.category}: ${e.amount}" for e in expenses])
    prompt = f"""
    You are an expert personal finance advisor bot.
    Analyze this financial summary:
    Total Monthly Income: ${income_total}
    Total Monthly Expenses: ${expense_total}
    Expense Breakdown: {expense_summary if expense_summary else 'No expenses logged yet.'}

    Provide:
    1. A short analysis of current spending habits.
    2. Overspending risk evaluation.
    3. 3 actionable savings recommendations and budget optimization tips.
    4. Emergency fund guidance tailored to this income level.
    Keep the response clear, practical, and structured in bullet points.
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
            )
            return response.text
        except Exception as e:
            error_message = str(e)
            
            # If network/SSL error occurs and we have retries left, wait briefly and retry
            if ("SSL" in error_message or "EOF" in error_message or "503" in error_message) and attempt < max_retries - 1:
                time.sleep(1)
                continue
            
            if "503" in error_message or "UNAVAILABLE" in error_message:
                return (
                    "🤖 AI service is temporarily busy. "
                    "Please refresh the dashboard and try again in a few moments."
                )

            if "SSL" in error_message or "EOF" in error_message:
                return (
                    "🤖 Network connection issue occurred while generating AI advice. "
                    "Please refresh the page to try again."
                )

            return f"Could not generate AI advice at this time. Error: {error_message}"


# --------------------------------------------------
# Flask App Setup
# --------------------------------------------------

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


# --------------------------------------------------
# Flask Login Setup
# --------------------------------------------------

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------
# AI Financial Recommendation
# --------------------------------------------------

def get_ai_recommendation(income_total, expense_total, expenses):

    api_key = app.config.get('GEMINI_API_KEY')

    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        return "Gemini API key is not configured. Add your API key to the .env file."

    expense_summary = ", ".join(
        [f"{e.category}: ${e.amount}" for e in expenses]
    )

    prompt = f"""
    You are an expert personal finance advisor bot.

    Analyze this financial summary:

    Total Monthly Income: ${income_total}
    Total Monthly Expenses: ${expense_total}

    Expense Breakdown:
    {expense_summary if expense_summary else 'No expenses logged yet.'}

    Provide:

    1. A short analysis of current spending habits.
    2. Overspending risk evaluation.
    3. 3 actionable savings recommendations and budget optimization tips.
    4. Emergency fund guidance tailored to this income level.

    Keep the response clear, practical and structured in bullet points.
    """

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
        )

        return response.text

    except Exception as e:
        return f"Could not generate AI advice at this time. Error: {str(e)}"


# --------------------------------------------------
# Home
# --------------------------------------------------

@app.route('/')
def home():

    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    return redirect(url_for('login'))


# --------------------------------------------------
# Register
# --------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        # Check empty fields
        if not username or not email or not password:

            flash(
                'Please fill in all fields.',
                'danger'
            )

            return redirect(url_for('register'))

        # Check duplicate username
        existing_username = User.query.filter_by(
            username=username
        ).first()

        if existing_username:

            flash(
                'Username already exists! Please choose another username.',
                'danger'
            )

            return redirect(url_for('register'))

        # Check duplicate email
        existing_email = User.query.filter_by(
            email=email
        ).first()

        if existing_email:

            flash(
                'Email already registered! Please use another email.',
                'danger'
            )

            return redirect(url_for('register'))

        # Hash password
        hashed_pwd = generate_password_hash(
            password,
            method='scrypt'
        )

        # Create new user
        new_user = User(
            username=username,
            email=email,
            password=hashed_pwd
        )

        try:

            db.session.add(new_user)
            db.session.commit()

            flash(
                'Account created successfully! Please login.',
                'success'
            )

            return redirect(url_for('login'))

        except Exception:

            db.session.rollback()

            flash(
                'Registration failed. Please try again.',
                'danger'
            )

            return redirect(url_for('register'))

    return render_template('register.html')


# --------------------------------------------------
# Login
# --------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            login_user(user)

            return redirect(
                url_for('dashboard')
            )

        else:

            flash(
                'Invalid login credentials.',
                'danger'
            )

    return render_template('login.html')


# --------------------------------------------------
# Logout
# --------------------------------------------------

@app.route('/logout')
@login_required
def logout():

    logout_user()

    flash(
        'Logged out successfully.',
        'info'
    )

    return redirect(
        url_for('login')
    )


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():

    incomes = Income.query.filter_by(
        user_id=current_user.id
    ).all()

    expenses = Expense.query.filter_by(
        user_id=current_user.id
    ).all()

    total_income = sum(
        i.amount for i in incomes
    )

    total_expense = sum(
        e.amount for e in expenses
    )

    net_savings = (
        total_income - total_expense
    )

    ai_advice = get_ai_recommendation(
        total_income,
        total_expense,
        expenses
    )

    return render_template(
        'dashboard.html',
        user=current_user,
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expense=total_expense,
        net_savings=net_savings,
        ai_advice=ai_advice
    )


# --------------------------------------------------
# Add Income
# --------------------------------------------------

@app.route('/add_income', methods=['GET', 'POST'])
@login_required
def add_income():

    if request.method == 'POST':

        source = request.form.get('source')
        raw_amount = request.form.get('amount')

        try:

            amount = float(raw_amount)

        except (ValueError, TypeError):

            flash(
                'Invalid amount entered.',
                'danger'
            )

            return render_template(
                'add_income.html'
            )

        if amount <= 0:

            flash(
                'Amount must be greater than 0.',
                'danger'
            )

            return render_template(
                'add_income.html'
            )

        income = Income(
            source=source,
            amount=amount,
            user_id=current_user.id
        )

        db.session.add(income)
        db.session.commit()

        flash(
            'Income added successfully!',
            'success'
        )

        return redirect(
            url_for('dashboard')
        )

    return render_template(
        'add_income.html'
    )


# --------------------------------------------------
# Add Expense
# --------------------------------------------------

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():

    if request.method == 'POST':

        category = request.form.get('category')
        raw_amount = request.form.get('amount')
        description = request.form.get(
            'description',
            ''
        )

        try:

            amount = float(raw_amount)

        except (ValueError, TypeError):

            flash(
                'Invalid amount entered.',
                'danger'
            )

            return render_template(
                'add_expense.html'
            )

        if amount <= 0:

            flash(
                'Amount must be greater than 0.',
                'danger'
            )

            return render_template(
                'add_expense.html'
            )

        try:

            expense = Expense(
                category=category,
                amount=amount,
                description=description,
                user_id=current_user.id
            )

            db.session.add(expense)
            db.session.commit()

            flash(
                'Expense added successfully!',
                'success'
            )

            return redirect(
                url_for('dashboard')
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f'Failed to add expense: {str(e)}',
                'danger'
            )

            return render_template(
                'add_expense.html'
            )

    return render_template(
        'add_expense.html'
    )


# --------------------------------------------------
# Run Application
# --------------------------------------------------

if __name__ == '__main__':

    with app.app_context():
        db.create_all()

    app.run(debug=True)