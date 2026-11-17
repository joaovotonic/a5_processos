import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kanban import create_app
from kanban.database import connect, init_db
from tests._db_snapshot import restore_db_snapshot, take_db_snapshot


class TestDiretoriaAuthFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._db_snap = take_db_snapshot()

    @classmethod
    def tearDownClass(cls):
        restore_db_snapshot(getattr(cls, "_db_snap", None))

    def test_diretoria_and_unified_auth_flow(self):
        app = create_app()
        app.config["TESTING"] = True
        init_db()
        client = app.test_client()

        with connect() as conn:
            conn.execute("DELETE FROM settings WHERE key IN ('director_user', 'director_pass', 'director_first_access_done')")

        # 1. Acesso anônimo a /diretoria e /admin redireciona para /login
        r_dir = client.get("/diretoria")
        self.assertEqual(r_dir.status_code, 302)
        self.assertIn("/login", r_dir.headers["Location"])

        r_login_page = client.get("/login")
        self.assertEqual(r_login_page.status_code, 200)
        self.assertIn("window.__A5_CONFIG__", r_login_page.get_data(as_text=True))

        # 2. Login incorreto retorna 401
        r_bad = client.post("/api/auth/login", json={"username": "admin", "password": "123"})
        self.assertEqual(r_bad.status_code, 401)
        self.assertFalse(r_bad.get_json()["success"])

        # 3. Login Master (admin / admin) dá acesso a /diretoria e /admin
        r_master = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        self.assertEqual(r_master.status_code, 200)
        self.assertEqual(r_master.get_json()["user"]["role"], "master")

        r_dir_ok = client.get("/diretoria")
        self.assertEqual(r_dir_ok.status_code, 200)
        self.assertIn('<div id="root"></div>', r_dir_ok.get_data(as_text=True))

        r_adm_ok = client.get("/admin")
        self.assertEqual(r_adm_ok.status_code, 200)

        # 4. Logout limpa sessão e volta para /login
        r_out = client.get("/diretoria/logout", follow_redirects=False)
        self.assertEqual(r_out.status_code, 302)
        self.assertIn("/login", r_out.headers["Location"])

        # 5. Primeiro Acesso do Sr. Jacson via /api/auth/setup-director
        r_setup = client.post("/api/auth/setup-director", json={
            "username": "jacson",
            "password": "senha_jacson_2026",
            "confirm_password": "senha_jacson_2026",
        })
        self.assertEqual(r_setup.status_code, 200)
        setup_json = r_setup.get_json()
        self.assertTrue(setup_json["success"])
        self.assertEqual(setup_json["redirect_to"], "/diretoria")
        self.assertEqual(setup_json["user"]["role"], "diretoria")

        # Sr. Jacson autenticado acessa /diretoria, mas é redirecionado se tentar /admin
        self.assertEqual(client.get("/diretoria").status_code, 200)
        r_block_admin = client.get("/admin", follow_redirects=False)
        self.assertEqual(r_block_admin.status_code, 302)
        self.assertIn("/diretoria", r_block_admin.headers["Location"])

        # 6. Novo login com a senha recém-cadastrada pelo Sr. Jacson
        client.post("/api/auth/logout")
        r_relogin = client.post("/api/auth/login", json={
            "username": "jacson",
            "password": "senha_jacson_2026",
        })
        self.assertEqual(r_relogin.status_code, 200)
        self.assertEqual(r_relogin.get_json()["redirect_to"], "/diretoria")


if __name__ == "__main__":
    unittest.main(verbosity=2)
