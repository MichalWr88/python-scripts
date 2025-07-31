#!/bin/bash
# MongoDB Client Installation Script for Debian/Ubuntu

set -e

echo "🍃 Installing MongoDB Client Tools..."

# Update package lists
echo "📦 Updating package lists..."
sudo apt update

# Install MongoDB client tools
echo "⚙️ Installing mongodb-clients..."
sudo apt install -y mongodb-clients

# Verify installation
echo "✅ Verifying installation..."
if command -v mongodump &> /dev/null; then
    echo "✅ mongodump installed successfully: $(which mongodump)"
    mongodump --version
else
    echo "❌ mongodump installation failed"
    exit 1
fi

if command -v mongorestore &> /dev/null; then
    echo "✅ mongorestore installed successfully: $(which mongorestore)"
    mongorestore --version
else
    echo "❌ mongorestore installation failed"
    exit 1
fi

echo "🎉 MongoDB client tools installed successfully!"
echo "💡 You can now run MongoDB backups without Docker exec."
