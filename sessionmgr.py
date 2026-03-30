#!/usr/bin/env python3
"""
Gerenciador de Sessões para I.A.M
Visualiza, exporta e gerencia conversas armazenadas
"""

import sys
from pathlib import Path
from IAMconfig import SessionManager, ContextAnalyzer, IAMConfig
import json
from datetime import datetime


class SessionManagerCLI:
    """Interface de linha de comando para gerenciar sessões"""
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.analyzer = ContextAnalyzer()
        self.config = IAMConfig()
    
    def list_sessions(self):
        """Lista todas as sessões"""
        sessions = self.session_manager.list_sessions()
        
        if not sessions:
            print("Nenhuma sessão encontrada.")
            return
        
        print("\n" + "="*80)
        print(f"{'ID da Sessão':<30} {'Data':<25} {'Resumo':<25}")
        print("="*80)
        
        for session in sessions:
            session_id = session['id'][:28] + ".."
            created = session['created_at'][:19]
            summary = session['summary'][:23] if session['summary'] else "Sem resumo"
            print(f"{session_id:<30} {created:<25} {summary:<25}")
        
        print("="*80 + "\n")
    
    def view_session(self, session_id: str):
        """Visualiza uma sessão específica"""
        messages = self.session_manager.get_session_messages(session_id)
        
        if not messages:
            print(f"Sessão '{session_id}' não encontrada ou vazia.")
            return
        
        print("\n" + "="*80)
        print(f"SESSÃO: {session_id}")
        print("="*80 + "\n")
        
        for i, msg in enumerate(messages, 1):
            role = "👤 USUÁRIO" if msg['role'] == 'user' else "🤖 I.A.M"
            timestamp = msg['timestamp']
            content = msg['message']
            
            print(f"[{i}] {role} - {timestamp}")
            print("-" * 80)
            print(content)
            print("\n")
        
        # Mostra análise
        print("="*80)
        print("ANÁLISE DA SESSÃO")
        print("="*80)
        summary = self.analyzer.get_session_summary(session_id)
        print(summary)
        print()
    
    def export_session(self, session_id: str, format: str = "json"):
        """Exporta uma sessão"""
        valid_formats = ["json", "txt", "markdown"]
        
        if format not in valid_formats:
            print(f"Formato inválido. Use: {', '.join(valid_formats)}")
            return
        
        content = self.session_manager.export_session(session_id, format)
        
        if not content:
            print(f"Sessão '{session_id}' não encontrada.")
            return
        
        # Salva arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.{format if format != 'markdown' else 'md'}"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Sessão exportada para '{filename}'")
    
    def search_sessions(self, keyword: str):
        """Busca sessões por palavra-chave"""
        sessions = self.session_manager.list_sessions()
        found = []
        
        for session in sessions:
            messages = self.session_manager.get_session_messages(session['id'])
            for msg in messages:
                if keyword.lower() in msg['message'].lower():
                    found.append({
                        'session_id': session['id'],
                        'timestamp': msg['timestamp'],
                        'preview': msg['message'][:100]
                    })
        
        if not found:
            print(f"Nenhuma mensagem encontrada contendo '{keyword}'")
            return
        
        print(f"\n✓ Encontradas {len(found)} mensagens contendo '{keyword}':\n")
        
        for item in found:
            print(f"Sessão: {item['session_id']}")
            print(f"Data: {item['timestamp']}")
            print(f"Preview: {item['preview']}...")
            print("-" * 80)
    
    def show_config(self):
        """Mostra configurações atuais"""
        print("\n" + "="*80)
        print("CONFIGURAÇÃO ATUAL")
        print("="*80)
        print(json.dumps(self.config.config, ensure_ascii=False, indent=2))
        print("="*80 + "\n")
    
    def get_stats(self):
        """Mostra estatísticas gerais"""
        sessions = self.session_manager.list_sessions()
        
        total_sessions = len(sessions)
        total_messages = 0
        
        for session in sessions:
            messages = self.session_manager.get_session_messages(session['id'])
            total_messages += len(messages)
        
        print("\n" + "="*80)
        print("ESTATÍSTICAS")
        print("="*80)
        print(f"Total de sessões: {total_sessions}")
        print(f"Total de mensagens: {total_messages}")
        print(f"Média por sessão: {total_messages // max(total_sessions, 1):.1f}")
        print("="*80 + "\n")
    
    def show_help(self):
        """Mostra ajuda dos comandos"""
        help_text = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    GERENCIADOR DE SESSÕES I.A.M                           ║
╚════════════════════════════════════════════════════════════════════════════╝

COMANDOS DISPONÍVEIS:

  list                       Lista todas as sessões
  view <session_id>          Visualiza uma sessão específica
  export <session_id>        Exporta sessão em JSON (padrão)
  export <session_id> txt    Exporta sessão em TXT
  export <session_id> md     Exporta sessão em Markdown
  search <palavra>           Busca sessões por palavra-chave
  config                     Mostra configurações atuais
  stats                      Mostra estatísticas gerais
  help                       Mostra esta mensagem

EXEMPLOS:

  python session_manager.py list
  python session_manager.py view session_20240115_120530
  python session_manager.py export session_20240115_120530 md
  python session_manager.py search Python
  python session_manager.py config
  python session_manager.py stats

"""
        print(help_text)


def main():
    """Função principal"""
    manager = SessionManagerCLI()
    
    if len(sys.argv) < 2:
        manager.show_help()
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "list":
            manager.list_sessions()
        
        elif command == "view":
            if len(sys.argv) < 3:
                print("Uso: python session_manager.py view <session_id>")
                return
            manager.view_session(sys.argv[2])
        
        elif command == "export":
            if len(sys.argv) < 3:
                print("Uso: python session_manager.py export <session_id> [formato]")
                return
            format_type = sys.argv[3].lower() if len(sys.argv) > 3 else "json"
            manager.export_session(sys.argv[2], format_type)
        
        elif command == "search":
            if len(sys.argv) < 3:
                print("Uso: python session_manager.py search <palavra>")
                return
            manager.search_sessions(sys.argv[2])
        
        elif command == "config":
            manager.show_config()
        
        elif command == "stats":
            manager.get_stats()
        
        elif command == "help":
            manager.show_help()
        
        else:
            print(f"Comando desconhecido: {command}")
            manager.show_help()
    
    except Exception as e:
        print(f"Erro: {e}")


if __name__ == "__main__":
    main()