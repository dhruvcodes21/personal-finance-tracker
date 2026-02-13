from flask import Flask, request, jsonify
import os
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import numpy as np
from sklearn.linear_model import LinearRegression
import pandas as pd
from predictions import FinancialPredictor

app = Flask(__name__)
financial_predictor = FinancialPredictor()
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

CORS(app)
jwt = JWTManager(app)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'finance_tracker_p3',
    'user': 'root',
    'password': 'root@123'
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def get_user_transactions_df(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            transaction_date AS date,
            amount,
            type,
            category,
            merchant
        FROM transactions
        WHERE user_id = %s
        ORDER BY transaction_date DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    df = pd.DataFrame(rows)

    if not df.empty:
        df["amount"] = df["amount"].astype(float)

    return df

# ==================== Authentication Routes ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    
    if not email or not password or not name:
        return jsonify({'error': 'Missing required fields'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'error': 'User already exists'}), 409
        
        # Create user
        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s)",
            (email, hashed_password, name)
        )
        connection.commit()
        user_id = cursor.lastrowid
        
        access_token = create_access_token(identity=str(user_id))
        return jsonify({
            'message': 'User created successfully',
            'access_token': access_token,
            'user': {'id': user_id, 'email': email, 'name': name}
        }), 201
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Missing credentials'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, email, password_hash, name FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()
        
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        access_token = create_access_token(identity=str(user['id']))
        return jsonify({
            'access_token': access_token,
            'user': {'id': user['id'], 'email': user['email'], 'name': user['name']}
        }), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

# ==================== Transaction Routes ====================

@app.route('/api/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    print("REached get_transactions")
    user_id = int(get_jwt_identity())
    print(1)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM transactions WHERE user_id = %s"
        params = [user_id]
        
        if start_date:
            query += " AND transaction_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND transaction_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY transaction_date DESC"
        cursor.execute(query, params)
        transactions = cursor.fetchall()
        
        return jsonify(transactions), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/transactions', methods=['POST'])
@jwt_required()
def create_transaction():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ['type', 'category', 'amount', 'transaction_date']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO transactions 
            (user_id, type, category, amount, transaction_date, description, merchant)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, data['type'], data['category'], data['amount'],
             data['transaction_date'], data.get('description'), data.get('merchant'))
        )
        connection.commit()
        
        return jsonify({
            'message': 'Transaction created',
            'id': cursor.lastrowid
        }), 201
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/transactions/<int:transaction_id>', methods=['PUT'])
@jwt_required()
def update_transaction(transaction_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Verify ownership
        cursor.execute(
            "SELECT id FROM transactions WHERE id = %s AND user_id = %s",
            (transaction_id, user_id)
        )
        if not cursor.fetchone():
            return jsonify({'error': 'Transaction not found'}), 404
        
        cursor.execute(
            """UPDATE transactions SET 
            type = %s, category = %s, amount = %s, 
            transaction_date = %s, description = %s, merchant = %s
            WHERE id = %s AND user_id = %s""",
            (data.get('type'), data.get('category'), data.get('amount'),
             data.get('transaction_date'), data.get('description'),
             data.get('merchant'), transaction_id, user_id)
        )
        connection.commit()
        
        return jsonify({'message': 'Transaction updated'}), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/transactions/<int:transaction_id>', methods=['DELETE'])
@jwt_required()
def delete_transaction(transaction_id):
    user_id = get_jwt_identity()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM transactions WHERE id = %s AND user_id = %s",
            (transaction_id, user_id)
        )
        connection.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Transaction not found'}), 404
        
        return jsonify({'message': 'Transaction deleted'}), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

# ==================== Budget Routes ====================

