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
        try:
            # Added a standard browser User-Agent to prevent 403 Forbidden errors
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            loader = WebBaseLoader(source, header_template=headers)
            docs = loader.load()
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg:
                raise Exception(f"Access Denied for URL: {source}. The website might be blocking automated access.")
            elif "404" in error_msg:
                raise Exception(f"URL not found: {source}. Please check the link.")
            else:
                raise Exception(f"Failed to load URL {source}: {error_msg}")
        
    elif source_type == 'text':
        # Wrap raw text straight into a document
        docs = [Document(page_content=source, metadata={"source": "raw_text"})]
        
    else:
        raise ValueError(f"Unsupported source type: '{source_type}'")
        
    # Optional cleanup step: Strip excessive whitespace
    for doc in docs:
        doc.page_content = " ".join(doc.page_content.split())
        
    return docs

