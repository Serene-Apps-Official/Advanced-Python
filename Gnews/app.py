import streamlit as st
from Gnews import get_news

st.title("🗞️ GNews Latest News Fetcher")
topic = st.text_input("Enter topic for news (e.g., India, Technology, Sports):", "India")
if st.button("Fetch News"):
    news = get_news(topic)
    if "❌ Error" in news:
        st.error("News Fetching Failed")
    else:
        st.balloons()
        st.success("News fetched Successfully")  
        st.info("\n".join(news[:4]))   
        st.link_button("Read more", news[4].split("   🔗 ")[1])