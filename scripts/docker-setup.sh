#!/bin/bash

# Project Chimera Docker Setup Script
# This script helps set up the project for Docker deployment

set -e

echo "🚀 Project Chimera Docker Setup"
echo "================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "✅ Created .env file. Please edit it with your configuration."
    echo "   Required: Set your GOOGLE_API_KEY"
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data/uploads
mkdir -p data/sample_docs
echo "✅ Directories created"

# Build the Docker image
echo "🔨 Building Docker image..."
docker-compose build

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys and configuration"
echo "2. Start the application: docker-compose up"
echo "3. Access the app at: http://localhost:8000"
echo ""
echo "For production deployment:"
echo "  docker-compose --profile production up -d"
echo ""
echo "For more information, see the README.md file."
