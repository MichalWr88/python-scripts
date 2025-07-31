#!/bin/bash
# Quick Setup Script for Database Backup Tools

echo "🗄️ Database Backup/Restore Script Setup"
echo "========================================"
echo ""
echo "This script provides database backup and restore functionality for:"
echo "- PostgreSQL"
echo "- MariaDB" 
echo "- MongoDB"
echo ""
echo "📋 Setup Options:"
echo ""
echo "1. 🐳 Use Docker Exec (Recommended)"
echo "   - No installation required on host"
echo "   - Uses database tools inside Docker containers"
echo "   - Add 'use_docker_exec': true to config.json"
echo ""
echo "2. 🖥️ Install Client Tools on Host"
echo "   - Run: ./install_postgres_client.sh"
echo "   - Run: ./install_mariadb_client.sh"
echo "   - Run: ./install_mongodb_client.sh"
echo "   - Or run: ./install_all_clients.sh"
echo ""
echo "📖 Configuration:"
echo "   - Copy config.example.json to config.json"
echo "   - Edit config.json with your database details"
echo "   - Set 'use_docker_exec': true for Docker method"
echo ""
echo "🚀 Usage:"
echo "   - List databases: python3 db_backup_restore.py list"
echo "   - Backup all: python3 db_backup_restore.py backup"
echo "   - Restore: python3 db_backup_restore.py restore <name> <file>"
echo ""
echo "📚 For detailed instructions, see README.md"
echo ""

# Check if config.json exists
if [ -f "config.json" ]; then
    echo "✅ config.json found"
else
    echo "⚠️ config.json not found - copy from config.example.json"
fi

# Check for Docker
if command -v docker &> /dev/null; then
    echo "✅ Docker is available"
else
    echo "❌ Docker not found - install Docker or use host client tools"
fi

# Check PostgreSQL client
if command -v pg_dump &> /dev/null; then
    echo "✅ PostgreSQL client tools available"
else
    echo "ℹ️ PostgreSQL client tools not installed (optional if using Docker exec)"
fi

echo ""
echo "🎯 Your current setup is ready to use Docker exec method!"
echo "💡 Test with: python3 db_backup_restore.py list"
