import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import dateutil.relativedelta # Required for robust month calculations

# --- Page Configuration ---
st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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

    gc = gspread.authorize(credentials)
    spreadsheet_url = gcp_secrets["spreadsheet"]
    sh = gc.open_by_url(spreadsheet_url)
    worksheet = sh.worksheet("Expenses") # IMPORTANT: Change "Expenses" to your actual sheet name!

except Exception as e:
    st.error(
        f"**Connection Error:** Couldn't connect to Google Sheets. "
        f"Please double-check your `secrets.toml` content in Streamlit Cloud, "
        f"your Google Cloud setup, and sheet sharing permissions. "
        f"Details: {e}"
    )
    st.stop()

# --- Load and Process All Data from Google Sheet ---
try:
    all_records = worksheet.get_all_records()
    df_all_data = pd.DataFrame(all_records)

    if not df_all_data.empty:
        # Convert 'Amount' to numeric, coercing errors to NaN
        df_all_data['Amount'] = pd.to_numeric(df_all_data['Amount'], errors='coerce')
        df_all_data.dropna(subset=['Amount'], inplace=True) # Remove rows where Amount couldn't be parsed

        # Convert 'Purchase Date' to datetime
        # Use errors='coerce' and let Pandas infer, or try specific formats from screenshot: M/D/YYYY
        if 'Purchase Date' in df_all_data.columns:
            # Try to parse M/D/YYYY. If that fails, let Pandas infer.
            try:
                df_all_data['Purchase Date'] = pd.to_datetime(df_all_data['Purchase Date'], format="%m/%d/%Y", errors='raise')
            except ValueError:
                df_all_data['Purchase Date'] = pd.to_datetime(df_all_data['Purchase Date'], errors='coerce')
            df_all_data.dropna(subset=['Purchase Date'], inplace=True) # Remove rows with unparseable dates

        # Convert 'Timestamp' to datetime for true recency sorting
        if 'Timestamp' in df_all_data.columns:
            df_all_data['Timestamp'] = pd.to_datetime(df_all_data['Timestamp'], errors='coerce')
            df_all_data.dropna(subset=['Timestamp'], inplace=True)

except Exception as e:
    st.error(f"Error reading or processing data from Google Sheet: {e}")
    st.stop()

# --- Function to Add Data to Google Sheet ---
def add_transaction_to_sheet(user, purchase_date, item, amount, category, payment_method):
    """
    Appends a new row of transaction data (expense or income) to the Google Sheet.
    """
    try:
        # Prepare the new data as a list of values
        # Ensure order matches your Google Sheet headers exactly.
        # Format date as M/D/YYYY to match existing data and parsing
        new_row_values = [
            datetime.now().strftime("%m/%d/%Y %H:%M:%S"), # Timestamp
            user,
            purchase_date.strftime("%#m/%#d/%Y"), # Format as M/D/YYYY (%#m/%#d for single digit month/day on Windows, %-m/%-d for Linux/macOS)
            item,
            amount,
            category,
            payment_method
        ]
        # For cross-platform compatibility, a simpler format string might be needed if %#m fails on Linux/macOS
        # On Linux/macOS: purchase_date.strftime("%-m/%-d/%Y")

        worksheet.append_row(new_row_values)
        return True
    except Exception as e:
        st.error(f"**Failed to save transaction:** {e}")
        return False

# --- Streamlit App UI ---
st.title("💸 Personal Expense & Income Tracker")
st.markdown("Easily log your financial transactions to keep track of where your money goes.")

st.markdown("---") # Visual separator

st.subheader("Record a New Transaction")

# --- Custom Date Input Simulation (as requested previously) ---
if 'selected_transaction_date' not in st.session_state:
    st.session_state.selected_transaction_date = datetime.today().date()

st.write("**Date of Transaction**")

col1, col2, col3, col4 = st.columns([1, 1, 1, 3])

with col1:
    if st.button("⬅️ Previous Day", key="prev_day"):
        st.session_state.selected_transaction_date -= timedelta(days=1)
with col2:
    if st.button("🏠 Today", key="today_date"):
        st.session_state.selected_transaction_date = datetime.today().date()
with col3:
    if st.button("Next Day ➡️", key="next_day", disabled=(st.session_state.selected_transaction_date >= datetime.today().date())):
        st.session_state.selected_transaction_date += timedelta(days=1)

with col4:
    st.session_state.selected_transaction_date = st.date_input(
        "Select Date",
        value=st.session_state.selected_transaction_date,
        key="direct_date_input",
        label_visibility="collapsed"
    )

