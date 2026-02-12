-- Create Database
CREATE DATABASE IF NOT EXISTS finance_tracker_p3;
USE finance_tracker_p3;

-- Users Table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email)
);

-- Transactions Table
CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    type ENUM('income', 'expense') NOT NULL,
    category VARCHAR(50) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    transaction_date DATE NOT NULL,
    description TEXT,
    merchant VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_date (user_id, transaction_date),
    INDEX idx_category (category),
    INDEX idx_type (type)
);

-- Budgets Table
CREATE TABLE budgets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    category VARCHAR(50) NOT NULL,
    limit_amount DECIMAL(10, 2) NOT NULL,
    period ENUM('monthly', 'yearly') DEFAULT 'monthly',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_category (user_id, category),
    INDEX idx_user (user_id)
);

-- Savings Goals Table
CREATE TABLE savings_goals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    goal_name VARCHAR(100) NOT NULL,
    target_amount DECIMAL(10, 2) NOT NULL,
    current_amount DECIMAL(10, 2) DEFAULT 0.00,
    deadline DATE NOT NULL,
    status ENUM('active', 'completed', 'cancelled') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_status (status)
);

-- Categories Reference Table (Optional - for standardization)
CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    type ENUM('income', 'expense', 'both') DEFAULT 'both',
    icon VARCHAR(50),
    color VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default categories
INSERT INTO categories (name, type, icon, color) VALUES
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
('Other', 'both', 'more-horizontal', '#6b7280');

-- Notifications Table
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    type ENUM('budget_alert', 'goal_reminder', 'insight', 'general') NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_read (user_id, is_read)
);

-- User Preferences Table
CREATE TABLE user_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    currency VARCHAR(10) DEFAULT 'INR',
    budget_alert_threshold INT DEFAULT 80,
    enable_notifications BOOLEAN DEFAULT TRUE,
    theme ENUM('light', 'dark', 'auto') DEFAULT 'light',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Recurring Transactions Table
CREATE TABLE recurring_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    type ENUM('income', 'expense') NOT NULL,
    category VARCHAR(50) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    description TEXT,
    merchant VARCHAR(100),
    frequency ENUM('daily', 'weekly', 'monthly', 'yearly') NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    last_processed DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_active (user_id, is_active)
);

-- Financial Insights Cache Table (for ML predictions)
CREATE TABLE insights_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    insight_type VARCHAR(50) NOT NULL,
    insight_data JSON NOT NULL,
    valid_until TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_type (user_id, insight_type),
    INDEX idx_valid (valid_until)
);

-- Views for common queries

-- Monthly Summary View
CREATE VIEW v_monthly_summary AS
SELECT 
    user_id,
    DATE_FORMAT(transaction_date, '%Y-%m') as month,
    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses,
    SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as net_balance,
    COUNT(*) as transaction_count
FROM transactions
GROUP BY user_id, DATE_FORMAT(transaction_date, '%Y-%m');

-- Category Spending View
CREATE VIEW v_category_spending AS
SELECT 
    user_id,
    category,
    DATE_FORMAT(transaction_date, '%Y-%m') as month,
    SUM(amount) as total_spent,
    COUNT(*) as transaction_count,
    AVG(amount) as avg_transaction
FROM transactions
WHERE type = 'expense'
GROUP BY user_id, category, DATE_FORMAT(transaction_date, '%Y-%m');

-- Budget Performance View
CREATE VIEW v_budget_performance AS
SELECT 
    b.id as budget_id,
    b.user_id,
    b.category,
    b.limit_amount,
    COALESCE(SUM(t.amount), 0) as spent,
    b.limit_amount - COALESCE(SUM(t.amount), 0) as remaining,
    ROUND((COALESCE(SUM(t.amount), 0) / b.limit_amount) * 100, 2) as usage_percentage
FROM budgets b
LEFT JOIN transactions t ON 
    t.user_id = b.user_id 
    AND t.category = b.category 
    AND t.type = 'expense'
    AND MONTH(t.transaction_date) = MONTH(CURRENT_DATE())
    AND YEAR(t.transaction_date) = YEAR(CURRENT_DATE())
GROUP BY b.id, b.user_id, b.category, b.limit_amount;

-- Stored Procedures

DELIMITER //

