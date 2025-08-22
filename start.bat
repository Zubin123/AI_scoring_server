@echo off
REM AI Scoring Server Startup Script for Windows
REM This script starts the entire stack using Docker Compose

echo 🚀 Starting AI Scoring Server Stack...
echo ======================================

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose is not installed. Please install Docker Compose and try again.
    pause
    exit /b 1
)

REM Clean up any existing containers
echo 🧹 Cleaning up existing containers...
docker-compose down --remove-orphans >nul 2>&1

REM Start the stack
echo 🚀 Starting services...
docker-compose up -d

REM Wait for services to be ready
echo ⏳ Waiting for services to be ready...
timeout /t 45 /nobreak >nul

REM Wait for Kafka to be fully ready
echo 📋 Waiting for Kafka to be ready...
:wait_kafka
docker exec -T kafka kafka-topics --bootstrap-server localhost:9092 --list >nul 2>&1
echo ✅ Kafka is ready!

REM Create Kafka topics
echo 📋 Setting up Kafka topics...
docker exec kafka kafka-topics --create --topic wallet-transactions --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 --if-not-exists
docker exec kafka kafka-topics --create --topic wallet-scores-success --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 --if-not-exists
docker exec kafka kafka-topics --create --topic wallet-scores-failure --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 --if-not-exists

echo ✅ Kafka topics created successfully

REM Wait a bit more for services to be fully ready
echo ⏳ Waiting for services to be fully ready...
timeout /t 20 /nobreak >nul

REM Check service health
echo 🔍 Checking service health...

REM Check AI Scoring Server
echo ⏳ Checking AI Scoring Server...
:wait_server
curl -f http://localhost:8000/api/v1/health >nul 2>&1

echo ✅ AI Scoring Server is healthy

REM Check Kafka
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Kafka is healthy
) else (
    echo ❌ Kafka health check failed
)

REM Check MongoDB
docker exec mongodb mongosh --eval "db.adminCommand('ping')" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ MongoDB is healthy
) else (
    echo ❌ MongoDB health check failed
)

echo.
echo 🎉 AI Scoring Server Stack is running!
echo ======================================
echo 📊 AI Scoring Server: http://localhost:8000
echo 📈 API Documentation: http://localhost:8000/docs
echo 🔍 Health Check: http://localhost:8000/api/v1/health
echo 📊 Statistics: http://localhost:8000/api/v1/stats
echo.
echo 📋 Kafka Topics:
echo    - Input: wallet-transactions
echo    - Success: wallet-scores-success
echo    - Failure: wallet-scores-failure
echo.
echo 🛠️  Development Tools (if enabled):
echo    - Kafka UI: http://localhost:8080
echo    - MongoDB Express: http://localhost:8081
echo.
echo 🧪 To run tests:
echo    python test_challenge.py
echo.
echo 🛑 To stop the stack:
echo    docker-compose down
echo.
echo 📝 Logs:
echo    docker-compose logs -f ai-scoring-server
echo.
pause 