"""Testes automatizados da Fase 2: bugs de VPS/Linux, alerta de senha padrão, updater GitHub e /api/ingest-pdf."""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kanban import config, create_app
from kanban.auth import reset_login_rate_limits
from kanban.database import connect, init_db
from kanban.services import tts, updater
from kanban.utils import adopt_pre_entry_photos
from tests._db_snapshot import restore_db_snapshot, take_db_snapshot


class TestPhase2VpsAndUpdater(unittest.TestCase):
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
        updater.invalidate_update_cache()

    def _login(self, username: str, password: str):
        c = self.app.test_client()
        r = c.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(r.status_code, 200)
        return c

    def test_01_adopt_pre_entry_photos_works_when_data_dir_outside_base_dir(self):
        """adopt_pre_entry_photos encontra e move fotos em UPLOAD_FOLDER mesmo com A5_DATA_DIR separado."""
        with tempfile.TemporaryDirectory() as tmp_data:
            custom_uploads = os.path.join(tmp_data, "static", "uploads")
            pre_dir = os.path.join(custom_uploads, "OS_PRE_999", "pre_entrada")
            os.makedirs(pre_dir, exist_ok=True)
            sample_file = os.path.join(pre_dir, "pre_entrada_test.jpg")
            with open(sample_file, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0fakejpg")

            with patch("kanban.utils.UPLOAD_FOLDER", custom_uploads):
                adopted = adopt_pre_entry_photos(
                    ["/static/uploads/OS_PRE_999/pre_entrada/pre_entrada_test.jpg"],
                    os_number="099999",
                    stage="entrada",
                )

            self.assertEqual(len(adopted), 1)
            self.assertEqual(adopted[0], "/static/uploads/OS_099999/entrada/entrada_test.jpg")
            dest_file = os.path.join(custom_uploads, "OS_099999", "entrada", "entrada_test.jpg")
            self.assertTrue(os.path.isfile(dest_file))
            self.assertFalse(os.path.exists(sample_file))

    def test_02_tts_cache_lives_inside_db_dir(self):
        """Cache neural Edge-TTS deve residir dentro de config.DB_DIR (persistido em A5_DATA_DIR)."""
        self.assertEqual(
            os.path.abspath(tts.CACHE_DIR),
            os.path.abspath(os.path.join(config.DB_DIR, "tts_cache")),
        )

    def test_03_default_password_warning_in_auth_me_and_clears_after_change(self):
        """Detecta senha padrão inicial em /api/auth/me e limpa o alerta após alterar a senha."""
        priscila = self._login("priscila", "priscila123")
        r_me1 = priscila.get("/api/auth/me")
        self.assertEqual(r_me1.status_code, 200)
        me1 = r_me1.get_json()
        self.assertTrue(me1["using_default_password"])
        self.assertTrue(any(u["username"] == "priscila" for u in me1["default_password_users"]))

        r_chg = priscila.post("/api/auth/change-password", json={"new_password": "NovaSenhaForte2026!"})
        self.assertEqual(r_chg.status_code, 200)

        r_me2 = priscila.get("/api/auth/me")
        me2 = r_me2.get_json()
        self.assertFalse(me2["using_default_password"])
        self.assertEqual(me2["default_password_users"], [])

        # Restaura senha original da Priscila no snapshot de teste para não afetar outros testes da mesma sessão
        priscila.post("/api/auth/change-password", json={"new_password": "priscila123"})

    def test_04_github_update_status_and_apply_permissions(self):
        """Master e Admin Recepção consultam/aplicam atualizações; Diretoria e anônimos são bloqueados."""
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/system/update-status").status_code, 401)
        self.assertEqual(anon.post("/api/system/apply-update").status_code, 401)

        jacson = self._login("jacson", "jacson123")
        self.assertEqual(jacson.get("/api/system/update-status").status_code, 403)
        self.assertEqual(jacson.post("/api/system/apply-update").status_code, 403)

        def fake_git(args, timeout=45):
            cmd = " ".join(args)
            if args[:2] == ["rev-parse", "--short"] and args[2] == "HEAD":
                return subprocess.CompletedProcess(args, 0, stdout="aaa1111\n", stderr="")
            if args[:2] == ["rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(args, 0, stdout="aaa11110000\n", stderr="")
            if args[:2] == ["log", "-1"] and "%s" in cmd:
                return subprocess.CompletedProcess(args, 0, stdout="commit atual\n", stderr="")
            if args[:2] == ["log", "-1"] and "%ci" in cmd:
                return subprocess.CompletedProcess(args, 0, stdout="2026-11-26 10:00:00 -0400\n", stderr="")
            if args[0] == "fetch":
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[:2] == ["rev-parse", "--short"] and args[2].startswith("origin/"):
                return subprocess.CompletedProcess(args, 0, stdout="bbb2222\n", stderr="")
            if args[0] == "log" and "HEAD..origin/" in args[1]:
                out = (
                    "bbb2222|feat: nova melhoria na esteira|joaovotonic|2026-11-26 11:00:00 -0400\n"
                    "ccc3333|Backup Nuvem Banco de Dados (Oficina A5) - 26/11/2026|joaovotonic|2026-11-26 10:50:00 -0400\n"
                )
                return subprocess.CompletedProcess(args, 0, stdout=out, stderr="")
            if args[:2] == ["reset", "--hard"]:
                return subprocess.CompletedProcess(args, 0, stdout="HEAD is now at bbb2222\n", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        priscila = self._login("priscila", "priscila123")
        with patch("kanban.services.updater._run_git", side_effect=fake_git):
            r_st = priscila.get("/api/system/update-status?force=1")
            self.assertEqual(r_st.status_code, 200)
            st = r_st.get_json()
            self.assertTrue(st["success"])
            self.assertTrue(st["has_update"])
            # Ignora commit puro de backup do banco na contagem de novidades de código
            self.assertEqual(st["behind_count"], 1)
            self.assertEqual(st["commits"][0]["hash"], "bbb2222")

            # Testa aplicação (sem reiniciar processo em TESTING e sem sobrescrever banco real)
            with patch("kanban.services.updater.perform_daily_backup", return_value="fake_backup.db"), \
                 patch("kanban.db_guard.checkpoint_and_snapshot", return_value={"sha256": "x"}), \
                 patch("kanban.db_guard.restore_snapshot", return_value={"sha256": "x"}), \
                 patch("kanban.db_guard.verify_post_init", return_value={"counts": {}}):
                r_apply = priscila.post("/api/system/apply-update")
                self.assertEqual(r_apply.status_code, 200)
                ap = r_apply.get_json()
                self.assertTrue(ap["success"])
                self.assertFalse(ap["restarting"])

    def test_05_ingest_pdf_token_auth_and_validation(self):
        """/api/ingest-pdf exige token ou sessão, valida cabeçalho %PDF- e aciona o parser."""
        anon = self.app.test_client()

        # Sem token -> 401
        r_noauth = anon.post(
            "/api/ingest-pdf",
            data={"kind": "oficina", "file": (io.BytesIO(b"%PDF-1.4\ntest"), "os.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(r_noauth.status_code, 401)

        with patch.dict(os.environ, {"A5_PDF_INGEST_TOKEN": "segredo-super-forte-123456"}):
            # Token errado -> 401
            r_bad = anon.post(
                "/api/ingest-pdf",
                headers={"X-A5-Ingest-Token": "errado"},
                data={"kind": "oficina", "file": (io.BytesIO(b"%PDF-1.4\ntest"), "os.pdf")},
                content_type="multipart/form-data",
            )
            self.assertEqual(r_bad.status_code, 401)

            # Arquivo que não é PDF -> 400
            r_notpdf = anon.post(
                "/api/ingest-pdf",
                headers={"X-A5-Ingest-Token": "segredo-super-forte-123456"},
                data={"kind": "oficina", "file": (io.BytesIO(b"<html>not pdf</html>"), "fake.pdf")},
                content_type="multipart/form-data",
            )
            self.assertEqual(r_notpdf.status_code, 400)

            # PDF válido com token certo -> 200 e dispara process_pdf_file
            with patch("kanban.services.pdf_watcher.process_pdf_file", return_value=True) as mock_proc:
                r_ok = anon.post(
                    "/api/ingest-pdf",
                    headers={"X-A5-Ingest-Token": "segredo-super-forte-123456"},
                    data={"kind": "oficina", "file": (io.BytesIO(b"%PDF-1.4\n%conteudo"), "os_teste.pdf")},
                    content_type="multipart/form-data",
                )
                self.assertEqual(r_ok.status_code, 200)
                body = r_ok.get_json()
                self.assertTrue(body["success"])
                self.assertTrue(body["processed"])
                mock_proc.assert_called_once()
                # Remove arquivo temporário criado no ENTRADA_PDFS_DIR pelo teste mockado
                created_path = mock_proc.call_args[0][0]
                if os.path.isfile(created_path):
                    os.remove(created_path)

    def test_06_behind_proxy_and_public_url_resolution(self):
        """A5_BEHIND_PROXY ativa SESSION_COOKIE_SECURE e A5_PUBLIC_URL resolve URLs de QR Code."""
        with (
            patch.object(config, "BEHIND_PROXY", True),
            patch.object(config, "TUNNEL_MODE", False),
            patch.object(config, "PUBLIC_URL", "https://kanban.a5painel.cloud"),
            patch.object(config, "SOCKETIO_ASYNC_MODE", "threading"),
        ):
            proxy_app = create_app()
            proxy_app.config["TESTING"] = True
            self.assertTrue(proxy_app.config["SESSION_COOKIE_SECURE"])
            c = proxy_app.test_client()
            r_me = c.get("/api/auth/me", headers={"Host": "127.0.0.1:5000"})
            self.assertEqual(r_me.status_code, 200)
            self.assertEqual(
                r_me.get_json()["config"]["public_url"],
                "https://kanban.a5painel.cloud",
            )

    def test_07_board_payload_truncates_old_finished_and_tv_omits_finished_cards(self):
        """/api/board limita FINALIZADAS a 60 por padrão, suporta ?all_finished=1 e TV omite FINALIZADAS."""
        master = self._login("admin", "admin")
        r_default = master.get("/api/board")
        self.assertEqual(r_default.status_code, 200)
        b_def = r_default.get_json()
        fin_def = next(l for l in b_def["lists"] if l.get("role") == "finalizada" or "FINALIZAD" in l["title"].upper())
        if fin_def["total_card_count"] > 60:
            self.assertEqual(len(fin_def["cards"]), 60)
            self.assertTrue(fin_def["truncated"])

            r_all = master.get("/api/board?all_finished=1")
            self.assertEqual(r_all.status_code, 200)
            fin_all = next(l for l in r_all.get_json()["lists"] if l["id"] == fin_def["id"])
            self.assertEqual(len(fin_all["cards"]), fin_def["total_card_count"])
            self.assertFalse(fin_all["truncated"])

        anon = self.app.test_client()
        r_tv = anon.get("/api/board")
        self.assertEqual(r_tv.status_code, 200)
        fin_tv = next(l for l in r_tv.get_json()["lists"] if l["id"] == fin_def["id"])
        self.assertEqual(fin_tv["cards"], [])
        self.assertEqual(fin_tv["card_count"], fin_def["total_card_count"])

    def test_08_youtube_stream_cache_eviction_cap(self):
        """Cache de streams do YouTube limita entradas para não vazar RAM na VPS."""
        from kanban.services import youtube as yt
        with yt._CACHE_LOCK:
            yt._STREAM_CACHE.clear()
            for i in range(120):
                yt._STREAM_CACHE[f"vid_{i:04d}"] = {"expires_at": 9999999999.0 + i}
            yt._prune_stream_cache_unlocked(1000.0)
            self.assertLessEqual(len(yt._STREAM_CACHE), yt._STREAM_CACHE_MAX_ENTRIES)
            yt._STREAM_CACHE.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
