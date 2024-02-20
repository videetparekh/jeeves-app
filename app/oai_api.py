from openai import OpenAI
import json

SYSTEM_MESSAGE = {
    "role": "system", 
    "content": """
    You will be provided with a meeting transcript, and your task is to summarize the meeting in the following format:
    - Overall summary of discussion (max 500 words)
    - Broad Topics of conversation (up to 7)
    - Action items - If Applicable (What needs to be done, who is doing it)
    - Relevant Reading - URLs to news links for the topics of discussion. Between 2-5 links. If no relevant links found, return "N/A", "N/A"
    
    Your response should be formatted as follows:
    {"summary": str, "topics": List[str], "action_items": List[str], "relevant_reading": List[str]}
    
    Example: 
    {
        "summary": "The user spoke about Manchester United football club.", 
        "action_items":[], 
        "topics": ["Manchester United Football Club"], 
        "relevant_reading": ["https://en.wikipedia.org/wiki/Manchester_United_F.C."]
    }
    """
}

CHAT_SYSTEM_MESSAGE = {
    "role": "system", 
    "content": """
    You will be provided with a transcript of a meeting. Your task is to help users by answering questions 
    about the meeting and its topics. Be as helpful as possible, and provide answers as though you are 
    well versed with all the topics of the meeting.
    
    Keep answers short, with a maximum length of 300 characters.
    Transcript:
    """
}

SUMMARIZE_MODEL_OPTS = dict(model="gpt-3.5-turbo", temperature=0.2, max_tokens=1000, top_p=0.25)
CHAT_MODEL_OPTS = dict(model="gpt-3.5-turbo-16k", temperature=0.7, max_tokens=300, top_p=1.0)


def register_client(OPENAI_API_KEY):
    return OpenAI(api_key=OPENAI_API_KEY)

def summarize(oai_client, transcript):
    message =  {"role": "user", "content": transcript}
    response = oai_client.chat.completions.create(
        messages=[SYSTEM_MESSAGE, message],
        **SUMMARIZE_MODEL_OPTS
    )
    return json.loads(response.choices[0].message.content)

def chat(oai_client, conversation_meta, message):
    CHAT_SYSTEM_MESSAGE["content"] = CHAT_SYSTEM_MESSAGE["content"] + conversation_meta
    response = oai_client.chat.completions.create(
        messages=[CHAT_SYSTEM_MESSAGE, {"role": "user", "content": message}],
        **CHAT_MODEL_OPTS
    )
    return response.choices[0].message.content
    