#!/bin/bash
# PostgreSQL Client Installation Script for Debian/Ubuntu

set -e

echo "🐘 Installing PostgreSQL Client Tools..."

# Update package lists
echo "📦 Updating package lists..."
sudo apt update

# Install PostgreSQL client
echo "⚙️ Installing postgresql-client..."
sudo apt install -y postgresql-client-15

# Verify installation
echo "✅ Verifying installation..."
if command -v pg_dump &> /dev/null; then
    echo "✅ pg_dump installed successfully: $(which pg_dump)"
    pg_dump --version
else
    echo "❌ pg_dump installation failed"
    exit 1
fi

if command -v pg_restore &> /dev/null; then
    echo "✅ pg_restore installed successfully: $(which pg_restore)"
    pg_restore --version
else
    echo "❌ pg_restore installation failed"
    exit 1
fi

echo "🎉 PostgreSQL client tools installed successfully!"
echo "💡 You can now run PostgreSQL backups without Docker exec."
