import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import dateutil.relativedelta
import altair as alt # Import Altair for custom chart labels

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
        if 'Purchase Date' in df_all_data.columns:
            try:
                # Try to parse M/D/YYYY (from screenshot)
                df_all_data['Purchase Date'] = pd.to_datetime(df_all_data['Purchase Date'], format="%m/%d/%Y", errors='raise')
            except ValueError:
                # Fallback to general inference if specific format fails
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
            datetime.now().strftime("%m-%d-%Y %H:%M:%S"), # Timestamp
            user,
            purchase_date.strftime("%#m/%#d/%Y"), # Windows: %#m/%#d. Linux/macOS: %-m/%-d
            item,
            amount,
            category,
            payment_method
        ]

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

# --- Date Input (Back to Default) ---
transaction_date_form = st.date_input(
    "**Date of Transaction**",
    value=datetime.today().date(), # Defaults to today's date
    help="Choose the date the transaction occurred."
)

# --- Transaction Form ---
with st.form(key="transaction_form", clear_on_submit=True):
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
                    st.rerun() # Refresh data after adding a new transaction
                else:
                    st.warning("⚠️ Could not add transaction. Check error messages above.")

st.markdown("---")

# --- Define the Recurring Monthly Period ---
today_date_period_calc = datetime.today().date()

if today_date_period_calc.day >= 28:
    period_start = today_date_period_calc.replace(day=28)
    period_end = period_start + dateutil.relativedelta.relativedelta(months=1)
else:
    period_end = today_date_period_calc.replace(day=28)
    period_start = period_end - dateutil.relativedelta.relativedelta(months=1)

# Filter all data for the current period
df_period = df_all_data[
    (df_all_data['Purchase Date'] >= pd.to_datetime(period_start)) &
    (df_all_data['Purchase Date'] < pd.to_datetime(period_end))
].copy() # Use .copy() to avoid SettingWithCopyWarning


# --- Visual 1: Total Expenses for Specific Categories (Recurring Monthly) ---
st.subheader("📊 Expense Analytics")
st.markdown("#### Monthly Category Spending")

if not df_all_data.empty and 'Category' in df_all_data.columns and 'Amount' in df_all_data.columns:
    st.info(f"Analyzing expenses from **{period_start.strftime('%B %d, %Y')}** to **{(period_end - timedelta(days=1)).strftime('%B %d, %Y')}**")

    # Filter for specified categories within the period
    target_categories = ["Bills", "Food & Drink", "Transport"]
    df_filtered_categories = df_period[df_period['Category'].isin(target_categories)]

    if not df_filtered_categories.empty:
        category_spending = df_filtered_categories.groupby('Category')['Amount'].sum().reset_index()
        category_spending.rename(columns={'Amount': 'Total Spending'}, inplace=True)

        # Ensure all target categories are in the dataframe, even if they have 0 spending
        full_category_df = pd.DataFrame({'Category': target_categories})
        category_spending = pd.merge(full_category_df, category_spending, on='Category', how='left').fillna(0)

        # Build Altair chart with labels
        chart_category = alt.Chart(category_spending).mark_bar().encode(
            x=alt.X('Category', sort=target_categories, title=None, axis=alt.Axis(labelAngle=0)), # Order and hide label
            y=alt.Y('Total Spending', title='Total Spending (IDR)'),
            tooltip=['Category', alt.Tooltip('Total Spending', format=',.2f')]
        )

        text_category = chart_category.mark_text(
            align='center',
            baseline='middle',
            dy=-10 # Nudges text up slightly
        ).encode(
            text=alt.Text('Total Spending', format=',.0f'), # Format as whole numbers with comma separators
            color=alt.value('white')
        )

        st.altair_chart(chart_category + text_category, use_container_width=True)

        st.write("Total spending in selected categories for the period:")
        st.dataframe(category_spending.style.format({"Total Spending": "{:,.0f}"}), use_container_width=True)
    else:
        st.info("No transactions found for the selected categories in the current period.")
else:
    st.info("Not enough data to display monthly category spending.")

st.markdown("---")

# --- Visual 2: Total Spending Per User (Current Period) ---
st.markdown("#### Total Spending Per User")

# Use df_period to filter by the current monthly date range
if not df_period.empty and 'User' in df_period.columns and 'Amount' in df_period.columns:
    user_spending = df_period.groupby('User')['Amount'].sum().reset_index()
    user_spending.rename(columns={'Amount': 'Total Spending'}, inplace=True)

    # Build Altair chart with labels
    chart_user = alt.Chart(user_spending).mark_bar().encode(
        x=alt.X('User', title=None, axis=alt.Axis(labelAngle=0)), # Hide x-axis label
        y=alt.Y('Total Spending', title='Total Spending (IDR)'),
        tooltip=['User', alt.Tooltip('Total Spending', format=',.2f')]
    )

    text_user = chart_user.mark_text(
        align='center',
        baseline='middle',
        dy=-10 # Nudges text up slightly
    ).encode(
        text=alt.Text('Total Spending', format=',.0f'), # Format as whole numbers with comma separators
        color=alt.value('white')
    )

    st.altair_chart(chart_user + text_user, use_container_width=True)

    st.write("Total spending per user for the period:")
    st.dataframe(user_spending.style.format({"Total Spending": "{:,.0f}"}), use_container_width=True)
else:
    st.info("No user data or transactions found for spending analysis in the current period.")

st.markdown("---") # Final separator

# --- Recent Transactions Display (using df_all_data) ---
st.subheader("📝 Recent Transactions")
if not df_all_data.empty:
    df_display = df_all_data.copy()

    if 'Timestamp' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Timestamp']):
        df_display = df_display.sort_values(by='Timestamp', ascending=False)
    elif 'Purchase Date' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Purchase Date']):
        df_display = df_display.sort_values(by='Purchase Date', ascending=False)

    df_display["Purchase Date"] = df_display["Purchase Date"].dt.date

    st.dataframe(df_display.head(10), use_container_width=True)
else:
    st.info("No transactions found in the sheet yet. Add your first one above!")