@app.route('/api/budgets', methods=['GET'])
@jwt_required()
def get_budgets():
    user_id = get_jwt_identity()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT b.*, 
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as spent
            FROM budgets b
            LEFT JOIN transactions t ON t.user_id = b.user_id 
            AND t.category = b.category
            AND MONTH(t.transaction_date) = MONTH(CURRENT_DATE())
            AND YEAR(t.transaction_date) = YEAR(CURRENT_DATE())
            WHERE b.user_id = %s
            GROUP BY b.id""",
            (user_id,)
        )
        budgets = cursor.fetchall()
        
        return jsonify(budgets), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/budgets', methods=['POST'])
@jwt_required()
def create_budget():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data.get('category') or not data.get('limit_amount'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO budgets (user_id, category, limit_amount) VALUES (%s, %s, %s)",
            (user_id, data['category'], data['limit_amount'])
        )
        connection.commit()
        
        return jsonify({
            'message': 'Budget created',
            'id': cursor.lastrowid
        }), 201
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/budgets/<int:budget_id>', methods=['PUT'])
@jwt_required()
def update_budget(budget_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data.get('category') or not data.get('limit_amount'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            """UPDATE budgets SET 
            category = %s, limit_amount = %s
            WHERE id = %s AND user_id = %s""",
            (data.get('category'), data.get('limit_amount')
            ,budget_id, user_id)
        )
        connection.commit()
        
        return jsonify({
            'message': 'Budget updated'
        }), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/budgets/<int:budget_id>', methods=['DELETE'])
@jwt_required()
def delete_budget(budget_id):
    user_id = get_jwt_identity()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            """DELETE FROM budgets 
            WHERE id = %s AND user_id = %s""",
            (budget_id, user_id)
        )
        connection.commit()
        
        return jsonify({
            'message': 'Budget deleted',
            'id': cursor.lastrowid
        }), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()
# ==================== Savings Goals Routes ====================

@app.route('/api/goals', methods=['GET'])
@jwt_required()
def get_goals():
    user_id = get_jwt_identity()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM savings_goals WHERE user_id = %s ORDER BY deadline ASC",
            (user_id,)
        )
        goals = cursor.fetchall()
        
        return jsonify(goals), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/goals', methods=['POST'])
@jwt_required()
def create_goal():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ['goal_name', 'target_amount', 'deadline']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO savings_goals 
            (user_id, goal_name, target_amount, current_amount, deadline)
            VALUES (%s, %s, %s, %s, %s)""",
            (user_id, data['goal_name'], data['target_amount'],
             data.get('current_amount', 0), data['deadline'])
        )
        connection.commit()
        
        cursor.execute(
            """INSERT INTO savings_goals 
            (user_id, goal_name, target_amount, current_amount, deadline)
            VALUES (%s, %s, %s, %s, %s)""",
            (user_id, data['goal_name'], data['target_amount'],
            data.get('current_amount', 0), data['deadline'])
        )
        connection.commit()

        goal_id = cursor.lastrowid

        return jsonify({
            "id": goal_id,
            "goal_name": data['goal_name'],
            "target_amount": float(data['target_amount']),
            "current_amount": float(data.get('current_amount', 0)),
            "deadline": data['deadline']
        }), 201
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
@jwt_required()
def update_goal(goal_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    
    required_fields = ['goal_name', 'target_amount', 'deadline']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            """UPDATE savings_goals 
            SET goal_name=%s, target_amount=%s, current_amount=%s, deadline=%s
            WHERE user_id=%s AND id=%s""",
            (data['goal_name'], data['target_amount'],
             data.get('current_amount', 0), data['deadline'],user_id,goal_id)
        )
        connection.commit()
        
        return jsonify({
            'message': 'Goal updated',
            'id': cursor.lastrowid
        }), 201
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()


@app.route('/api/goals/<int:goal_id>', methods=['DELETE'])
@jwt_required()
def delete_goal(goal_id):
    user_id = get_jwt_identity()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            """DELETE FROM savings_goals 
            WHERE user_id=%s AND id=%s
            """,
            (user_id,goal_id)
        )
        connection.commit()
        
        return jsonify({
            'message': 'Goal deleted',
            'id': cursor.lastrowid
        }), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

# ==================== Analytics & Predictions ====================

