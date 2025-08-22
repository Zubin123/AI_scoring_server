import json
import time
import asyncio
from typing import Optional, Dict, Any
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError
import structlog
from pydantic import ValidationError

from app.utils.types import (
    WalletTransactionInput, 
    WalletScoreSuccess, 
    WalletScoreFailure,
    CategoryError
)
from app.models.dex_model import DEXScoringModel

logger = structlog.get_logger(__name__)


class KafkaService:
    """
    Kafka service for consuming wallet transaction messages and producing scoring results.
    Handles message processing, AI scoring, and result publication.
    """
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.logger = logger
        self.scoring_model = DEXScoringModel()
        
        # Kafka configuration
        self.bootstrap_servers = config.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.input_topic = config.get('KAFKA_INPUT_TOPIC', 'wallet-transactions')
        self.success_topic = config.get('KAFKA_SUCCESS_TOPIC', 'wallet-scores-success')
        self.failure_topic = config.get('KAFKA_FAILURE_TOPIC', 'wallet-scores-failure')
        self.consumer_group = config.get('KAFKA_CONSUMER_GROUP', 'ai-scoring-service')
        
        # Kafka clients
        self.consumer: Optional[KafkaConsumer] = None
        self.producer: Optional[KafkaProducer] = None
        
        # Statistics
        self.stats = {
            'total_wallets_processed': 0,
            'successful_wallets': 0,
            'failed_wallets': 0,
            'total_processing_time_ms': 0,
            'last_processed_wallet': None,
            'start_time': time.time()
        }
        
        # Initialize Kafka clients
        self._init_kafka_clients()
    
    def _init_kafka_clients(self):
        """Initialize Kafka consumer and producer."""
        try:
            # Initialize consumer
            self.consumer = KafkaConsumer(
                self.input_topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=1000,  # 1 second timeout for non-blocking
                max_poll_records=10,  # Process up to 10 messages per poll
                session_timeout_ms=30000,
                heartbeat_interval_ms=3000
            )
            
            # Initialize producer
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                acks='all',  # Wait for all replicas
                retries=3,
                max_in_flight_requests_per_connection=1,
               # enable_idempotence=True
            )
            
            self.logger.info("Kafka clients initialized successfully", 
                           bootstrap_servers=self.bootstrap_servers,
                           input_topic=self.input_topic)
            
        except Exception as e:
            self.logger.error("Failed to initialize Kafka clients", error=str(e))
            raise
    
    async def start_consuming(self):
        """Start consuming messages from Kafka."""
        self.logger.info("Starting Kafka consumer", topic=self.input_topic)
        
        try:
            while True:
                # Poll for messages
                message_batch = self.consumer.poll(timeout_ms=1000, max_records=10)
                
                for tp, messages in message_batch.items():
                    for message in messages:
                        try:
                            await self._process_message(message)
                        except Exception as e:
                            self.logger.error("Error processing message", 
                                           error=str(e), 
                                           topic=tp.topic,
                                           partition=tp.partition,
                                           offset=message.offset)
                            
                            # Publish failure message
                            await self._publish_failure(
                                wallet_address="unknown",
                                error=f"Message processing failed: {str(e)}",
                                processing_time_ms=0
                            )
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal, stopping consumer")
        except Exception as e:
            self.logger.error("Consumer error", error=str(e))
        finally:
            await self.shutdown()
    
    async def _process_message(self, message):
        """Process a single Kafka message."""
        start_time = time.time()
        wallet_address = "unknown"
        
        try:
            # Parse message
            message_data = message.value
            self.logger.debug("Processing message", message_data=message_data)
            
            # Validate input data
            wallet_input = WalletTransactionInput(**message_data)
            wallet_address = wallet_input.wallet_address
            
            self.logger.info("Processing wallet", wallet_address=wallet_address)
            
            # Process with AI model
            category_scores, overall_score = self.scoring_model.process_wallet_data(wallet_input.data)
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create success message
            success_message = WalletScoreSuccess(
                wallet_address=wallet_address,
                zscore=f"{overall_score:.18f}",  # 18 decimal places for precision
                timestamp=int(time.time()),
                processing_time_ms=processing_time_ms,
                categories=category_scores
            )
            
            # Publish success message
            await self._publish_success(success_message)
            
            # Update statistics
            self._update_stats(True, processing_time_ms, wallet_address)
            
            self.logger.info("Successfully processed wallet", 
                           wallet_address=wallet_address,
                           score=overall_score,
                           processing_time_ms=processing_time_ms)
            
        except ValidationError as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Validation error: {str(e)}"
            
            await self._publish_failure(
                wallet_address=wallet_address,
                error=error_msg,
                processing_time_ms=processing_time_ms,
                categories=self._create_error_categories(message_data)
            )
            
            self._update_stats(False, processing_time_ms, wallet_address)
            self.logger.error("Validation error", error=error_msg, wallet_address=wallet_address)
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Processing error: {str(e)}"
            
            await self._publish_failure(
                wallet_address=wallet_address,
                error=error_msg,
                processing_time_ms=processing_time_ms,
                categories=self._create_error_categories(message_data if 'message_data' in locals() else {})
            )
            
            self._update_stats(False, processing_time_ms, wallet_address)
            self.logger.error("Processing error", error=error_msg, wallet_address=wallet_address)
    
    def _create_error_categories(self, message_data: Dict[str, Any]) -> list:
        """Create error categories for failure messages."""
        try:
            categories = []
            if 'data' in message_data:
                for protocol_data in message_data['data']:
                    category_error = CategoryError(
                        category=protocol_data.get('protocolType', 'unknown'),
                        error="Failed to process",
                        transaction_count=len(protocol_data.get('transactions', []))
                    )
                    categories.append(category_error)
            return categories
        except Exception:
            return [CategoryError(category="unknown", error="Failed to process", transaction_count=0)]
    
    async def _publish_success(self, success_message: WalletScoreSuccess):
        """Publish success message to Kafka."""
        try:
            future = self.producer.send(
                self.success_topic,
                value=success_message.dict()
            )
            
            # Wait for the message to be sent
            record_metadata = future.get(timeout=10)
            
            self.logger.debug("Success message published", 
                            topic=record_metadata.topic,
                            partition=record_metadata.partition,
                            offset=record_metadata.offset)
            
        except Exception as e:
            self.logger.error("Failed to publish success message", error=str(e))
            raise
    
    async def _publish_failure(self, wallet_address: str, error: str, 
                              processing_time_ms: int, categories: list = None):
        """Publish failure message to Kafka."""
        try:
            failure_message = WalletScoreFailure(
                wallet_address=wallet_address,
                error=error,
                timestamp=int(time.time()),
                processing_time_ms=processing_time_ms,
                categories=categories or []
            )
            
            future = self.producer.send(
                self.failure_topic,
                value=failure_message.dict()
            )
            
            # Wait for the message to be sent
            record_metadata = future.get(timeout=10)
            
            self.logger.debug("Failure message published", 
                            topic=record_metadata.topic,
                            partition=record_metadata.partition,
                            offset=record_metadata.offset)
            
        except Exception as e:
            self.logger.error("Failed to publish failure message", error=str(e))
            raise
    
    def _update_stats(self, success: bool, processing_time_ms: int, wallet_address: str):
        """Update processing statistics."""
        self.stats['total_wallets_processed'] += 1
        self.stats['total_processing_time_ms'] += processing_time_ms
        
        if success:
            self.stats['successful_wallets'] += 1
        else:
            self.stats['failed_wallets'] += 1
        
        self.stats['last_processed_wallet'] = wallet_address
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current processing statistics."""
        uptime_seconds = int(time.time() - self.stats['start_time'])
        
        stats = self.stats.copy()
        stats['uptime_seconds'] = uptime_seconds
        
        if stats['total_wallets_processed'] > 0:
            stats['average_processing_time_ms'] = (
                stats['total_processing_time_ms'] / stats['total_wallets_processed']
            )
        else:
            stats['average_processing_time_ms'] = 0.0
        
        return stats
    
    def get_health_status(self) -> str:
        """Get Kafka health status."""
        try:
            # Check if consumer and producer are working
            if self.consumer and self.producer:
                # Try to get metadata to verify connection
                self.producer.metrics()
                return "healthy"
            else:
                return "unhealthy"
        except Exception:
            return "unhealthy"
    
    async def shutdown(self):
        """Gracefully shutdown Kafka service."""
        self.logger.info("Shutting down Kafka service")
        
        try:
            if self.consumer:
                self.consumer.close()
                self.logger.info("Kafka consumer closed")
            
            if self.producer:
                self.producer.flush(timeout=10)
                self.producer.close()
                self.logger.info("Kafka producer closed")
                
        except Exception as e:
            self.logger.error("Error during shutdown", error=str(e)) 