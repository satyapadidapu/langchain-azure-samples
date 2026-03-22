import os
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
    TextLoader,
    CSVLoader,
    UnstructuredPowerPointLoader,
    UnstructuredHTMLLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings

LOADER_MAP = {
    ".pdf": PyPDFLoader,
    ".docx": Docx2txtLoader,
    ".doc": Docx2txtLoader,
    ".txt": TextLoader,
    ".csv": CSVLoader,
    ".xlsx": UnstructuredExcelLoader,
    ".xls": UnstructuredExcelLoader,
    ".pptx": UnstructuredPowerPointLoader,
    ".html": UnstructuredHTMLLoader,
    ".htm": UnstructuredHTMLLoader,
    ".md": TextLoader,
    ".json": TextLoader,
    ".py": TextLoader,
    ".js": TextLoader,
    ".xml": TextLoader,
    ".yaml": TextLoader,
    ".yml": TextLoader,
    ".log": TextLoader,
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


def get_embeddings():
    return AzureOpenAIEmbeddings(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].replace("/openai/v1", ""),
        api_key=os.environ["AZURE_AI_API_KEY"],
        model=os.environ.get("EMBEDDING_MODEL", "text-embedding-ada-002"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
    )


def is_image(file_path):
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS


def encode_image_to_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(file_path):
    ext = Path(file_path).suffix.lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
        ".tiff": "image/tiff",
    }
    return mime_map.get(ext, "image/png")


def load_document(file_path):
    ext = Path(file_path).suffix.lower()
    loader_cls = LOADER_MAP.get(ext, TextLoader)
    return loader_cls(file_path).load()


def process_files(file_paths):
    all_docs = []
    image_data = []
    file_names = []

    for fp in file_paths:
        name = Path(fp).name
        file_names.append(name)
        if is_image(fp):
            image_data.append((encode_image_to_base64(fp), get_image_mime_type(fp), name))
        else:
            chunks = text_splitter.split_documents(load_document(fp))
            all_docs.extend(chunks)

    vector_store = None
    if all_docs:
        vector_store = FAISS.from_documents(all_docs, get_embeddings())

    return vector_store, image_data, file_names


def retrieve_context(vector_store, query, k=4):
    if vector_store is None:
        return ""
    docs = vector_store.similarity_search(query, k=k)
    return "\n\n---\n\n".join(doc.page_content for doc in docs)
