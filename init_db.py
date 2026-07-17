"""
Script separado para criar/migrar o schema do banco (Postgres/Supabase).

Rode manualmente quando precisar criar ou atualizar as tabelas:
    python init_db.py

Não é chamado automaticamente pelo app em cada cold start.
"""

import database as db

if __name__ == "__main__":
    db.init_db()
    print("Schema aplicado com sucesso (CREATE TABLE IF NOT EXISTS).")
