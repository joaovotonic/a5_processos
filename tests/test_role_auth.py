import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kanban import create_app
from kanban.database import connect, init_db
from kanban.services.esteira import create_manual_os
from tests._db_snapshot import restore_db_snapshot, take_db_snapshot


class TestRoleBasedAuthAndPublicRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._db_snap = take_db_snapshot()
        init_db()
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        restore_db_snapshot(getattr(cls, "_db_snap", None))

    def _login(self, username: str, password: str):
        c = self.app.test_client()
        r = c.post("/api/auth/login", json={"username": username, "password": password})
        return c, r

    def test_01_public_routes_accessible_without_login(self):
        """TV, QR Code da balança (/os/<os>), pré-entrada (/recepcao-fotos), etiqueta e healthz funcionam sem login."""
        test_os = "995501"
        with connect() as conn:
            conn.execute("DELETE FROM cards WHERE os_number = ?", (test_os,))
        create_manual_os({"os_number": test_os, "client_name": "CLIENTE QR TESTE", "equipment_model": "Prix 5 Plus"})

        anon = self.app.test_client()
        for url in ("/tv", "/painel-tv", "/recepcao-fotos", "/healthz", "/login", f"/os/{test_os}", f"/etiqueta/{test_os}"):
            res = anon.get(url)
            self.assertEqual(res.status_code, 200, f"Rota pública {url} deveria abrir sem login")

        # Verifica modernização Light/Dark nos templates públicos
        tv_html = anon.get("/tv").get_data(as_text=True)
        self.assertIn("toggleTvTheme", tv_html)
        self.assertIn("theme-clean", tv_html)
        self.assertIn("ember-hatch", tv_html)
        self.assertIn("ytFloatingWidget", tv_html)

        os_html = anon.get(f"/os/{test_os}").get_data(as_text=True)
        self.assertIn("toggleTheme", os_html)
        self.assertIn("A5 Tecnologia", os_html)

        fotos_html = anon.get("/recepcao-fotos").get_data(as_text=True)
        self.assertIn("toggleTheme", fotos_html)
        self.assertIn('name="entry_photos"', fotos_html)

    def test_02_anonymous_blocked_from_protected_pages_and_apis(self):
        anon = self.app.test_client()
        for page in ("/", "/admin", "/diretoria", "/chamado"):
            res = anon.get(page, follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn("/login", res.headers["Location"])

        for endpoint in (
            ("POST", "/api/cards/manual"),
            ("GET", "/api/diretoria/report"),
            ("GET", "/api/chat/messages"),
            ("GET", "/api/externos/orders"),
            ("POST", "/api/director/call"),
            ("POST", "/api/admin/call-tech"),
        ):
            method, path = endpoint
            res = anon.open(path, method=method, json={})
            self.assertEqual(res.status_code, 401, f"{method} {path} deveria exigir autenticação")

    def test_03_jacson_only_accesses_diretoria(self):
        """Sr. Jacson (diretoria) acessa /diretoria e é bloqueado de /admin e APIs da Recepção."""
        c, r = self._login("jacson", "jacson123")
        self.assertEqual(r.status_code, 200)
        payload = r.get_json()
        self.assertEqual(payload["redirect_to"], "/diretoria")
        self.assertEqual(payload["user"]["role"], "diretoria")

        self.assertEqual(c.get("/diretoria").status_code, 200)
        self.assertEqual(c.get("/chamado").status_code, 200)

        r_home = c.get("/", follow_redirects=False)
        self.assertEqual(r_home.status_code, 302)
        self.assertTrue(r_home.headers["Location"].endswith("/diretoria"))

        r_admin = c.get("/admin", follow_redirects=False)
        self.assertEqual(r_admin.status_code, 302)
        self.assertTrue(r_admin.headers["Location"].endswith("/diretoria"))

        self.assertEqual(c.get("/api/diretoria/report").status_code, 200)
        self.assertEqual(c.get("/api/analytics").status_code, 200)
        self.assertEqual(c.post("/api/admin/panic-silence", json={"muted": False}).status_code, 403)
        self.assertEqual(c.post("/api/cards/manual", json={"os_number": "1", "client_name": "X"}).status_code, 403)
        self.assertEqual(c.get("/api/backup/github-status").status_code, 403)

    def test_04_priscila_only_accesses_admin(self):
        """Priscila (admin_recepcao) acessa /admin e é bloqueada de /diretoria e APIs exclusivas da Diretoria."""
        c, r = self._login("priscila", "priscila123")
        self.assertEqual(r.status_code, 200)
        payload = r.get_json()
        self.assertEqual(payload["redirect_to"], "/admin")
        self.assertEqual(payload["user"]["role"], "admin_recepcao")

        self.assertEqual(c.get("/admin").status_code, 200)

        r_home = c.get("/", follow_redirects=False)
        self.assertEqual(r_home.status_code, 302)
        self.assertTrue(r_home.headers["Location"].endswith("/admin"))

        for dir_url in ("/diretoria", "/chamado"):
            r_block = c.get(dir_url, follow_redirects=False)
            self.assertEqual(r_block.status_code, 302)
            self.assertTrue(r_block.headers["Location"].endswith("/admin"))

        self.assertEqual(c.get("/api/backup/github-status").status_code, 200)
        self.assertEqual(c.post("/api/admin/panic-silence", json={"muted": False}).status_code, 200)
        self.assertEqual(c.get("/api/diretoria/report").status_code, 403)
        self.assertEqual(c.get("/api/analytics").status_code, 403)
        self.assertEqual(c.get("/api/export/csv?period=day").status_code, 403)
        self.assertEqual(c.post("/api/externos/routes/save", json={}).status_code, 403)

    def test_05_master_accesses_both_panels_and_all_apis(self):
        c, r = self._login("admin", "admin")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["user"]["role"], "master")

        self.assertEqual(c.get("/admin").status_code, 200)
        self.assertEqual(c.get("/diretoria").status_code, 200)
        self.assertEqual(c.get("/api/diretoria/report").status_code, 200)
        self.assertEqual(c.get("/api/backup/github-status").status_code, 200)
        self.assertEqual(c.get("/api/auth/users").status_code, 200)

    def test_06_etiqueta_qr_resolves_for_lan_and_cloudflare_and_opens_os_mobile(self):
        """QR Code da etiqueta nunca usa localhost/127.0.0.1, respeita Cloudflare/Proxy, usa JS local e abre /os/<os> sem login."""
        import re
        from unittest.mock import patch
        from urllib.parse import urlparse
        from kanban import config

        with connect() as conn:
            conn.execute("DELETE FROM cards WHERE os_number IN ('026991', '26991')")
        create_manual_os({"os_number": "26991", "client_name": "TESTE QR CLOUD", "equipment_model": "PRIX 5"})

        anon = self.app.test_client()
        try:
            # 1. Busca sem zero à esquerda também abre etiqueta (antes dava 404)
            r_local = anon.get("/etiqueta/26991", headers={"Host": "127.0.0.1:5000"})
            self.assertEqual(r_local.status_code, 200)
            html_local = r_local.get_data(as_text=True)
            self.assertIn("/static/js/qrcode.min.js", html_local)
            self.assertNotIn("cdnjs.cloudflare.com", html_local)
            m_local = re.search(r'qrText\s*=\s*"([^"]+)"', html_local)
            self.assertIsNotNone(m_local)
            qr_local = m_local.group(1)
            self.assertNotIn("127.0.0.1", qr_local)
            self.assertNotIn("localhost", qr_local)
            self.assertTrue(qr_local.endswith("/os/026991"))

            # 2. Com headers de Túnel Cloudflare (mesmo sem TUNNEL_MODE=True), gera URL HTTPS pública do túnel
            r_cf = anon.get(
                "/etiqueta/026991",
                headers={
                    "Host": "127.0.0.1:5000",
                    "X-Forwarded-Host": "teste-a5.trycloudflare.com",
                    "X-Forwarded-Proto": "https",
                },
            )
            self.assertEqual(r_cf.status_code, 200)
            html_cf = r_cf.get_data(as_text=True)
            self.assertIn('"https://teste-a5.trycloudflare.com/os/026991"', html_cf)

            # 3. Com TUNNEL_MODE=True e hostname fixo, usa sempre o hostname HTTPS público mesmo acessando via localhost
            with (
                patch.object(config, "TUNNEL_MODE", True),
                patch.object(config, "TUNNEL_PUBLIC_HOSTNAME", "kanban.a5painel.cloud"),
            ):
                r_prod = anon.get("/etiqueta/026991", headers={"Host": "localhost:5000"})
                self.assertEqual(r_prod.status_code, 200)
                self.assertIn('"https://kanban.a5painel.cloud/os/026991"', r_prod.get_data(as_text=True))

            # 4. Abrindo a exata rota codificada no QR Code (/os/026991) sem login e avançando esteira
            target_path = urlparse(qr_local).path
            r_os = anon.get(target_path)
            self.assertEqual(r_os.status_code, 200)
            self.assertIn("TESTE QR CLOUD", r_os.get_data(as_text=True))

            r_claim = anon.post("/api/esteira/claim-orcamento", json={"os_number": "026991", "tecnico": "Enzo"})
            self.assertEqual(r_claim.status_code, 200)
            self.assertTrue(r_claim.get_json()["success"])

            # 5. O.S. inexistente retorna HTML mobile amigável 404 (e não JSON bruto)
            r_missing = anon.get("/os/99999999")
            self.assertEqual(r_missing.status_code, 404)
            self.assertIn("Ordem de Serviço não localizada", r_missing.get_data(as_text=True))
        finally:
            with connect() as conn:
                conn.execute("DELETE FROM card_history WHERE os_number = '026991'")
                conn.execute("DELETE FROM cards WHERE os_number = '026991'")

    def test_07_tech_budget_timer_and_tv_light_blue_and_admin_drag(self):
        """Técnico pode acionar Estufa/Teste ao iniciar orçamento; Admin sem timer no card e drag no card inteiro; TV em azul claro."""
        test_os = "995502"
        with connect() as conn:
            conn.execute("DELETE FROM card_history WHERE os_number = ?", (test_os,))
            conn.execute("DELETE FROM cards WHERE os_number = ?", (test_os,))
        create_manual_os({"os_number": test_os, "client_name": "CLIENTE ESTUFA TESTE", "equipment_model": "Prix 4 Uno"})

        anon = self.app.test_client()
        try:
            # 1. Na tela de escolher técnico para orçamento já existe opção opcional de Estufa/Teste
            r_wait = anon.get(f"/os/{test_os}")
            self.assertEqual(r_wait.status_code, 200)
            wait_html = r_wait.get_data(as_text=True)
            self.assertIn("Iniciar já com Estufa ou Teste?", wait_html)
            self.assertIn("setPreTimerMode", wait_html)

            # 2. Técnico assume orçamento e inicia cronômetro sem precisar de login
            r_claim = anon.post("/api/esteira/claim-orcamento", json={"os_number": test_os, "tecnico": "Enzo"})
            self.assertEqual(r_claim.status_code, 200)
            self.assertTrue(r_claim.get_json()["success"])

            r_orc_html = anon.get(f"/os/{test_os}")
            self.assertEqual(r_orc_html.status_code, 200)
            orc_html = r_orc_html.get_data(as_text=True)
            self.assertIn("Estufa / Teste na TV", orc_html)
            self.assertIn("Estufa de Placa", orc_html)
            self.assertIn("Teste em Bancada", orc_html)

            r_start = anon.post("/api/timer/start", json={"os_number": "995502", "minutes": 30, "label": "Teste em Bancada"})
            self.assertEqual(r_start.status_code, 200)
            self.assertTrue(r_start.get_json()["success"])

            r_active_html = anon.get(f"/os/{test_os}")
            self.assertIn("Cancelar Cronômetro", r_active_html.get_data(as_text=True))

            r_cancel = anon.post("/api/timer/cancel", json={"os_number": test_os})
            self.assertEqual(r_cancel.status_code, 200)

            # 3. TV repaginada com azul claro nos dois modos, layout compacto 1080p, Motion techs/YouTube e popout azul claro
            tv_html = anon.get("/tv").get_data(as_text=True)
            self.assertIn("#38BDF8", tv_html)
            self.assertIn("sky-400", tv_html)
            self.assertIn("Som da Oficina", tv_html)
            self.assertIn("enterTechRow", tv_html)
            self.assertIn("exitTechRow", tv_html)
            self.assertIn("openYtWidgetMotion", tv_html)
            self.assertIn("closeYtWidgetMotion", tv_html)
            self.assertIn("w-[248px]", tv_html)

            # 4. CardDetailModal sem controles de Estufa/Teste e KanbanCardItem arrastável pelo card inteiro
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            with open(os.path.join(base_dir, "frontend", "src", "components", "admin", "CardDetailModal.tsx"), "r", encoding="utf-8") as f:
                detail_src = f.read()
            self.assertNotIn("Cronômetro de Estufa", detail_src)
            self.assertNotIn("/api/timer/start", detail_src)

            with open(os.path.join(base_dir, "frontend", "src", "components", "admin", "KanbanCardItem.tsx"), "r", encoding="utf-8") as f:
                card_src = f.read()
            self.assertIn("{...attributes}\n      {...listeners}", card_src)

            with open(os.path.join(base_dir, "frontend", "src", "components", "admin", "KanbanBoard.tsx"), "r", encoding="utf-8") as f:
                board_src = f.read()
            self.assertIn("SmartPointerSensor", board_src)

            # 5. AdminPage conecta Pré-Entrada, Chamar TV e Silenciar TV + NewOsModal aceita initialEntry
            with open(os.path.join(base_dir, "frontend", "src", "pages", "AdminPage.tsx"), "r", encoding="utf-8") as f:
                admin_src = f.read()
            self.assertIn("PendingPhotosModal", admin_src)
            self.assertIn("CallTechModal", admin_src)
            self.assertIn("/api/admin/panic-silence", admin_src)

            with open(os.path.join(base_dir, "frontend", "src", "components", "admin", "NewOsModal.tsx"), "r", encoding="utf-8") as f:
                newos_src = f.read()
            self.assertIn("pending_entry_id", newos_src)
            self.assertIn("initialEntry", newos_src)
        finally:
            with connect() as conn:
                conn.execute("DELETE FROM card_history WHERE os_number = ?", (test_os,))
                conn.execute("DELETE FROM cards WHERE os_number = ?", (test_os,))

    def test_08_tv_lite_optimization_fade_and_brief_notifications(self):
        """TV sem confete/blur/rodapé prontas, com esmaecer, data entrada maior e avisos breves."""
        from unittest.mock import patch
        from kanban import realtime

        anon = self.app.test_client()
        tv_html = anon.get("/tv").get_data(as_text=True)

        # Removidos por performance / solicitação
        self.assertNotIn("canvas-confetti", tv_html)
        self.assertNotIn("confetti(", tv_html)
        self.assertNotIn("backdrop-filter: blur", tv_html)
        self.assertNotIn("backdrop-blur-", tv_html)
        self.assertNotIn("tvFooterTicker", tv_html)
        self.assertNotIn("Prontas p/ Retirada", tv_html)

        # Recursos adicionados: esmaecer + data de entrada maior
        self.assertIn("fadeSwap(", tv_html)
        self.assertIn("fadeIn(", tv_html)
        self.assertIn("fadeOut(", tv_html)
        self.assertIn("Entrada: ${esc(entryInfo.dateStr)}", tv_html)
        self.assertIn("xl:text-[14px]", tv_html)

        # Notificações TTS breves
        captured = []
        with patch("kanban.realtime.get_neural_audio_base64", return_value=None), patch("kanban.realtime._emit_safe", side_effect=lambda ev, pl: captured.append((ev, pl))):
            realtime.announce_arrival({"os_number": "77123", "client_name": "CLIENTE A", "equipment_type": "Balança"}, "ORÇAMENTO")
            realtime.announce_arrival({"os_number": "77123", "client_name": "CLIENTE A", "equipment_type": "Balança"}, "APROVADA")
            realtime.announce_finished_mobile("77123", "CLIENTE A", "TEC. GUILHERME", "123", 1)
            realtime.announce_finished_on_board({"os_number": "77124", "client_name": "CLIENTE B", "tech_name": "TEC. ENZO"}, "Priscila", 2)

        tts_list = [pl["tts_text"] for ev, pl in captured if ev == "tv_announcement"]
        self.assertEqual(tts_list[0], "O.S. 77123 para orçamento.")
        self.assertEqual(tts_list[1], "O.S. 77123 aprovada.")
        self.assertEqual(tts_list[2], "O.S. 77123 finalizada pelo técnico Guilherme.")
        self.assertEqual(tts_list[3], "O.S. 77124 finalizada pelo técnico Enzo.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
