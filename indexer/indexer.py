import os
import uuid
import torch
import logging
import time
from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path

from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client.http.models import Distance, VectorParams, Filter, FieldCondition, MatchValue
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain_community.document_loaders import (
    TextLoader,
    CSVLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
    PyMuPDFLoader,
    UnstructuredPowerPointLoader,
)

from storage import MinimaStore, IndexingStatus

logger = logging.getLogger(__name__)


@dataclass
class Config:
    EXTENSIONS_TO_LOADERS = {
        ".pdf": PyMuPDFLoader,
        ".pptx": UnstructuredPowerPointLoader,
        ".ppt": UnstructuredPowerPointLoader,
        ".xls": UnstructuredExcelLoader,
        ".xlsx": UnstructuredExcelLoader,
        ".docx": Docx2txtLoader,
        ".doc": Docx2txtLoader,
        ".txt": TextLoader,
        ".md": TextLoader,
        ".csv": CSVLoader,
    }
    
    DEVICE = torch.device(
        "mps" if torch.backends.mps.is_available() else
        "cuda" if torch.cuda.is_available() else
        "cpu"
    )
    
    START_INDEXING = os.environ.get("START_INDEXING")
    LOCAL_FILES_PATH = os.environ.get("LOCAL_FILES_PATH")
    CONTAINER_PATH = os.environ.get("CONTAINER_PATH")
    QDRANT_COLLECTION = "mnm_storage"
    QDRANT_BOOTSTRAP = "qdrant"
    EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID")
    EMBEDDING_SIZE = os.environ.get("EMBEDDING_SIZE")
    
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 200

