import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- Page Configuration ---
st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Google Sheets Connection Setup (Manual gspread)
try:
    # Get the service account credentials from st.secrets
    gcp_secrets = st.secrets["connections"]["gsheets"]

    SCOPE = ['https://www.googleapis.com/auth/spreadsheets']

    # The private_key from st.secrets needs to be formatted correctly for Credentials
    # It typically comes with escaped newlines (\n), but gspread expects actual newlines.
    # Replace escaped newlines with actual newlines.
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
            "client_x509_cert_url": gcp_secrets["client_x509_cert_url"]
        },
        scopes=SCOPE
    )

    # Authorize gspread client
    gc = gspread.authorize(credentials)

    # Open the spreadsheet using the URL from secrets
    spreadsheet_url = gcp_secrets["spreadsheet"]
    # Extract spreadsheet ID from the URL if needed, or open by URL directly
    # gspread can open by URL, title, or key. Using URL is usually easiest.
    sh = gc.open_by_url(spreadsheet_url)

    # Define the worksheet you're working with
    # IMPORTANT: Change "Expenses" to your actual sheet name!
    worksheet = sh.worksheet("Expenses")

except Exception as e:
    st.error(
        f"**Connection Error:** Couldn't connect to Google Sheets. "
        f"Please double-check your `secrets.toml` content in Streamlit Cloud, "
        f"your Google Cloud setup, and sheet sharing permissions. "
        f"Details: {e}"
    )
    st.stop() # Stop the app if we can't connect to prevent further errors.

# --- Function to Add Data to Google Sheet ---
def add_transaction_to_sheet(user, purchase_date, item, amount, category, payment_method):
    """
    Appends a new row of transaction data (expense or income) to the Google Sheet.
    """
    try:
        # Prepare the new data as a list of values
        # Ensure order matches your Google Sheet headers exactly.
        new_row_values = [
            datetime.now().strftime("%m-%d-%Y %H:%M:%S"),
            user,
            purchase_date.strftime("%m-%d-%Y"),
            item,
            amount,
            category,
            payment_method
        ]

        # Append the new data to the worksheet
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

# Using a Streamlit form for better input management and atomic submission
with st.form(key="transaction_form", clear_on_submit=True):

    # User (Radio buttons for choice)
    users_options = ["Mikael", "Josephine"]
    selected_user = st.radio(
        "**Who is making this transaction?**",
        options=users_options,
        index=0, # Defaults to the first user in the list
        help="Select the individual associated with this transaction."
    )

    # Date (Date input widget)
    transaction_date = st.date_input(
        "**Date of Transaction**",
        value=datetime.today(), # Defaults to today's date
        help="Choose the date the transaction occurred."
    )

    # Item Description (Text input)
    item_description = st.text_input(
        "**Item Description**",
        placeholder="e.g., Groceries from ABC Mart, Monthly Salary, Coffee Shop",
        help="Provide a brief description of the item or source of income."
    )

    # Amount (Number input)
    amount_value = st.number_input(
        "**Amount**",
        min_value=0.01, # Ensure amount is positive
        format="%.2f", # Display as currency with 2 decimal places
        help="Enter the monetary value of the transaction."
    )

    # Category (Dropdown select box)
    category_options = [
        "Bills", "Subscriptions", "Entertainment", "Food & Drink", "Groceries",
        "Health & Wellbeing", "Shopping", "Transport", "Travel", "Business",
        "Gifts", "Other"
    ]
    selected_category = st.selectbox(
        "**Category**",
        options=category_options,
        index=0, # Defaults to the first category
        help="Select the category that best describes this transaction."
    )

    # Payment Method
    payment_method_options = ["CC", "Debit", "Cash"]
    selected_payment_method = st.radio(
        "**Payment Method**",
        options=payment_method_options,
        index=0, # Defaults to the first option
        help="How was this transaction paid?"
    )

    st.markdown("---") # Visual separator

    # Submit Button
    submit_button = st.form_submit_button(label="🚀 Add Transaction")

    # Handle form submission
    if submit_button:
        # --- Basic Input Validation ---
        if not item_description:
            st.error("🚨 Please provide an **Item Description**.")
        elif amount_value <= 0:
            st.error("🚨 **Amount** must be a positive value.")
        else:
            # Show a spinner while saving data
            with st.spinner("Saving transaction..."):
                if add_transaction_to_sheet(
                    selected_user,
                    transaction_date,
                    item_description,
                    amount_value,
                    selected_category,
                    selected_payment_method
                ):
                    st.success("✅ Transaction successfully added!")
                else:
                    st.warning("⚠️ Could not add transaction. Check error messages above.")

st.markdown("---") # Final separator

st.info("💡 Your data is securely saved to your linked Google Sheet. You can view and analyze it there.")

# This section reads and displays the last few entries from your Google Sheet.
st.subheader("📝 Recent Transactions")
try:
    # Read all records as a list of lists, then convert to DataFrame
    all_records = worksheet.get_all_records()
    df_recent = pd.DataFrame(all_records)
    
    if not df_recent.empty:
        # Display the last 10 entries. Sort by Purchase Date.
        if 'Purchase Date' in df_recent.columns:
            df_recent['Purchase Date'] = pd.to_datetime(df_recent['Purchase Date'], format="%m-%d-%Y", errors='coerce')
            df_recent = df_recent.sort_values(by='Purchase Date', ascending=False)
        
        st.dataframe(df_recent.head(10), use_container_width=True)
    else:
        st.info("No transactions found in the sheet yet. Add your first one above!")
except Exception as e:
    st.warning(f"Couldn't fetch recent transactions. Check sheet permissions or data format. Error: {e}")