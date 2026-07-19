#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
  CREATE ROLE app LOGIN PASSWORD '${APP_DB_PASSWORD}';
  CREATE DATABASE stock_intelligence OWNER app;
  CREATE DATABASE temporal OWNER postgres;
  CREATE DATABASE temporal_visibility OWNER postgres;
  CREATE DATABASE mlflow OWNER postgres;
SQL

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname stock_intelligence <<-SQL
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gist;
  GRANT ALL ON SCHEMA public TO app;
SQL
