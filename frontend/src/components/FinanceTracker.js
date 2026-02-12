import React, { useState, useMemo, useEffect } from 'react';
import { PieChart, Pie, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, Wallet, Target, AlertCircle, PlusCircle, Calendar, CreditCard, Award, Activity } from 'lucide-react';
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
// import { useEffect } from 'react';

const FinanceTracker = () => {
  const {token, userId, logout} = useAuth();
  const navigate = useNavigate();
//   const { logout } = useAuth();
    const handleLogout = () => {
        logout();
        navigate("/login");
    };
    
    const API_BASE = "http://localhost:5000/api";

    const authHeaders = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
    };
  const [activeTab, setActiveTab] = useState('dashboard');
  const [editingTransaction, setEditingTransaction] = useState(null);
  const [transactions, setTransactions] = useState([]);

  const [budgets, setBudgets] = useState([]);
  const [goalProjections, setGoalProjections] = useState({});
  const [contributionAmount, setContributionAmount] = useState("");
  const [activeGoalId, setActiveGoalId] = useState(null);

  const [spendingInsights, setSpendingInsights] = useState(null);



  const [savingsGoals, setSavingsGoals] = useState([]);

  const [newTransaction, setNewTransaction] = useState({
    type: 'expense',
    category: 'Food & Dining',
    amount: '',
    date: new Date().toISOString().split('T')[0],
    description: '',
    merchant: ''
  });

  const [newBudget, setNewBudget] = useState({ category: '', limit: '' });
  const [newGoal, setNewGoal] = useState({ name: '', target: '', deadline: '' });
  const [analytics, setAnalytics] = useState(null);
  const [cashflowPrediction, setCashflowPrediction] = useState(null);
  const [budgetRisks, setBudgetRisks] = useState([]);
  const [cashFlowData, setCashFlowData] = useState([]);

useEffect(() => {
  if (!token) return;

  const loadTransactions = async () => {
    try {
      const res = await fetch(`${API_BASE}/transactions`, {
        headers: authHeaders
      });

      if (!res.ok) throw new Error("Failed to fetch transactions");

      const data = await res.json();

      if (Array.isArray(data)) {
        // 🔥 Normalize backend data → UI format
        setTransactions(
          data.map(t => ({
            ...t,
            amount: Number(t.amount),
            date: t.transaction_date
          }))
        );
      }
    } catch (err) {
      console.error("Backend fetch failed, using mock data", err);
    }
  };

  loadTransactions();
}, [token]);

useEffect(() => {
  if (editingTransaction) {
    setNewTransaction({
      type: editingTransaction.type || "expense",
      category: editingTransaction.category || "Food & Dining",
      amount: editingTransaction.amount?.toString() || "",
      date:
        editingTransaction.transaction_date || // ✅ backend field
        editingTransaction.date ||              // fallback for mock data
        new Date().toISOString().split("T")[0],
      description: editingTransaction.description || "",
      merchant: editingTransaction.merchant || ""
    });
  }
}, [editingTransaction]);

useEffect(() => {
  if (!token) return;

  fetch(`${API_BASE}/budgets`, {
    headers: authHeaders
  })
    .then(res => res.json())
    .then(data => {
      if (Array.isArray(data)) {
        setBudgets(data);
        console.log("Budgets loaded from backend");
      }
    })
    .catch(err => {
      console.warn("Using mock budgets", err);
    });
}, [token]);
useEffect(() => {
  if (!token) return;

  fetch(`${API_BASE}/goals`, {
    headers: authHeaders
  })
    .then(res => res.json())
    .then(data => {
      if (Array.isArray(data)) {
        setSavingsGoals(data);
        console.log("Goals loaded from backend");
      }
    })
    .catch(err => {
      console.warn("Using mock goals", err);
    });
}, [token]);

useEffect(() => {
  if (!token) return;

  fetch(`${API_BASE}/analytics/dashboard`, {
    headers: authHeaders
  })
    .then(res => res.json())
    .then(data => {
      setAnalytics(data);
      console.log("Analytics loaded");
    })
    .catch(err => {
      console.warn("Analytics fetch failed, using frontend fallback", err);
    });
}, [token]);

useEffect(() => {
  if (!token) return;

  fetch(`${API_BASE}/predictions/cashflow-advanced`, {
    headers: authHeaders
  })
    .then(res => {
      if (!res.ok) throw new Error("Cashflow fetch failed");
      return res.json();
    })
    .then(data => {
      setCashflowPrediction(data);
      setCashFlowData(data.historical_data || []);
    })
    .catch(err => {
      console.error("Cashflow prediction failed:", err);
    });
}, [token]);

