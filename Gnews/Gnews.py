import requests

API_KEY = "980c447f4a0c72f7a74ba9ed8c781164" 
BASE_URL = "https://gnews.io/api/v4/search"

def get_news(topic="India"):
    """
    Fetches latest news headlines from GNews.io API.
    """
    params = {
        "q": topic,           # Search query (topic)
        "lang": "en",         # Language: English
        "country": "in",      # Country: India
        "max": 10,            # Number of news articles
        "apikey": API_KEY     # Your GNews.io API key
    }
    
    response = requests.get(BASE_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()
        articles = data.get("articles", [])
        
        if not articles:
            return "No news articles found for this topic."
        
        heading = f"\n🗞️ Latest News on '{topic.title()}':"
        for i, article in enumerate(articles, 1):
            title = f"{i}. {article['title']}"
            source = f"   📰 {article['source']['name']}"
            pubished_at = f"   📅 {article['publishedAt']}"
            url = f"   🔗 {article['url']}"

            news_info = [heading, title, source, pubished_at, url]
            return news_info
    else:
         return (f"❌ Error {response.status_code}: {response.text}")


if __name__ == "__main__":
    topic = input("Enter topic for news (e.g., India, Technology, Sports): ") or "India"
    news = get_news(topic)
    print(news)
