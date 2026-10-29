
import os
import tempfile
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME", "cloudpass_db"),
    }

    ca_content = os.getenv("DB_SSL_CA_CONTENT")
    ca_path = os.getenv("DB_SSL_CA")

    if ca_content:
        ca_file = Path(tempfile.gettempdir()) / "cloudpass-ca.pem"
        ca_file.write_text(ca_content, encoding="utf-8")
        ca_path = str(ca_file)

    if ca_path:
        config["ssl_ca"] = ca_path
        config["ssl_verify_cert"] = True
        config["ssl_verify_identity"] = True

    return mysql.connector.connect(**config)