-- Procedure to add transaction and update budget
CREATE PROCEDURE sp_add_transaction(
    IN p_user_id INT,
    IN p_type VARCHAR(10),
    IN p_category VARCHAR(50),
    IN p_amount DECIMAL(10, 2),
    IN p_date DATE,
    IN p_description TEXT,
    IN p_merchant VARCHAR(100)
)
BEGIN
    DECLARE v_transaction_id INT;
    DECLARE v_budget_limit DECIMAL(10, 2);
    DECLARE v_current_spent DECIMAL(10, 2);
    
    -- Insert transaction
    INSERT INTO transactions (user_id, type, category, amount, transaction_date, description, merchant)
    VALUES (p_user_id, p_type, p_category, p_amount, p_date, p_description, p_merchant);
    
    SET v_transaction_id = LAST_INSERT_ID();
    
    -- Check budget if expense
    IF p_type = 'expense' THEN
        SELECT limit_amount INTO v_budget_limit
        FROM budgets
        WHERE user_id = p_user_id AND category = p_category;
        
        IF v_budget_limit IS NOT NULL THEN
            SELECT COALESCE(SUM(amount), 0) INTO v_current_spent
            FROM transactions
            WHERE user_id = p_user_id 
            AND category = p_category 
            AND type = 'expense'
            AND MONTH(transaction_date) = MONTH(p_date)
            AND YEAR(transaction_date) = YEAR(p_date);
            
            -- Create notification if over 80% of budget
            IF (v_current_spent / v_budget_limit) > 0.8 THEN
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (
                    p_user_id,
                    'Budget Alert',
                    CONCAT('You have spent ', ROUND((v_current_spent/v_budget_limit)*100, 0), 
                           '% of your ', p_category, ' budget'),
                    'budget_alert'
                );
            END IF;
        END IF;
    END IF;
    
    SELECT v_transaction_id as transaction_id;
END //

-- Procedure to calculate savings rate
CREATE PROCEDURE sp_calculate_savings_rate(
    IN p_user_id INT,
    IN p_start_date DATE,
    IN p_end_date DATE
)
BEGIN
    SELECT 
        SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
        SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses,
        SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as net_savings,
        CASE 
            WHEN SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) > 0 
            THEN ROUND(
                (SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) / 
                 SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END)) * 100, 
                2
            )
            ELSE 0 
        END as savings_rate
    FROM transactions
    WHERE user_id = p_user_id
    AND transaction_date BETWEEN p_start_date AND p_end_date;
END //

-- Procedure to get financial health metrics
CREATE PROCEDURE sp_financial_health_metrics(
    IN p_user_id INT
)
BEGIN
    DECLARE v_avg_monthly_expenses DECIMAL(10, 2);
    DECLARE v_emergency_fund DECIMAL(10, 2);
    
    -- Calculate average monthly expenses (last 6 months)
    SELECT AVG(monthly_expenses) INTO v_avg_monthly_expenses
    FROM (
        SELECT SUM(amount) as monthly_expenses
        FROM transactions
        WHERE user_id = p_user_id
        AND type = 'expense'
        AND transaction_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
    ) as monthly_data;
    
    -- Get emergency fund (sum of savings goals marked as emergency)
    SELECT COALESCE(SUM(current_amount), 0) INTO v_emergency_fund
    FROM savings_goals
    WHERE user_id = p_user_id
    AND goal_name LIKE '%emergency%'
    AND status = 'active';
    
    -- Return metrics
    SELECT 
        v_avg_monthly_expenses as avg_monthly_expenses,
        v_emergency_fund as emergency_fund,
        CASE 
            WHEN v_avg_monthly_expenses > 0 
            THEN ROUND(v_emergency_fund / v_avg_monthly_expenses, 1)
            ELSE 0 
        END as months_covered,
        (SELECT COUNT(*) FROM budgets WHERE user_id = p_user_id) as total_budgets,
        (SELECT COUNT(*) FROM savings_goals WHERE user_id = p_user_id AND status = 'active') as active_goals;
END //

DELIMITER ;

-- Triggers

-- Trigger to update goal status when target is reached
DELIMITER //
CREATE TRIGGER trg_check_goal_completion
AFTER UPDATE ON savings_goals
FOR EACH ROW
BEGIN
    IF NEW.current_amount >= NEW.target_amount AND OLD.status = 'active' THEN
        UPDATE savings_goals 
        SET status = 'completed' 
        WHERE id = NEW.id;
        
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (
            NEW.user_id,
            'Goal Achieved! 🎉',
            CONCAT('Congratulations! You have reached your ', NEW.goal_name, ' goal!'),
            'goal_reminder'
        );
    END IF;
END //
DELIMITER ;

-- Sample Data (for testing)
INSERT INTO users (email, password_hash, name) VALUES
('sahil@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7nQQ4EqYvS', 'Sahil Saini');

-- Note: Password is 'password123' (hashed with bcrypt)