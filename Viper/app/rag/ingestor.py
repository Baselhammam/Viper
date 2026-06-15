"""
Document ingestion layer.

Supported formats: .md / .txt  (TextLoader)
                   .pdf         (PyPDFLoader)

Returns a flat list of LangChain Document objects — each one is a chunk
ready to be embedded and stored in the vector store.
"""
from pathlib import Path
from typing import List

from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import cfg


def _load_file(file_path: str) -> List[Document]:
    """Dispatch to the right loader based on file extension."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        loader = PyPDFLoader(str(path))
    else:
        # TextLoader handles .md, .txt, and most other plain-text formats.
        loader = TextLoader(str(path), encoding="utf-8")

    return loader.load()


def ingest_documents(file_paths: List[str]) -> List[Document]:
    """
    Load every file, split into chunks, and return the full chunk list.
    Separators are ordered so the splitter prefers Markdown headings first,
    then paragraph breaks, then lines, then word boundaries.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.rag.chunk_size,
        chunk_overlap=cfg.rag.chunk_overlap,
        separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
    )

    all_chunks: List[Document] = []
    for fp in file_paths:
        raw = _load_file(fp)
        chunks = splitter.split_documents(raw)
        # Attach the source filename to every chunk's metadata for traceability.
        for chunk in chunks:
            chunk.metadata.setdefault("source", str(fp))
        all_chunks.extend(chunks)
        print(f"  Ingested '{fp}' → {len(chunks)} chunks")

    return all_chunks
