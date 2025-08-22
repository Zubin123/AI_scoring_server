#!/bin/bash

# AI Scoring Server Startup Script
# This script starts the entire stack using Docker Compose

set -e

echo "🚀 Starting AI Scoring Server Stack..."
echo "======================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose and try again."
    exit 1
fi

# Clean up any existing containers
echo "🧹 Cleaning up existing containers..."
docker-compose down --remove-orphans > /dev/null 2>&1 || true

# Start the stack
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 45

# Wait for Kafka to be fully ready
echo "📋 Waiting for Kafka to be ready..."
until docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list > /dev/null 2>&1; do
    echo "   Waiting for Kafka... (retrying in 10 seconds)"
    sleep 10
done

echo "✅ Kafka is ready!"

# Create Kafka topics
echo "🔧 Creating Kafka topics..."
docker exec kafka kafka-topics --create --topic wallet-transactions --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 --if-not-exists
docker exec kafka kafka-topics --create --topic wallet-scores-success --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 --if-not-exists
docker exec kafka kafka-topics --create --topic wallet-scores-failure --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 --if-not-exists

echo "✅ Kafka topics created successfully"

# Wait a bit more for services to be fully ready
echo "⏳ Waiting for services to be fully ready..."
sleep 20

# Check service health
echo "🔍 Checking service health..."

# Check AI Scoring Server
echo "⏳ Checking AI Scoring Server..."
until curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; do
    echo "   Waiting for AI Scoring Server... (retrying in 10 seconds)"
    sleep 10
done
echo "✅ AI Scoring Server is healthy"

# Check Kafka
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Kafka is healthy"
else
    echo "❌ Kafka health check failed"
fi

# Check MongoDB
docker exec mongodb mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ MongoDB is healthy"
else
    echo "❌ MongoDB health check failed"
fi

echo ""
echo "🎉 AI Scoring Server Stack is running!"
echo "======================================"
echo "📊 AI Scoring Server: http://localhost:8000"
echo "📈 API Documentation: http://localhost:8000/docs"
echo "🔍 Health Check: http://localhost:8000/api/v1/health"
echo "📊 Statistics: http://localhost:8000/api/v1/stats"
echo ""
echo "📋 Kafka Topics:"
echo "   - Input: wallet-transactions"
echo "   - Success: wallet-scores-success"
echo "   - Failure: wallet-scores-failure"
echo ""
echo "🛠️  Development Tools (if enabled):"
echo "   - Kafka UI: http://localhost:8080"
echo "   - MongoDB Express: http://localhost:8081"
echo ""
echo "🧪 To run tests:"
echo "   python test_challenge.py"
echo ""
echo "🛑 To stop the stack:"
echo "   docker-compose down"
echo ""
echo "📝 Logs:"
echo "   docker-compose logs -f ai-scoring-server"
echo ""
echo "Press any key to continue..."
read -n 1 