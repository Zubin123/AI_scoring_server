import asyncio
from typing import Optional, Dict, Any, List
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import structlog

logger = structlog.get_logger(__name__)


class MongoDBService:
    """
    MongoDB service for managing configuration data, tokens, and protocol thresholds.
    Provides async interface for database operations.
    """
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.logger = logger
        
        # MongoDB configuration
        self.mongodb_url = config.get('MONGODB_URL', 'mongodb://localhost:27017')
        self.database_name = config.get('MONGODB_DATABASE', 'ai_scoring')
        self.tokens_collection = config.get('MONGODB_TOKENS_COLLECTION', 'tokens')
        self.thresholds_collection = config.get('MONGODB_THRESHOLDS_COLLECTION', 'protocol-thresholds-percentiles')
        
        # MongoDB client
        self.client: Optional[MongoClient] = None
        self.database = None
        
        # Initialize connection
        self._init_connection()
    
    def _init_connection(self):
        """Initialize MongoDB connection."""
        try:
            self.client = MongoClient(
                self.mongodb_url,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            self.database = self.client[self.database_name]
            
            self.logger.info("MongoDB connection established", 
                           database=self.database_name,
                           collections=[self.tokens_collection, self.thresholds_collection])
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            self.logger.error("Failed to connect to MongoDB", error=str(e))
            raise
        except Exception as e:
            self.logger.error("MongoDB initialization error", error=str(e))
            raise
    
    def get_health_status(self) -> str:
        """Get MongoDB health status."""
        try:
            if self.client:
                # Ping the database
                self.client.admin.command('ping')
                return "healthy"
            else:
                return "unhealthy"
        except Exception:
            return "unhealthy"
    
    async def get_token_info(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get token information from the database.
        
        Args:
            token_address: Token contract address
            
        Returns:
            Token information dictionary or None if not found
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.database[self.tokens_collection].find_one(
                    {"address": token_address}
                )
            )
            
            return result
            
        except Exception as e:
            self.logger.error("Error fetching token info", 
                            token_address=token_address, 
                            error=str(e))
            return None
    
    async def get_protocol_thresholds(self, protocol_type: str) -> Optional[Dict[str, Any]]:
        """
        Get protocol thresholds and percentiles for scoring.
        
        Args:
            protocol_type: Protocol type (e.g., 'dexes', 'lending', etc.)
            
        Returns:
            Protocol thresholds dictionary or None if not found
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.database[self.thresholds_collection].find_one(
                    {"protocol_type": protocol_type}
                )
            )
            
            return result
            
        except Exception as e:
            self.logger.error("Error fetching protocol thresholds", 
                            protocol_type=protocol_type, 
                            error=str(e))
            return None
    
    async def update_token_info(self, token_address: str, token_data: Dict[str, Any]) -> bool:
        """
        Update or insert token information.
        
        Args:
            token_address: Token contract address
            token_data: Token data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.database[self.tokens_collection].update_one(
                    {"address": token_address},
                    {"$set": token_data},
                    upsert=True
                )
            )
            
            self.logger.info("Token info updated", 
                           token_address=token_address,
                           modified_count=result.modified_count,
                           upserted_id=result.upserted_id)
            
            return True
            
        except Exception as e:
            self.logger.error("Error updating token info", 
                            token_address=token_address, 
                            error=str(e))
            return False
    
    async def update_protocol_thresholds(self, protocol_type: str, thresholds: Dict[str, Any]) -> bool:
        """
        Update or insert protocol thresholds.
        
        Args:
            protocol_type: Protocol type
            thresholds: Threshold data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.database[self.thresholds_collection].update_one(
                    {"protocol_type": protocol_type},
                    {"$set": thresholds},
                    upsert=True
                )
            )
            
            self.logger.info("Protocol thresholds updated", 
                           protocol_type=protocol_type,
                           modified_count=result.modified_count,
                           upserted_id=result.upserted_id)
            
            return True
            
        except Exception as e:
            self.logger.error("Error updating protocol thresholds", 
                            protocol_type=protocol_type, 
                            error=str(e))
            return False
    
    async def get_all_tokens(self) -> List[Dict[str, Any]]:
        """
        Get all tokens from the database.
        
        Returns:
            List of token dictionaries
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                lambda: self.database[self.tokens_collection].find({})
            )
            
            # Convert cursor to list
            tokens = await loop.run_in_executor(None, lambda: list(cursor))
            
            return tokens
            
        except Exception as e:
            self.logger.error("Error fetching all tokens", error=str(e))
            return []
    
    async def get_all_protocols(self) -> List[Dict[str, Any]]:
        """
        Get all protocol configurations from the database.
        
        Returns:
            List of protocol dictionaries
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                lambda: self.database[self.thresholds_collection].find({})
            )
            
            # Convert cursor to list
            protocols = await loop.run_in_executor(None, lambda: list(cursor))
            
            return protocols
            
        except Exception as e:
            self.logger.error("Error fetching all protocols", error=str(e))
            return []
    
    async def create_indexes(self):
        """Create database indexes for better performance."""
        try:
            # Create indexes for tokens collection
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.database[self.tokens_collection].create_index("address", unique=True)
            )
            
            # Create indexes for thresholds collection
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.database[self.thresholds_collection].create_index("protocol_type", unique=True)
            )
            
            self.logger.info("Database indexes created successfully")
            
        except Exception as e:
            self.logger.error("Error creating database indexes", error=str(e))
    
    async def close(self):
        """Close MongoDB connection."""
        try:
            if self.client:
                self.client.close()
                self.logger.info("MongoDB connection closed")
        except Exception as e:
            self.logger.error("Error closing MongoDB connection", error=str(e)) 