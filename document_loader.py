import os
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_core.documents import Document

def load_document(source: str, source_type: str) -> list[Document]:
    """
    Extracts text from various file sources.
    source_type: 'pdf', 'url', 'text'
    source: A filepath, URL, or raw text string.
    """
    docs = []
    
    if source_type == 'pdf':
        if not os.path.exists(source):
            raise FileNotFoundError(f"PDF file not found: {source}")
        loader = PyPDFLoader(source)
        docs = loader.load()
        
    elif source_type == 'url':
        loader = WebBaseLoader(source)
        docs = loader.load()
        
    elif source_type == 'text':
        # Wrap raw text straight into a document
        docs = [Document(page_content=source, metadata={"source": "raw_text"})]
        
    else:
        raise ValueError(f"Unsupported source type: '{source_type}'")
        
    # Optional cleanup step: Strip excessive whitespace
    for doc in docs:
        doc.page_content = " ".join(doc.page_content.split())
        
    return docs