# --- Transaction Form ---
with st.form(key="transaction_form", clear_on_submit=True):
    transaction_date_form = st.session_state.selected_transaction_date # Use the date from session state

    users_options = ["Mikael", "Josephine"]
    selected_user = st.radio(
        "**Who is making this transaction?**", options=users_options, index=0
    )
    item_description = st.text_input(
        "**Item Description**", placeholder="e.g., Groceries"
    )
    amount_value = st.number_input(
        "**Amount**", min_value=0.01, format="%.2f"
    )
    category_options = [
        "Bills", "Subscriptions", "Entertainment", "Food & Drink", "Groceries",
        "Health & Wellbeing", "Shopping", "Transport", "Travel", "Business",
        "Gifts", "Other"
    ]
    selected_category = st.selectbox(
        "**Category**", options=category_options, index=0
    )
    payment_method_options = ["CC", "Debit", "Cash"]
    selected_payment_method = st.radio(
        "**Payment Method**", options=payment_method_options, index=0
    )

    st.markdown("---")
    submit_button = st.form_submit_button(label="🚀 Add Transaction")

    if submit_button:
        if not item_description:
            st.error("🚨 Please provide an **Item Description**.")
        elif amount_value <= 0:
            st.error("🚨 **Amount** must be a positive value.")
        else:
            with st.spinner("Saving transaction..."):
                if add_transaction_to_sheet(
                    selected_user,
                    transaction_date_form, # Use the date from the date input
                    item_description,
                    amount_value,
                    selected_category,
                    selected_payment_method
                ):
                    st.success("✅ Transaction successfully added!")
                    # Refresh data after adding a new transaction
                    # This will re-run the script and fetch latest data
                    st.rerun()
                else:
                    st.warning("⚠️ Could not add transaction. Check error messages above.")

st.markdown("---")

# --- Visual 1: Total Expenses for Specific Categories (Recurring Monthly) ---
st.subheader("📊 Expense Analytics")
st.markdown("#### Monthly Category Spending")

if not df_all_data.empty and 'Category' in df_all_data.columns and 'Amount' in df_all_data.columns:
    # Define the recurring monthly period (e.g., 28th to 28th)
    today_date_period_calc = datetime.today().date()

    if today_date_period_calc.day >= 28:
        period_start = today_date_period_calc.replace(day=28)
        period_end = period_start + dateutil.relativedelta.relativedelta(months=1)
    else:
        period_end = today_date_period_calc.replace(day=28)
        period_start = period_end - dateutil.relativedelta.relativedelta(months=1)

    st.info(f"Analyzing expenses from **{period_start.strftime('%B %d, %Y')}** to **{(period_end - timedelta(days=1)).strftime('%B %d, %Y')}**")

    # Filter data for the current period
    df_period = df_all_data[
        (df_all_data['Purchase Date'] >= pd.to_datetime(period_start)) &
        (df_all_data['Purchase Date'] < pd.to_datetime(period_end))
    ].copy() # Use .copy() to avoid SettingWithCopyWarning

    # Filter for specified categories
    target_categories = ["Bills", "Food & Drink", "Transport"]
    df_filtered_categories = df_period[df_period['Category'].isin(target_categories)]

    if not df_filtered_categories.empty:
        category_spending = df_filtered_categories.groupby('Category')['Amount'].sum().reset_index()
        category_spending.rename(columns={'Amount': 'Total Spending'}, inplace=True)
        
        # Ensure all target categories are in the dataframe, even if they have 0 spending
        full_category_df = pd.DataFrame({'Category': target_categories})
        category_spending = pd.merge(full_category_df, category_spending, on='Category', how='left').fillna(0)


        st.bar_chart(category_spending.set_index('Category'))
        st.write("Total spending in selected categories for the period:")
        st.dataframe(category_spending, use_container_width=True)
    else:
        st.info("No transactions found for the selected categories in the current period.")
else:
    st.info("Not enough data to display monthly category spending.")

st.markdown("---")

# --- Visual 2: Total Spending Per User ---
st.markdown("#### Total Spending Per User (All Time)")

if not df_all_data.empty and 'User' in df_all_data.columns and 'Amount' in df_all_data.columns:
    user_spending = df_all_data.groupby('User')['Amount'].sum().reset_index()
    user_spending.rename(columns={'Amount': 'Total Spending'}, inplace=True)

    st.bar_chart(user_spending.set_index('User'))
    st.write("Total spending per user (all recorded transactions):")
    st.dataframe(user_spending, use_container_width=True)
else:
    st.info("No user data or transactions found for spending analysis.")

st.markdown("---") # Final separator

# --- Recent Transactions Display (using df_all_data) ---
st.subheader("📝 Recent Transactions")
if not df_all_data.empty:
    df_display = df_all_data.copy() # Use a copy for display manipulation

    # Sort by Timestamp if available, otherwise by Purchase Date for true recency
    if 'Timestamp' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Timestamp']):
        df_display = df_display.sort_values(by='Timestamp', ascending=False)
    elif 'Purchase Date' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Purchase Date']):
        df_display = df_display.sort_values(by='Purchase Date', ascending=False)

    st.dataframe(df_display.head(10), use_container_width=True)
else:
    st.info("No transactions found in the sheet yet. Add your first one above!")