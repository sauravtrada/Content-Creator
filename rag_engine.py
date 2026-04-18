import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from document_loader import load_document

# Load the local sentence transformer model once when the module imports
# Use the highly efficient 'all-MiniLM-L6-v2' model for our CPU
_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def ingest_document(sources: list[str] | str, source_type: str) -> FAISS:
    """
    Loads, chunks, and embeds documents from one or more sources into a 
    single local FAISS vector store.
    sources: A list of filepaths/URLs, or a single path/URL/string.
    """
    if isinstance(sources, str):
        sources = [sources]

    all_docs = []
    print(f"Loading {len(sources)} documents from {source_type}...")
    
    for idx, src in enumerate(sources):
        try:
            print(f"[{idx+1}/{len(sources)}] Processing: {src[:60]}")
            docs = load_document(src, source_type)
            all_docs.extend(docs)
        except Exception as e:
            print(f"Warning: Failed to load source {src}: {e}")

    if not all_docs:
        raise ValueError("No documents were successfully loaded from the provided sources.")

    # Text Chunking Strategy
    print(f"Chunking {len(all_docs)} loaded documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,      # Slightly larger chunks for multi-doc context
        chunk_overlap=240,
        length_function=len
    )
    chunks = text_splitter.split_documents(all_docs)
    
    if not chunks:
        raise ValueError("Document aggregation yielded 0 text chunks.")
        
    print(f"Creating FAISS index with {len(chunks)} chunks using all-MiniLM-L6-v2...")
    vectorstore = FAISS.from_documents(chunks, _embeddings)
    
    print("FAISS index created successfully with combined knowledge.")
    return vectorstore

def format_docs(docs):
    """Utility to format retrieved docs into a single string for prompts."""
    return "\n\n".join(doc.page_content for doc in docs)
