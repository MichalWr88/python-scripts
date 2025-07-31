#!/bin/bash
# MariaDB Client Installation Script for Debian/Ubuntu

set -e

echo "🐬 Installing MariaDB Client Tools..."

# Update package lists
echo "📦 Updating package lists..."
sudo apt update

# Install MariaDB client
echo "⚙️ Installing mariadb-client..."
sudo apt install -y mariadb-client

# Verify installation
echo "✅ Verifying installation..."
if command -v mysqldump &> /dev/null; then
    echo "✅ mysqldump installed successfully: $(which mysqldump)"
    mysqldump --version
else
    echo "❌ mysqldump installation failed"
    exit 1
fi

if command -v mysql &> /dev/null; then
    echo "✅ mysql installed successfully: $(which mysql)"
    mysql --version
else
    echo "❌ mysql installation failed"
    exit 1
fi

echo "🎉 MariaDB client tools installed successfully!"
echo "💡 You can now run MariaDB backups without Docker exec."
