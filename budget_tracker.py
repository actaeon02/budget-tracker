import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import dateutil.relativedelta
import altair as alt
import pytz

# --- Page Configuration ---
st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- App Title and Tab Menu ---
st.title("💸 Personal Finance Tracker")
menu = st.radio("📚 Select View", ["Expenses", "Income", "Budget"], horizontal=True)

# --- Google Sheets Connection Setup ---
try:
    gcp_secrets = st.secrets["connections"]["gsheets"]
    SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
    private_key = gcp_secrets["private_key"].replace("\\n", "\n")
    credentials = Credentials.from_service_account_info(
        {
            "type": gcp_secrets["type"],
            "project_id": gcp_secrets["project_id"],
            "private_key_id": gcp_secrets["private_key_id"],
            "private_key": private_key,
            "client_email": gcp_secrets["client_email"],
            "client_id": gcp_secrets["client_id"],
            "auth_uri": gcp_secrets["auth_uri"],
            "token_uri": gcp_secrets["token_uri"],
            "auth_provider_x509_cert_url": gcp_secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": gcp_secrets["client_x509_cert_url"],
        },
        scopes=SCOPE
    )
    spreadsheet_url = gcp_secrets["spreadsheet"]
except Exception:
    SERVICE_ACCOUNT_FILE = r"C:\\Users\\Mikael Andrew\\service_account_keys.json"
    SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPE)
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1DZc7Ls-3xDOgRG5OLhTcSsjDvrLw9YeA-gYeLJ9hOiE/edit#gid=258870691"

# Connect to Google Sheets
gc = gspread.authorize(credentials)
sh = gc.open_by_url(spreadsheet_url)
ws_expenses = sh.worksheet("Expenses")
ws_income = sh.worksheet("Income")
ws_budget = sh.worksheet("Budget")

# Load data
expenses_df = pd.DataFrame(ws_expenses.get_all_records())
income_df = pd.DataFrame(ws_income.get_all_records())
budget_df = pd.DataFrame(ws_budget.get_all_records())

# Preprocess dates and values
if not expenses_df.empty:
    expenses_df["Amount"] = pd.to_numeric(expenses_df["Amount"], errors="coerce")
    expenses_df.dropna(subset=["Amount"], inplace=True)
    expenses_df["Purchase Date"] = pd.to_datetime(expenses_df["Purchase Date"], errors="coerce")
    expenses_df["Timestamp"] = pd.to_datetime(expenses_df["Timestamp"], errors="coerce")
    expenses_df.dropna(subset=["Purchase Date", "Timestamp"], inplace=True)

if not income_df.empty:
    income_df["Income Amount"] = pd.to_numeric(income_df["Income Amount"], errors="coerce")
    income_df["Date"] = pd.to_datetime(income_df["Date"], errors="coerce")
    income_df.dropna(subset=["Date", "Income Amount"], inplace=True)

# Define monthly period range
today = datetime.today().date()
if today.day >= 28:
    period_start = today.replace(day=28)
    period_end = period_start + dateutil.relativedelta.relativedelta(months=1)
else:
    period_end = today.replace(day=28)
    period_start = period_end - dateutil.relativedelta.relativedelta(months=1)

period_start_dt = pd.to_datetime(period_start)
period_end_dt = pd.to_datetime(period_end)

expenses_period = expenses_df[
    (expenses_df["Purchase Date"] >= period_start_dt) & 
    (expenses_df["Purchase Date"] < period_end_dt)
].copy()

income_period = income_df[
    (income_df["Date"] >= period_start_dt) & 
    (income_df["Date"] < period_end_dt)
].copy()

