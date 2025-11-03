import google.generativeai as genai
import websearch
genai.configure(api_key="AIzaSyDfn99Bg2PgO66dTN50B2eenTIEm9YXoWY")
model = genai.GenerativeModel("gemini-2.0-flash")

def AI_Summarise(text):
    prompt = f"Generate a detailed description of this website : {text} "
    result = model.generate_content(prompt)
    return result.text

website = input('Enter URL : ')
website_description = websearch.getWebDescript(website)
print(AI_Summarise(website_description))
