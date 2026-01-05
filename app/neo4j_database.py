
import logging
from dotenv import load_dotenv
from neo4j import GraphDatabase
import os
from app.neo4j_quries import Queries

logger = logging.getLogger(__name__)

load_dotenv(override=True)

# Singleton driver instance - thread-safe and reusable
_neo4j_driver = None


def get_neo4j_driver():
    """Get or create a singleton Neo4j driver instance."""
    global _neo4j_driver
    if _neo4j_driver is None:
        uri = os.environ.get("NEO4J_URI")
        user = os.environ.get("NEO4J_USER", "neo4j")  # Default to "neo4j" if not set
        password = os.environ.get("NEO4J_PASSWORD")
        _neo4j_driver = GraphDatabase.driver(uri, auth=(user, password))
        _neo4j_driver.verify_connectivity()
        logger.info("Neo4j driver connection established")
    return _neo4j_driver


class Neo4JDatabase:
    """
    Class to interact with the Neo4J database
    """

    def __init__(self, neo4j_uri: str = None, neo4j_auth: tuple = None):
        """
        Initialize the Neo4JDatabase instance
        """
        if neo4j_uri and neo4j_auth:
            self.__driver = GraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
        else:
            self.__driver = get_neo4j_driver()
        logger.info("Neo4JDatabase instance initialized with shared driver")
    
    def get_session(self):
        """Return a new database session."""
        return self.__driver.session()

    def get_segments_by_manifestation(self, manifestation_id: str) -> list[dict]:
        """
        Get all segments from segmentation or pagination annotation for a manifestation.

        Args:
            manifestation_id: The manifestation ID

        Returns:
            List of dictionaries containing segment_id, span_start, and span_end
        """
        with self.get_session() as session:
            result = session.execute_read(
                lambda tx: list(tx.run(
                    Queries.segments["get_segments_by_manifestation"],
                    manifestation_id=manifestation_id
                ))
            )
            return [dict(record) for record in result]

    def has_alignment_annotation(self, manifestation_id: str) -> bool:
        """
        Method to check if a manifestation has an alignment annotation
        """
        with self.get_session() as session:
            result = session.execute_read(
                lambda tx: tx.run(
                    Queries.annotations["has_alignment_annotation"],
                    manifestation_id=manifestation_id
                ).single()
            )
            if result is None:
                return False
            return result["has_alignment"]

    def get_text_ids_with_alignment(self, text_ids: list[str]) -> dict[str, bool]:
        """
        Check alignment annotations for multiple text_ids in a single query.

        Args:
            text_ids: List of text IDs to check

        Returns:
            Dictionary mapping text_id -> has_alignment (bool)
        """
        if not text_ids:
            return {}
        
        with self.get_session() as session:
            result = session.execute_read(
                lambda tx: list(tx.run(
                    Queries.annotations["batch_has_alignment_annotation"],
                    text_ids=text_ids
                ))
            )
            return {record["text_id"]: record["has_alignment"] for record in result}