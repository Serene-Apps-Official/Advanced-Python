import feedparser

def get_headlines():
    url = "https://www.indiatoday.in/rss/india.xml"
    news_feed = feedparser.parse(url)
    
    print("📰 Today's Headlines from India Today:\n")
    for entry in news_feed.entries[:10]:  # Top 10
        print(f"- {entry.title}")
        print(f"  {entry.link}\n")

get_headlines()
