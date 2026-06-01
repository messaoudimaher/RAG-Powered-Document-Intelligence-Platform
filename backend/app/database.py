import logging

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger("docmind.database")

class DatabaseManager:
    """
    Manages ChromaDB persistent storage, collections creation,
    and basic query operations.
    """
    def __init__(self):
        # Initialize Persistent Client
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.initialize_collections()

    def initialize_collections(self):
        """
        Initializes the public and papers collections using cosine similarity.
        """
        try:
            self.public_collection = self.client.get_or_create_collection(
                name=settings.chroma_collection_public,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Initialized collection: {settings.chroma_collection_public}")

            self.papers_collection = self.client.get_or_create_collection(
                name=settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Initialized collection: {settings.chroma_collection_name}")
        except Exception as e:
            logger.error(f"Error initializing ChromaDB collections: {e}")
            raise

    def get_collection(self, collection_type: str):
        """
        Returns the appropriate collection based on type ('public' or 'papers').
        """
        if collection_type == "public":
            return self.public_collection
        elif collection_type == "papers":
            return self.papers_collection
        else:
            raise ValueError(f"Unknown collection type: {collection_type}. Use 'public' or 'papers'.")

    def add_chunks(
        self,
        collection_type: str,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str]
    ):
        """
        Adds vector embeddings and source chunks to the database.
        """
        collection = self.get_collection(collection_type)
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
        logger.info(f"Added {len(ids)} chunks to {collection_type} collection.")

    def query(
        self,
        collection_type: str,
        query_embeddings: list[list[float]],
        n_results: int = 5,
        where: dict = None
    ) -> dict:
        """
        Performs vector search using query embeddings in the selected collection.
        Returns matches including documents, metadatas, and distances.
        """
        collection = self.get_collection(collection_type)
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        return results

    def get_unique_documents(self, collection_type: str) -> list[dict]:
        """
        Returns a list of unique source documents in the collection,
        including chunk count and overall file metadata.
        """
        collection = self.get_collection(collection_type)

        # Retrieve all items (only metadatas to optimize speed/memory)
        # Note: Chroma allows calling get() with empty parameter, but to prevent loading all text
        # we can specify including only metadata.
        result = collection.get(include=["metadatas"])
        metadatas = result.get("metadatas", [])

        if not metadatas:
            return []

        doc_map = {}
        for meta in metadatas:
            if not meta or "source" not in meta:
                continue
            source = meta["source"]
            if source not in doc_map:
                doc_map[source] = {
                    "source": source,
                    "title": meta.get("title", source),
                    "chunk_count": 0,
                    "file_type": meta.get("file_type", "unknown"),
                    "added_at": meta.get("added_at", "unknown"),
                }
            doc_map[source]["chunk_count"] += 1

        return list(doc_map.values())

    def delete_document(self, collection_type: str, source_name: str) -> bool:
        """
        Deletes all chunks corresponding to a specific source document.
        """
        collection = self.get_collection(collection_type)
        try:
            # Delete by metadata filter 'source'
            collection.delete(where={"source": source_name})
            logger.info(f"Deleted document '{source_name}' from {collection_type} collection.")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document '{source_name}': {e}")
            return False

    def get_stats(self) -> dict:
        """
        Returns system collection count statistics.
        """
        try:
            return {
                "public_count": self.public_collection.count(),
                "papers_count": self.papers_collection.count(),
                "status": "healthy"
            }
        except Exception as e:
            logger.error(f"Error getting DB statistics: {e}")
            return {
                "public_count": 0,
                "papers_count": 0,
                "status": "degraded",
                "error": str(e)
            }

# Global singleton
db_manager = DatabaseManager()
