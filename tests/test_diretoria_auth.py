import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kanban import create_app
from kanban.database import init_db

def test_diretoria_flow():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    print("--- 1. Testando acesso anônimo a /diretoria ---")
    res = client.get("/diretoria")
    assert res.status_code == 200
    assert "Acesso Restrito" in res.data.decode("utf-8")
    assert "Painel do Sr. Jacson" in res.data.decode("utf-8")
    print("  -> OK: Tela de login exibida com sucesso.")

    print("--- 2. Testando login incorreto ---")
    res = client.post("/diretoria", data={"username": "admin", "password": "123"})
    assert res.status_code == 200
    assert "Usuário ou senha incorretos" in res.data.decode("utf-8")
    print("  -> OK: Bloqueado com mensagem de erro.")

    print("--- 3. Testando login correto (admin / admin) ---")
    res = client.post("/diretoria", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "DIRETORIA EXECUTIVA" in html
    assert "Exportar CSV" in html
    assert "Central de Chamados TV" in html
    assert "Sair" in html
    print("  -> OK: Autenticado com sucesso no Painel da Diretoria!")

    print("--- 4. Testando logout ---")
    res = client.get("/diretoria/logout", follow_redirects=True)
    assert res.status_code == 200
    assert "Acesso Restrito" in res.data.decode("utf-8")
    print("  -> OK: Sessão encerrada com sucesso.")

    print("--- 5. Testando remoção dos botões da navbar no /admin ---")
    res = client.get("/admin")
    assert res.status_code == 200
    admin_html = res.data.decode("utf-8")
    # Garante que os botões foram removidos da barra de navegação
    assert "<span>Nova O.S.</span>" not in admin_html
    assert "<span>Chamar Técnico</span>" not in admin_html
    assert "<span>Exportar</span>" not in admin_html
    assert "TV Ativa" in admin_html
    assert "Diretoria" in admin_html
    print("  -> OK: Botões 'Nova O.S.', 'Chamar Técnico' e 'Exportar' removidos da navbar de /admin.")

    print("\nTODOS OS TESTES DE AUTENTICAÇÃO E DIRETORIA PASSARAM 100%!")

if __name__ == "__main__":
    test_diretoria_flow()
