"""Testes automatizados das correções críticas de segurança para produção/VPS."""
import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kanban import create_app
from kanban.auth import reset_login_rate_limits
from kanban.config import ROTAS_IMAGENS_DIR
from kanban.database import connect, init_db
from kanban.extensions import socketio
from kanban.services.esteira import create_manual_os
from tests._db_snapshot import restore_db_snapshot, take_db_snapshot

# PNG 1x1 válido em base64
VALID_PNG_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class TestSecurityHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._db_snap = take_db_snapshot()
        init_db()
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        reset_login_rate_limits()
        restore_db_snapshot(getattr(cls, "_db_snap", None))

    def setUp(self):
        reset_login_rate_limits()

    def _login(self, username: str, password: str):
        c = self.app.test_client()
        r = c.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(r.status_code, 200)
        return c

    def test_01_post_diretoria_first_access_cannot_overwrite_password(self):
        """Impede takeover da conta da Diretoria via POST /diretoria action=first_access."""
        with connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_first_access_done', '1')")
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_user', 'jacson')")

        anon = self.app.test_client()
        r = anon.post(
            "/diretoria",
            data={
                "action": "first_access",
                "username": "invasor",
                "password": "hacked123",
                "confirm_password": "hacked123",
            },
        )
        self.assertEqual(r.status_code, 403)

        r_login = anon.post("/api/auth/login", json={"username": "invasor", "password": "hacked123"})
        self.assertEqual(r_login.status_code, 401)

    def test_02_board_never_leaks_password_hash_and_sanitizes_pii_for_tv(self):
        """GET /api/board nunca vaza director_pass e remove PII/notas internas para clientes sem login."""
        with connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_pass', 'scrypt:fakehash')")
            conn.execute("DELETE FROM cards WHERE os_number = '998877'")
        create_manual_os({
            "os_number": "998877",
            "client_name": "CLIENTE SEC TESTE",
            "equipment_model": "Prix 5",
        })
        with connect() as conn:
            conn.execute(
                "UPDATE cards SET cnpj_cpf = '12345678000199', phone = '92999990000', admin_notes = 'NOTA PRIVADA' WHERE os_number = '998877'"
            )

        try:
            anon = self.app.test_client()
            r_pub = anon.get("/api/board")
            self.assertEqual(r_pub.status_code, 200)
            pub_data = r_pub.get_json()
            self.assertNotIn("director_pass", pub_data.get("settings", {}))
            self.assertEqual(pub_data.get("pending_entries"), [])
            all_pub_cards = [c for lst in pub_data["lists"] for c in lst["cards"]]
            c_pub = next((c for c in all_pub_cards if c["os_number"] == "998877"), None)
            self.assertIsNotNone(c_pub)
            self.assertNotIn("cnpj_cpf", c_pub)
            self.assertNotIn("phone", c_pub)
            self.assertNotIn("admin_notes", c_pub)

            master = self._login("admin", "admin")
            r_auth = master.get("/api/board")
            self.assertEqual(r_auth.status_code, 200)
            auth_data = r_auth.get_json()
            self.assertNotIn("director_pass", auth_data.get("settings", {}))
            all_auth_cards = [c for lst in auth_data["lists"] for c in lst["cards"]]
            c_auth = next((c for c in all_auth_cards if c["os_number"] == "998877"), None)
            self.assertEqual(c_auth.get("admin_notes"), "NOTA PRIVADA")
        finally:
            with connect() as conn:
                conn.execute("DELETE FROM card_history WHERE os_number = '998877'")
                conn.execute("DELETE FROM cards WHERE os_number = '998877'")

    def test_03_anonymous_socket_blocked_from_privileged_events(self):
        """Clientes WebSocket anônimos não podem chamar técnicos, enviar áudio da diretoria nem mutar a TV."""
        with connect() as conn:
            conn.execute("UPDATE settings SET value = '0' WHERE key = 'tv_muted'")

        anon_sio = socketio.test_client(self.app)
        anon_sio.get_received()  # limpa buffer inicial

        anon_sio.emit("call_tech_reception", {"tech_name": "Enzo", "reason": "Spam"})
        anon_sio.emit("director_call_tech", {"tech_name": "Oficina", "message": "Spam"})
        anon_sio.emit("panic_silence_tv", {"muted": True})

        recv = anon_sio.get_received()
        ev_names = [e["name"] for e in recv]
        self.assertNotIn("tv_announcement", ev_names)
        self.assertNotIn("tv_mute_changed", ev_names)

        with connect() as conn:
            muted = conn.execute("SELECT value FROM settings WHERE key = 'tv_muted'").fetchone()["value"]
        self.assertEqual(muted, "0")
        anon_sio.disconnect()

    def test_04_route_image_blocks_path_traversal_and_non_images(self):
        """Bloqueia Path Traversal e payloads não-imagem em /api/externos/save-image."""
        master = self._login("admin", "admin")

        # 1. Path traversal com extensão .py
        r_py = master.post("/api/externos/save-image", json={
            "filename": "../../evil.py",
            "image_base64": VALID_PNG_B64,
        })
        self.assertEqual(r_py.status_code, 400)

        # 2. Conteúdo texto disfarçado de .png
        fake_b64 = base64.b64encode(b"<script>alert(1)</script>").decode()
        r_fake = master.post("/api/externos/save-image", json={
            "filename": "ROTA_TESTE.png",
            "image_base64": fake_b64,
        })
        self.assertEqual(r_fake.status_code, 400)

        # 3. Path traversal com extensão .png é sanitizado para ficar estritamente em ROTAS_IMAGENS_DIR
        r_ok = master.post("/api/externos/save-image", json={
            "filename": "../../ROTA_SAFE_TEST.png",
            "image_base64": VALID_PNG_B64,
        })
        self.assertEqual(r_ok.status_code, 200)
        saved_name = r_ok.get_json()["filename"]
        self.assertEqual(saved_name, "ROTA_SAFE_TEST.png")
        saved_path = os.path.join(ROTAS_IMAGENS_DIR, saved_name)
        self.assertTrue(os.path.isfile(saved_path))
        try:
            os.remove(saved_path)
        except OSError:
            pass

    def test_05_sensitive_endpoints_require_auth_and_block_cross_site_youtube(self):
        """Endpoints de clientes/CNPJ/YouTube account exigem login e stream bloqueia cross-site."""
        anon = self.app.test_client()
        for method, path in (
            ("GET", "/api/cnpj/84083807000125"),
            ("GET", "/api/clients/search?q=a"),
            ("POST", "/api/clients"),
            ("POST", "/api/youtube/account"),
        ):
            r = anon.open(path, method=method, json={})
            self.assertEqual(r.status_code, 401, f"{method} {path} deveria retornar 401")

        # Rotas removidas de fotos da recepção retornam 404
        self.assertEqual(anon.get("/recepcao-fotos").status_code, 404)
        self.assertEqual(anon.post("/api/pending-entries").status_code, 404)

        # Cross-site hotlink bloqueado no YouTube proxy
        r_hotlink = anon.get(
            "/api/youtube/search?q=test",
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(r_hotlink.status_code, 403)

    def test_06_login_rate_limit_blocks_brute_force(self):
        """Após 10 tentativas inválidas de login no mesmo IP, retorna HTTP 429."""
        anon = self.app.test_client()
        for _ in range(10):
            r = anon.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
            self.assertEqual(r.status_code, 401)
        r_blocked = anon.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        self.assertEqual(r_blocked.status_code, 429)

    def test_07_delete_card_rejects_password_in_query_string(self):
        """Credenciais de exclusão na URL (query string) são ignoradas/rejeitadas para não vazar em logs."""
        master = self._login("admin", "admin")
        test_os = "998878"
        with connect() as conn:
            conn.execute("DELETE FROM cards WHERE os_number = ?", (test_os,))
        create_manual_os({"os_number": test_os, "client_name": "TESTE DEL URL", "equipment_model": "Prix 5"})
        try:
            r = master.delete(f"/api/cards/{test_os}?login=admin&senha=admin")
            self.assertEqual(r.status_code, 403)
        finally:
            with connect() as conn:
                conn.execute("DELETE FROM card_history WHERE os_number = ?", (test_os,))
                conn.execute("DELETE FROM cards WHERE os_number = ?", (test_os,))

    def test_08_security_headers_and_spa_xss_escaping(self):
        """Respostas incluem headers de segurança e _render_spa escapa </script>."""
        with connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_user', 'x</script><img src=x>')")
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_first_access_done', '1')")
        anon = self.app.test_client()
        r = anon.get("/login")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(r.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        html = r.get_data(as_text=True)
        self.assertNotIn("x</script><img", html)
        self.assertIn("\\u003c/script\\u003e", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
