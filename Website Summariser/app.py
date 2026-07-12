import streamlit as st
import pandas as pd

# 1. Initialize Persistent Storage State
if "poll_data" not in st.session_state:
    st.session_state.poll_data = {
        "Python": 0,
        "JavaScript": 0,
        "C++": 0,
        "Rust": 0
    }
if "has_voted" not in st.session_state:
    st.session_state.has_voted = False

# 2. Application UI Layout
st.title("Streamlit Real-Time Polling Application")
st.write("Cast your vote below to see the community preferences update instantaneously.")

# 3. Voting Interface Logic
if not st.session_state.has_voted:
    st.subheader("What is your primary programming language for automation?")
    
    # Selection component
    choice = st.radio(
        label="Select an option:",
        options=list(st.session_state.poll_data.keys())
    )
    
    # Vote submission processing
    if st.button("Submit Vote"):
        st.session_state.poll_data[choice] += 1
        st.session_state.has_voted = True
        st.rerun()

# 4. Results & Visualization Rendering
else:
    st.success("Thank you for voting! Here are the current metrics:")
    
    # Transform session state data into a Pandas DataFrame for charting
    df = pd.DataFrame(
        list(st.session_state.poll_data.items()), 
        columns=["Language", "Votes"]
    ).set_index("Language")
    
    # Display graphical results
    st.bar_chart(df)
    
    # Display raw metric cards
    cols = st.columns(len(st.session_state.poll_data))
    for col, (lang, count) in zip(cols, st.session_state.poll_data.items()):
        col.metric(label=lang, value=count)
        
    # Option to reset state (for testing purposes)
    if st.button("Vote Again (Reset)"):
        st.session_state.has_voted = False
        st.rerun()
