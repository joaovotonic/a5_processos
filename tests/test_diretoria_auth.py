import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kanban import create_app
from kanban.database import connect, init_db

def test_diretoria_flow():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    # 0. Garante que comece no modo Primeiro Acesso
    with connect() as conn:
        conn.execute("DELETE FROM settings WHERE key IN ('director_user', 'director_pass', 'director_first_access_done')")

    print("--- 1. Testando acesso anônimo a /diretoria (Primeiro Acesso) ---")
    res = client.get("/diretoria")
    assert res.status_code == 200
    assert "Acesso Restrito" in res.data.decode("utf-8")
    assert "Painel do Sr. Jacson" in res.data.decode("utf-8")
    assert "Primeiro Acesso" in res.data.decode("utf-8")
    print("  -> OK: Tela de Primeiro Acesso exibida com sucesso para o Sr. Jacson.")

    print("--- 2. Testando login incorreto ---")
    res = client.post("/diretoria", data={"action": "login", "username": "admin", "password": "123"})
    assert res.status_code == 200
    assert "Usuário ou senha incorretos" in res.data.decode("utf-8")
    print("  -> OK: Bloqueado com mensagem de erro.")

    print("--- 3. Testando login master admin do João (admin / admin) ---")
    res = client.post("/diretoria", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "DIRETORIA EXECUTIVA" in html
    assert "Exportar CSV" in html
    assert "Central de Chamados TV" in html
    assert "Sair" in html
    print("  -> OK: João autenticado com sucesso via admin / admin!")

    print("--- 4. Testando logout ---")
    res = client.get("/diretoria/logout", follow_redirects=True)
    assert res.status_code == 200
    assert "Acesso Restrito" in res.data.decode("utf-8")
    print("  -> OK: Sessão encerrada com sucesso.")

    print("--- 5. Testando criação de usuário pelo Sr. Jacson (Primeiro Acesso) ---")
    res_setup = client.post("/diretoria", data={
        "action": "first_access",
        "username": "jacson",
        "password": "senha_jacson_2026",
        "confirm_password": "senha_jacson_2026"
    }, follow_redirects=True)
    assert res_setup.status_code == 200
    assert "DIRETORIA EXECUTIVA" in res_setup.data.decode("utf-8")
    print("  -> OK: Sr. Jacson criou seu usuário e senha e entrou diretamente no Painel!")

    print("--- 6. Testando login subsequente com a senha criada pelo Sr. Jacson ---")
    client.get("/diretoria/logout", follow_redirects=True)
    res_jacson_login = client.post("/diretoria", data={
        "action": "login",
        "username": "jacson",
        "password": "senha_jacson_2026"
    }, follow_redirects=True)
    assert res_jacson_login.status_code == 200
    assert "DIRETORIA EXECUTIVA" in res_jacson_login.data.decode("utf-8")
    print("  -> OK: Login do Sr. Jacson com novas credenciais funcionando perfeitamente!")

    # 7. Limpa para deixar amanha cedo pronto pro Jacson
    with connect() as conn:
        conn.execute("DELETE FROM settings WHERE key IN ('director_user', 'director_pass', 'director_first_access_done')")

    print("--- 7. Testando remoção dos botões da navbar no /admin ---")
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

    print("\nTODOS OS TESTES DE AUTENTICAÇÃO E PRIMEIRO ACESSO PASSARAM 100%!")

if __name__ == "__main__":
    test_diretoria_flow()