@app.route('/api/analytics/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_analytics():
    user_id = get_jwt_identity()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Current month statistics
        cursor.execute(
            """SELECT 
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses,
            COUNT(*) as transaction_count
            FROM transactions 
            WHERE user_id = %s 
            AND MONTH(transaction_date) = MONTH(CURRENT_DATE())
            AND YEAR(transaction_date) = YEAR(CURRENT_DATE())""",
            (user_id,)
        )
        monthly_stats = cursor.fetchone()
        
        # Category breakdown
        cursor.execute(
            """SELECT category, SUM(amount) as total
            FROM transactions
            WHERE user_id = %s 
            AND type = 'expense'
            AND MONTH(transaction_date) = MONTH(CURRENT_DATE())
            AND YEAR(transaction_date) = YEAR(CURRENT_DATE())
            GROUP BY category
            ORDER BY total DESC""",
            (user_id,)
        )
        category_breakdown = cursor.fetchall()
        
        return jsonify({
            'monthly_stats': monthly_stats,
            'category_breakdown': category_breakdown
        }), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/predictions/cashflow', methods=['GET'])
@jwt_required()
def predict_cashflow():
    user_id = get_jwt_identity()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get last 6 months of data
        cursor.execute(
            """SELECT 
            DATE_FORMAT(transaction_date, '%Y-%m') as month,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
            FROM transactions
            WHERE user_id = %s
            AND transaction_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
            ORDER BY month ASC""",
            (user_id,)
        )
        historical_data = cursor.fetchall()
        
        if len(historical_data) < 2:
            return jsonify({'error': 'Insufficient data for prediction'}), 400
        
        # Simple linear regression for prediction
        df = pd.DataFrame(historical_data)
        df['month_num'] = range(len(df))
        
        # Predict expenses
        X = df[['month_num']].values
        y_expenses = df['expenses'].values
        
        model = LinearRegression()
        model.fit(X, y_expenses)
        
        next_month = len(df)
        predicted_expenses = model.predict([[next_month]])[0]
        
        # Average income for prediction
        avg_income = df['income'].mean()
        
        predicted_balance = avg_income - predicted_expenses
        
        return jsonify({
            'predicted_expenses': round(predicted_expenses, 2),
            'predicted_income': round(avg_income, 2),
            'predicted_balance': round(predicted_balance, 2),
            'confidence': 'medium',
            'historical_data': historical_data
        }), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/insights/spending-patterns', methods=['GET'])
@jwt_required()
def get_spending_patterns():
    user_id = get_jwt_identity()
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Day of week analysis
        cursor.execute(
            """SELECT 
            DAYNAME(transaction_date) as day_of_week,
            COUNT(*) as transaction_count,
            SUM(amount) as total_amount
            FROM transactions
            WHERE user_id = %s AND type = 'expense'
            GROUP BY DAYNAME(transaction_date)
            ORDER BY FIELD(DAYNAME(transaction_date), 
                'Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                'Friday', 'Saturday', 'Sunday')""",
            (user_id,)
        )
        day_patterns = cursor.fetchall()
        
        # Top merchants
        cursor.execute(
            """SELECT merchant, COUNT(*) as visits, SUM(amount) as total_spent
            FROM transactions
            WHERE user_id = %s AND type = 'expense' AND merchant IS NOT NULL
            GROUP BY merchant
            ORDER BY total_spent DESC
            LIMIT 10""",
            (user_id,)
        )
        top_merchants = cursor.fetchall()
        
        return jsonify({
            'day_patterns': day_patterns,
            'top_merchants': top_merchants
        }), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/predictions/cashflow-advanced', methods=['GET'])
@jwt_required()
def cashflow_prediction_advanced():
    user_id = get_jwt_identity()
    df = get_user_transactions_df(user_id)

    if df.empty:
        return jsonify({
            "confidence": "low",
            "message": "Insufficient data",
            "historical_data": []
        }), 200

    result = financial_predictor.predict_cash_flow(df)
    df['date'] = pd.to_datetime(df['date'])
    monthly = df.groupby(
        [df['date'].dt.year.rename('year'), df['date'].dt.month.rename('month'), 'type']
    )['amount'].sum().unstack(fill_value=0).reset_index()

    historical_data = []
    for _, row in monthly.iterrows():
        historical_data.append({
            "month": f"{int(row['year'])}-{int(row['month']):02}",
            "income": float(row.get('income', 0)),
            "expenses": float(row.get('expense', 0))
        })

    result["historical_data"] = historical_data

    return jsonify(result), 200


@app.route('/api/predictions/budget-risk', methods=['GET'])
@jwt_required()
def budget_risk_prediction():
    user_id = get_jwt_identity()
    df = get_user_transactions_df(user_id)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT category, limit_amount
        FROM budgets
        WHERE user_id = %s
    """, (user_id,))
    budgets = {row["category"]: float(row["limit_amount"]) for row in cursor.fetchall()}
    cursor.close()
    connection.close()

    result = financial_predictor.predict_budget_overrun(df, budgets)
    return jsonify(result), 200

@app.route('/api/predictions/goal-timeline/<int:goal_id>', methods=['GET'])
@jwt_required()
def goal_timeline_prediction(goal_id):
    user_id = get_jwt_identity()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT current_amount, target_amount
        FROM savings_goals
        WHERE id = %s AND user_id = %s
    """, (goal_id, user_id))
    goal = cursor.fetchone()

    cursor.execute("""
        SELECT
            SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS expense
        FROM transactions
        WHERE user_id = %s
    """, (user_id,))
    totals = cursor.fetchone()

    cursor.close()
    connection.close()

    result = financial_predictor.calculate_savings_goal_timeline(
        float(goal["current_amount"]),
        float(goal["target_amount"]),
        float(totals["income"] or 0),
        float(totals["expense"] or 0)
    )

    return jsonify(result), 200

