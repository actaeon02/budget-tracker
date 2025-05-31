import streamlit as st
import pandas as pd
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Google Sheets Connection ---
# This attempts to connect to your Google Sheet using credentials
# stored in .streamlit/secrets.toml under the 'gsheets' section.
try:
    conn = st.connection("gsheets")
except Exception as e:
    st.error(
        f"**Connection Error:** Couldn't connect to Google Sheets. "
        f"Please double-check your `secrets.toml` file and Google Cloud setup. "
        f"Details: {e}"
    )
    st.stop() # Stop the app if we can't connect to prevent further errors.

# --- Function to Add Data to Google Sheet ---
def add_transaction_to_sheet(user, date, item, amount, category, payment_method):
    """
    Appends a new row of transaction data (expense or income) to the Google Sheet.
    """
    try:
        # Prepare the new data as a DataFrame
        # Ensure column names match your Google Sheet headers exactly.
        new_data = pd.DataFrame([{
            "Timestamp": datetime.now().strftime("%m-%d-%Y %H:%M:%S"),
            "User": user,
            "Purchase Date": date.strftime("%m-%d-%Y"),
            "Item": item,
            "Amount": amount,
            "Category": category,
            "Payment Method": payment_method
        }])

        # Append the new data to the specified worksheet
        conn.append(
            worksheet="Expenses", # <<-- IMPORTANT: Change if your sheet name is different!
            data=new_data
        )
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
        "Bills", "Subscriptions", "Entertainment", "Food & Drink", "Groceris",
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
# It's useful for immediate verification.
st.subheader("📝 Recent Transactions")
try:
    # Read the data from your sheet. 'ttl=5' means it will cache the data for 5 minutes.
    df_recent = conn.read(worksheet="Expenses", ttl=5)
    
    if not df_recent.empty:
        # Display the last 10 entries. Sort by Date if you have it.
        if 'Purchase Date' in df_recent.columns:
            df_recent['Date'] = pd.to_datetime(df_recent['Date'], errors='coerce')
            df_recent = df_recent.sort_values(by='Date', ascending=False)
        
        st.dataframe(df_recent.head(10), use_container_width=True)
    else:
        st.info("No transactions found in the sheet yet. Add your first one above!")
except Exception as e:
    st.warning(f"Couldn't fetch recent transactions. Check sheet permissions or data format. Error: {e}")