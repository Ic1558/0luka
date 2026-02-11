#!/bin/bash
# Quick Start Script for /02luka

echo "🚀 /02luka - The Edge Co. Ltd AI Automation Quick Start"

# Check if we're in the right directory
if [ ! -d "/02luka" ]; then
    echo "❌ /02luka directory not found. Please run this from /02luka/"
    exit 1
fi

cd /02luka

echo "📝 Step 1: Update API Keys"
echo "Edit the .env file with your actual API keys:"
echo "nano .env"
echo ""
echo "Replace:"
echo "OPENAI_API_KEY=sk-your-openai-key-here"
echo "ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here"
echo ""
echo "With your actual keys from:"
echo "- OpenAI: https://platform.openai.com/api-keys"
echo "- Anthropic: https://console.anthropic.com/"
echo ""

echo "📦 Step 2: Install Dependencies"
python3 -m pip install --upgrade pip
python3 -m pip install -r deployment/requirements.txt

echo "🧪 Step 3: Test System"
python3 tests/test_integration.py

echo "🌐 Step 4: Start Dashboard"
echo "Starting web dashboard at http://localhost:8080"
python3 web/app.py