useEffect(() => {
  if (!token) return;

  fetch(`${API_BASE}/predictions/budget-risk`, {
    headers: authHeaders
  })
    .then(res => res.json())
    .then(setBudgetRisks)
    .catch(() => {});
}, [token]);
useEffect(() => {
  if (!token) return;

  fetch(`${API_BASE}/predictions/spending-insights`, {
    headers: authHeaders
  })
    .then(res => res.json())
    .then(setSpendingInsights)
    .catch(err => console.error("Failed to load insights", err));
}, [token]);

const loadGoalProjection = async (goalId) => {
  if (goalProjections[goalId]) return;

  const res = await fetch(
    `${API_BASE}/predictions/goal-timeline/${goalId}`,
    { headers: authHeaders }
  );
  const data = await res.json();

  setGoalProjections(prev => ({
    ...prev,
    [goalId]: data
  }));
};
  const handleAddContribution = async () => {
      if (!contributionAmount || !activeGoalId) return;

      try {
        const res = await fetch(
          `${API_BASE}/goals/${activeGoalId}/contribute`,
          {
            method: "POST",
            headers: authHeaders,
            body: JSON.stringify({
              amount: Number(contributionAmount)
            })
          }
        );

        if (!res.ok) throw new Error("Contribution failed");

        // 🔥 Update goal locally (optimistic update)
        setSavingsGoals(prev =>
          prev.map(goal =>
            goal.id === activeGoalId
              ? {
                  ...goal,
                  current_amount:
                    Number(goal.current_amount ?? 0) +
                    Number(contributionAmount)
                }
              : goal
          )
        );

        setContributionAmount("");
        setActiveGoalId(null);

      } catch (err) {
        console.error(err);
        alert("Failed to add contribution");
      }
    };

  const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#6366f1', '#ef4444'];
  
  const categories = ['Food & Dining', 'Transportation', 'Entertainment', 'Utilities', 'Shopping', 'Healthcare', 'Education', 'Other'];

  // Calculate insights and predictions
  const insights = useMemo(() => {
    const currentMonth = new Date().getMonth();
    const currentYear = new Date().getFullYear();
    
    const currentMonthTransactions = transactions.filter(t => {
      const tDate = new Date(t.date);
      return tDate.getMonth() === currentMonth && tDate.getFullYear() === currentYear;
    });

    const insights = analytics
  ? {
      totalIncome: analytics.monthly_stats.total_income || 0,
      totalExpenses: analytics.monthly_stats.total_expenses || 0,
      balance:
        (analytics.monthly_stats.total_income || 0) -
        (analytics.monthly_stats.total_expenses || 0),
      transactionCount: analytics.monthly_stats.transaction_count || 0
    }
  : null;


    const expenses = currentMonthTransactions.filter(t => t.type === 'expense');
    const income = currentMonthTransactions.filter(t => t.type === 'income');
    
    const totalExpenses = expenses.reduce((sum, t) => sum + Number(t.amount||0), 0);
    const totalIncome = income.reduce((sum, t) => sum + Number(t.amount||0), 0);
    



    // Cash flow prediction (simple linear)
    const avgDailySpend = totalExpenses / new Date().getDate();
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    const predictedMonthlyExpense = avgDailySpend * daysInMonth;
    const predictedBalance = totalIncome - predictedMonthlyExpense;

    // Savings rate
   const savingsRate = insights
  ? insights.totalIncome > 0
    ? (
        ((insights.totalIncome - insights.totalExpenses) /
          insights.totalIncome) *
        100
      )
    : 0
  : 0;

    // Budget alerts
    const budgetAlerts = budgets.filter(b => (b.spent / b.limit_amount) > 0.8);
    const topCategory = analytics?.category_breakdown?.length
  ? analytics.category_breakdown.reduce(
      (max, curr) => (curr.total > max.total ? curr : max),
      analytics.category_breakdown[0]
    )
  : null;

return {
  totalExpenses,
  totalIncome,
  balance: (totalIncome - totalExpenses),

  predictedMonthlyExpense: Math.round(predictedMonthlyExpense),
  predictedBalance: Math.round(predictedBalance),

  savingsRate: Number(savingsRate.toFixed(1)),

  topCategory: topCategory ? topCategory.category : "N/A",
  topCategoryAmount: topCategory ? topCategory.total : 0,

  budgetAlerts
};

  }, [transactions, budgets, analytics]);
    // Category breakdown
