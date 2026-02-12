import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import calendar
import json

class FinancialPredictor:
    """
    Advanced financial prediction models for personal finance tracking
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        
    def predict_cash_flow(self, transactions_df):
        """
        Predict end-of-month balance based on current spending patterns
        
        Args:
            transactions_df: DataFrame with columns [date, amount, type]
        
        Returns:
            dict: Predicted balance, confidence, and breakdown
        """
        if len(transactions_df) < 5:
            return {"error": "Insufficient data for prediction"}
        
        # Prepare data
        transactions_df['date'] = pd.to_datetime(transactions_df['date'])
        transactions_df['day'] = transactions_df['date'].dt.day
        
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Filter current month
        current_month_data = transactions_df[
            (transactions_df['date'].dt.month == current_month) & 
            (transactions_df['date'].dt.year == current_year)
        ]
        
        # Calculate daily spending rate
        income = current_month_data[current_month_data['type'] == 'income']['amount'].sum()
        expenses = current_month_data[current_month_data['type'] == 'expense']['amount'].sum()
        
        days_passed = datetime.now().day
        days_in_month = calendar.monthrange(current_year, current_month)[1]
        
        # Linear projection
        avg_daily_expense = expenses / days_passed if days_passed > 0 else 0
        projected_monthly_expense = avg_daily_expense * days_in_month
        
        # Get historical average for better prediction
        historical_months = transactions_df[
            transactions_df['date'] < datetime(current_year, current_month, 1)
        ]
        
        if len(historical_months) > 0:
            monthly_avg = historical_months.groupby(
                [historical_months['date'].dt.year, historical_months['date'].dt.month]
            )['amount'].sum().mean()
            
            # Weighted average (60% current trend, 40% historical)
            projected_monthly_expense = (0.6 * projected_monthly_expense + 0.4 * monthly_avg)
        
        predicted_balance = income - projected_monthly_expense
        
        # Calculate confidence based on data variance
        confidence = "high" if len(transactions_df) > 30 else "medium" if len(transactions_df) > 10 else "low"
        
        return {
            "predicted_balance": round(predicted_balance, 2),
            "predicted_expenses": round(projected_monthly_expense, 2),
            "current_income": round(income, 2),
            "days_remaining": days_in_month - days_passed,
            "confidence": confidence,
            "avg_daily_spend": round(avg_daily_expense, 2)
        }
    
    def predict_category_spending(self, transactions_df, category):
        """
        Predict spending for a specific category next month
        
        Args:
            transactions_df: DataFrame with transaction history
            category: Category to predict
            
        Returns:
            dict: Prediction with confidence intervals
        """
        category_data = transactions_df[
            (transactions_df['category'] == category) & 
            (transactions_df['type'] == 'expense')
        ].copy()
        
        if len(category_data) < 3:
            return {"error": "Insufficient data for category prediction"}
        
        # Group by month
        category_data['date'] = pd.to_datetime(category_data['date'])
        monthly_spending = category_data.groupby(
            [category_data['date'].dt.year, category_data['date'].dt.month]
        )['amount'].sum().reset_index()
        
        monthly_spending.columns = ['year', 'month', 'amount']
        monthly_spending['month_num'] = range(len(monthly_spending))
        
        # Train linear regression
        X = monthly_spending[['month_num']].values
        y = monthly_spending['amount'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Predict next month
        next_month = len(monthly_spending)
        prediction = model.predict([[next_month]])[0]
        
        # Calculate standard deviation for confidence interval
        std_dev = np.std(y)
        
        return {
            "predicted_amount": round(max(0, prediction), 2),
            "lower_bound": round(max(0, prediction - std_dev), 2),
            "upper_bound": round(prediction + std_dev, 2),
            "avg_historical": round(np.mean(y), 2),
            "trend": "increasing" if model.coef_[0] > 0 else "decreasing"
        }
    
    def detect_anomalies(self, transactions_df, threshold=2.5):
        """
        Detect unusual spending patterns (potential fraud or errors)
        
        Args:
            transactions_df: DataFrame with transaction history
            threshold: Number of standard deviations to consider anomalous
            
        Returns:
            list: Anomalous transactions
        """
        if len(transactions_df) < 10:
            return []
        
        expenses = transactions_df[transactions_df['type'] == 'expense'].copy()
        
        # Calculate statistics by category
        anomalies = []
        
        for category in expenses['category'].unique():
            cat_data = expenses[expenses['category'] == category]
            
            if len(cat_data) < 3:
                continue
            
            mean_amount = cat_data['amount'].mean()
            std_amount = cat_data['amount'].std()
            
            if std_amount == 0:
                continue
            
            # Find outliers
            cat_data['z_score'] = (cat_data['amount'] - mean_amount) / std_amount
            outliers = cat_data[abs(cat_data['z_score']) > threshold]
            
            for _, row in outliers.iterrows():
                anomalies.append({
                    "transaction_id": row.get('id'),
                    "date": str(row['date']),
                    "category": category,
                    "amount": float(row['amount']),
                    "expected_range": f"{round(mean_amount - std_amount, 2)} - {round(mean_amount + std_amount, 2)}",
                    "severity": "high" if abs(row['z_score']) > 3 else "medium"
                })
        
        return anomalies
    
    def predict_budget_overrun(self, transactions_df, budgets_dict):
        """
        Predict which budgets are likely to be exceeded
        
        Args:
            transactions_df: DataFrame with current month transactions
            budgets_dict: Dictionary of {category: budget_limit}
            
        Returns:
            list: Categories at risk with predictions
        """
        current_month = datetime.now().month
        current_year = datetime.now().year
        current_day = datetime.now().day
        days_in_month = calendar.monthrange(current_year, current_month)[1]
        
        at_risk = []
        
        transactions_df['date'] = pd.to_datetime(transactions_df['date'])
        current_month_expenses = transactions_df[
            (transactions_df['date'].dt.month == current_month) & 
            (transactions_df['date'].dt.year == current_year) &
            (transactions_df['type'] == 'expense')
        ]
        
        for category, budget_limit in budgets_dict.items():
            cat_expenses = current_month_expenses[
                current_month_expenses['category'] == category
            ]['amount'].sum()
            
            # Project to end of month
            daily_rate = cat_expenses / current_day if current_day > 0 else 0
            projected_total = daily_rate * days_in_month
            
            if projected_total > budget_limit:
                at_risk.append({
                    "category": category,
                    "budget_limit": budget_limit,
                    "current_spent": round(cat_expenses, 2),
                    "projected_total": round(projected_total, 2),
                    "overrun_amount": round(projected_total - budget_limit, 2),
                    "risk_level": "high" if projected_total > budget_limit * 1.2 else "medium",
                    "days_until_overrun": max(0, int((budget_limit - cat_expenses) / daily_rate)) if daily_rate > 0 else days_in_month - current_day
                })
        
        return sorted(at_risk, key=lambda x: x['overrun_amount'], reverse=True)
    
    def calculate_savings_goal_timeline(self, current_amount, target_amount, 
                                       monthly_income, monthly_expenses):
        """
        Calculate realistic timeline to reach savings goal
        
        Args:
            current_amount: Current savings
            target_amount: Goal amount
            monthly_income: Average monthly income
            monthly_expenses: Average monthly expenses
            
        Returns:
            dict: Timeline and recommendations
        """
        remaining = target_amount - current_amount
        
        if remaining <= 0:
            return {
                "status": "achieved",
                "message": "Goal already reached!"
            }
        
        monthly_surplus = monthly_income - monthly_expenses
        
        if monthly_surplus <= 0:
            return {
                "status": "impossible",
                "message": "Current spending exceeds income. Reduce expenses first.",
                "recommendation": "Cut expenses by at least " + str(round(abs(monthly_surplus) + 100, 2))
            }
        
        # Conservative estimate (70% of surplus)
        conservative_monthly = monthly_surplus * 0.7
        conservative_months = remaining / conservative_monthly if conservative_monthly > 0 else float('inf')
        
        # Aggressive estimate (90% of surplus)
        aggressive_monthly = monthly_surplus * 0.9
        aggressive_months = remaining / aggressive_monthly if aggressive_monthly > 0 else float('inf')
        
        return {
            "status": "achievable",
            "remaining_amount": round(remaining, 2),
            "conservative_timeline": {
                "months": round(conservative_months, 1),
                "monthly_savings": round(conservative_monthly, 2)
            },
            "aggressive_timeline": {
                "months": round(aggressive_months, 1),
                "monthly_savings": round(aggressive_monthly, 2)
            },
            "recommendation": f"Save {round(conservative_monthly, 2)} per month for comfortable progress"
        }
    
    def identify_subscription_waste(self, transactions_df):
        """
        Identify potentially unused recurring subscriptions
        
        Args:
            transactions_df: DataFrame with transaction history
            
        Returns:
            list: Suspicious subscriptions
        """
        # Look for recurring patterns
        transactions_df['date'] = pd.to_datetime(transactions_df['date'])
        
        # Group by merchant and amount
        recurring = transactions_df.groupby(['merchant', 'amount']).agg({
            'date': ['count', 'min', 'max'],
            'amount': 'first'
        }).reset_index()
        
        recurring.columns = ['merchant', 'amount_group', 'count', 'first_date', 'last_date', 'amount']
        
        # Find subscriptions (3+ occurrences of same amount from same merchant)
        subscriptions = recurring[recurring['count'] >= 3]
        
        suspicious = []
        for _, sub in subscriptions.iterrows():
            # Check if last transaction was recent
            days_since_last = (datetime.now() - sub['last_date']).days
            
            if days_since_last < 60:  # Active subscription
                suspicious.append({
                    "merchant": sub['merchant'],
                    "amount": round(float(sub['amount']), 2),
                    "frequency": int(sub['count']),
                    "annual_cost": round(float(sub['amount']) * 12, 2),
                    "last_charged": str(sub['last_date'].date()),
                    "status": "active"
                })
        
        return suspicious
    
    def generate_spending_insights(self, transactions_df):
        """
        Generate comprehensive spending insights
        
        Args:
            transactions_df: DataFrame with transaction history
            
        Returns:
            dict: Various insights and recommendations
        """
        transactions_df['date'] = pd.to_datetime(transactions_df['date'])
        
        # Time-based patterns
        transactions_df['day_of_week'] = transactions_df['date'].dt.day_name()
        transactions_df['hour'] = transactions_df['date'].dt.hour if 'time' in transactions_df.columns else 12
        
        insights = {
            "top_spending_day": transactions_df.groupby('day_of_week')['amount'].sum().idxmax(),
            "weekend_vs_weekday": self._weekend_analysis(transactions_df),
            "monthly_trend": self._calculate_trend(transactions_df),
            "category_concentration": self._category_concentration(transactions_df),
            "impulse_spending_score": self._calculate_impulse_score(transactions_df)
        }
        
        return insights
    
    def _weekend_analysis(self, df):
        """Compare weekend vs weekday spending"""
        df['is_weekend'] = df['date'].dt.dayofweek >= 5
        weekend_avg = float(df[df['is_weekend'] & (df['type'] == 'expense')]['amount'].mean() or 0)
        weekday_avg = float(df[~df['is_weekend'] & (df['type'] == 'expense')]['amount'].mean() or 0)
        
        return {
            "weekend_avg": round(weekend_avg, 2) if not np.isnan(weekend_avg) else 0,
            "weekday_avg": round(weekday_avg, 2) if not np.isnan(weekday_avg) else 0,
            "difference_pct": round((weekend_avg / weekday_avg - 1) * 100, 1) if weekday_avg > 0 else 0
        }
    
    def _calculate_trend(self, df):
        """Calculate spending trend over time"""
        monthly = df[df['type'] == 'expense'].groupby(
            [df['date'].dt.year, df['date'].dt.month]
        )['amount'].sum()
        
        if len(monthly) < 2:
            return "insufficient_data"
        
        # Simple trend: compare last month to average
        last_month = float(monthly.iloc[-1])
        avg_previous = float(monthly.iloc[:-1].mean())
        
        change = (last_month / avg_previous - 1) * 100 if avg_previous > 0 else 0
        
        if change > 10:
            return "increasing"
        elif change < -10:
            return "decreasing"
        else:
            return "stable"
    
    def _category_concentration(self, df):
        """Calculate spending concentration (Herfindahl index)"""
        expenses = df[df['type'] == 'expense']
        category_totals = expenses.groupby('category')['amount'].sum()
        total_spending = category_totals.sum()
        
        if total_spending == 0:
            return 0
        
        shares = (category_totals / total_spending) ** 2
        hhi = shares.sum() * 100
        
        # Interpretation
        if hhi > 25:
            return "highly_concentrated"
        elif hhi > 15:
            return "moderately_concentrated"
        else:
            return "diversified"
    
    def _calculate_impulse_score(self, df):
        """Estimate impulse spending based on transaction patterns"""
        expenses = df[df['type'] == 'expense'].copy()
        
        if len(expenses) < 10:
            return 0
        
        # Small transactions (<$50) in non-essential categories
        impulse_categories = ['Entertainment', 'Shopping', 'Food & Dining']
        impulse_transactions = expenses[
            (expenses['category'].isin(impulse_categories)) & 
            (expenses['amount'] < 50)
        ]
        
        impulse_ratio = len(impulse_transactions) / len(expenses)
        
        return round(impulse_ratio * 100, 1)