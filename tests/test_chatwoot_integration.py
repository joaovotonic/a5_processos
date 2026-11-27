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

    def test_04_pdf_library_upload_dedup_search_and_download(self):
        """Upload de PDF no acervo deduplica por SHA-256, ordena mais recente primeiro e permite download."""
        import io
        import time

        hdr = {"X-A5-Integration-Token": "test-integration-secret-token"}
        r_unauth = self.client.post("/api/integration/pdf-library/check", json={"hashes": ["abc"]})
        self.assertEqual(r_unauth.status_code, 401)

        older_pdf = b"%PDF-1.4\n% Ordem de Servico: 099101\n% Cliente: PADARIA TESTE ALFA\n% Equipamento: PRIX 4 DUE\n%%EOF\n"
        newer_pdf = b"%PDF-1.4\n% Ordem de Servico: 099202\n% Cliente: PADARIA TESTE ALFA\n% Equipamento: PRIX 5 PLUS\n%%EOF\n"

        t_old = time.time() - 86400 * 30
        t_new = time.time() - 60

        r1 = self.client.post(
            "/api/integration/pdf-library/upload",
            headers=hdr,
            data={
                "source_rel_path": "Técnico/2026/O.S. 099101 Padaria Teste Alfa.pdf",
                "file_mtime": str(t_old),
                "file": (io.BytesIO(older_pdf), "O.S. 099101 Padaria Teste Alfa.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(r1.status_code, 200)
        d1 = r1.get_json()
        self.assertTrue(d1["success"])
        self.assertFalse(d1["deduplicated"])

        r2 = self.client.post(
            "/api/integration/pdf-library/upload",
            headers=hdr,
            data={
                "source_rel_path": "Técnico/2026/O.S. 099202 Padaria Teste Alfa.pdf",
                "file_mtime": str(t_new),
                "file": (io.BytesIO(newer_pdf), "O.S. 099202 Padaria Teste Alfa.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(r2.status_code, 200)
        d2 = r2.get_json()
        self.assertTrue(d2["success"])

        # Reenvio do mesmo arquivo deve deduplicar
        r2_dup = self.client.post(
            "/api/integration/pdf-library/upload",
            headers=hdr,
            data={
                "source_rel_path": "Técnico/2026/O.S. 099202 Padaria Teste Alfa.pdf",
                "file_mtime": str(t_new),
                "file": (io.BytesIO(newer_pdf), "O.S. 099202 Padaria Teste Alfa.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(r2_dup.status_code, 200)
        self.assertTrue(r2_dup.get_json()["deduplicated"])

        # Check batch hash
        r_chk = self.client.post(
            "/api/integration/pdf-library/check",
            headers=hdr,
            json={"hashes": [d1["sha256"], d2["sha256"], "naoexiste"]},
        )
        self.assertEqual(r_chk.status_code, 200)
        self.assertIn(d2["sha256"], r_chk.get_json()["existing"])

        # Search deve devolver 099202 (mais recente) em 1º lugar
        r_search = self.client.get(
            "/api/integration/pdf-library/search?q=Padaria+Teste+Alfa",
            headers=hdr,
        )
        self.assertEqual(r_search.status_code, 200)
        items = r_search.get_json()["items"]
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items[0]["os_number"], "099202")
        self.assertTrue(items[0]["is_latest"])

        # Download retorna o PDF real
        r_dl = self.client.get(
            f"/api/integration/pdf-library/{d2['id']}/download",
            headers=hdr,
        )
        self.assertEqual(r_dl.status_code, 200)
        self.assertEqual(r_dl.mimetype, "application/pdf")
        self.assertTrue(r_dl.data.startswith(b"%PDF-"))
        r_dl.close()

        # Limpa registros de teste da biblioteca local
        from kanban.services.pdf_library import resolve_safe_pdf_path

        for pid in (d1["id"], d2["id"]):
            fpath, _ = resolve_safe_pdf_path(pid)
            if fpath and os.path.isfile(fpath):
                os.remove(fpath)
        with connect() as conn:
            conn.execute("DELETE FROM pdf_library WHERE id IN (?, ?)", (d1["id"], d2["id"]))


if __name__ == "__main__":
    unittest.main()
