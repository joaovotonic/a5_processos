import unittest
from unittest.mock import patch

from kanban import config, create_app
from kanban.database import init_db
from tests._db_snapshot import restore_db_snapshot, take_db_snapshot


class TestCloudflareTunnel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._db_snap = take_db_snapshot()

    @classmethod
    def tearDownClass(cls):
        restore_db_snapshot(getattr(cls, "_db_snap", None))

    def test_tunnel_uses_secure_cookies_and_public_intake_url(self):
        with (
            patch.object(config, "TUNNEL_MODE", True),
            patch.object(config, "TUNNEL_PUBLIC_HOSTNAME", "kanban.a5painel.cloud"),
            patch.object(config, "SOCKETIO_ASYNC_MODE", "threading"),
        ):
            app = create_app()
            init_db()

        app.config["TESTING"] = True
        client = app.test_client()

        health = client.get("/healthz")
        removed_intake = client.get("/recepcao-fotos")

        tunnel_headers = {
            "Host": "127.0.0.1:5000",
            "X-Forwarded-Host": "kanban.a5painel.cloud",
            "X-Forwarded-Proto": "https",
        }

        # Autentica como Priscila para validar URL pública injetada no /admin autenticado
        with (
            patch.object(config, "TUNNEL_MODE", True),
            patch.object(config, "TUNNEL_PUBLIC_HOSTNAME", "kanban.a5painel.cloud"),
        ):
            r_login = client.post(
                "/api/auth/login",
                json={"username": "priscila", "password": "priscila123"},
                headers=tunnel_headers,
            )
            self.assertEqual(r_login.status_code, 200)

            response = client.get(
                "/admin",
                headers=tunnel_headers,
            )

        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(health.get_json(), {"service": "a5-kanban", "status": "ok"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(removed_intake.status_code, 404)
        self.assertIn(
            "https://kanban.a5painel.cloud",
            response.get_data(as_text=True),
        )


if __name__ == "__main__":
    unittest.main()
