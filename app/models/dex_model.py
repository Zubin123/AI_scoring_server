import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import structlog
from app.utils.types import Transaction, ProtocolData, CategoryFeatures, CategoryScore

logger = structlog.get_logger(__name__)


class DEXScoringModel:
    """
    AI-powered DEX reputation scoring model that processes transaction data
    and calculates wallet reputation scores based on liquidity provision and trading patterns.
    """
    
    def __init__(self):
        self.logger = logger
        # Scoring weights for different components
        self.lp_weight = 0.6  # Liquidity provision weight
        self.swap_weight = 0.4  # Trading weight
        
        # Score normalization parameters
        self.min_score = 0
        self.max_score = 1000
        
        # Feature thresholds for scoring
        self.volume_thresholds = {
            'low': 100,      # $100
            'medium': 1000,  # $1,000
            'high': 10000,   # $10,000
            'whale': 100000  # $100,000
        }
        
        self.frequency_thresholds = {
            'low': 1,        # 1 transaction
            'medium': 5,     # 5 transactions
            'high': 20,      # 20 transactions
            'very_high': 50  # 50+ transactions
        }
        
        self.holding_time_thresholds = {
            'short': 7,      # 7 days
            'medium': 30,    # 30 days
            'long': 90,      # 90 days
            'hodl': 365      # 1 year
        }
    
    def process_wallet_data(self, wallet_data: List[ProtocolData]) -> Tuple[List[CategoryScore], float]:
        """
        Process wallet transaction data and calculate category scores.
        
        Args:
            wallet_data: List of protocol data containing transactions
            
        Returns:
            Tuple of (category_scores, overall_score)
        """
        try:
            category_scores = []
            total_score = 0.0
            total_weight = 0.0
            
            for protocol_data in wallet_data:
                if protocol_data.protocolType.lower() == 'dexes':
                    category_score = self._calculate_dex_score(protocol_data.transactions)
                    category_scores.append(category_score)
                    
                    # Weight the category score (DEX gets full weight for now)
                    weighted_score = category_score.score * 1.0
                    total_score += weighted_score
                    total_weight += 1.0
                else:
                    # For other protocol types, create a basic score
                    category_score = self._calculate_basic_protocol_score(protocol_data)
                    category_scores.append(category_score)
                    
                    # Other protocols get reduced weight
                    weighted_score = category_score.score * 0.5
                    total_score += weighted_score
                    total_weight += 0.5
            
            # Calculate overall weighted score
            overall_score = total_score / total_weight if total_weight > 0 else 0.0
            
            return category_scores, overall_score
            
        except Exception as e:
            self.logger.error("Error processing wallet data", error=str(e), wallet_data=wallet_data)
            raise
    
    def _calculate_dex_score(self, transactions: List[Transaction]) -> CategoryScore:
        """
        Calculate DEX-specific reputation score based on transaction patterns.
        
        Args:
            transactions: List of DEX transactions
            
        Returns:
            CategoryScore with calculated score and features
        """
        try:
            # Convert transactions to DataFrame for easier processing
            df = self._transactions_to_dataframe(transactions)
            
            # Extract features
            features = self._extract_dex_features(df)
            
            # Calculate LP score (liquidity provision)
            lp_score = self._calculate_lp_score(features)
            
            # Calculate swap score (trading activity)
            swap_score = self._calculate_swap_score(features)
            
            # Combine scores with weights
            combined_score = (lp_score * self.lp_weight) + (swap_score * self.swap_weight)
            
            # Normalize score to 0-1000 range
            normalized_score = self._normalize_score(combined_score)
            
            # Create category score
            category_score = CategoryScore(
                category="dexes",
                score=round(normalized_score, 2),
                transaction_count=len(transactions),
                features=features
            )
            
            return category_score
            
        except Exception as e:
            self.logger.error("Error calculating DEX score", error=str(e), transactions=transactions)
            raise
    
    def _transactions_to_dataframe(self, transactions: List[Transaction]) -> pd.DataFrame:
        """Convert transactions to pandas DataFrame for analysis."""
        data = []
        
        for tx in transactions:
            row = {
                'document_id': tx.document_id,
                'action': tx.action,
                'timestamp': tx.timestamp,
                'caller': tx.caller,
                'protocol': tx.protocol,
                'poolId': tx.poolId,
                'poolName': tx.poolName,
                'token_in_amount': tx.tokenIn.amountUSD if tx.tokenIn else 0,
                'token_out_amount': tx.tokenOut.amountUSD if tx.tokenOut else 0,
                'token0_amount': tx.token0.amountUSD if tx.token0 else 0,
                'token1_amount': tx.token1.amountUSD if tx.token1 else 0,
                'datetime': datetime.fromtimestamp(tx.timestamp)
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        df = df.sort_values('timestamp')
        return df
    
    def _extract_dex_features(self, df: pd.DataFrame) -> CategoryFeatures:
        """Extract meaningful features from transaction data."""
        features = CategoryFeatures()
        
        try:
            # Basic transaction counts
            features.num_deposits = len(df[df['action'].isin(['deposit', 'add_liquidity'])])
            features.num_swaps = len(df[df['action'] == 'swap'])
            features.num_withdraws = len(df[df['action'].isin(['withdraw', 'remove_liquidity'])])
            
            # Volume calculations
            features.total_deposit_usd = df[df['action'].isin(['deposit', 'add_liquidity'])]['token0_amount'].sum() + \
                                       df[df['action'].isin(['deposit', 'add_liquidity'])]['token1_amount'].sum()
            
            features.total_swap_volume = df[df['action'] == 'swap']['token_in_amount'].sum()
            features.total_withdraw_usd = df[df['action'].isin(['withdraw', 'remove_liquidity'])]['token0_amount'].sum() + \
                                        df[df['action'].isin(['withdraw', 'remove_liquidity'])]['token1_amount'].sum()
            
            # Unique pools
            features.unique_pools = df['poolId'].nunique()
            
            # Average transaction size
            total_volume = features.total_deposit_usd + features.total_swap_volume + features.total_withdraw_usd
            total_transactions = len(df)
            features.avg_transaction_size_usd = total_volume / total_transactions if total_transactions > 0 else 0
            
            # Holding time calculation (simplified - assumes deposits are held until now)
            if features.num_deposits > 0:
                deposit_times = df[df['action'].isin(['deposit', 'add_liquidity'])]['datetime']
                if len(deposit_times) > 0:
                    # Calculate average time since deposit
                    now = datetime.now()
                    hold_times = [(now - dt).days for dt in deposit_times]
                    features.avg_hold_time_days = np.mean(hold_times)
            
            # Transaction frequency
            if len(df) > 1:
                time_span = (df['datetime'].max() - df['datetime'].min()).days
                features.transaction_frequency_days = time_span / len(df) if time_span > 0 else 0
            
        except Exception as e:
            self.logger.warning("Error extracting some features", error=str(e))
            # Continue with default values
        
        return features
    
    def _calculate_lp_score(self, features: CategoryFeatures) -> float:
        """Calculate liquidity provider score based on LP behavior."""
        score = 0.0
        
        try:
            # Volume-based scoring
            if features.total_deposit_usd >= self.volume_thresholds['whale']:
                score += 300
            elif features.total_deposit_usd >= self.volume_thresholds['high']:
                score += 200
            elif features.total_deposit_usd >= self.volume_thresholds['medium']:
                score += 150
            elif features.total_deposit_usd >= self.volume_thresholds['low']:
                score += 100
            
            # Frequency-based scoring
            if features.num_deposits >= self.frequency_thresholds['very_high']:
                score += 200
            elif features.num_deposits >= self.frequency_thresholds['high']:
                score += 150
            elif features.num_deposits >= self.frequency_thresholds['medium']:
                score += 100
            elif features.num_deposits >= self.frequency_thresholds['low']:
                score += 50
            
            # Holding time scoring
            if features.avg_hold_time_days >= self.holding_time_thresholds['hodl']:
                score += 200
            elif features.avg_hold_time_days >= self.holding_time_thresholds['long']:
                score += 150
            elif features.avg_hold_time_days >= self.holding_time_thresholds['medium']:
                score += 100
            elif features.avg_hold_time_days >= self.holding_time_thresholds['short']:
                score += 50
            
            # Pool diversity bonus
            if features.unique_pools >= 5:
                score += 100
            elif features.unique_pools >= 3:
                score += 50
            elif features.unique_pools >= 1:
                score += 25
            
            # Liquidity retention bonus (deposits > withdrawals)
            if features.total_deposit_usd > features.total_withdraw_usd:
                retention_ratio = (features.total_deposit_usd - features.total_withdraw_usd) / features.total_deposit_usd
                score += retention_ratio * 100
            
        except Exception as e:
            self.logger.warning("Error calculating LP score", error=str(e))
        
        return min(score, 1000)  # Cap at 1000
    
    def _calculate_swap_score(self, features: CategoryFeatures) -> float:
        """Calculate trading score based on swap activity."""
        score = 0.0
        
        try:
            # Volume-based scoring
            if features.total_swap_volume >= self.volume_thresholds['whale']:
                score += 300
            elif features.total_swap_volume >= self.volume_thresholds['high']:
                score += 200
            elif features.total_swap_volume >= self.volume_thresholds['medium']:
                score += 150
            elif features.total_swap_volume >= self.volume_thresholds['low']:
                score += 100
            
            # Frequency-based scoring
            if features.num_swaps >= self.frequency_thresholds['very_high']:
                score += 200
            elif features.num_swaps >= self.frequency_thresholds['high']:
                score += 150
            elif features.num_swaps >= self.frequency_thresholds['medium']:
                score += 100
            elif features.num_swaps >= self.frequency_thresholds['low']:
                score += 50
            
            # Transaction size consistency
            if features.avg_transaction_size_usd > 0:
                if features.avg_transaction_size_usd >= 1000:
                    score += 100
                elif features.avg_transaction_size_usd >= 100:
                    score += 75
                elif features.avg_transaction_size_usd >= 10:
                    score += 50
            
            # Pool diversity bonus
            if features.unique_pools >= 5:
                score += 100
            elif features.unique_pools >= 3:
                score += 50
            elif features.unique_pools >= 1:
                score += 25
            
        except Exception as e:
            self.logger.warning("Error calculating swap score", error=str(e))
        
        return min(score, 1000)  # Cap at 1000
    
    def _calculate_basic_protocol_score(self, protocol_data: ProtocolData) -> CategoryScore:
        """Calculate basic score for non-DEX protocols."""
        features = CategoryFeatures()
        features.transaction_count = len(protocol_data.transactions)
        features.unique_pools = len(set(tx.poolId for tx in protocol_data.transactions))
        
        # Basic scoring for other protocols
        base_score = min(features.transaction_count * 10 + features.unique_pools * 5, 500)
        
        return CategoryScore(
            category=protocol_data.protocolType,
            score=round(base_score, 2),
            transaction_count=len(protocol_data.transactions),
            features=features
        )
    
    def _normalize_score(self, score: float) -> float:
        """Normalize score to 0-1000 range."""
        # Apply sigmoid-like normalization for better distribution
        normalized = 1000 / (1 + np.exp(-(score - 500) / 200))
        return max(0, min(1000, normalized))
    
    def get_user_tags(self, features: CategoryFeatures, overall_score: float) -> List[str]:
        """Generate user behavior tags based on features and score."""
        tags = []
        
        try:
            # Volume-based tags
            if features.total_deposit_usd >= self.volume_thresholds['whale']:
                tags.append("Whale LP")
            elif features.total_deposit_usd >= self.volume_thresholds['high']:
                tags.append("Large LP")
            
            if features.total_swap_volume >= self.volume_thresholds['whale']:
                tags.append("Whale Trader")
            elif features.total_swap_volume >= self.volume_thresholds['high']:
                tags.append("Active Trader")
            
            # Behavior-based tags
            if features.avg_hold_time_days >= self.holding_time_thresholds['hodl']:
                tags.append("HODLer")
            elif features.avg_hold_time_days >= self.holding_time_thresholds['long']:
                tags.append("Long-term LP")
            
            if features.num_deposits >= self.frequency_thresholds['very_high']:
                tags.append("Frequent LP")
            if features.num_swaps >= self.frequency_thresholds['very_high']:
                tags.append("Frequent Trader")
            
            # Score-based tags
            if overall_score >= 800:
                tags.append("Elite User")
            elif overall_score >= 600:
                tags.append("Premium User")
            elif overall_score >= 400:
                tags.append("Regular User")
            else:
                tags.append("New User")
                
        except Exception as e:
            self.logger.warning("Error generating user tags", error=str(e))
        
        return tags 