const categoryChartData =
  analytics && Array.isArray(analytics.category_breakdown)
    ? analytics.category_breakdown.map(c => ({
        name: c.category,
        value: Math.round(c.total)
      }))
    : [];


  const handleAddTransaction = async () => {
        if (!newTransaction.amount || !newTransaction.category) return;

        const payload = {
        type: newTransaction.type,
        category: newTransaction.category,
        amount: Number(newTransaction.amount),
        transaction_date: newTransaction.date,   // REQUIRED
        description: newTransaction.description || "",
        merchant: newTransaction.merchant || ""
        };

        // 1️⃣ Optimistic UI
        setTransactions(prev => [
            ...prev,
            { id: Date.now(), ...payload,
              date: payload.transaction_date,
              amount: Number(payload.amount)
             }
        ]);

        // 2️⃣ Backend persistence
await fetch(`${API_BASE}/transactions`, {
  method: "POST",
  headers: authHeaders,
  body: JSON.stringify(payload)
});

await loadBudgets();
// 🔄 Re-fetch from backend
const refreshed = await fetch(`${API_BASE}/transactions`, {
  headers: authHeaders
});
const data = await refreshed.json();

setTransactions(
  data.map(t => ({
    ...t,
    amount: Number(t.amount),
    date: t.transaction_date
  }))
);


        // 3️⃣ Reset form
        setNewTransaction({
            type: "expense",
            category: "Food & Dining",
            amount: "",
            date: new Date().toISOString().split("T")[0],
            description: "",
            merchant: ""
        });
    };
  const handleDeleteTransaction = async (id) => {
  // Optimistic UI
    setTransactions(prev => prev.filter(t => t.id !== id));

    try {
        await fetch(`${API_BASE}/transactions/${id}`, {
        method: "DELETE",
        headers: authHeaders
        });
        await loadBudgets();
    } catch (err) {
        console.error("Failed to delete transaction", err);
    }
  };
const loadBudgets = async () => {
  try {
    const res = await fetch(`${API_BASE}/budgets`, {
      headers: authHeaders
    });
    const data = await res.json();

    if (Array.isArray(data)) {
      setBudgets(data);
    }
  } catch (err) {
    console.error("Failed to load budgets", err);
  }
};

const handleAddBudget = async () => {
  if (!newBudget.category || !newBudget.limit) return;

  const payload = {
    category: newBudget.category,
    limit_amount: Number(newBudget.limit)
  };

  // Optimistic UI


  try {
    await fetch(`${API_BASE}/budgets`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify(payload)
    });
    await loadBudgets();
  } catch (err) {
    console.error("Failed to save budget", err);
  }

  setNewBudget({ category: "", limit: "" });
};


const handleDeleteBudget = async (id) => {
  setBudgets(prev => prev.filter(b => b.id !== id));

  try {
    await fetch(`${API_BASE}/budgets/${id}`, {
      method: "DELETE",
      headers: authHeaders
    });
  } catch (err) {
    console.error("Failed to delete budget", err);
  }
};

const handleAddGoal = async () => {
  if (!newGoal.name || !newGoal.target || !newGoal.deadline) return;

  const payload = {
    goal_name: newGoal.name,
    target_amount: Number(newGoal.target),
    deadline: newGoal.deadline
  };

  try {
    const res = await fetch(`${API_BASE}/goals`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify(payload)
    });

    const savedGoal = await res.json(); // 👈 get real DB goal
    const normalizedGoal = {
      ...savedGoal,
      target_amount: Number(savedGoal.target_amount ?? payload.target_amount ?? 0),
      current_amount: Number(savedGoal.current_amount ?? 0),
    };
    setSavingsGoals(prev => [...prev, normalizedGoal]);

  } catch (err) {
    console.error("Failed to save goal", err);
  }

  setNewGoal({ name: "", target: "", deadline: "" });
};


const handleDeleteGoal = async (id) => {
  setSavingsGoals(prev => prev.filter(g => g.id !== id));

  try {
    await fetch(`${API_BASE}/goals/${id}`, {
      method: "DELETE",
      headers: authHeaders
    });
  } catch (err) {
    console.error("Failed to delete goal", err);
  }
};

  const budgetChartData = budgets.map(b => ({
    name: b.category,
    spent: b.spent,
    limit: b.limit_amount,
    remaining: Math.max(0, b.limit_amount - b.spent)
  }));

const handleUpdateTransaction = async () => {
  if (!editingTransaction) return;

  const payload = {
    type: newTransaction.type,
    category: newTransaction.category,
    amount: Number(newTransaction.amount),
    transaction_date: newTransaction.date,
    description: newTransaction.description || "",
    merchant: newTransaction.merchant || ""
  };

  // ✅ Optimistic UI (correct mapping)
  setTransactions(prev =>
    prev.map(t =>
      t.id === editingTransaction.id
        ? { ...t, ...payload, date: payload.transaction_date,amount: Number(payload.amount) }
        : t
    )
  );

  try {
    const res = await fetch(
      `${API_BASE}/transactions/${editingTransaction.id}`,
      {
        method: "PUT",
        headers: authHeaders,
        body: JSON.stringify(payload)
      }
    );

    if (!res.ok) {
      throw new Error("Update failed");
    }
  } catch (err) {
    console.error(err);
    alert("Failed to update transaction on server");
  }

  setEditingTransaction(null);
  setNewTransaction({
    type: "expense",
    category: "Food & Dining",
    amount: "",
    date: new Date().toISOString().split("T")[0],
    description: "",
    merchant: ""
  });
};

