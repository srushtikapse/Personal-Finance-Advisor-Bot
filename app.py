import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai
from config import Config
from models import db, User, Income, Expense

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_ai_recommendation(income_total, expense_total, expenses):
    api_key = app.config.get('GEMINI_API_KEY')
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        return "Gemini API key is not configured. Add your API key to the .env file."

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
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Could not generate AI advice at this time. Error: {str(e)}"

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        hashed_pwd = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, email=email, password=hashed_pwd)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid login credentials.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    incomes = Income.query.filter_by(user_id=current_user.id).all()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    total_income = sum(i.amount for i in incomes)
    total_expense = sum(e.amount for e in expenses)
    net_savings = total_income - total_expense

    ai_advice = get_ai_recommendation(total_income, total_expense, expenses)

    return render_template('dashboard.html', 
                           user=current_user, 
                           incomes=incomes, 
                           expenses=expenses, 
                           total_income=total_income, 
                           total_expense=total_expense, 
                           net_savings=net_savings, 
                           ai_advice=ai_advice)

@app.route('/add_income', methods=['GET', 'POST'])
@login_required
def add_income():
    if request.method == 'POST':
        source = request.form.get('source')
        raw_amount = request.form.get('amount')

        try:
            amount = float(raw_amount)
        except (ValueError, TypeError):
            flash('Invalid amount entered.', 'danger')
            return render_template('add_income.html')

        income = Income(source=source, amount=amount, user_id=current_user.id)
        db.session.add(income)
        db.session.commit()
        flash('Income added!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_income.html')

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        category = request.form.get('category')
        raw_amount = request.form.get('amount')
        description = request.form.get('description', '')

        try:
            amount = float(raw_amount)
        except (ValueError, TypeError):
            flash('Invalid amount entered.', 'danger')
            return render_template('add_expense.html')

        try:
            expense = Expense(category=category, amount=amount, description=description, user_id=current_user.id)
            db.session.add(expense)
            db.session.commit()
            flash('Expense added!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add expense: {str(e)}', 'danger')
            return render_template('add_expense.html')

    return render_template('add_expense.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)