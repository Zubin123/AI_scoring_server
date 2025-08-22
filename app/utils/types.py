from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, validator
from decimal import Decimal
import time


class TokenInfo(BaseModel):
    amount: int
    amountUSD: float
    address: str
    symbol: str


class Transaction(BaseModel):
    document_id: str
    action: str
    timestamp: int
    caller: str
    protocol: str
    poolId: str
    poolName: str
    tokenIn: Optional[TokenInfo] = None
    tokenOut: Optional[TokenInfo] = None
    token0: Optional[TokenInfo] = None
    token1: Optional[TokenInfo] = None

    @validator('action')
    def validate_action(cls, v):
        valid_actions = ['swap', 'deposit', 'withdraw', 'add_liquidity', 'remove_liquidity']
        if v not in valid_actions:
            raise ValueError(f'Invalid action: {v}. Must be one of {valid_actions}')
        return v


class ProtocolData(BaseModel):
    protocolType: str
    transactions: List[Transaction]


class WalletTransactionInput(BaseModel):
    wallet_address: str
    data: List[ProtocolData]

    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid wallet address format')
        return v


class CategoryFeatures(BaseModel):
    total_deposit_usd: float = 0.0
    total_swap_volume: float = 0.0
    num_deposits: int = 0
    num_swaps: int = 0
    avg_hold_time_days: float = 0.0
    unique_pools: int = 0
    total_withdraw_usd: float = 0.0
    num_withdraws: int = 0
    avg_transaction_size_usd: float = 0.0
    transaction_frequency_days: float = 0.0


class CategoryScore(BaseModel):
    category: str
    score: float
    transaction_count: int
    features: CategoryFeatures


class WalletScoreSuccess(BaseModel):
    wallet_address: str
    zscore: str
    timestamp: int
    processing_time_ms: int
    categories: List[CategoryScore]

    @validator('zscore')
    def validate_zscore(cls, v):
        try:
            Decimal(v)
        except:
            raise ValueError('zscore must be a valid decimal string')
        return v


class CategoryError(BaseModel):
    category: str
    error: str
    transaction_count: int


class WalletScoreFailure(BaseModel):
    wallet_address: str
    error: str
    timestamp: int
    processing_time_ms: int
    categories: List[CategoryError]


class HealthResponse(BaseModel):
    status: str
    timestamp: int
    version: str
    environment: str
    kafka_status: str
    mongodb_status: str


class StatsResponse(BaseModel):
    total_wallets_processed: int
    successful_wallets: int
    failed_wallets: int
    average_processing_time_ms: float
    last_processed_wallet: Optional[str] = None
    uptime_seconds: int 