# --- Expense Tab ---
if menu == "Expenses":
    st.header("💳 Expense Tracker")
    st.subheader("Record a New Expense")

    with st.form("expense_form", clear_on_submit=True):
        user = st.radio("Who?", ["Mikael", "Josephine"], key="expense_user")
        purchase_date = st.date_input("Date", value=datetime.today().date(), key="expense_date")
        item = st.text_input("Description", key="expense_desc")
        amount = st.number_input("Amount", min_value=0.01, format="%.2f", key="expense_amount")
        category = st.selectbox("Category", [
            "Bills", "Subscriptions", "Entertainment", "Food & Drink", "Groceries",
            "Health & Wellbeing", "Shopping", "Transport", "Travel", "Business",
            "Laundry", "Gifts", "Investment", "Other"
        ], key="expense_category")
        method = st.radio("Payment Method", ["CC", "Debit", "Cash"], key="expense_method")
        submit = st.form_submit_button("➕ Add Expense")
        if submit and item and amount > 0:
            timestamp = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%m/%d/%Y %H:%M:%S")
            row = [timestamp, user, purchase_date.strftime("%m/%d/%Y"), item, amount, category, method]
            ws_expenses.append_row(row)
            st.success("Expense added!")
            st.rerun()

    # Expense by Category
    st.subheader("📊 Monthly Category Spending")
    if not expenses_period.empty:
        target_categories = ["Bills", "Food & Drink", "Transport"]
        filtered = expenses_period[expenses_period["Category"].isin(target_categories)]
        category_spending = filtered.groupby("Category")["Amount"].sum().reset_index()
        full_category_df = pd.DataFrame({"Category": target_categories})
        category_spending = pd.merge(full_category_df, category_spending, on="Category", how="left").fillna(0)

        bar = alt.Chart(category_spending).mark_bar().encode(
            x=alt.X("Category", sort=target_categories, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Amount", title="Total Spending (IDR)"),
            color=alt.Color("Category", legend=None),
            tooltip=["Category", alt.Tooltip("Amount", format=",.2f")]
        )

        text = alt.Chart(category_spending).mark_text(
            align='center',
            baseline='bottom',
            color='white',
            dy=-10
        ).encode(
            x=alt.X("Category", sort=target_categories),
            y="Amount",
            text=alt.Text("Amount:Q", format=",.0f")
        )

        st.altair_chart(bar + text, use_container_width=True)
        st.dataframe(category_spending, column_config={
            "Amount": st.column_config.NumberColumn("Amount", format='accounting')
        }, use_container_width=True)

    # Spending per User
    st.subheader("📊 Total Spending Per User")
    if not expenses_period.empty:
        user_spending = expenses_period.groupby("User")["Amount"].sum().reset_index()

        user_order = user_spending.sort_values("Amount", ascending=False)["User"].tolist()
        user_spending["User"] = pd.Categorical(user_spending["User"], categories=user_order, ordered=True)

        bar_user = alt.Chart(user_spending).mark_bar().encode(
            x=alt.X("User", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Amount", sort=user_order, title="Total Spending (IDR)"),
            color=alt.Color("User", legend=None),
            tooltip=["User", alt.Tooltip("Amount", format=",.2f")]
        )

        text_user = alt.Chart(user_spending).mark_text(
            align='center',
            baseline='bottom',
            color='white',
            dy=-10
        ).encode(
            x="User",
            y="Amount",
            text=alt.Text("Amount:Q", format=",.0f")
        )

        st.altair_chart(bar_user + text_user, use_container_width=True)

        # Sort user_spending by Amount descending
        user_spending_sorted = user_spending.sort_values("Amount", ascending=False).reset_index(drop=True)
        st.dataframe(user_spending_sorted, column_config={
            "Amount": st.column_config.NumberColumn("Amount", format='accounting')
        }, use_container_width=True)

    # Recent Transactions
    st.subheader("📝 Recent Transactions")
    if not expenses_df.empty:
        df_show = expenses_df.copy()
        df_show["Purchase Date"] = df_show["Purchase Date"].dt.date
        st.dataframe(df_show.tail(25).drop(columns=["Timestamp"]), use_container_width=True)

# --- Income Tab ---
elif menu == "Income":
    st.header("💰 Income Recorder")
    st.subheader("Record a New Income")

    with st.form("income_form", clear_on_submit=True):
        income_user = st.radio("Who earned it?", ["Mikael", "Josephine"], key="income_user")
        income_date = st.date_input("Income Date", value=datetime.today().date())
        income_source = st.selectbox("Source", ["Salary", "Freelance", "Other"])
        income_desc = st.text_input("Income Description")
        income_amt = st.number_input("Income Amount", min_value=0.01, format="%.2f")
        income_submit = st.form_submit_button("➕ Add Income")
        if income_submit and income_amt > 0:
            timestamp = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%m/%d/%Y %H:%M:%S")
            row = [timestamp, income_user, income_date.strftime("%m/%d/%Y"), income_source, income_desc, income_amt]
            ws_income.append_row(row)
            st.success("Income recorded!")
            st.rerun()

    # Income vs Expense Chart
    st.subheader("📊 Income vs. Expenses")
    income_sum = income_period["Income Amount"].sum()
    expense_sum = expenses_period["Amount"].sum()
    inc_exp_df = pd.DataFrame({"Type": ["Income", "Expenses"], "Amount": [income_sum, expense_sum]})
    inc_exp_df["Type"] = pd.Categorical(inc_exp_df["Type"], categories=["Income", "Expenses"], ordered=True)

    color_scale = alt.Scale(domain=["Income", "Expenses"], range=["#0a54a3", "#88bdee"])

    bar_income = alt.Chart(inc_exp_df).mark_bar().encode(
        x=alt.X("Type", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Amount", title="Amount (IDR)"),
        color=alt.Color("Type", scale=color_scale, legend=None),
        tooltip=["Type", alt.Tooltip("Amount", format=",.0f")]
    )

    text_income = alt.Chart(inc_exp_df).mark_text(
        align='center',
        baseline='bottom',
        dy=-5,
        color='white'
    ).encode(
        x="Type",
        y="Amount",
        text=alt.Text("Amount:Q", format=",.0f")
    )

    st.altair_chart(bar_income + text_income, use_container_width=True)

# --- Budget Tab ---
elif menu == "Budget":
    st.header("📈 Budget Overview")
    st.markdown(f"Budget period: **{period_start}** to **{period_end - timedelta(days=1)}**")

    if not budget_df.empty and not expenses_period.empty:
        df_sum = expenses_period.groupby("Category")["Amount"].sum().reset_index()
        df_merged = pd.merge(budget_df, df_sum, on="Category", how="left").fillna(0)
        df_merged["Total Budget"] = pd.to_numeric(df_merged["Total Budget"], errors="coerce")
        df_merged["Remaining"] = df_merged["Total Budget"] - df_merged["Amount"]

        # Format for display (accounting style with commas, parentheses for negatives)
        display_df = df_merged[["Category", "Mikael", "Josephine", "Total Budget", "Amount", "Remaining"]].copy()
        for col in ["Mikael", "Josephine", "Total Budget", "Amount", "Remaining"]:
            display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f}" if x >= 0 else "0")

        # Show in Streamlit
        st.dataframe(display_df)

        bar = alt.Chart(df_merged).mark_bar().encode(
            x=alt.X("Category", axis=alt.Axis(labelAngle=-30)),
            y=alt.Y("Total Budget", title="IDR"),
            y2="Amount",
            color=alt.condition(
                alt.datum["Amount"] > alt.datum["Total Budget"],
                alt.value("red"),
                alt.value("green")
            ),
            tooltip=["Category", "Total Budget", "Amount", "Remaining"]
        )
        st.altair_chart(bar, use_container_width=True)
    else:
        st.info("No budget or expense data found.")