const fetchGoalTimeline = async (goalId) => {
  const res = await fetch(
    `${API_BASE}/predictions/goal-timeline/${goalId}`,
    { headers: authHeaders }
  );
  return res.json();
};


    const emergencyFundAmount =
  savingsGoals.find(g => g.goal_name === "Emergency Fund")
    ?.current_amount || 0;

const monthlyExpenses =
  analytics?.monthly_stats.total_expenses || 0;

const emergencyMonths =
  monthlyExpenses > 0
    ? (emergencyFundAmount / monthlyExpenses).toFixed(1)
    : "0.0";

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      {/* Header */}
      <header className="bg-white shadow-md border-b border-indigo-100">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2 rounded-xl">
                <Wallet className="text-white" size={28} />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  FinanceTrack Pro
                </h1>
                <p className="text-sm text-gray-500">Smart Financial Management</p>
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-2 px-4 py-2
                                    text-red-600 border border-red-200
                                    rounded-lg hover:bg-red-50"
                        >
                        <LogOut size={18} />
                        Logout
                    </button>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm text-gray-500">Current Balance</p>
                <p className="text-2xl font-bold text-gray-800">₹{insights.balance.toLocaleString()}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex gap-1">
            {['dashboard', 'transactions', 'budgets', 'goals', 'insights'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-3 font-medium capitalize transition-all ${
                  activeTab === tab
                    ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Key Metrics */}
            {insights && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-gray-500 text-sm font-medium">Total Income</p>
                  <TrendingUp className="text-green-500" size={20} />
                </div>
                <p className="text-3xl font-bold text-gray-800">₹{insights.totalIncome.toLocaleString()}</p>
                <p className="text-xs text-green-600 mt-1">This month</p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-gray-500 text-sm font-medium">Total Expenses</p>
                  <TrendingDown className="text-red-500" size={20} />
                </div>
                <p className="text-3xl font-bold text-gray-800">₹{insights.totalExpenses.toLocaleString()}</p>
                <p className="text-xs text-red-600 mt-1">This month</p>
              </div>
            
              <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-gray-500 text-sm font-medium">Savings Rate</p>
                  <Award className="text-purple-500" size={20} />
                </div>
                <p className="text-3xl font-bold text-gray-800">{insights.savingsRate}%</p>
                <p className="text-xs text-purple-600 mt-1">
                  {insights.savingsRate > 20 ? 'Excellent!' : 'Keep improving'}
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-gray-500 text-sm font-medium">Emergency Fund</p>
                  <Activity className="text-blue-500" size={20} />
                </div>
                <p className="text-3xl font-bold text-gray-800">
                  {emergencyMonths} mo
                </p>
                <p className="text-xs text-blue-600 mt-1">Months covered</p>
              </div>
            </div>
            )}
            {cashflowPrediction && (
  <div className="bg-white p-6 rounded-xl shadow border">
    <h3 className="text-lg font-semibold mb-2">
      🔮 Cashflow Prediction
    </h3>

    <div className="space-y-1 text-sm">
      <p>
        Predicted Expenses:{" "}
        <strong>₹{cashflowPrediction.predicted_expenses?.toLocaleString()}</strong>
      </p>

      <p>
        End-of-Month Balance:{" "}
        <strong className={
          cashflowPrediction.predicted_balance >= 0
            ? "text-green-600"
            : "text-red-600"
        }>
          ₹{cashflowPrediction.predicted_balance?.toLocaleString()}
        </strong>
      </p>

      <p>Avg Daily Spend: ₹{cashflowPrediction.avg_daily_spend}</p>
      <p>Days Remaining: {cashflowPrediction.days_remaining}</p>

      <span
        className={`inline-block mt-2 px-2 py-1 rounded text-xs font-medium
        ${
          cashflowPrediction.confidence === "high"
            ? "bg-green-100 text-green-700"
            : "bg-yellow-100 text-yellow-700"
        }`}
      >
        Confidence: {cashflowPrediction.confidence}
      </span>
    </div>
  </div>
)}

            {/* Predictions & Alerts */}
            {cashflowPrediction && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-6 shadow-lg text-white">
                <div className="flex items-center gap-3 mb-4">
                  <TrendingUp size={24} />
                  <h3 className="text-xl font-bold">Cash Flow Forecast</h3>
                </div>
                <div className="space-y-3">
                  <div>
                    <p className="text-blue-100 text-sm">Predicted Month-End Balance</p>
                    <p className="text-3xl font-bold">₹{cashflowPrediction?.predicted_balance?.toLocaleString() || "—"}</p>
                  </div>
                  <div className="bg-blue-400 bg-opacity-30 rounded-lg p-3">
                    <p className="text-sm">Based on current spending patterns, you're on track to save ₹{cashflowPrediction?.predicted_balance?.toLocaleString() || "—"} this month.</p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                <div className="flex items-center gap-3 mb-4">
                  <AlertCircle className="text-orange-500" size={24} />
                  <h3 className="text-xl font-bold text-gray-800">Budget Alerts</h3>
                </div>
                {insights.budgetAlerts.length > 0 ? (
                  <div className="space-y-2">
                    {insights.budgetAlerts.map(alert => (
                      <div key={alert.category} className="bg-orange-50 border border-orange-200 rounded-lg p-3">
                        <p className="font-medium text-orange-800">{alert.category}</p>
                        <p className="text-sm text-orange-600">
                          {((alert.spent / alert.limit_amount) * 100).toFixed(0)}% of budget used
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500">All budgets are on track! 🎉</p>
                )}


              </div>
            </div>
            )}

            {/* Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                <h3 className="text-lg font-bold text-gray-800 mb-4">Spending by Category</h3>
                {categoryChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={categoryChartData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {categoryChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => `₹${value.toLocaleString()}`} />
                  </PieChart>
                </ResponsiveContainer>
                ) : (
                    <p className="text-gray-500">No spending data available.</p>
                )}
              </div>

              <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                <h3 className="text-lg font-bold text-gray-800 mb-4">Cash Flow Trend</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={cashFlowData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="month"
                      tickFormatter={(value) => {
                        const [year, month] = value.split("-");
                        return new Date(year, month - 1).toLocaleString("default", {
                          month: "short",
                          year: "numeric"
                        });
                      }}
                    />

                    <YAxis />
                    <Tooltip formatter={(value) => `₹${value.toLocaleString()}`} />
                    <Legend />
                    <Line type="monotone" dataKey="income" stroke="#10b981" strokeWidth={2} />
                    <Line type="monotone" dataKey="expenses" stroke="#ef4444" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Budget Progress */}
            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
              <h3 className="text-lg font-bold text-gray-800 mb-4">Budget vs Spending</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={budgetChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(value) => `₹${value.toLocaleString()}`} />
                  <Legend />
                  <Bar dataKey="spent" fill="#ef4444" name="Spent" />
                  <Bar dataKey="remaining" fill="#10b981" name="Remaining" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {activeTab === 'transactions' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
              <h3 className="text-xl font-bold text-gray-800 mb-4">Add Transaction</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <select
                  value={newTransaction.type}
                  onChange={(e) => setNewTransaction({...newTransaction, type: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="expense">Expense</option>
                  <option value="income">Income</option>
                </select>
                <select
                  value={newTransaction.category}
                  onChange={(e) => setNewTransaction({...newTransaction, category: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                </select>
                <input
                  type="number"
                  placeholder="Amount"
                  value={newTransaction.amount}
                  onChange={(e) => setNewTransaction({...newTransaction, amount: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <input
                  type="date"
                  value={newTransaction.date}
                  onChange={(e) => setNewTransaction({...newTransaction, date: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <input
                  type="text"
                  placeholder="Description"
                  value={newTransaction.description}
                  onChange={(e) => setNewTransaction({...newTransaction, description: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <input
                  type="text"
                  placeholder="Merchant"
                  value={newTransaction.merchant}
                  onChange={(e) => setNewTransaction({...newTransaction, merchant: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
                <button
                onClick={editingTransaction ? handleUpdateTransaction : handleAddTransaction}
                className="bg-gradient-to-r from-blue-500 to-purple-600 text-white px-6 py-2 rounded-lg flex items-center gap-2"
                >
                <PlusCircle size={20} />
                {editingTransaction ? "Update Transaction" : "Add Transaction"}
                </button>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
              <h3 className="text-xl font-bold text-gray-800 mb-4">Recent Transactions</h3>
              <div className="space-y-2">
                {transactions.slice().map(t => (
                    <div
                        key={t.id}
                        className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                    <div>
                        <p className="font-medium text-gray-800">{t.description}</p>
                        <p className="text-sm text-gray-500">
                        {t.category} • {t.date}
                        </p>
                    </div>

                    <div className="flex items-center gap-3">
                        <p className={`font-bold ${t.type === 'income' ? 'text-green-600' : 'text-red-600'}`}>
                        {t.type === 'income' ? '+' : '-'}₹{t.amount}
                        </p>

                        <button
                        onClick={() => setEditingTransaction(t)}
                        className="text-blue-600 hover:underline text-sm"
                        >
                        Edit
                        </button>

                        <button
                        onClick={() => handleDeleteTransaction(t.id)}
                        className="text-red-600 hover:underline text-sm"
                        >
                        Delete
                        </button>
                    </div>
                    </div>

                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'budgets' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
              <h3 className="text-xl font-bold text-gray-800 mb-4">Add Budget</h3>
              <div className="flex gap-4">
                <select
                  value={newBudget.category}
                  onChange={(e) => setNewBudget({...newBudget, category: e.target.value})}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Select Category</option>
                  {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                </select>
                <input
                  type="number"
                  placeholder="Budget Limit"
                  value={newBudget.limit}
                  onChange={(e) => setNewBudget({...newBudget, limit: e.target.value})}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  onClick={handleAddBudget}
                  className="bg-gradient-to-r from-blue-500 to-purple-600 text-white px-6 py-2 rounded-lg hover:from-blue-600 hover:to-purple-700 transition-all"
                >
                  Add
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {budgets.map(budget => {
                const percentage = (budget.spent / budget.limit_amount) * 100;
                const isOverBudget = percentage > 100;
                const isWarning = percentage > 80 && percentage <= 100;
                
                return (
                  <div key={budget.category} className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-lg font-bold text-gray-800">{budget.category}</h4>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                        isOverBudget ? 'bg-red-100 text-red-700' :
                        isWarning ? 'bg-orange-100 text-orange-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {percentage.toFixed(0)}%
                      </span>
                    </div>
                    <div className="mb-3">
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className={`h-3 rounded-full transition-all ${
                            isOverBudget ? 'bg-red-500' :
                            isWarning ? 'bg-orange-500' :
                            'bg-green-500'
                          }`}
                          style={{ width: `${Math.min(percentage, 100)}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Spent: ₹{budget.spent.toLocaleString()}</span>
                      <span className="text-gray-600">Limit: ₹{budget.limit_amount.toLocaleString()}</span>
                    </div>
                    <button
                        onClick={() => handleDeleteBudget(budget.id)}
                        className="text-red-600 text-sm hover:underline"
                        >
                        Delete
                    </button>
                                          {budgetRisks
                        .filter(r => r.category === budget.category)
                        .map((risk, idx) => (
                          <p key={idx} className="text-sm text-red-600 mt-1">
                            ⚠️ Likely to exceed by ₹{Math.round(risk.overrun_amount)}
                          </p>
                      ))}
                  </div>
                  
                );
              })}
            </div>
          </div>
        )}

        {activeTab === 'goals' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
              <h3 className="text-xl font-bold text-gray-800 mb-4">Add Savings Goal</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <input
                  type="text"
                  placeholder="Goal Name"
                  value={newGoal.name}
                  onChange={(e) => setNewGoal({...newGoal, name: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <input
                  type="number"
                  placeholder="Target Amount"
                  value={newGoal.target}
                  onChange={(e) => setNewGoal({...newGoal, target: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <input
                  type="date"
                  value={newGoal.deadline}
                  onChange={(e) => setNewGoal({...newGoal, deadline: e.target.value})}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <button
                onClick={handleAddGoal}
                className="mt-4 bg-gradient-to-r from-blue-500 to-purple-600 text-white px-6 py-2 rounded-lg hover:from-blue-600 hover:to-purple-700 transition-all flex items-center gap-2"
              >
                <Target size={20} />
                Add Goal
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {savingsGoals.map(goal => {
                const current=Number(goal.current_amount ?? 0);
                const target=Number(goal.target_amount ?? 0);
                const percentage = target > 0 ? (current / target) * 100 : 0;
                const remaining = Number(goal.target_amount??0) - Number(goal.current_amount??0);
                const daysUntilDeadline = Math.ceil((new Date(goal.deadline) - new Date()) / (1000 * 60 * 60 * 24));
                const monthlyRequired = daysUntilDeadline > 0 ? Math.ceil(remaining / (daysUntilDeadline / 30)) : 0;
                
                return (
                  <div key={goal.id} className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2 rounded-lg">
                        <Target className="text-white" size={20} />
                      </div>
                      <h4 className="text-lg font-bold text-gray-800">{goal.goal_name}</h4>
                    </div>
                    <div className="mb-3">
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className="h-3 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all"
                          style={{ width: `${Math.min(percentage, 100)}%` }}
                        />
                      </div>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Progress:</span>
                        <span className="font-bold text-gray-800">{percentage.toFixed(0)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Current:</span>
                        <span className="font-medium text-gray-800">₹{Number(goal.current_amount??0).toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Target:</span>
                        <span className="font-medium text-gray-800">₹{Number(goal.target_amount??0).toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Deadline:</span>
                        <span className="font-medium text-gray-800">{goal.deadline}</span>
                      </div>
                      <button
                        onClick={() => handleDeleteGoal(goal.id)}
                        className="text-red-600 text-sm hover:underline"
                        >
                        Delete
                      </button>
                      <div className="mt-3">
                        {activeGoalId === goal.id ? (
                          <div className="flex gap-2">
                            <input
                              type="number"
                              placeholder="Amount"
                              value={contributionAmount}
                              onChange={(e) => setContributionAmount(e.target.value)}
                              className="px-2 py-1 border rounded"
                            />
                            <button
                              onClick={handleAddContribution}
                              className="bg-green-500 text-white px-3 py-1 rounded"
                            >
                              Add
                            </button>
                            <button
                              onClick={() => setActiveGoalId(null)}
                              className="text-gray-500"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setActiveGoalId(goal.id)}
                            className="text-green-600 text-sm hover:underline mt-2"
                          >
                            + Add Contribution
                          </button>
                        )}
                      </div>

                      <button
                        onClick={async () => {
                          const timeline = await fetchGoalTimeline(goal.id);

                          alert(
                            `Goal Status: ${timeline.status.toUpperCase()}\n\n` +
                            `Remaining Amount: ₹${Number(timeline.remaining_amount??0).toLocaleString()}\n\n` +

                            `Conservative Plan:\n` +
                            `• Months: ${timeline.conservative_timeline.months}\n` +
                            `• Monthly Savings: ₹${Math.round(
                              timeline.conservative_timeline.monthly_savings
                            ).toLocaleString()}\n\n` +

                            `Aggressive Plan:\n` +
                            `• Months: ${timeline.aggressive_timeline.months}\n` +
                            `• Monthly Savings: ₹${Math.round(
                              timeline.aggressive_timeline.monthly_savings
                            ).toLocaleString()}\n\n` +

                            `Recommendation:\n${timeline.recommendation}`
                          );
                        }}
                        className="text-blue-600 text-sm mt-2 hover:underline"
                      >
                        View Projection
                      </button>



                    </div>
                    {/* <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                      <p className="text-sm text-blue-800">
                        <span className="font-bold">Save ₹{monthlyRequired.toLocaleString()}/month</span> to reach goal on time
                      </p>
                    </div> */}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {activeTab === 'insights' && (
          <div className="space-y-6">
            {/* AI Insights */}
            <div className="bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl p-6 shadow-lg text-white">
              <h3 className="text-2xl font-bold mb-4">🤖 AI Financial Insights</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white bg-opacity-20 rounded-lg p-4">
                  <p className="text-sm opacity-90 mb-1">Top Spending Category</p>
                  <p className="text-2xl font-bold">{insights?.topCategory || "-"}</p>
                  <p className="text-sm">₹{insights?.topCategoryAmount?.toLocaleString() || "-"} spent</p>
                </div>
                <div className="bg-white bg-opacity-20 rounded-lg p-4">
                  <p className="text-sm opacity-90 mb-1">Predicted Monthly Spend</p>
                  <p className="text-2xl font-bold">₹{cashflowPrediction?.predicted_expenses?.toLocaleString() || "-"}</p>
                  <p className="text-sm">Based on current trends</p>
                </div>
              </div>
            </div>

            {/* Financial Health Score */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

  {/* Savings Rate */}
  <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
    <h4 className="font-bold text-gray-800 mb-3">Savings Rate</h4>
    <div className="text-center">
      <div className="text-4xl font-bold text-blue-600 mb-2">
        {insights?.savingsRate??0}%
      </div>
      <div
        className={`px-3 py-1 rounded-full text-sm inline-block ${
          (insights?.savingsRate??0) >= 20
            ? "bg-green-100 text-green-700"
            : (insights?.savingsRate??0) >= 10
            ? "bg-yellow-100 text-yellow-700"
            : "bg-red-100 text-red-700"
        }`}
      >
        {(insights?.savingsRate??0) >= 20
          ? "Excellent"
          : (insights?.savingsRate??0) >= 10
          ? "Good"
          : "Needs Improvement"}
      </div>
    </div>
  </div>

  {/* Emergency Fund */}
  <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
    <h4 className="font-bold text-gray-800 mb-3">Emergency Fund</h4>
    <div className="text-center">
      <div className="text-4xl font-bold text-purple-600 mb-2">
        {emergencyMonths}
      </div>
      <div
        className={`px-3 py-1 rounded-full text-sm inline-block ${
          emergencyMonths >= 6
            ? "bg-green-100 text-green-700"
            : emergencyMonths >= 3
            ? "bg-yellow-100 text-yellow-700"
            : "bg-red-100 text-red-700"
        }`}
      >
        {emergencyMonths >= 6
          ? "Well Protected"
          : emergencyMonths >= 3
          ? "Adequate"
          : "Build More"}
      </div>
      <p className="text-xs text-gray-500 mt-2">Months of expenses</p>
    </div>
  </div>

  {/* Budget Health */}
  <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
    <h4 className="font-bold text-gray-800 mb-3">Budget Health</h4>
    <div className="text-center">
      <div className="text-4xl font-bold text-green-600 mb-2">
        {budgets.filter(b => Number(b.spent ?? 0) <= Number(b.limit_amount??0)).length}/{budgets.length}
      </div>
      <div className="px-3 py-1 rounded-full text-sm inline-block bg-green-100 text-green-700">
        Categories on Track
      </div>
    </div>
  </div>

</div>


            {/* Spending Patterns */}
            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
              <h3 className="text-xl font-bold text-gray-800 mb-4">📊 Spending Patterns & Trends</h3>
              <div className="space-y-4">
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="text-blue-600" size={20} />
                    <h4 className="font-bold text-blue-800">Trend Analysis</h4>
                  </div>
                    <p className="text-sm text-blue-700">
                      Spending trend:{" "}
                      <strong>{spendingInsights?.monthly_trend || "N/A"}</strong>
                    </p>
                </div>

                <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Award className="text-green-600" size={20} />
                    <h4 className="font-bold text-green-800">Smart Insights</h4>
                  </div>
                    <p className="text-sm text-green-700">
                      Weekend Avg: ₹{spendingInsights?.weekend_vs_weekday?.weekend_avg ?? 0}
                      <br />
                      Weekday Avg: ₹{spendingInsights?.weekend_vs_weekday?.weekday_avg ?? 0}
                    </p>
                </div>

                <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertCircle className="text-orange-600" size={20} />
                    <h4 className="font-bold text-orange-800">Recommendations</h4>
                  </div>
                    <p className="text-sm text-orange-700">
                      Impulse Score:{" "}
                      <strong>{spendingInsights?.impulse_spending_score ?? 0}%</strong>
                    </p>
                </div>
              </div>
            </div>

            {/* Behavioral Insights */}
<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
  <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
    <h4 className="font-bold text-gray-800 mb-4">
      🎯 Goal Progress Prediction
    </h4>

    <div className="space-y-3">
      {savingsGoals.map(goal => {
        const projection = goalProjections[goal.id];

        return (
          <div
            key={goal.id}
            className="p-3 bg-gray-50 rounded-lg"
          >
            <p className="font-medium text-gray-800">
              {goal.goal_name}
            </p>

            {projection ? (
              <p className="text-sm text-gray-600">
                Conservative:{" "}
                <strong>
                  {projection.conservative_timeline.months} months
                </strong>{" "}
                • Save ₹
                {Math.round(
                  projection.conservative_timeline.monthly_savings
                ).toLocaleString()}
                /month
              </p>
            ) : (
              <button
                onClick={() => loadGoalProjection(goal.id)}
                className="text-sm text-blue-600 hover:underline mt-1"
              >
                Calculate projection
              </button>
            )}
          </div>
        );
      })}
    </div>
  </div>
</div>


            {/* Comparative Analysis */}
            <div className="bg-white rounded-xl p-6 shadow-lg border border-gray-100">
              <h3 className="text-xl font-bold text-gray-800 mb-4">📈 Comparative Benchmarks</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="text-sm text-gray-600 mb-2">Your Savings Rate</p>
                  <p className="text-2xl font-bold text-blue-600">{insights.savingsRate}%</p>
                  <p className="text-xs text-gray-500 mt-1">vs 15% average</p>
                </div>
                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="text-sm text-gray-600 mb-2">Food & Dining Budget</p>
                  <p className="text-2xl font-bold text-purple-600">18%</p>
                  <p className="text-xs text-gray-500 mt-1">vs 20% recommended</p>
                </div>
                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="text-sm text-gray-600 mb-2">Emergency Fund Months</p>
                  <p className="text-2xl font-bold text-green-600">
                    {monthlyExpenses > 0
                     ? (emergencyFundAmount / monthlyExpenses).toFixed(1)
                    : "0.0"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">vs 6 months ideal</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default FinanceTracker;