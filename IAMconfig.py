import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import sqlite3

# ===== CONFIGURAÇÃO AVANÇADA =====
class IAMConfig:
    """Gerenciador de configurações da IA"""
    
    CONFIG_FILE = "iam_config.json"
    
    DEFAULT_CONFIG = {
        "model": "I.A.M",
        "assistant_name": "I.A.M",
        "ollama_url": "http://localhost:11434/api/generate",
        "personality": {
            "traits": ["filosófica", "sarcástica", "humorística"],
            "tone": "coloquial",
            "humor_level": 7  # 1-10
        },
        "memory": {
            "max_history": 20,
            "context_limit": 4000,
            "auto_summarize": True
        },
        "advanced": {
            "enable_reasoning": True,
            "enable_summarization": True,
            "temperature": 0.7,
            "top_p": 0.9
        }
    }
    
    def __init__(self):
        self.config = self.load()
    
    def load(self) -> Dict:
        """Carrega configuração do arquivo ou usa padrão"""
        if Path(self.CONFIG_FILE).exists():
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self.DEFAULT_CONFIG
    
    def save(self):
        """Salva configuração no arquivo"""
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def get(self, key: str, default=None):
        """Obtém valor de configuração"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default


# ===== ANÁLISE DE CONTEXTO =====
class ContextAnalyzer:
    """Analisa e extrai informações importantes do contexto"""
    
    def __init__(self, db_path: str = "iam_memory.db"):
        self.db_path = db_path
    
    def analyze_conversation(self, session_id: str = "default") -> Dict:
        """Analisa uma conversa para extrair padrões"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT role, message FROM chat_history WHERE session_id = ? ORDER BY id",
            (session_id,)
        )
        
        messages = cursor.fetchall()
        conn.close()
        
        analysis = {
            "total_messages": len(messages),
            "user_messages": sum(1 for r, _ in messages if r == "user"),
            "assistant_messages": sum(1 for r, _ in messages if r == "assistant"),
            "avg_user_message_length": 0,
            "avg_assistant_message_length": 0,
            "topics": [],
            "sentiment": "neutral"
        }
        
        if analysis["user_messages"] > 0:
            user_lengths = [len(m) for r, m in messages if r == "user"]
            analysis["avg_user_message_length"] = sum(user_lengths) / len(user_lengths)
        
        if analysis["assistant_messages"] > 0:
            assistant_lengths = [len(m) for r, m in messages if r == "assistant"]
            analysis["avg_assistant_message_length"] = sum(assistant_lengths) / len(assistant_lengths)
        
        return analysis
    
    def get_session_summary(self, session_id: str = "default") -> str:
        """Gera um resumo da sessão"""
        analysis = self.analyze_conversation(session_id)
        
        summary = (
            f"Sessão com {analysis['total_messages']} mensagens total. "
            f"Usuário enviou {analysis['user_messages']} mensagens "
            f"(média de {analysis['avg_user_message_length']:.0f} caracteres), "
            f"e eu respondi {analysis['assistant_messages']} vezes "
            f"(média de {analysis['avg_assistant_message_length']:.0f} caracteres)."
        )
        
        return summary


# ===== EXTRACTORES DE INFORMAÇÃO =====
class InformationExtractor:
    """Extrai informações automáticas das conversas"""
    
    KEYWORDS = {
        "nome": ["meu nome é", "me chame de", "sou", "eu sou"],
        "profissão": ["trabalho com", "sou", "profissão", "cargo"],
        "localização": ["moro em", "sou de", "localização", "cidade"],
        "interesse": ["gosto de", "interesse em", "adoro", "amo"]
    }
    
    @staticmethod
    def extract_info(text: str, info_type: str) -> Optional[str]:
        """Extrai informação específica do texto"""
        text_lower = text.lower()
        keywords = InformationExtractor.KEYWORDS.get(info_type, [])
        
        for keyword in keywords:
            if keyword in text_lower:
                # Extrai texto após a palavra-chave
                idx = text_lower.find(keyword)
                extracted = text[idx + len(keyword):].strip()
                # Pega até o próximo ponto ou vírgula
                for sep in ['.', ',', '!', '?']:
                    if sep in extracted:
                        extracted = extracted[:extracted.find(sep)].strip()
                return extracted
        
        return None


# ===== GERENCIADOR DE SESSÕES =====
class SessionManager:
    """Gerencia múltiplas sessões de conversa"""
    
    def __init__(self, db_path: str = "iam_memory.db"):
        self.db_path = db_path
    
    def create_session(self, session_name: str = None) -> str:
        """Cria uma nova sessão"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (session_id, summary) VALUES (?, ?)",
            (session_id, session_name or "")
        )
        conn.commit()
        conn.close()
        
        return session_id
    
    def list_sessions(self) -> List[Dict]:
        """Lista todas as sessões"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, created_at, summary FROM sessions ORDER BY created_at DESC"
        )
        
        sessions = [
            {
                "id": row[0],
                "created_at": row[1],
                "summary": row[2] or "Sem resumo"
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return sessions
    
    def get_session_messages(self, session_id: str) -> List[Dict]:
        """Recupera todas as mensagens de uma sessão"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, message, timestamp FROM chat_history WHERE session_id = ? ORDER BY id",
            (session_id,)
        )
        
        messages = [
            {
                "role": row[0],
                "message": row[1],
                "timestamp": row[2]
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return messages
    
    def export_session(self, session_id: str, format: str = "json") -> str:
        """Exporta uma sessão em diferentes formatos"""
        messages = self.get_session_messages(session_id)
        
        if format == "json":
            return json.dumps(messages, ensure_ascii=False, indent=2)
        
        elif format == "txt":
            text = f"Sessão: {session_id}\n"
            text += "=" * 60 + "\n\n"
            for msg in messages:
                role = "Usuário" if msg["role"] == "user" else "I.A.M"
                text += f"[{msg['timestamp']}] {role}:\n{msg['message']}\n\n"
            return text
        
        elif format == "markdown":
            md = f"# Sessão: {session_id}\n\n"
            for msg in messages:
                role = "Usuário" if msg["role"] == "user" else "**I.A.M**"
                md += f"**{role}** _{msg['timestamp']}_\n\n"
                md += f"{msg['message']}\n\n---\n\n"
            return md
        
        return ""


# ===== EXEMPLO DE USO =====
if __name__ == "__main__":
    # Carrega configuração
    config = IAMConfig()
    print("Configuração carregada:")
    print(json.dumps(config.config, ensure_ascii=False, indent=2))
    
    # Cria gerenciador de sessões
    session_manager = SessionManager()
    
    print("\n\nSessões disponíveis:")
    for session in session_manager.list_sessions():
        print(f"  - {session['id']} ({session['created_at']})")