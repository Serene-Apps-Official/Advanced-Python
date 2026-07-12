import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path

# Configuration
POLL_DATA_FILE = "poll_results.json"

# Initialize persistent storage
def load_poll_data():
    """Load poll data from file"""
    if os.path.exists(POLL_DATA_FILE):
        try:
            with open(POLL_DATA_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "Python": 0,
        "JavaScript": 0,
        "C++": 0,
        "Rust": 0
    }

def save_poll_data(data):
    """Save poll data to file"""
    with open(POLL_DATA_FILE, "w") as f:
        json.dump(data, f)

# Initialize session state
if "has_voted" not in st.session_state:
    st.session_state.has_voted = False

# 2. Application UI Layout
st.title("🗳️ Streamlit Real-Time Polling Application")
st.write("Cast your vote below to see the community preferences update instantaneously across all users!")

# 3. Voting Interface Logic
col1, col2 = st.columns([2, 1])

with col1:
    if not st.session_state.has_voted:
        st.subheader("What is your primary programming language for automation?")
        
        poll_data = load_poll_data()
        # Selection component
        choice = st.radio(
            label="Select an option:",
            options=list(poll_data.keys()),
            key="vote_choice"
        )
        
        # Vote submission processing
        if st.button("Submit Vote", type="primary"):
            poll_data[choice] += 1
            save_poll_data(poll_data)
            st.session_state.has_voted = True
            st.success("✅ Your vote has been recorded!")
            st.rerun()
    else:
        st.info("✨ You've already voted. Results are updating in real-time below!")

# 4. Real-Time Results & Visualization (auto-refreshes every 1 second)
@st.fragment(run_every=1)
def display_results():
    """Display live results that update in real-time"""
    poll_data = load_poll_data()
    
    st.subheader("📊 Live Results")
    
    # Transform data into a Pandas DataFrame for charting
    df = pd.DataFrame(
        list(poll_data.items()), 
        columns=["Language", "Votes"]
    ).set_index("Language")
    
    # Display graphical results
    st.bar_chart(df)
    
    # Display metric cards
    cols = st.columns(len(poll_data))
    for col, (lang, count) in zip(cols, poll_data.items()):
        col.metric(label=lang, value=count)
    
    # Total votes
    total_votes = sum(poll_data.values())
    st.caption(f"Total votes cast: {total_votes}")

display_results()

# Option to reset voting status and vote again
with col2:
    st.write("")
    st.write("")
    if st.button("Vote Again", help="Click to vote a second time"):
        st.session_state.has_voted = False
        st.rerun()

# Footer
st.divider()
st.caption("🔄 Results update in real-time across all users!")
