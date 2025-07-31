# Database Backup/Restore Script

This script allows you to backup and restore databases of different types: PostgreSQL, MariaDB, and MongoDB.

## Prerequisites

### Option 1: Using Docker Exec (Recommended)
If your databases are running in Docker containers, the script can use the database tools inside the containers. No additional installation required on the host system.

### Option 2: Installing Database Client Tools on Host

#### PostgreSQL Client Tools
For PostgreSQL backups, you need `pg_dump` and `pg_restore` tools:

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y postgresql-client-15

# Or run the provided installation script
./install_postgres_client.sh
```

#### MariaDB Client Tools
For MariaDB backups, you need `mysqldump` and `mysql` tools:

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y mariadb-client

# Or run the provided installation script
./install_mariadb_client.sh
```

#### MongoDB Client Tools
For MongoDB backups, you need `mongodump` and `mongorestore` tools:

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y mongodb-clients

# Or run the provided installation script
./install_mongodb_client.sh
```

## Configuration

Create a `config.json` file with your database configurations:

```json
{
  "databases": [
    {
      "name": "my_postgres",
      "type": "postgresql",
      "host": "192.168.0.81",
      "port": 5432,
      "user": "postgres_user",
      "password": "your_password",
      "database": "database_name",
      "backup_path": "./backups/postgres",
      "docker_container": "postgres_container",
      "use_docker_exec": true
    }
  ]
}
```

### Configuration Options

- `name`: Unique identifier for the database
- `type`: Database type (`postgresql`, `mariadb`, `mongodb`)
- `host`: Database host (use `localhost` if using docker exec)
- `port`: Database port
- `user`: Database username
- `password`: Database password
- `database`: Database name to backup
- `backup_path`: Local path where backups will be stored
- `docker_container`: (Optional) Docker container name for restart after backup
- `use_docker_exec`: (Optional) Set to `true` to use docker exec instead of host tools

## Usage

### List Available Databases
```bash
python3 db_backup_restore.py list
```

### Backup All Databases
```bash
python3 db_backup_restore.py backup
```

### Restore Specific Database
```bash
python3 db_backup_restore.py restore <database_name> <backup_file_or_directory>
```

## Examples

### PostgreSQL Backup/Restore
```bash
# Backup
python3 db_backup_restore.py backup

# Restore
python3 db_backup_restore.py restore my_postgres ./backups/postgres/database_name_20250730_160030.dump
```

### Docker Container Configuration

If your PostgreSQL is running in Docker (like postgres:17.4), you can either:

1. **Use Docker Exec** (Recommended): Set `use_docker_exec: true` in config
2. **Install Client Tools**: Use the provided installation scripts

## Troubleshooting

### "Nie znaleziono programu: pg_dump"
This error occurs when PostgreSQL client tools are not installed. Solutions:

1. **Use Docker Exec**: Add `"use_docker_exec": true` to your database config
2. **Install Client Tools**: Run `./install_postgres_client.sh`

### Connection Issues
- Verify host and port settings
- Check if database is accessible from the backup machine
- Ensure firewall allows connections on the database port

### Permission Issues
- Verify database user has backup/restore permissions
- Check file system permissions for backup directory

## File Formats

- **PostgreSQL**: Custom binary format (`.dump` files)
- **MariaDB**: SQL text format (`.sql` files)
- **MongoDB**: BSON directory structure

## Security Notes

- Passwords are passed via environment variables to avoid exposure in process lists
- Backup files may contain sensitive data - secure them appropriately
- Use strong passwords and limit network access to databases

## Logs

The script creates detailed logs in `backup.log` file. Check this file for troubleshooting backup/restore operations.
