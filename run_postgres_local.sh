#!/bin/bash

# This script sets up a local PostgreSQL database for the application.
# It is intended for users who cannot or do not want to use Docker.

# Exit immediately if a command exits with a non-zero status.
set -e

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Install PostgreSQL if it's not already installed
if ! command_exists psql; then
  echo "PostgreSQL not found. Installing..."
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Debian/Ubuntu
    sudo apt-get update
    sudo apt-get install -y postgresql postgresql-contrib
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS with Homebrew
    brew install postgresql
  else
    echo "Unsupported OS. Please install PostgreSQL manually."
    exit 1
  fi
fi

# Start PostgreSQL service if it's not running
if ! pg_isready -q; then
  echo "Starting PostgreSQL service..."
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo service postgresql start
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    brew services start postgresql
  fi
  # Wait for the service to start
  sleep 5
fi

# Create database and user
DB_NAME="graphvis"
DB_USER="postgres"
DB_PASSWORD="password"

echo "Creating database '$DB_NAME' and user '$DB_USER'..."

# Use psql to create the database and user.
# The -U postgres argument connects as the default postgres superuser.
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" || echo "Database $DB_NAME already exists."
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" || echo "User $DB_USER already exists."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

echo "PostgreSQL setup complete."
echo "You can now connect to the database with the following URL:"
echo "DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"

# Update .env file with the local database URL
if [ -f .env ]; then
  sed -i'' -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME|" .env
  echo "Updated DATABASE_URL in .env file."
fi
