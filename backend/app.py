from flask import Flask, request, jsonify
import os
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import Error
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

# PostgreSQL/Supabase Database configuration
# Get these from your Supabase project settings -> Database
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'qzugxebcrwmdgtccidxj.supabase.co'),
    'database': os.environ.get('DB_NAME', 'postgres'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'Dhruv@supabase1'),
    'port': os.environ.get('DB_PORT', '5432')
}

def get_db_connection():
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

def get_user_transactions_df(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

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
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'error': 'User already exists'}), 409
        
        # Create user
        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s) RETURNING id",
            (email, hashed_password, name)
        )
        user_id = cursor.fetchone()['id']
        connection.commit()
        
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
        cursor = connection.cursor(cursor_factory=RealDictCursor)
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
    print("Reached get_transactions")
    user_id = int(get_jwt_identity())
    print(1)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
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
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """INSERT INTO transactions 
            (user_id, type, category, amount, transaction_date, description, merchant)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (user_id, data['type'], data['category'], data['amount'],
             data['transaction_date'], data.get('description'), data.get('merchant'))
        )
        transaction_id = cursor.fetchone()['id']
        connection.commit()
        
        return jsonify({
            'message': 'Transaction created',
            'id': transaction_id
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
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
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
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM budgets WHERE user_id = %s", (user_id,))
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
    
    if not all(k in data for k in ['category', 'limit_amount']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """INSERT INTO budgets (user_id, category, limit_amount, period)
            VALUES (%s, %s, %s, %s) RETURNING id""",
            (user_id, data['category'], data['limit_amount'], 
             data.get('period', 'monthly'))
        )
        budget_id = cursor.fetchone()['id']
        connection.commit()
        
        return jsonify({'message': 'Budget created', 'id': budget_id}), 201
        
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
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            """UPDATE budgets SET category = %s, limit_amount = %s, period = %s
            WHERE id = %s AND user_id = %s""",
            (data.get('category'), data.get('limit_amount'), 
             data.get('period'), budget_id, user_id)
        )
        connection.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Budget not found'}), 404
        
        return jsonify({'message': 'Budget updated'}), 200
        
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
            "DELETE FROM budgets WHERE id = %s AND user_id = %s",
            (budget_id, user_id)
        )
        connection.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Budget not found'}), 404
        
        return jsonify({'message': 'Budget deleted'}), 200
        
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
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM savings_goals WHERE user_id = %s", (user_id,))
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
    
    required = ['goal_name', 'target_amount', 'deadline']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """INSERT INTO savings_goals 
            (user_id, goal_name, target_amount, current_amount, deadline)
            VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (user_id, data['goal_name'], data['target_amount'],
             data.get('current_amount', 0), data['deadline'])
        )
        goal_id = cursor.fetchone()['id']
        connection.commit()
        
        return jsonify({'message': 'Goal created', 'id': goal_id}), 201
        
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
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            """UPDATE savings_goals SET 
            goal_name = %s, target_amount = %s, current_amount = %s,
            deadline = %s, status = %s
            WHERE id = %s AND user_id = %s""",
            (data.get('goal_name'), data.get('target_amount'),
             data.get('current_amount'), data.get('deadline'),
             data.get('status'), goal_id, user_id)
        )
        connection.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Goal not found'}), 404
        
        return jsonify({'message': 'Goal updated'}), 200
        
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
            "DELETE FROM savings_goals WHERE id = %s AND user_id = %s",
            (goal_id, user_id)
        )
        connection.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Goal not found'}), 404
        
        return jsonify({'message': 'Goal deleted'}), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

# ==================== Analytics Routes ====================

@app.route('/api/analytics/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    user_id = int(get_jwt_identity())
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Get total income and expenses
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses
            FROM transactions
            WHERE user_id = %s
        """, (user_id,))
        totals = cursor.fetchone()
        
        # Get recent transactions
        cursor.execute("""
            SELECT * FROM transactions
            WHERE user_id = %s
            ORDER BY transaction_date DESC
            LIMIT 5
        """, (user_id,))
        recent = cursor.fetchall()
        
        # Get category breakdown
        cursor.execute("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE user_id = %s AND type = 'expense'
            GROUP BY category
            ORDER BY total DESC
        """, (user_id,))
        categories = cursor.fetchall()
        
        return jsonify({
            'totals': totals,
            'recent_transactions': recent,
            'category_breakdown': categories
        }), 200
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/analytics/cash-flow', methods=['GET'])
@jwt_required()
def predict_cash_flow():
    user_id = int(get_jwt_identity())
    
    transactions_df = get_user_transactions_df(user_id)
    
    if transactions_df.empty:
        return jsonify({'error': 'Insufficient data'}), 200
    
    try:
        prediction = financial_predictor.predict_cash_flow(transactions_df)
        return jsonify(prediction), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/analytics/goal-progress/<int:goal_id>", methods=["GET"])
@jwt_required()
def goal_progress(goal_id):
    user_id = int(get_jwt_identity())

    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = connection.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT current_amount, target_amount
        FROM savings_goals
        WHERE id = %s AND user_id = %s
    """, (goal_id, user_id))

    goal = cursor.fetchone()

    if not goal:
        cursor.close()
        connection.close()
        return jsonify({"error": "Goal not found"}), 404

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
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT 
                TO_CHAR(transaction_date, 'YYYY-MM') as month,
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
        cursor = connection.cursor(cursor_factory=RealDictCursor)

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
        cursor = connection.cursor(cursor_factory=RealDictCursor)

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

@app.route('/api/predictions/goal-timeline/<int:goal_id>', methods=['GET'])
@jwt_required()
def predict_goal_timeline(goal_id):
    user_id = int(get_jwt_identity())

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)

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
                TO_CHAR(transaction_date, 'YYYY-MM') as month,
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

@app.route('/api/goals/<int:goal_id>/contribute', methods=['POST'])
@jwt_required()
def contribute_to_goal(goal_id):
    user_id = get_jwt_identity()
    data = request.get_json()

    amount = float(data.get('amount', 0))

    connection = get_db_connection()
    cursor = connection.cursor()

    # Update goal current_amount
    cursor.execute("""
        UPDATE savings_goals
        SET current_amount = current_amount + %s
        WHERE id = %s AND user_id = %s
    """, (amount, goal_id, user_id))

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({"message": "Contribution added"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
