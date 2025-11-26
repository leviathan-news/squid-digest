#!/bin/bash

# ⚠️ DEPRECATED: This script is kept for backward compatibility only.
# This project now uses `uv` for dependency management.
# 
# For new setups, use: uv sync
# See README.md for installation instructions.
#
# This script may be removed in a future version.

# Setup script for squid-digest project
# This script sets up the virtual environment and installs dependencies

set -e

echo "⚠️  WARNING: This setup script is deprecated."
echo "⚠️  Please use 'uv sync' instead (see README.md)"
echo ""
echo "🚀 Setting up squid-digest project (legacy method)..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install pip-tools if not present
echo "📚 Installing pip-tools..."
pip install pip-tools

# Compile requirements from requirements.in
echo "🔨 Compiling requirements.txt from requirements.in..."
pip-compile requirements.in

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists, if not create from template
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp env.template .env
    echo "⚠️  Please edit .env file with your actual API keys and configuration"
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run migrations: python manage.py migrate"
echo "3. Test the command: python manage.py pull_news --test --dry-run"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "source venv/bin/activate"

