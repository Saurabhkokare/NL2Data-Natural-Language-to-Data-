from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

def results_to_text_llm_db(user_question, db_type, query, results):
    llm = ChatGroq(
        model_name="llama3-8b-8192",
        temperature=0.0
    )
    prompt = (
        "You are a helpful assistant. Given the following query result (in JSON format) and the user's question, "
        "write a clear, concise, and conversational answer. "
        "If the result is empty or there are no matching records, honestly say so and explain that no data was found for their query.\n\n"
        f"Database/File type: {db_type}\n"
        f"User question: {user_question}\n"
        f"Query: {query}\n"
        f"Result (JSON): {results}\n"
        "Answer:"
    )
    answer = llm.invoke(prompt)
    return answer.content.strip()

def results_to_text_llm_file(user_question, db_type, query, results):
    # Use OpenAI GPT-3.5-turbo for file queries (set your API key in env)
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0.0
    )
    prompt = (
        "You are a helpful assistant. Given the following tabular data (in JSON format) and the user's question, "
        "write a clear, concise, and conversational answer. "
        "If the result is empty or there are no matching records, honestly say so and explain that no data was found for their query.\n\n"
        f"File type: {db_type}\n"
        f"User question: {user_question}\n"
        f"Query: {query}\n"
        f"Result (JSON): {results}\n"
        "Answer:"
    )
    answer = llm.invoke(prompt)
    return answer.content.strip()
