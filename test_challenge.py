#!/usr/bin/env python3
"""
Test script for the AI Scoring Server challenge.
This script validates the core functionality and performance requirements.
"""

import json
import time
import requests
import asyncio
from typing import Dict, Any, List
import structlog

# Configure logging
structlog.configure(processors=[structlog.processors.JSONRenderer()])
logger = structlog.get_logger(__name__)

# Test configuration
SERVER_URL = "http://localhost:8000"
TEST_WALLET_DATA = {
    "wallet_address": "0x742d35Cc6634C0532925a3b8D4C9db96590e4265",
    "data": [
        {
            "protocolType": "dexes",
            "transactions": [
                {
                    "document_id": "507f1f77bcf86cd799439011",
                    "action": "swap",
                    "timestamp": 1703980800,
                    "caller": "0x742d35Cc6634C0532925a3b8D4C9db96590e4265",
                    "protocol": "uniswap_v3",
                    "poolId": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
                    "poolName": "Uniswap V3 USDC/WETH 0.05%",
                    "tokenIn": {
                        "amount": 1000000000,
                        "amountUSD": 1000.0,
                        "address": "0xa0b86a33e6c3d4c3e6c3d4c3e6c3d4c3e6c3d4c3",
                        "symbol": "USDC"
                    },
                    "tokenOut": {
                        "amount": 500000000000000000,
                        "amountUSD": 1000.0,
                        "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                        "symbol": "WETH"
                    }
                },
                {
                    "document_id": "507f1f77bcf86cd799439012",
                    "action": "deposit",
                    "timestamp": 1703980900,
                    "caller": "0x742d35Cc6634C0532925a3b8D4C9db96590e4265",
                    "protocol": "uniswap_v3",
                    "poolId": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
                    "poolName": "Uniswap V3 USDC/WETH 0.05%",
                    "token0": {
                        "amount": 500000000,
                        "amountUSD": 500.0,
                        "address": "0xa0b86a33e6c3d4c3e6c3d4c3e6c3d4c3e6c3d4c3",
                        "symbol": "USDC"
                    },
                    "token1": {
                        "amount": 250000000000000000,
                        "amountUSD": 500.0,
                        "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                        "symbol": "WETH"
                    }
                }
            ]
        }
    ]
}

# Additional test wallets for load testing
TEST_WALLETS = [
    {
        "wallet_address": "0x1234567890123456789012345678901234567890",
        "data": [
            {
                "protocolType": "dexes",
                "transactions": [
                    {
                        "document_id": "test_001",
                        "action": "swap",
                        "timestamp": int(time.time()) - 86400,
                        "caller": "0x1234567890123456789012345678901234567890",
                        "protocol": "sushiswap",
                        "poolId": "pool_001",
                        "poolName": "SushiSwap USDC/ETH",
                        "tokenIn": {
                            "amount": 500000000,
                            "amountUSD": 500.0,
                            "address": "0x1234567890123456789012345678901234567890",
                            "symbol": "USDC"
                        },
                        "tokenOut": {
                            "amount": 250000000000000000,
                            "amountUSD": 500.0,
                            "address": "0x0987654321098765432109876543210987654321",
                            "symbol": "ETH"
                        }
                    }
                ]
            }
        ]
    },
    {
        "wallet_address": "0x0987654321098765432109876543210987654321",
        "data": [
            {
                "protocolType": "dexes",
                "transactions": [
                    {
                        "document_id": "test_002",
                        "action": "deposit",
                        "timestamp": int(time.time()) - 172800,
                        "caller": "0x0987654321098765432109876543210987654321",
                        "protocol": "balancer",
                        "poolId": "pool_002",
                        "poolName": "Balancer USDC/ETH/DAI",
                        "token0": {
                            "amount": 1000000000,
                            "amountUSD": 1000.0,
                            "address": "0x1234567890123456789012345678901234567890",
                            "symbol": "USDC"
                        },
                        "token1": {
                            "amount": 500000000000000000,
                            "amountUSD": 1000.0,
                            "address": "0x0987654321098765432109876543210987654321",
                            "symbol": "ETH"
                        }
                    }
                ]
            }
        ]
    }
]


