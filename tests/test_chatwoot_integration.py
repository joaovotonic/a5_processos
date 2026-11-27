"""Testes da integração bidirecional Esteira A5 <-> Chatwoot / WhatsApp."""
import os
import unittest
from unittest.mock import patch

from kanban import create_app
from kanban.database import connect, init_db
from kanban.routes.integrations import compute_chatwoot_dashboard_token


class TestChatwootIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["A5_PDF_INGEST_TOKEN"] = "test-integration-secret-token"
        init_db()
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_01_os_lookup_requires_auth_and_works_with_tokens(self):
        """GET /api/integration/os-lookup bloqueia anônimos e aceita token de integração ou dashboard."""
        r_anon = self.client.get("/api/integration/os-lookup?q=999999")
        self.assertEqual(r_anon.status_code, 401)

        with connect() as conn:
            sample = conn.execute("SELECT os_number, client_name FROM cards ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(sample)

        r_tok = self.client.get(
            f"/api/integration/os-lookup?q={sample['os_number']}",
            headers={"X-A5-Integration-Token": "test-integration-secret-token"},
        )
        self.assertEqual(r_tok.status_code, 200)
        data = r_tok.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 1)
        first = data["items"][0]
        self.assertEqual(first["os_number"], sample["os_number"])
        self.assertIn("suggested_whatsapp_reply", first)
        self.assertIn("stage_label", first)

        dash_tok = compute_chatwoot_dashboard_token()
        r_dash = self.client.get(
            f"/api/integration/os-lookup?q={sample['os_number']}",
            headers={"X-A5-Dashboard-Token": dash_tok},
        )
        self.assertEqual(r_dash.status_code, 200)

    def test_02_chatwoot_dashboard_page_headers_and_auth(self):
        """GET /integracao/chatwoot exige token e libera iframe somente para chat.a5painel.cloud."""
        r_unauth = self.client.get("/integracao/chatwoot")
        self.assertEqual(r_unauth.status_code, 401)

        dash_tok = compute_chatwoot_dashboard_token()
        r_ok = self.client.get(f"/integracao/chatwoot?token={dash_tok}")
        self.assertEqual(r_ok.status_code, 200)
        csp = r_ok.headers.get("Content-Security-Policy", "")
        self.assertIn("frame-ancestors", csp)
        self.assertIn("https://chat.a5painel.cloud", csp)
        self.assertNotIn("X-Frame-Options", r_ok.headers)

    def test_03_notify_whatsapp_requires_staff_session_and_proxies_bridge(self):
        """POST /api/integration/notify-whatsapp exige login staff e envia payload para a ponte."""
        r_anon = self.client.post(
            "/api/integration/notify-whatsapp",
            json={"phone": "92984123456", "message": "Teste"},
        )
        self.assertEqual(r_anon.status_code, 401)

        with self.client.session_transaction() as sess:
            sess["user"] = {
                "username": "master",
                "display_name": "Master",
                "role": "master",
                "home_route": "/admin",
            }

        class _FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"success": true, "delivered_via": "chatwoot"}'

        with patch("urllib.request.urlopen", return_value=_FakeResp()) as mock_open:
            r_ok = self.client.post(
                "/api/integration/notify-whatsapp",
                json={
                    "os_number": "12345",
                    "client_name": "CLIENTE TESTE",
                    "phone": "(92) 98412-3456",
                    "message": "Sua balança está pronta!",
                    "inbox": "laboratorio",
                },
            )
            self.assertEqual(r_ok.status_code, 200)
            self.assertTrue(r_ok.get_json()["success"])
            self.assertEqual(mock_open.call_count, 1)


if __name__ == "__main__":
    unittest.main()