class Indexer:
    def __init__(self):
        self.config = Config()
        self.qdrant = self._initialize_qdrant()
        self.embed_model = self._initialize_embeddings()
        self.document_store = self._setup_collection()
        self.text_splitter = self._initialize_text_splitter()

    def _initialize_qdrant(self) -> QdrantClient:
        return QdrantClient(host=self.config.QDRANT_BOOTSTRAP)

    def _initialize_embeddings(self) -> HuggingFaceEmbeddings:
        return HuggingFaceEmbeddings(
            model_name=self.config.EMBEDDING_MODEL_ID,
            model_kwargs={'device': self.config.DEVICE},
            encode_kwargs={'normalize_embeddings': False}
        )

    def _initialize_text_splitter(self) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter(
            chunk_size=self.config.CHUNK_SIZE,
            chunk_overlap=self.config.CHUNK_OVERLAP
        )

    def _setup_collection(self) -> QdrantVectorStore:
        if not self.qdrant.collection_exists(self.config.QDRANT_COLLECTION):
            self.qdrant.create_collection(
                collection_name=self.config.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=self.config.EMBEDDING_SIZE,
                    distance=Distance.COSINE
                ),
            )
        self.qdrant.create_payload_index(
            collection_name=self.config.QDRANT_COLLECTION,
            field_name="fpath",
            field_schema="keyword"
        )
        return QdrantVectorStore(
            client=self.qdrant,
            collection_name=self.config.QDRANT_COLLECTION,
            embedding=self.embed_model,
        )

    def _create_loader(self, file_path: str):
        file_extension = Path(file_path).suffix.lower()
        loader_class = self.config.EXTENSIONS_TO_LOADERS.get(file_extension)
        
        if not loader_class:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        return loader_class(file_path=file_path)

    def _process_file(self, loader) -> List[str]:
        try:
            documents = loader.load_and_split(self.text_splitter)
            if not documents:
                logger.warning(f"No documents loaded from {loader.file_path}")
                return []

            for doc in documents:
                doc.metadata['file_path'] = loader.file_path

            uuids = [str(uuid.uuid4()) for _ in range(len(documents))]
            ids = self.document_store.add_documents(documents=documents, ids=uuids)
            
            logger.info(f"Successfully processed {len(ids)} documents from {loader.file_path}")
            return ids
            
        except Exception as e:
            logger.error(f"Error processing file {loader.file_path}: {str(e)}")
            return []

    def index(self, message: Dict[str, any]) -> None:
        start = time.time()
        path, file_id, last_updated_seconds = message["path"], message["file_id"], message["last_updated_seconds"]
        logger.info(f"Processing file: {path} (ID: {file_id})")
        indexing_status: IndexingStatus = MinimaStore.check_needs_indexing(fpath=path, last_updated_seconds=last_updated_seconds)
        if indexing_status != IndexingStatus.no_need_reindexing:
            logger.info(f"Indexing needed for {path} with status: {indexing_status}")
            try:
                if indexing_status == IndexingStatus.need_reindexing:
                    logger.info(f"Removing {path} from index storage for reindexing")
                    self.remove_from_storage(files_to_remove=[path])
                loader = self._create_loader(path)
                ids = self._process_file(loader)
                if ids:
                    logger.info(f"Successfully indexed {path} with IDs: {ids}")
            except Exception as e:
                logger.error(f"Failed to index file {path}: {str(e)}")
        else:
            logger.info(f"Skipping {path}, no indexing required. timestamp didn't change")
        end = time.time()
        logger.info(f"Processing took {end - start} seconds for file {path}")

    def purge(self, message: Dict[str, any]) -> None:
        existing_file_paths: list[str] = message["existing_file_paths"]
        files_to_remove = MinimaStore.find_removed_files(existing_file_paths=set(existing_file_paths))
        if len(files_to_remove) > 0:
            logger.info(f"purge processing removing old files {files_to_remove}")
            self.remove_from_storage(files_to_remove)
        else:
            logger.info("Nothing to purge")

    def remove_from_storage(self, files_to_remove: list[str]):
        filter_conditions = Filter(
            must=[
                FieldCondition(
                    key="fpath",
                    match=MatchValue(value=fpath)
                )
                for fpath in files_to_remove
            ]
        )
        response = self.qdrant.delete(
            collection_name=self.config.QDRANT_COLLECTION,
            points_selector=filter_conditions,
            wait=True
        )
        logger.info(f"Delete response for {len(files_to_remove)} for files: {files_to_remove} is: {response}")

    def find(self, query: str) -> Dict[str, any]:
        try:
            logger.info(f"Searching for: {query}")
            found = self.document_store.search(query, search_type="similarity")
            
            if not found:
                logger.info("No results found")
                return {"links": set(), "output": ""}

            links = set()
            results = []
            
            for item in found:
                path = item.metadata["file_path"].replace(
                    self.config.CONTAINER_PATH,
                    self.config.LOCAL_FILES_PATH
                )
                links.add(f"file://{path}")
                results.append(item.page_content)

            output = {
                "links": links,
                "output": ". ".join(results)
            }
            
            logger.info(f"Found {len(found)} results")
            return output
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return {"error": "Unable to find anything for the given query"}

    def embed(self, query: str):
        return self.embed_model.embed_query(query)
    
    def get_qdrant_document_count(self) -> tuple[int, int]:
        """Get the number of documents in Qdrant collection"""
        try:
            collection_info = self.qdrant.get_collection(self.config.QDRANT_COLLECTION)
            return collection_info.points_count, collection_info.indexed_vectors_count
        except Exception as e:
            logger.warning(f"Could not get Qdrant document count: {e}")
            return 0, 0
    
    def get_sqlite_file_count(self) -> int:
        """Get the number of files tracked in SQLite"""
        try:
            from storage import MinimaStore, engine
            from sqlmodel import text
            with engine.connect() as connection:
                result = connection.execute(text("SELECT COUNT(*) FROM minimadoc"))
                return result.scalar()
        except Exception as e:
            logger.warning(f"Could not get SQLite file count: {e}")
            return 0
    
    def validate_data_consistency(self) -> bool:
        """Check if SQLite and Qdrant data are consistent"""
        qdrant_count, indexed_count = self.get_qdrant_document_count()
        sqlite_count = self.get_sqlite_file_count()
        
        logger.info(f"Data consistency check - Qdrant: {qdrant_count} docs ({indexed_count} indexed), SQLite: {sqlite_count} files")
        
        # If SQLite has files but Qdrant is empty, we have a consistency issue
        if sqlite_count > 0 and qdrant_count == 0:
            logger.warning("Data inconsistency detected: SQLite has file records but Qdrant is empty")
            return False
        
        # If vectors exist but aren't indexed, check if it's due to indexing threshold
        # Qdrant only builds HNSW index when document count exceeds indexing_threshold (default: 10000)
        if qdrant_count > 0 and indexed_count == 0 and qdrant_count >= 10000:
            logger.warning("Data inconsistency detected: Large dataset but vectors are not indexed")
            return False
        
        # Test if vector search actually works by doing a simple search
        if qdrant_count > 0:
            try:
                # Try a simple vector search to detect corrupted data
                test_result = self.document_store.similarity_search("test query", k=1)
                logger.info(f"Vector search test successful: {len(test_result)} results")
            except Exception as e:
                error_str = str(e)
                if "OutputTooSmall" in error_str or "Service internal error" in error_str:
                    logger.warning(f"Data inconsistency detected: Vector search fails with corruption error: {error_str}")
                    return False
                else:
                    logger.warning(f"Vector search test failed with unknown error: {error_str}")
                    # Don't fail for unknown errors, might be temporary
        
        # If there's a large discrepancy (more than 50% difference), something's wrong
        if sqlite_count > 0:
            ratio = qdrant_count / (sqlite_count * 3)  # Rough estimate: ~3 chunks per file
            if ratio < 0.5:
                logger.warning(f"Data inconsistency detected: Too few documents in Qdrant (ratio: {ratio:.2f})")
                return False
        
        logger.info("Data consistency check passed")
        return True
    
    def force_reindex_all(self):
        """Force reindexing of all files by clearing SQLite records"""
        try:
            from storage import engine
            from sqlmodel import text
            with engine.connect() as connection:
                connection.execute(text("DELETE FROM minimadoc"))
                connection.commit()
            logger.info("Cleared SQLite records to force reindexing")
        except Exception as e:
            logger.error(f"Failed to clear SQLite records: {e}")
    
    def startup_integrity_check(self):
        """Perform startup integrity check and fix inconsistencies"""
        logger.info("Running startup integrity check...")
        
        if not self.validate_data_consistency():
            logger.warning("Data inconsistency detected. Forcing reindexing...")
            self.force_reindex_all()
        else:
            logger.info("Data integrity check passed")