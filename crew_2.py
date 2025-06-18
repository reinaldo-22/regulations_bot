import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PDFPlumberLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from crewai import Agent, Task, Crew, LLM


LLM_MODEL = "gpt-3.5-turbo"
DB_DIR = ""


OPENAI_API_KEY=""
MISTRAL_API_KEY="YOUR_MISTRAL_KEY"
LLM_PROVIDER="openai"  # or "mist
# -- LLM --
llm = LLM(model=LLM_MODEL, api_key=OPENAI_API_KEY, temperature=0.3)

# -- RAG Setup --
def build_vector_store(pdf_paths):
    docs = []
    for path in pdf_paths:
        docs += PDFPlumberLoader(path).load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150).split_documents(docs)
    return Chroma.from_documents(
        documents=chunks,
        embedding=OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY),
        persist_directory=DB_DIR
    )

def get_retriever(use_existing=True, pdf_paths=None):
    if use_existing and os.path.exists(DB_DIR):
        return Chroma(
            embedding_function=OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY),
            persist_directory=DB_DIR
        ).as_retriever(search_type="mmr", search_kwargs={"k": 3})
    else:
        return build_vector_store(pdf_paths).as_retriever(search_type="mmr", search_kwargs={"k": 3})

# -- Agents --
planner = Agent(
    role="Regulation Analyst",
    goal="Identify relevant banking regulations and ramifications based on a specific query",
    backstory="An experienced analyst in a bank's compliance department, responsible for uncovering relevant regulatory information for complex banking operations.",
    allow_delegation=False,
    verbose=True,
    llm=llm
)

writer = Agent(
    role="Compliance Writer",
    goal="Write an in-depth compliance report based on the planner’s findings",
    backstory="You are responsible for compiling clear, professional reports on regulations, summarizing relevant rules and outlining compliance implications.",
    allow_delegation=True,
    verbose=True,
    llm=llm
)

editor = Agent(
    role="Chief Compliance Officer",
    goal="Edit and approve the report for delivery to executive stakeholders",
    backstory="You ensure that the compliance report is accurate, professional, and aligned with regulatory tone and internal policy.",
    allow_delegation=True,
    verbose=True,
    llm=llm
)

# -- Crew Tasks --
def build_tasks(topic, retriever):
    context = "\n\n".join(doc.page_content for doc in retriever.get_relevant_documents(topic))

    return [
        Task(
            description=f"Using the following regulation context:\n{context}\n\nResearch relevant regulatory guidelines, rules, and ramifications for the topic: '{topic}'",
            expected_output="A summary of applicable regulations and possible implications",
            agent=planner
        ),
        Task(
            description="Write a structured compliance report based on the analyst’s findings. The report must include an executive summary, regulatory breakdown, and practical implications for the bank.¸\
                
            expected_output="A full markdown-formatted compliance report" ,
            agent=writer
        ),
        Task(
            description="Review and polish the report for clarity, accuracy, and tone. Ensure it is suitable for presentation to bank leadership. Language must be Spanish from the Rive Plate",
            expected_output="Finalized compliance report in markdown, reviewed and approved, writen in Spanish",
            agent=editor
        )
    ]

# -- CLI-Like Entry --
def run_crew(topic, pdf_paths=None):
    retriever = get_retriever(use_existing=(pdf_paths is None), pdf_paths=pdf_paths)
    tasks = build_tasks(topic, retriever)
    crew = Crew(
        agents=[planner, writer, editor],
        tasks=tasks,
        verbose=True
    )
    result = crew.kickoff()
    print(result)

# -- Ad-hoc Q&A --
def ask_question(question):
    retriever = get_retriever(use_existing= True)
    context = "\n\n".join(doc.page_content for doc in retriever.get_relevant_documents(question))
    ag = Agent(role="assistant", goal="Answer regulatory questions using provided documents", backstory="", llm=llm)
    t = Task(description=f"Context:\n{context}\n\nQuestion:\n{question}", expected_output="Detailed answer based on regulations", agent=ag)
    result = Crew(agents=[ag], tasks=[t], verbose=True,  memory=False).kickoff()
    #current_crew = Crew(agents=[ag], tasks=[t], verbose=True)
    return result.raw
    

















