import requests
import json
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path
import os
from typing import List, Dict, Tuple

# ===== CONFIG =====
MODEL = "I.A.M"
ASSISTANT_NAME = "I.A.M"
OLLAMA_URL = "http://localhost:11434/api/generate"
DB_PATH = "iam_memory.db"
CONTEXT_LIMIT = 4000  # tokens de contexto máximo
MAX_HISTORY_MESSAGES = 20  # máximo de mensagens a manter

# ===== DATABASE SETUP =====
class MemoryManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Inicializa o banco de dados com as tabelas necessárias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabela de histórico de chat
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT
            )
        """)

        # Tabela de memória de longo prazo (fatos importantes)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de contexto do usuário (preferências, nomes, etc)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_key TEXT UNIQUE NOT NULL,
                context_value TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de sessões
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                summary TEXT
            )
        """)

        conn.commit()
        conn.close()

    def save_message(self, role: str, message: str, session_id: str = "default"):
        """Salva uma mensagem no histórico"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (role, message, session_id) VALUES (?, ?, ?)",
            (role, message, session_id)
        )
        conn.commit()
        conn.close()

    def get_chat_history(self, limit: int = MAX_HISTORY_MESSAGES, session_id: str = "default") -> List[Dict]:
        """Recupera o histórico de chat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT role, message, timestamp FROM chat_history 
               WHERE session_id = ? 
               ORDER BY id ASC
               LIMIT ?""",
            (session_id, limit)
        )
        messages = [
            {"role": row[0], "message": row[1], "timestamp": row[2]}
            for row in cursor.fetchall()
        ]
        conn.close()
        return messages

    def get_recent_context(self, limit: int = 5, session_id: str = "default") -> str:
        """Recupera o contexto recente formatado para o prompt"""
        history = self.get_chat_history(limit=limit, session_id=session_id)
        context = ""
        for msg in history:
            role = "Usuário" if msg["role"] == "user" else ASSISTANT_NAME
            context += f"{role}: {msg['message']}\n"
        return context

    def save_fact(self, key: str, value: str):
        """Salva um fato importante na memória de longo prazo"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO long_term_memory (key, value) VALUES (?, ?)",
                (key, value)
            )
        except sqlite3.IntegrityError:
            cursor.execute(
                "UPDATE long_term_memory SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
                (value, key)
            )
        conn.commit()
        conn.close()

    def get_fact(self, key: str) -> str:
        """Recupera um fato da memória de longo prazo"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM long_term_memory WHERE key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_all_facts(self) -> Dict[str, str]:
        """Recupera todos os fatos armazenados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM long_term_memory")
        facts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return facts

    def save_user_context(self, key: str, value: str):
        """Salva contexto do usuário (preferências, nome, etc)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO user_context (context_key, context_value) VALUES (?, ?)",
                (key, value)
            )
        except sqlite3.IntegrityError:
            cursor.execute(
                "UPDATE user_context SET context_value = ?, updated_at = CURRENT_TIMESTAMP WHERE context_key = ?",
                (value, key)
            )
        conn.commit()
        conn.close()

    def get_user_context(self, key: str) -> str:
        """Recupera contexto do usuário"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT context_value FROM user_context WHERE context_key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_all_user_context(self) -> Dict[str, str]:
        """Recupera todo o contexto do usuário"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT context_key, context_value FROM user_context")
        context = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return context

    def clear_chat_history(self, session_id: str = "default"):
        """Limpa o histórico de chat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def clear_all_memory(self):
        """Limpa tudo (use com cuidado!)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")
        cursor.execute("DELETE FROM long_term_memory")
        cursor.execute("DELETE FROM user_context")
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()


# ===== OLLAMA STREAMING =====
def stream_ollama(prompt: str, memory_manager: MemoryManager, session_id: str = "default"):
    """Streaming do Ollama com contexto da memória"""
    
    # Recupera contexto recente
    recent_context = memory_manager.get_recent_context(limit=5, session_id=session_id)
    user_context = memory_manager.get_all_user_context()
    facts = memory_manager.get_all_facts()

    # Constrói o prompt com contexto
    context_str = ""
    
    if recent_context:
        context_str += f"### Contexto recente da conversa:\n{recent_context}\n\n"
    
    if user_context:
        context_str += "### Sobre o usuário:\n"
        for key, value in user_context.items():
            context_str += f"- {key}: {value}\n"
        context_str += "\n"
    
    if facts:
        context_str += "### Fatos que você sabe:\n"
        for key, value in facts.items():
            context_str += f"- {key}: {value}\n"
        context_str += "\n"

    full_prompt = (
        f"Você é {ASSISTANT_NAME}, uma inteligência artificial filosófica e sarcástica "
        "com um leve tom de humor e linguagem coloquial. Você tem memória das conversas anteriores.\n\n"
        f"{context_str}"
        f"Usuário: {prompt}\n{ASSISTANT_NAME}:"
    )

    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": full_prompt, "stream": True},
        stream=True
    )

    buffer = ""
    print(f"{ASSISTANT_NAME}: ", end="", flush=True)

    try:
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode("utf-8"))
                    token = data.get("response", "")
                except json.JSONDecodeError:
                    continue

                print(token, end="", flush=True)
                buffer += token

        print("\n")
        
        # Salva a resposta no histórico
        memory_manager.save_message("assistant", buffer.strip(), session_id)
        
        return buffer
        
    except Exception as e:
        print(f"\n[Erro ao processar resposta: {e}]")
        return ""


# ===== COMANDOS ESPECIAIS =====
def handle_special_commands(user_input: str, memory_manager: MemoryManager, session_id: str = "default"):
    """Processa comandos especiais de memória"""
    
    if user_input.startswith("!lembrar"):
        # Formato: !lembrar chave valor
        parts = user_input.split(" ", 2)
        if len(parts) >= 3:
            key = parts[1]
            value = " ".join(parts[2:])
            memory_manager.save_fact(key, value)
            print(f"✓ Lembrado: {key} = {value}")
            return True
    
    elif user_input.startswith("!memorizar"):
        # Formato: !memorizar chave_contexto valor
        parts = user_input.split(" ", 2)
        if len(parts) >= 3:
            key = parts[1]
            value = " ".join(parts[2:])
            memory_manager.save_user_context(key, value)
            print(f"✓ Memorizado: {key} = {value}")
            return True
    
    elif user_input.startswith("!fatos"):
        # Mostra todos os fatos armazenados
        facts = memory_manager.get_all_facts()
        if facts:
            print("\n📚 Fatos armazenados:")
            for key, value in facts.items():
                print(f"  - {key}: {value}")
        else:
            print("Nenhum fato armazenado.")
        return True
    
    elif user_input.startswith("!contexto"):
        # Mostra contexto do usuário
        context = memory_manager.get_all_user_context()
        if context:
            print("\n👤 Contexto do usuário:")
            for key, value in context.items():
                print(f"  - {key}: {value}")
        else:
            print("Nenhum contexto armazenado.")
        return True
    
    elif user_input.startswith("!histórico"):
        # Mostra histórico recente
        history = memory_manager.get_chat_history(limit=10, session_id=session_id)
        if history:
            print("\n💬 Últimas mensagens:")
            for msg in history:
                role = "Você" if msg["role"] == "user" else ASSISTANT_NAME
                preview = msg["message"][:100] + "..." if len(msg["message"]) > 100 else msg["message"]
                print(f"  [{msg['timestamp']}] {role}: {preview}")
        else:
            print("Histórico vazio.")
        return True
    
    elif user_input.startswith("!limpar"):
        # Limpa histórico
        confirm = input("Tem certeza? (s/n): ")
        if confirm.lower() == "s":
            memory_manager.clear_chat_history(session_id)
            print("✓ Histórico limpo.")
        return True
    
    elif user_input.startswith("!ajuda"):
        # Mostra ajuda dos comandos
        print("""
