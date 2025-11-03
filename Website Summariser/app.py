import streamlit as st
import google.generativeai as genai
import websearch

# Configure Gemini (use your API key directly here for now)
genai.configure(api_key="AIzaSyDfn99Bg2PgO66dTN50B2eenTIEm9YXoWY")
model = genai.GenerativeModel("gemini-2.0-flash")

# Streamlit UI
st.title("🌐 AI Website Summarizer")

url = st.text_input("Enter a website URL")

if st.button("Summarize"):
    if url:
        st.write("⏳ Fetching website content...")
        try:
            website_description = websearch.getWebDescript('https://'+url)
            st.write("✅ Website content fetched!")

            st.write("🧠 Generating summary...")
            prompt = f"Summarize this website content clearly:\n\n{website_description}"
            result = model.generate_content(prompt)

            st.subheader("AI Summary")
            st.write(result.text)
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("Please enter a valid URL.")
