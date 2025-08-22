import asyncio
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import structlog
import uvicorn

from app.utils.config import config
from app.services.kafka_service import KafkaService
from app.services.mongodb_service import MongoDBService
from app.utils.types import HealthResponse, StatsResponse

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global service instances
kafka_service: KafkaService = None
mongodb_service: MongoDBService = None
consumer_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    global kafka_service, mongodb_service, consumer_task
    
    # Startup
    logger.info("Starting AI Scoring Server", version=config.VERSION, environment=config.ENVIRONMENT)
    
    try:
        # Initialize MongoDB service
        mongodb_service = MongoDBService(config.get_mongodb_config())
        logger.info("MongoDB service initialized")
        
        # Create database indexes
        await mongodb_service.create_indexes()
        logger.info("Database indexes created")
        
        # Initialize Kafka service
        kafka_service = KafkaService(config.get_kafka_config())
        logger.info("Kafka service initialized")
        
        # Start Kafka consumer in background
        consumer_task = asyncio.create_task(kafka_service.start_consuming())
        logger.info("Kafka consumer started")
        
        logger.info("AI Scoring Server started successfully")
        
    except Exception as e:
        logger.error("Failed to start services", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Scoring Server")
    
    try:
        # Stop Kafka consumer
        if consumer_task and not consumer_task.done():
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
            logger.info("Kafka consumer stopped")
        
        # Shutdown Kafka service
        if kafka_service:
            await kafka_service.shutdown()
            logger.info("Kafka service shutdown")
        
        # Close MongoDB service
        if mongodb_service:
            await mongodb_service.close()
            logger.info("MongoDB service closed")
        
        logger.info("AI Scoring Server shutdown complete")
        
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=config.APP_NAME,
    description=config.DESCRIPTION,
    version=config.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if config.is_development() else None,
    redoc_url="/redoc" if config.is_development() else None
)


@app.get("/", response_model=Dict[str, Any])
async def root():
    """Root endpoint with service information."""
    return {
        "service": config.APP_NAME,
        "version": config.VERSION,
        "environment": config.ENVIRONMENT,
        "description": config.DESCRIPTION,
        "endpoints": {
            "health": "/api/v1/health",
            "stats": "/api/v1/stats",
            "docs": "/docs" if config.is_development() else "disabled"
        }
    }


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check Kafka health
        kafka_status = kafka_service.get_health_status() if kafka_service else "unhealthy"
        
        # Check MongoDB health
        mongodb_status = mongodb_service.get_health_status() if mongodb_service else "unhealthy"
        
        # Overall status
        overall_status = "healthy" if kafka_status == "healthy" and mongodb_status == "healthy" else "unhealthy"
        
        return HealthResponse(
            status=overall_status,
            timestamp=int(time.time()),
            version=config.VERSION,
            environment=config.ENVIRONMENT,
            kafka_status=kafka_status,
            mongodb_status=mongodb_status
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_stats():
    """Get processing statistics."""
    try:
        if not kafka_service:
            raise HTTPException(status_code=503, detail="Kafka service not available")
        
        stats = kafka_service.get_stats()
        
        return StatsResponse(
            total_wallets_processed=stats['total_wallets_processed'],
            successful_wallets=stats['successful_wallets'],
            failed_wallets=stats['failed_wallets'],
            average_processing_time_ms=stats['average_processing_time_ms'],
            last_processed_wallet=stats['last_processed_wallet'],
            uptime_seconds=stats['uptime_seconds']
        )
        
    except Exception as e:
        logger.error("Failed to get statistics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@app.post("/api/v1/process-wallet")
async def process_wallet_sync(wallet_data: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Synchronous endpoint to process a single wallet (for testing).
    This endpoint processes the wallet immediately and returns the result.
    """
    try:
        if not kafka_service:
            raise HTTPException(status_code=503, detail="Kafka service not available")
        
        # Process wallet using the scoring model directly
        from app.utils.types import WalletTransactionInput
        from app.models.dex_model import DEXScoringModel
        
        # Validate input
        wallet_input = WalletTransactionInput(**wallet_data)
        
        # Process with AI model
        scoring_model = DEXScoringModel()
        category_scores, overall_score = scoring_model.process_wallet_data(wallet_input.data)
        
        # Create success response
        result = {
            "wallet_address": wallet_input.wallet_address,
            "zscore": f"{overall_score:.18f}",
            "timestamp": int(time.time()),
            "categories": [
                {
                    "category": cat.category,
                    "score": cat.score,
                    "transaction_count": cat.transaction_count,
                    "features": {
                        "total_deposit_usd": cat.features.total_deposit_usd,
                        "total_swap_volume": cat.features.total_swap_volume,
                        "num_deposits": cat.features.num_deposits,
                        "num_swaps": cat.features.num_swaps,
                        "avg_hold_time_days": cat.features.avg_hold_time_days,
                        "unique_pools": cat.features.unique_pools
                    }
                }
                for cat in category_scores
            ]
        }
        
        return JSONResponse(content=result, status_code=200)
        
    except Exception as e:
        logger.error("Failed to process wallet", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process wallet: {str(e)}")


@app.get("/api/v1/config")
async def get_config():
    """Get current configuration (development only)."""
    if config.is_production():
        raise HTTPException(status_code=403, detail="Configuration endpoint disabled in production")
    
    return {
        "server": config.get_server_config(),
        "kafka": config.get_kafka_config(),
        "mongodb": config.get_mongodb_config(),
        "performance": {
            "max_workers": config.MAX_WORKERS,
            "batch_size": config.BATCH_SIZE,
            "processing_timeout_ms": config.PROCESSING_TIMEOUT_MS
        }
    }


# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=config.is_development(),
        workers=1  # Single worker for Kafka consumer
    ) 