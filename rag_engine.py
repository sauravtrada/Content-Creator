import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from document_loader import load_document

# Load the local sentence transformer model once when the module imports
# Use the highly efficient 'all-MiniLM-L6-v2' model for our CPU
_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def ingest_document(source: str, source_type: str) -> FAISS:
    """
    Loads, chunks, and embeds a document into a local FAISS vector store.
    Returns the FAISS object.
    """
    print(f"Loading document from {source_type}...")
    docs = load_document(source, source_type)
    
    # Text Chunking Strategy
    print("Chunking document...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_documents(docs)
    
    if not chunks:
        raise ValueError("Document yielded 0 text chunks.")
        
    print(f"Creating FAISS index with {len(chunks)} chunks using all-MiniLM-L6-v2...")
    # FAISS will compute embeddings for all chunks here
    vectorstore = FAISS.from_documents(chunks, _embeddings)
    
    print("FAISS index created successfully.")
    return vectorstore

def format_docs(docs):
    """Utility to format retrieved docs into a single string for prompts."""
    return "\n\n".join(doc.page_content for doc in docs)
