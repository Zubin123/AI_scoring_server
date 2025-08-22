import os
from typing import Dict, Any
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger(__name__)


class Config:
    """
    Configuration management class that loads environment variables
    and provides application settings.
    """
    
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Server configuration
        self.HOST = os.getenv('HOST', '0.0.0.0')
        self.PORT = int(os.getenv('PORT', '8000'))
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
        
        # Kafka configuration
        self.KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.KAFKA_INPUT_TOPIC = os.getenv('KAFKA_INPUT_TOPIC', 'wallet-transactions')
        self.KAFKA_SUCCESS_TOPIC = os.getenv('KAFKA_SUCCESS_TOPIC', 'wallet-scores-success')
        self.KAFKA_FAILURE_TOPIC = os.getenv('KAFKA_FAILURE_TOPIC', 'wallet-scores-failure')
        self.KAFKA_CONSUMER_GROUP = os.getenv('KAFKA_CONSUMER_GROUP', 'ai-scoring-service')
        
        # MongoDB configuration
        self.MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
        self.MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'ai_scoring')
        self.MONGODB_TOKENS_COLLECTION = os.getenv('MONGODB_TOKENS_COLLECTION', 'tokens')
        self.MONGODB_THRESHOLDS_COLLECTION = os.getenv('MONGODB_THRESHOLDS_COLLECTION', 'protocol-thresholds-percentiles')
        
        # Application metadata
        self.VERSION = "1.0.0"
        self.APP_NAME = "AI Scoring Server"
        self.DESCRIPTION = "Production-ready AI server for DeFi reputation scoring"
        
        # Performance configuration
        self.MAX_WORKERS = int(os.getenv('MAX_WORKERS', '4'))
        self.BATCH_SIZE = int(os.getenv('BATCH_SIZE', '10'))
        self.PROCESSING_TIMEOUT_MS = int(os.getenv('PROCESSING_TIMEOUT_MS', '5000'))
        
        # Logging configuration
        self.LOG_FORMAT = os.getenv('LOG_FORMAT', 'json')
        self.LOG_FILE = os.getenv('LOG_FILE', None)
        
        # Validation
        self._validate_config()
        
        logger.info("Configuration loaded successfully", 
                   environment=self.ENVIRONMENT,
                   kafka_servers=self.KAFKA_BOOTSTRAP_SERVERS,
                   mongodb_url=self.MONGODB_URL)
    
    def _validate_config(self):
        """Validate critical configuration values."""
        required_vars = [
            'KAFKA_BOOTSTRAP_SERVERS',
            'KAFKA_INPUT_TOPIC',
            'KAFKA_SUCCESS_TOPIC',
            'KAFKA_FAILURE_TOPIC',
            'MONGODB_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(self, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    def get_kafka_config(self) -> Dict[str, str]:
        """Get Kafka configuration as dictionary."""
        return {
            'KAFKA_BOOTSTRAP_SERVERS': self.KAFKA_BOOTSTRAP_SERVERS,
            'KAFKA_INPUT_TOPIC': self.KAFKA_INPUT_TOPIC,
            'KAFKA_SUCCESS_TOPIC': self.KAFKA_SUCCESS_TOPIC,
            'KAFKA_FAILURE_TOPIC': self.KAFKA_FAILURE_TOPIC,
            'KAFKA_CONSUMER_GROUP': self.KAFKA_CONSUMER_GROUP
        }
    
    def get_mongodb_config(self) -> Dict[str, str]:
        """Get MongoDB configuration as dictionary."""
        return {
            'MONGODB_URL': self.MONGODB_URL,
            'MONGODB_DATABASE': self.MONGODB_DATABASE,
            'MONGODB_TOKENS_COLLECTION': self.MONGODB_TOKENS_COLLECTION,
            'MONGODB_THRESHOLDS_COLLECTION': self.MONGODB_THRESHOLDS_COLLECTION
        }
    
    def get_server_config(self) -> Dict[str, Any]:
        """Get server configuration as dictionary."""
        return {
            'HOST': self.HOST,
            'PORT': self.PORT,
            'LOG_LEVEL': self.LOG_LEVEL,
            'ENVIRONMENT': self.ENVIRONMENT,
            'VERSION': self.VERSION,
            'APP_NAME': self.APP_NAME
        }
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == 'development'
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration as dictionary."""
        return {
            **self.get_kafka_config(),
            **self.get_mongodb_config(),
            **self.get_server_config(),
            'MAX_WORKERS': self.MAX_WORKERS,
            'BATCH_SIZE': self.BATCH_SIZE,
            'PROCESSING_TIMEOUT_MS': self.PROCESSING_TIMEOUT_MS
        }
    
    def __str__(self) -> str:
        """String representation of configuration."""
        return f"{self.APP_NAME} v{self.VERSION} - {self.ENVIRONMENT} environment"
    
    def __repr__(self) -> str:
        """Detailed string representation of configuration."""
        return f"Config(environment='{self.ENVIRONMENT}', version='{self.VERSION}', host='{self.HOST}:{self.PORT}')"


# Global configuration instance
config = Config() 