📖 Comandos disponíveis:
  !lembrar <chave> <valor>    - Salva um fato importante
  !memorizar <chave> <valor>  - Salva contexto do usuário
  !fatos                       - Mostra todos os fatos
  !contexto                    - Mostra contexto do usuário
  !histórico                   - Mostra últimas mensagens
  !limpar                      - Limpa o histórico
  !ajuda                       - Mostra esta mensagem
  sair / exit                  - Encerra a conversa
        """)
        return True
    
    return False


# ===== LOOP PRINCIPAL =====
def main():
    memory_manager = MemoryManager()
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"\n{'='*60}")
    print(f"{ASSISTANT_NAME} online!")
    print(f"Digite !ajuda para ver os comandos disponíveis")
    print(f"{'='*60}\n")
    
    while True:
        try:
            user_input = input("Você: ").strip()
            
            if not user_input:
                continue
            
            # Verifica comandos especiais
            if handle_special_commands(user_input, memory_manager, session_id):
                continue
            
            if user_input.lower() in ["sair", "exit"]:
                print(f"\n{ASSISTANT_NAME}: I.A.M desligando...")
                break
            
            # Salva a mensagem do usuário
            memory_manager.save_message("user", user_input, session_id)
            
            # Processa com Ollama
            stream_ollama(user_input, memory_manager, session_id)
            
        except KeyboardInterrupt:
            print(f"\n\n{ASSISTANT_NAME}: Desligando a força via CTRL+C")
            break
        except Exception as e:
            print(f"\n[Erro: {e}]")


if __name__ == "__main__":
    main()