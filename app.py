import gradio as gr
import pandas as pd
import sqlite3
import psycopg2
import mysql.connector
import cx_Oracle
import pyodbc
import pymongo
import re
import io
from sqlalchemy.engine.url import make_url
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from dotenv import load_dotenv
import os

from llm_utils import results_to_text_llm_db, results_to_text_llm_file

load_dotenv()

def main(db_type, db_url, file_obj, user_question):
    try:
        # File-based sources
        if db_type in ["csv", "excel", "json"]:
            if file_obj is None:
                return "Please upload a file."
            try:
                if db_type == "csv":
                    df = pd.read_csv(file_obj)
                elif db_type == "excel":
                    df = pd.read_excel(io.BytesIO(file_obj.read()))
                    file_obj.seek(0)
                elif db_type == "json":
                    df = pd.read_json(file_obj)
                else:
                    return "Unsupported file type."
            except Exception as e:
                return f"Error reading file: {e}"
            # Use alternate LLM for files
            return results_to_text_llm_file(
                user_question, db_type, "Pandas DataFrame", df.to_dict(orient="records")
            )
        
        # MongoDB
        elif db_type == "mongodb":
            if not db_url:
                return "Please provide a MongoDB URL."
            try:
                client = pymongo.MongoClient(db_url)
                dbname = db_url.rsplit('/', 1)[-1]
                db = client[dbname]
                collection_names = db.list_collection_names()
                if not collection_names:
                    return "No collections found in MongoDB."
                collection = db[collection_names[0]]
                docs = list(collection.find())
                for d in docs:
                    d.pop('_id', None)
                return results_to_text_llm_db(user_question, db_type, "MongoDB find()", docs)
            except Exception as e:
                return f"MongoDB error: {e}"

        # Relational DBs
        else:
            if not db_url:
                return "Please provide a database URL."
            try:
                db = SQLDatabase.from_uri(db_url)
                from langchain_groq import ChatGroq
                llm = ChatGroq(
                    model_name="llama3-8b-8192",
                    temperature=0.0
                )
                chain = create_sql_query_chain(llm, db)
                response = chain.invoke({"question": user_question})
                match = re.search(r'SQLQuery:\s*([\s\S]+?;?)\s*$', response, re.IGNORECASE)
                if not match:
                    return "No valid SQL query found in LLM response."
                sql_query = match.group(1).strip().rstrip(';')
                url = make_url(db_url)
                if db_type == "sqlite":
                    conn = sqlite3.connect(url.database)
                    cursor = conn.cursor()
                    cursor.execute(sql_query)
                    rows = cursor.fetchall()
                    column_names = [desc[0] for desc in cursor.description] if cursor.description else []
                elif db_type == "postgresql":
                    conn = psycopg2.connect(
                        dbname=url.database,
                        user=url.username,
                        password=url.password,
                        host=url.host,
                        port=url.port or 5432
                    )
                    cursor = conn.cursor()
                    cursor.execute(sql_query)
                    rows = cursor.fetchall()
                    column_names = [desc[0] for desc in cursor.description] if cursor.description else []
                elif db_type == "mysql":
                    conn = mysql.connector.connect(
                        database=url.database,
                        user=url.username,
                        password=url.password,
                        host=url.host,
                        port=url.port or 3306
                    )
                    cursor = conn.cursor()
                    cursor.execute(sql_query)
                    rows = cursor.fetchall()
                    column_names = [desc[0] for desc in cursor.description] if cursor.description else []
                elif db_type == "oracle":
                    conn = cx_Oracle.connect(
                        user=url.username,
                        password=url.password,
                        dsn=f"{url.host}:{url.port or 1521}/{url.database}"
                    )
                    cursor = conn.cursor()
                    cursor.execute(sql_query)
                    rows = cursor.fetchall()
                    column_names = [desc[0] for desc in cursor.description] if cursor.description else []
                elif db_type == "sqlserver":
                    conn_str = (
                        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                        f"SERVER={url.host},{url.port or 1433};"
                        f"DATABASE={url.database};"
                        f"UID={url.username};"
                        f"PWD={url.password}"
                    )
                    conn = pyodbc.connect(conn_str)
                    cursor = conn.cursor()
                    cursor.execute(sql_query)
                    rows = cursor.fetchall()
                    column_names = [column[0] for column in cursor.description] if cursor.description else []
                else:
                    return f"Unsupported database type: {db_type}"
                conn.close()
                results = [dict(zip(column_names, row)) for row in rows] if rows else []
                return results_to_text_llm_db(user_question, db_type, sql_query, results)
            except Exception as e:
                return f"Database error: {e}"
    except Exception as e:
        return f"Error: {e}"

# --- Custom CSS for Colorful UI ---
custom_css = """
body { background: #f0f4f8; }
.gradio-container { background: #f0f4f8 !important; }
h1, h2, h3, h4, h5, h6 { color: #2b4263 !important; }
.gr-button { background: linear-gradient(90deg, #4f8cff, #6ee7b7) !important; color: #fff !important; border: none !important; }
.gr-input, .gr-textbox, .gr-dropdown { border: 1px solid #4f8cff !important; background: #fff !important; }
.gr-box { background: #e0f2fe !important; border-radius: 10px !important; }
"""

with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as app:
    gr.Markdown("<h1 style='text-align:center; color:#4f8cff;'>Natural Language to Database/File Query Generator</h1>")
    gr.Markdown(
        "<div style='text-align:center; color:#2b4263; font-size:18px;'>"
        "Select your data source, upload your file or enter DB URL, and ask your question!"
        "</div>"
    )

    with gr.Row():
        db_type = gr.Dropdown(
            ["sqlite", "postgresql", "mysql", "oracle", "sqlserver", "mongodb", "csv", "excel", "json"],
            value="sqlite",
            label="Source Type"
        )
        db_url = gr.Textbox(label="Database URL (for DBs only)", placeholder="e.g., mysql://user:pass@host:3306/dbname")
        file_input = gr.File(label="Upload CSV, Excel, or JSON", file_count="single", visible=False, type="binary")

    user_question = gr.Textbox(label="Your Question", placeholder="e.g., Show all users who signed up in 2023")
    btn = gr.Button("Generate and Execute Query")
    results_text_output = gr.Textbox(
        label="Answer",
        lines=8,
        interactive=False,
        elem_id="llm-answer",
        show_copy_button=True
    )

    def show_hide_file(db_type_val):
        return gr.update(visible=db_type_val in ["csv", "excel", "json"])

    db_type.change(show_hide_file, db_type, file_input)

    btn.click(
        fn=main,
        inputs=[db_type, db_url, file_input, user_question],
        outputs=[results_text_output]
    )

app.launch(share=True)
