import streamlit as st
import hashlib

# Set page configuration
st.set_page_config(page_title="Login Page", layout="centered")

# Define correct credentials
CORRECT_USERNAME = "animesh"
# Store password as a hash for security
CORRECT_PASSWORD_HASH = hashlib.sha256("voiro123".encode()).hexdigest()

def check_password(password):
    """Check if the entered password matches the stored hash"""
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return password_hash == CORRECT_PASSWORD_HASH

def login_form():
    """Display and process the login form"""
    st.title("🔒 Login")
    
    # Create a form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            if username == CORRECT_USERNAME and check_password(password):
                st.session_state["authenticated"] = True
                st.success("Login successful! Redirecting...")
                st.rerun()
            else:
                st.error("Incorrect username or password. Please try again.")

def main():
    # Check if user is already authenticated
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    
    # Show login form or main content based on authentication status
    if not st.session_state["authenticated"]:
        login_form()
    else:
        # Main application content after successful login
        st.title("Welcome to the Application")
        st.write(f"Hello, {CORRECT_USERNAME}! You've successfully logged in.")
        
        # Add logout button
        if st.button("Logout"):
            st.session_state["authenticated"] = False
            st.rerun()

if __name__ == "__main__":
    main()
