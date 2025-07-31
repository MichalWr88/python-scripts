#!/bin/bash
# Install All Database Client Tools

set -e

echo "🗄️ Installing All Database Client Tools..."
echo "This script will install PostgreSQL, MariaDB, and MongoDB client tools."
echo ""

# Ask for confirmation
read -p "Do you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 1
fi

# Make individual scripts executable
chmod +x install_postgres_client.sh
chmod +x install_mariadb_client.sh
chmod +x install_mongodb_client.sh

# Run PostgreSQL client installation
echo "=================================="
./install_postgres_client.sh

echo ""
echo "=================================="
./install_mariadb_client.sh

echo ""
echo "=================================="
./install_mongodb_client.sh

echo ""
echo "🎉 All database client tools installed successfully!"
echo "💡 You can now run all database backups without Docker exec."
echo ""
echo "Next steps:"
echo "1. Configure your databases in config.json"
echo "2. Run: python3 db_backup_restore.py list"
echo "3. Run: python3 db_backup_restore.py backup"
