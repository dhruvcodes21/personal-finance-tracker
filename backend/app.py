from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-this')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
jwt = JWTManager(app)

# Database connection with timeout
def get_db_connection():
    try:
        database_url = os.environ.get('DATABASE_URL')

        if not database_url:
            print("DATABASE_URL not set!")
            return None

        conn = psycopg2.connect(
            database_url,
            connect_timeout=10,
            cursor_factory=RealDictCursor,
            sslmode="require"   # 👈 Force SSL for Supabase
        )

        return conn

    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Initialize database tables
def init_db():
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Transactions table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                amount DECIMAL(10, 2) NOT NULL,
                category VARCHAR(50) NOT NULL,
                description TEXT,
                transaction_type VARCHAR(20) NOT NULL,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        conn.close()

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200

# Register endpoint - FIXED (no ML training)
@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not all([username, email, password]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Check if user exists
            cur.execute('SELECT id FROM users WHERE username = %s OR email = %s', (username, email))
            if cur.fetchone():
                return jsonify({'error': 'User already exists'}), 409
            
            # Create user
            password_hash = generate_password_hash(password)
            cur.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
                (username, email, password_hash)
            )
            user_id = cur.fetchone()['id']
            conn.commit()
            
            # Create access token
            access_token = create_access_token(identity=user_id)
            
            return jsonify({
                'message': 'User registered successfully',
                'access_token': access_token,
                'user_id': user_id
            }), 201
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({'error': str(e)}), 500

# Login endpoint
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not all([username, password]):
            return jsonify({'error': 'Missing credentials'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute('SELECT id, password_hash FROM users WHERE username = %s', (username,))
            user = cur.fetchone()
            
            if not user or not check_password_hash(user['password_hash'], password):
                return jsonify({'error': 'Invalid credentials'}), 401
            
            access_token = create_access_token(identity=user['id'])
            
            return jsonify({
                'message': 'Login successful',
                'access_token': access_token,
                'user_id': user['id']
            }), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': str(e)}), 500

# Get transactions
@app.route('/api/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    try:
        user_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT * FROM transactions WHERE user_id = %s ORDER BY date DESC',
                (user_id,)
            )
            transactions = cur.fetchall()
            
            return jsonify({'transactions': transactions}), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Get transactions error: {e}")
        return jsonify({'error': str(e)}), 500

# Add transaction
@app.route('/api/transactions', methods=['POST'])
@jwt_required()
def add_transaction():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        amount = data.get('amount')
        category = data.get('category')
        description = data.get('description', '')
        transaction_type = data.get('type')
        date = data.get('date')
        
        if not all([amount, category, transaction_type, date]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute(
                '''INSERT INTO transactions (user_id, amount, category, description, transaction_type, date)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id''',
                (user_id, amount, category, description, transaction_type, date)
            )
            transaction_id = cur.fetchone()['id']
            conn.commit()
            
            return jsonify({
                'message': 'Transaction added successfully',
                'transaction_id': transaction_id
            }), 201
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Add transaction error: {e}")
        return jsonify({'error': str(e)}), 500

# ML Predictions endpoint - Train model ONLY when user requests predictions
@app.route('/api/predictions', methods=['GET'])
@jwt_required()
def get_predictions():
    try:
        user_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT amount, category, transaction_type, date FROM transactions WHERE user_id = %s',
                (user_id,)
            )
            transactions = cur.fetchall()
            
            # Need at least 10 transactions for meaningful predictions
            if len(transactions) < 10:
                return jsonify({
                    'message': 'Not enough data for predictions',
                    'required': 10,
                    'current': len(transactions)
                }), 200
            
            # Convert to DataFrame
            df = pd.DataFrame(transactions)
            
            # Feature engineering
            df['date'] = pd.to_datetime(df['date'])
            df['month'] = df['date'].dt.month
            df['day_of_week'] = df['date'].dt.dayofweek
            
            # Encode categorical variables
            df['category_encoded'] = pd.Categorical(df['category']).codes
            df['type_encoded'] = pd.Categorical(df['transaction_type']).codes
            
            # Prepare features
            X = df[['amount', 'category_encoded', 'type_encoded', 'month', 'day_of_week']]
            y = df['category_encoded']
            
            # Train model only if we have enough data
            if len(X) >= 10:
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                
                model = RandomForestClassifier(n_estimators=50, random_state=42, max_depth=5)
                model.fit(X_train, y_train)
                
                # Get predictions for next month
                next_month_predictions = {
                    'predicted_spending': float(df[df['transaction_type'] == 'expense']['amount'].mean()),
                    'predicted_categories': df['category'].value_counts().head(3).to_dict(),
                    'model_accuracy': float(model.score(X_test, y_test)) if len(X_test) > 0 else 0
                }
                
                return jsonify(next_month_predictions), 200
            else:
                return jsonify({'message': 'Not enough data'}), 200
                
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Predictions error: {e}")
        return jsonify({'error': str(e)}), 500

# Delete transaction
@app.route('/api/transactions/<int:transaction_id>', methods=['DELETE'])
@jwt_required()
def delete_transaction(transaction_id):
    try:
        user_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute(
                'DELETE FROM transactions WHERE id = %s AND user_id = %s RETURNING id',
                (transaction_id, user_id)
            )
            deleted = cur.fetchone()
            
            if not deleted:
                return jsonify({'error': 'Transaction not found'}), 404
            
            conn.commit()
            return jsonify({'message': 'Transaction deleted successfully'}), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Delete transaction error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=False)
