import mysql.connector
import os

def get_db_connection():
    # Configurações de conexão com valores padrão
    db_config = {
        #'host': os.environ.get('DB_HOST', 'mysql'), #Produção
        'host': os.environ.get('DB_HOST', 'localhost'), # Desenvolvimento
        'user': os.environ.get('DB_USER', 'root'),
        'password': os.environ.get('DB_PASSWORD', 'Vms071999'),
        'database': os.environ.get('DB_NAME', 'tonner')
    }
    
    try:
        # Estabelece a conexão com o banco de dados
        connection = mysql.connector.connect(**db_config)
        return connection
    except mysql.connector.Error as err:
        # Log de erro de conexão (considere usar logging em produção)
        print(f"Erro ao conectar ao banco de dados: {err}")
        raise
