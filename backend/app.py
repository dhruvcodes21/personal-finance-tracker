from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-this-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
jwt = JWTManager(app)

# Database connection with timeout
def get_db_connection():
    try:
        conn = psycopg2.connect(
            os.environ.get('DATABASE_URL'),
            connect_timeout=10,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Initialize database schema
def init_db():
    """Run the complete PostgreSQL schema"""
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to database")
        return
    
    try:
        cur = conn.cursor()
        print("📦 Creating database schema...")
        
        # Enable UUID extension
        cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        
        # Users Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        print("✅ Users table created")
        
        # Transactions Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                type VARCHAR(10) NOT NULL CHECK (type IN ('income', 'expense')),
                category VARCHAR(50) NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                transaction_date DATE NOT NULL,
                description TEXT,
                merchant VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_date)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type)')
        print("✅ Transactions table created")
        
        # Budgets Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS budgets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                category VARCHAR(50) NOT NULL,
                limit_amount NUMERIC(10, 2) NOT NULL,
                period VARCHAR(10) DEFAULT 'monthly' CHECK (period IN ('monthly', 'yearly')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE (user_id, category)
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_budgets_user ON budgets(user_id)')
        print("✅ Budgets table created")
        
        # Savings Goals Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS savings_goals (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                goal_name VARCHAR(100) NOT NULL,
                target_amount NUMERIC(10, 2) NOT NULL,
                current_amount NUMERIC(10, 2) DEFAULT 0.00,
                deadline DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_savings_goals_user ON savings_goals(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_savings_goals_status ON savings_goals(status)')
        print("✅ Savings goals table created")
        
        # Categories Reference Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                type VARCHAR(10) DEFAULT 'both' CHECK (type IN ('income', 'expense', 'both')),
                icon VARCHAR(50),
                color VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Categories table created")
        
        # Insert default categories
        cur.execute('''
            INSERT INTO categories (name, type, icon, color) 
            SELECT * FROM (VALUES
                ('Salary', 'income', 'briefcase', '#10b981'),
                ('Freelance', 'income', 'laptop', '#3b82f6'),
                ('Investments', 'income', 'trending-up', '#8b5cf6'),
                ('Other Income', 'income', 'dollar-sign', '#06b6d4'),
                ('Food & Dining', 'expense', 'utensils', '#ef4444'),
                ('Transportation', 'expense', 'car', '#f59e0b'),
                ('Shopping', 'expense', 'shopping-bag', '#ec4899'),
                ('Entertainment', 'expense', 'film', '#8b5cf6'),
                ('Utilities', 'expense', 'zap', '#10b981'),
                ('Healthcare', 'expense', 'heart', '#ef4444'),
                ('Education', 'expense', 'book', '#3b82f6'),
                ('Travel', 'expense', 'plane', '#06b6d4'),
                ('Insurance', 'expense', 'shield', '#6366f1'),
                ('Subscriptions', 'expense', 'refresh-cw', '#f59e0b'),
                ('Other', 'both', 'more-horizontal', '#6b7280')
            ) AS v(name, type, icon, color)
            WHERE NOT EXISTS (
                SELECT 1 FROM categories WHERE categories.name = v.name
            )
        ''')
        print("✅ Default categories inserted")
        
        # Notifications Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                type VARCHAR(20) NOT NULL CHECK (type IN ('budget_alert', 'goal_reminder', 'insight', 'general')),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)')
        print("✅ Notifications table created")
        
        # User Preferences Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL,
                currency VARCHAR(10) DEFAULT 'INR',
                budget_alert_threshold INTEGER DEFAULT 80,
                enable_notifications BOOLEAN DEFAULT TRUE,
                theme VARCHAR(10) DEFAULT 'light' CHECK (theme IN ('light', 'dark', 'auto')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        print("✅ User preferences table created")
        
        # Recurring Transactions Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS recurring_transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                type VARCHAR(10) NOT NULL CHECK (type IN ('income', 'expense')),
                category VARCHAR(50) NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                description TEXT,
                merchant VARCHAR(100),
                frequency VARCHAR(10) NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly', 'yearly')),
                start_date DATE NOT NULL,
                end_date DATE,
                is_active BOOLEAN DEFAULT TRUE,
                last_processed DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_recurring_transactions_user_active ON recurring_transactions(user_id, is_active)')
        print("✅ Recurring transactions table created")
        
        # Financial Insights Cache Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS insights_cache (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                insight_type VARCHAR(50) NOT NULL,
                insight_data JSONB NOT NULL,
                valid_until TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_insights_cache_user_type ON insights_cache(user_id, insight_type)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_insights_cache_valid ON insights_cache(valid_until)')
        print("✅ Insights cache table created")
        
        # Create trigger function for updated_at
        cur.execute('''
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        ''')
        
        # Apply triggers
        tables_with_updated_at = ['users', 'transactions', 'budgets', 'savings_goals', 'user_preferences', 'recurring_transactions']
        for table in tables_with_updated_at:
            cur.execute(f'''
                DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
                CREATE TRIGGER update_{table}_updated_at 
                BEFORE UPDATE ON {table}
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            ''')
        print("✅ Triggers created")
        
        conn.commit()
        cur.close()
        print("✅ Database schema initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        conn.rollback()
    finally:
        conn.close()

# Health check endpoint
@app.route('/api/health', methods=['GET'])
@app.route('/', methods=['GET'])
def health_check():
    db_status = 'disconnected'
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            db_status = 'connected'
    except:
        pass
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    }), 200

# Register endpoint - UPDATED TO MATCH SCHEMA
@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Schema uses 'name', 'email', 'password'
        name = data.get('username') or data.get('name')  # Accept both for compatibility
        email = data.get('email')
        password = data.get('password')
        
        if not all([name, email, password]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Check if user exists
            cur.execute('SELECT id FROM users WHERE email = %s', (email,))
            if cur.fetchone():
                return jsonify({'error': 'User already exists'}), 409
            
            # Create user
            password_hash = generate_password_hash(password)
            cur.execute(
                'INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id, name, email',
                (name, email, password_hash)
            )
            user = cur.fetchone()
            user_id = user['id']
            
            # Create default user preferences
            cur.execute(
                'INSERT INTO user_preferences (user_id) VALUES (%s)',
                (user_id,)
            )
            
            conn.commit()
            
            # Create access token
            access_token = create_access_token(identity=user_id)
            
            return jsonify({
                'message': 'User registered successfully',
                'access_token': access_token,
                'user': {
                    'id': user['id'],
                    'name': user['name'],
                    'email': user['email']
                }
            }), 201
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({'error': str(e)}), 500

# Login endpoint - UPDATED TO MATCH SCHEMA
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Accept either email or username (treat username as email)
        email = data.get('email') or data.get('username')
        password = data.get('password')
        
        if not all([email, password]):
            return jsonify({'error': 'Missing credentials'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute('SELECT id, name, email, password_hash FROM users WHERE email = %s', (email,))
            user = cur.fetchone()
            
            if not user or not check_password_hash(user['password_hash'], password):
                return jsonify({'error': 'Invalid credentials'}), 401
            
            access_token = create_access_token(identity=user['id'])
            
            return jsonify({
                'message': 'Login successful',
                'access_token': access_token,
                'user': {
                    'id': user['id'],
                    'name': user['name'],
                    'email': user['email']
                }
            }), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': str(e)}), 500

# Get categories
@app.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        category_type = request.args.get('type')  # 'income', 'expense', or None for all
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            if category_type:
                cur.execute(
                    "SELECT * FROM categories WHERE type = %s OR type = 'both' ORDER BY name",
                    (category_type,)
                )
            else:
                cur.execute('SELECT * FROM categories ORDER BY type, name')
            
            categories = cur.fetchall()
            return jsonify({'categories': categories}), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Get categories error: {e}")
        return jsonify({'error': str(e)}), 500

# Get all transactions
@app.route('/api/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    try:
        user_id = get_jwt_identity()
        limit = request.args.get('limit', 100, type=int)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT * FROM transactions
                WHERE user_id = %s
                ORDER BY transaction_date DESC, created_at DESC
                LIMIT %s
            ''', (user_id, limit))
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
        transaction_type = data.get('type')
        transaction_date = data.get('date') or datetime.now().date().isoformat()
        description = data.get('description', '')
        merchant = data.get('merchant', '')
        
        if not all([amount, category, transaction_type]):
            return jsonify({'error': 'Missing required fields (amount, category, type)'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Insert transaction
            cur.execute(
                '''INSERT INTO transactions 
                   (user_id, type, category, amount, transaction_date, description, merchant)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) 
                   RETURNING id, user_id, type, category, amount, transaction_date, description, merchant, created_at''',
                (user_id, transaction_type, category, amount, transaction_date, description, merchant)
            )
            transaction = cur.fetchone()
            
            conn.commit()
            
            return jsonify({
                'message': 'Transaction added successfully',
                'transaction': transaction
            }), 201
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Add transaction error: {e}")
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

# Get budgets
@app.route('/api/budgets', methods=['GET'])
@jwt_required()
def get_budgets():
    try:
        user_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute('SELECT * FROM budgets WHERE user_id = %s ORDER BY category', (user_id,))
            budgets = cur.fetchall()
            
            return jsonify({'budgets': budgets}), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Get budgets error: {e}")
        return jsonify({'error': str(e)}), 500

# Add budget
@app.route('/api/budgets', methods=['POST'])
@jwt_required()
def add_budget():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        category = data.get('category')
        limit_amount = data.get('limit_amount')
        period = data.get('period', 'monthly')
        
        if not all([category, limit_amount]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute(
                '''INSERT INTO budgets (user_id, category, limit_amount, period)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (user_id, category)
                   DO UPDATE SET limit_amount = EXCLUDED.limit_amount, period = EXCLUDED.period
                   RETURNING *''',
                (user_id, category, limit_amount, period)
            )
            budget = cur.fetchone()
            conn.commit()
            
            return jsonify({
                'message': 'Budget created/updated successfully',
                'budget': budget
            }), 201
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Add budget error: {e}")
        return jsonify({'error': str(e)}), 500

# Get savings goals
@app.route('/api/goals', methods=['GET'])
@jwt_required()
def get_goals():
    try:
        user_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute('SELECT * FROM savings_goals WHERE user_id = %s ORDER BY deadline', (user_id,))
            goals = cur.fetchall()
            
            return jsonify({'goals': goals}), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Get goals error: {e}")
        return jsonify({'error': str(e)}), 500

# Add savings goal
@app.route('/api/goals', methods=['POST'])
@jwt_required()
def add_goal():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        goal_name = data.get('goal_name')
        target_amount = data.get('target_amount')
        deadline = data.get('deadline')
        current_amount = data.get('current_amount', 0)
        
        if not all([goal_name, target_amount, deadline]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute(
                '''INSERT INTO savings_goals (user_id, goal_name, target_amount, current_amount, deadline)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING *''',
                (user_id, goal_name, target_amount, current_amount, deadline)
            )
            goal = cur.fetchone()
            conn.commit()
            
            return jsonify({
                'message': 'Goal created successfully',
                'goal': goal
            }), 201
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Add goal error: {e}")
        return jsonify({'error': str(e)}), 500

# Get dashboard summary
@app.route('/api/dashboard/summary', methods=['GET'])
@jwt_required()
def get_dashboard_summary():
    try:
        user_id = get_jwt_identity()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Get current month transactions
            cur.execute('''
                SELECT 
                    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
                    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE user_id = %s
                AND EXTRACT(MONTH FROM transaction_date) = EXTRACT(MONTH FROM CURRENT_DATE)
                AND EXTRACT(YEAR FROM transaction_date) = EXTRACT(YEAR FROM CURRENT_DATE)
            ''', (user_id,))
            summary = cur.fetchone()
            
            # Get active goals count
            cur.execute('SELECT COUNT(*) as active_goals FROM savings_goals WHERE user_id = %s AND status = %s', (user_id, 'active'))
            goals_count = cur.fetchone()
            
            # Get active budgets count
            cur.execute('SELECT COUNT(*) as active_budgets FROM budgets WHERE user_id = %s', (user_id,))
            budgets_count = cur.fetchone()
            
            return jsonify({
                'summary': {
                    'total_income': float(summary['total_income'] or 0),
                    'total_expenses': float(summary['total_expenses'] or 0),
                    'net_balance': float((summary['total_income'] or 0) - (summary['total_expenses'] or 0)),
                    'transaction_count': summary['transaction_count'],
                    'active_goals': goals_count['active_goals'],
                    'active_budgets': budgets_count['active_budgets']
                }
            }), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Dashboard summary error: {e}")
        return jsonify({'error': str(e)}), 500

# Initialize database on startup
try:
    print("="*60)
    print("🚀 STARTING PERSONAL FINANCE TRACKER API")
    print(f"PORT: {os.environ.get('PORT', 'NOT SET')}")
    print(f"DATABASE_URL: {'SET' if os.environ.get('DATABASE_URL') else 'NOT SET'}")
    print("="*60)
    init_db()
except Exception as e:
    print(f"⚠️ Startup initialization failed: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting Flask app on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