@app.route("/api/analytics/monthly-trend", methods=["GET"])
@jwt_required()
def get_monthly_trend():
    user_id = int(get_jwt_identity())

    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                DATE_FORMAT(transaction_date, '%Y-%m') as month,
                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
            FROM transactions
            WHERE user_id = %s
            GROUP BY month
            ORDER BY month ASC
        """

        cursor.execute(query, (user_id,))
        results = cursor.fetchall()

        return jsonify(results), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connection.close()
    
@app.route("/api/predictions/spending-insights", methods=["GET"])
@jwt_required()
def spending_insights():
    user_id = int(get_jwt_identity())

    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT transaction_date as date, amount, type, category FROM transactions WHERE user_id = %s",
            (user_id,)
        )

        rows = cursor.fetchall()

        if not rows:
            return jsonify({}), 200

        df = pd.DataFrame(rows)

        predictor = FinancialPredictor()
        insights = predictor.generate_spending_insights(df)

        return jsonify(insights), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connection.close()

@app.route('/api/predictions/budget-risk', methods=['GET'])
@jwt_required()
def predict_budget_risk():
    user_id = int(get_jwt_identity())

    # Get user transactions as DataFrame
    transactions_df = get_user_transactions_df(user_id)

    if transactions_df.empty:
        return jsonify([]), 200

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT category, limit_amount FROM budgets WHERE user_id = %s",
            (user_id,)
        )
        budgets = cursor.fetchall()

        # Convert to dict format expected by predictor
        budgets_dict = {
            b['category']: float(b['limit_amount'])
            for b in budgets
        }

        if not budgets_dict:
            return jsonify([]), 200

        risks = financial_predictor.predict_budget_overrun(
            transactions_df,
            budgets_dict
        )

        return jsonify(risks), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()
        connection.close()
@app.route('/api/predictions/spending-insights', methods=['GET'])
@jwt_required()
def get_spending_insights():
    user_id = int(get_jwt_identity())

    transactions_df = get_user_transactions_df(user_id)

    if transactions_df.empty:
        return jsonify({}), 200

    try:
        insights = financial_predictor.generate_spending_insights(
            transactions_df
        )

        return jsonify(insights), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/predictions/goal-timeline/<int:goal_id>', methods=['GET'])
@jwt_required()
def predict_goal_timeline(goal_id):
    user_id = int(get_jwt_identity())

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        # Get goal
        cursor.execute("""
            SELECT current_amount, target_amount
            FROM savings_goals
            WHERE id = %s AND user_id = %s
        """, (goal_id, user_id))

        goal = cursor.fetchone()

        if not goal:
            return jsonify({'error': 'Goal not found'}), 404

        # Get monthly income & expenses (last 3 months avg)
        cursor.execute("""
            SELECT
                DATE_FORMAT(transaction_date, '%Y-%m') as month,
                SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expenses
            FROM transactions
            WHERE user_id = %s
            GROUP BY month
            ORDER BY month DESC
            LIMIT 3
        """, (user_id,))

        monthly_data = cursor.fetchall()

        if not monthly_data:
            return jsonify({
                "status": "insufficient_data",
                "message": "Not enough transaction history"
            }), 200

        avg_income = sum(float(m['income']) for m in monthly_data) / len(monthly_data)
        avg_expenses = sum(float(m['expenses']) for m in monthly_data) / len(monthly_data)

        result = financial_predictor.calculate_savings_goal_timeline(
            float(goal['current_amount']),
            float(goal['target_amount']),
            avg_income,
            avg_expenses
        )

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()
        connection.close()
@app.route('/api/predictions/spending-insights', methods=['GET'])
@jwt_required()
def spending_insights_advanced():
    user_id = get_jwt_identity()
    df = get_user_transactions_df(user_id)

    if df.empty:
        return jsonify({
            "monthly_trend": "insufficient_data",
            "weekend_vs_weekday": {
                "weekend_avg": 0,
                "weekday_avg": 0,
                "difference_pct": 0
            },
            "impulse_spending_score": 0
        }), 200

    insights = financial_predictor.generate_spending_insights(df)
    return jsonify(insights), 200

@app.route('/api/goals/<int:goal_id>/contribute', methods=['POST'])
@jwt_required()
def contribute_to_goal(goal_id):
    user_id = get_jwt_identity()
    data = request.get_json()

    amount = float(data.get('amount', 0))

    connection = get_db_connection()
    cursor = connection.cursor()

    # Insert contribution
    cursor.execute("""
        INSERT INTO goal_contributions
        (user_id, goal_id, amount, contribution_date)
        VALUES (%s, %s, %s, CURDATE())
    """, (user_id, goal_id, amount))

    # Update goal current_amount
    cursor.execute("""
        UPDATE savings_goals
        SET current_amount = current_amount + %s
        WHERE id = %s AND user_id = %s
    """, (amount, goal_id, user_id))

    connection.commit()

    return jsonify({"message": "Contribution added"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
