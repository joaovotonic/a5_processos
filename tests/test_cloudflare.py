import unittest
from unittest.mock import patch

from kanban import config, create_app


class TestCloudflareTunnel(unittest.TestCase):
    def test_tunnel_uses_secure_cookies_and_public_intake_url(self):
        with (
            patch.object(config, "TUNNEL_MODE", True),
            patch.object(config, "TUNNEL_PUBLIC_HOSTNAME", "kanban.a5painel.cloud"),
            patch.object(config, "SOCKETIO_ASYNC_MODE", "threading"),
        ):
            app = create_app()

        app.config["TESTING"] = True
        client = app.test_client()
        health = client.get("/healthz")
        response = client.get(
            "/admin",
            headers={
                "Host": "127.0.0.1:5000",
                "X-Forwarded-Host": "kanban.a5painel.cloud",
                "X-Forwarded-Proto": "https",
            },
        )
        intake_page = client.get("/recepcao-fotos")

        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(health.get_json(), {"service": "a5-kanban", "status": "ok"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(intake_page.status_code, 200)
        self.assertIn('name="entry_photos"', intake_page.get_data(as_text=True))
        self.assertIn(
            "https://kanban.a5painel.cloud/recepcao-fotos",
            response.get_data(as_text=True),
        )


if __name__ == "__main__":
    unittest.main()
