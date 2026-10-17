"""Starts a local PostgreSQL that keeps running after this script exits."""
import os
import pgserver
import psycopg2

data = os.path.expanduser("~/.ahs-local/pg")
os.makedirs(data, exist_ok=True)
srv = pgserver.get_server(data, cleanup_mode=None)
sock = data
conn = psycopg2.connect(host=sock, dbname="postgres", user="postgres")
conn.autocommit = True
cur = conn.cursor()
cur.execute("select 1 from pg_database where datname='ahs'")
if not cur.fetchone():
    cur.execute("create database ahs")
print(f"postgresql+psycopg2://postgres:@/ahs?host={sock}")