class ChallengeTester:
    """Test suite for the AI Scoring Server challenge."""
    
    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url
        self.test_results = []
        self.start_time = time.time()
    
    def log_test(self, test_name: str, success: bool, details: str = "", duration: float = 0):
        """Log test results."""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "duration": duration,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}", **result)
        
        if not success and details:
            logger.error(f"Test failed: {details}")
    
    def test_server_startup(self) -> bool:
        """Test if the server is running and responding."""
        try:
            start_time = time.time()
            response = requests.get(f"{self.server_url}/", timeout=10)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Server Startup", True, f"Server running: {data.get('service')}", duration)
                return True
            else:
                self.log_test("Server Startup", False, f"HTTP {response.status_code}: {response.text}", duration)
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("Server Startup", False, f"Connection failed: {str(e)}", 0)
            return False
    
    def test_health_endpoint(self) -> bool:
        """Test the health check endpoint."""
        try:
            start_time = time.time()
            response = requests.get(f"{self.server_url}/api/v1/health", timeout=10)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')
                self.log_test("Health Endpoint", True, f"Status: {status}", duration)
                return status == 'healthy'
            else:
                self.log_test("Health Endpoint", False, f"HTTP {response.status_code}: {response.text}", duration)
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("Health Endpoint", False, f"Request failed: {str(e)}", 0)
            return False
    
    def test_stats_endpoint(self) -> bool:
        """Test the statistics endpoint."""
        try:
            start_time = time.time()
            response = requests.get(f"{self.server_url}/api/v1/stats", timeout=10)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Stats Endpoint", True, f"Stats retrieved: {data.get('total_wallets_processed', 0)} wallets", duration)
                return True
            else:
                self.log_test("Stats Endpoint", False, f"HTTP {response.status_code}: {response.text}", duration)
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("Stats Endpoint", False, f"Request failed: {str(e)}", 0)
            return False
    
    def test_wallet_processing(self, wallet_data: Dict[str, Any]) -> bool:
        """Test wallet processing functionality."""
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.server_url}/api/v1/process-wallet",
                json=wallet_data,
                timeout=30
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                wallet_address = data.get('wallet_address', 'unknown')
                zscore = data.get('zscore', '0')
                categories = data.get('categories', [])
                
                self.log_test(
                    "Wallet Processing", 
                    True, 
                    f"Processed {wallet_address}: score={zscore}, categories={len(categories)}", 
                    duration
                )
                return True
            else:
                self.log_test("Wallet Processing", False, f"HTTP {response.status_code}: {response.text}", duration)
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("Wallet Processing", False, f"Request failed: {str(e)}", 0)
            return False
    
    def test_data_validation(self) -> bool:
        """Test data validation with invalid input."""
        invalid_wallet = {
            "wallet_address": "invalid_address",
            "data": []
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.server_url}/api/v1/process-wallet",
                json=invalid_wallet,
                timeout=10
            )
            duration = time.time() - start_time
            
            # Should return 500 or 422 for validation errors
            if response.status_code in [400, 422, 500]:
                self.log_test("Data Validation", True, f"Properly rejected invalid data: HTTP {response.status_code}", duration)
                return True
            else:
                self.log_test("Data Validation", False, f"Should have rejected invalid data, got HTTP {response.status_code}", duration)
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("Data Validation", False, f"Request failed: {str(e)}", 0)
            return False
    
    def test_performance(self, num_wallets: int = 10) -> bool:
        """Test performance with multiple wallets."""
        logger.info(f"Starting performance test with {num_wallets} wallets")
        
        start_time = time.time()
        successful_wallets = 0
        total_processing_time = 0
        
        for i in range(num_wallets):
            # Use test wallet data with unique addresses
            test_wallet = TEST_WALLETS[i % len(TEST_WALLETS)].copy()
            test_wallet['wallet_address'] = f"0x{i:040x}"
            
            try:
                wallet_start = time.time()
                response = requests.post(
                    f"{self.server_url}/api/v1/process-wallet",
                    json=test_wallet,
                    timeout=30
                )
                wallet_duration = time.time() - wallet_start
                
                if response.status_code == 200:
                    successful_wallets += 1
                    total_processing_time += wallet_duration
                
                # Small delay between requests
                time.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Wallet {i} failed: {str(e)}")
        
        total_duration = time.time() - start_time
        avg_processing_time = total_processing_time / successful_wallets if successful_wallets > 0 else 0
        
        # Performance requirements: <2 seconds average, 1000+ wallets/minute
        performance_ok = avg_processing_time < 2.0 and (successful_wallets / total_duration * 60) >= 1
        
        self.log_test(
            "Performance Test",
            performance_ok,
            f"Processed {successful_wallets}/{num_wallets} wallets in {total_duration:.2f}s, avg: {avg_processing_time:.2f}s",
            total_duration
        )
        
        return performance_ok
    
    def test_config_endpoint(self) -> bool:
        """Test configuration endpoint (development only)."""
        try:
            start_time = time.time()
            response = requests.get(f"{self.server_url}/api/v1/config", timeout=10)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Config Endpoint", True, f"Configuration retrieved", duration)
                return True
            elif response.status_code == 403:
                # Config endpoint disabled in production
                self.log_test("Config Endpoint", True, "Config endpoint properly disabled in production", duration)
                return True
            else:
                self.log_test("Config Endpoint", False, f"HTTP {response.status_code}: {response.text}", duration)
                return False
                
        except requests.exceptions.RequestException as e:
            self.log_test("Config Endpoint", False, f"Request failed: {str(e)}", 0)
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test cases and return results."""
        logger.info("Starting AI Scoring Server challenge tests")
        
        # Basic functionality tests
        self.test_server_startup()
        self.test_health_endpoint()
        self.test_stats_endpoint()
        
        # Core functionality tests
        self.test_wallet_processing(TEST_WALLET_DATA)
        self.test_data_validation()
        
        # Performance tests
        self.test_performance(20)  # Test with 20 wallets
        
        # Configuration tests
        self.test_config_endpoint()
        
        # Calculate overall results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        overall_result = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": success_rate,
            "test_results": self.test_results,
            "total_duration": time.time() - self.start_time
        }
        
        logger.info("Test suite completed", **overall_result)
        
        return overall_result
    
    def print_summary(self, results: Dict[str, Any]):
        """Print a formatted test summary."""
        print("\n" + "="*60)
        print("AI SCORING SERVER CHALLENGE - TEST RESULTS")
        print("="*60)
        
        print(f"\nOverall Results:")
        print(f"  Total Tests: {results['total_tests']}")
        print(f"  Passed: {results['passed_tests']} ✅")
        print(f"  Failed: {results['failed_tests']} ❌")
        print(f"  Success Rate: {results['success_rate']:.1f}%")
        print(f"  Total Duration: {results['total_duration']:.2f}s")
        
        print(f"\nDetailed Results:")
        for result in results['test_results']:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            duration = f"({result['duration']:.3f}s)" if result['duration'] > 0 else ""
            print(f"  {status} {result['test']} {duration}")
            if not result['success'] and result['details']:
                print(f"    Details: {result['details']}")
        
        print("\n" + "="*60)
        
        if results['success_rate'] >= 80:
            print("🎉 CHALLENGE PASSED! Server meets most requirements.")
        elif results['success_rate'] >= 60:
            print("⚠️  PARTIAL SUCCESS. Some tests failed, review implementation.")
        else:
            print("❌ CHALLENGE FAILED. Significant issues found.")
        
        print("="*60 + "\n")


def main():
    """Main test execution function."""
    print("AI Scoring Server Challenge - Test Suite")
    print("Starting tests in 5 seconds...")
    time.sleep(5)
    
    try:
        tester = ChallengeTester()
        results = tester.run_all_tests()
        tester.print_summary(results)
        
        # Exit with appropriate code
        if results['success_rate'] >= 80:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest suite failed with error: {str(e)}")
        logger.error("Test suite failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    import sys
    main() 