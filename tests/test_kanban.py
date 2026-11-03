"""
Comprehensive Production Test Suite - A5 Kanban (Toledo Prix).
Validates 100% of routes, APIs, WebSockets, Backlog Items 1-17, metrology rules, and business flows.
"""
import io
import json
import os
import sys
import unittest

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from kanban import create_app
from kanban import database as db
from kanban.database import connect
from kanban.extensions import socketio
from kanban.rules import arrival_stage, is_approved_list, is_finished_list, is_ready_list, is_tech_list
from kanban.services.board import detect_weight_unit, enrich_card, get_analytics_summary, get_full_board, normalize_quote_data
from kanban.services.parts import load_parts_catalog, search_parts
from kanban.services.scales import evaluate_weight_test, get_scale_division, search_scale_models


class TestA5KanbanComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        db.init_db()
        cls.client = cls.app.test_client()
        cls.sio = socketio.test_client(cls.app)
        # Limpa dados de teste anteriores se houver
        with connect() as conn:
            conn.execute("DELETE FROM card_history WHERE os_number = '990001'")
            conn.execute("DELETE FROM cards WHERE os_number = '990001'")
            conn.execute("DELETE FROM pending_entries WHERE client_name LIKE '%PADARIA CENTRAL%'")

    def test_01_http_pages(self):
        """Testa todas as páginas web do sistema."""
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/admin"))

        pages = [
            "/admin",
            "/painel-tv",
            "/tv",
            "/saida",
            "/saida?os=026736",
            "/consulta",
            "/gerencia",
            "/recepcao",
            "/recepcao-fotos",
            "/diretoria",
            "/chamado",
            "/apresentacao",
        ]
        for p in pages:
            res = self.client.get(p)
            self.assertEqual(res.status_code, 200, f"Falha ao carregar página {p}")

    def test_02_catalogs_and_search(self):
        """Testa busca de peças Toledo e catálogo de modelos de balanças."""
        catalog = load_parts_catalog()
        self.assertGreater(len(catalog), 2000, "Catálogo de peças Toledo deve conter mais de 2.000 itens")

        res_parts = self.client.get("/api/parts/search?q=teclado prix")
        self.assertEqual(res_parts.status_code, 200)
        data_parts = res_parts.get_json()
        self.assertTrue("parts" in data_parts)
        self.assertGreater(len(data_parts["parts"]), 0)

        res_scales = self.client.get("/api/scales/search?q=prix")
        self.assertEqual(res_scales.status_code, 200)
        data_scales = res_scales.get_json()
        self.assertTrue("scales" in data_scales)
        self.assertGreater(len(data_scales["scales"]), 0)
        first_scale = data_scales["scales"][0]
        self.assertIn("model_name", first_scale)
        self.assertIn("division_rule", first_scale)

    def test_03_metrology_tolerance_rule(self):
        """Testa regra de tolerância metrológica de 2 incrementos (±2e)."""
        div, unit = get_scale_division(1.0, unit="kg", model_str="Prix 5 Plus")
        self.assertAlmostEqual(div, 0.002)

        eval_ok = evaluate_weight_test("1kg", 1.002, model_str="Prix 5 Plus", unit="kg")
        self.assertFalse(eval_ok["is_outside_tolerance"])
        self.assertEqual(eval_ok["status"], "DENTRO_DA_TOLERANCIA")

        eval_edge = evaluate_weight_test("1kg", 1.004, model_str="Prix 5 Plus", unit="kg")
        self.assertFalse(eval_edge["is_outside_tolerance"])

        eval_fail = evaluate_weight_test("1kg", 1.006, model_str="Prix 5 Plus", unit="kg")
        self.assertTrue(eval_fail["is_outside_tolerance"])
        self.assertEqual(eval_fail["status"], "FORA_DA_ESPECIFICACAO")

        eval_analytic_ok = evaluate_weight_test("1g", 1.02, model_str="Marte 510g", unit="g")
        self.assertFalse(eval_analytic_ok["is_outside_tolerance"])

        eval_analytic_fail = evaluate_weight_test("1g", 1.05, model_str="Marte 510g", unit="g")
        self.assertTrue(eval_analytic_fail["is_outside_tolerance"])

    def test_04_board_structure_and_ready_list(self):
        """Testa estrutura do quadro e presença de BALANÇAS PRONTAS antes de FINALIZADAS."""
        res = self.client.get("/api/board")
        self.assertEqual(res.status_code, 200)
        board = res.get_json()

        titles = [l["title"] for l in board["lists"]]
        self.assertIn("ORÇAMENTOS", titles)
        self.assertIn("APROVADAS", titles)
        self.assertIn("BALANÇAS PRONTAS", titles)
        self.assertIn("FINALIZADAS", titles)

        idx_prontas = titles.index("BALANÇAS PRONTAS")
        idx_finalizadas = titles.index("FINALIZADAS")
        self.assertLess(idx_prontas, idx_finalizadas, "BALANÇAS PRONTAS deve vir antes de FINALIZADAS")

    def test_05_complete_card_lifecycle(self):
        """Ciclo completo de vida de uma O.S.: criação, claim, orçamento, reabertura, aprovação, finalização mobile, conferência admin."""
        test_os = "990001"

        # 1. Pré-Entrada de fotos na recepção
        r_pre = self.client.post("/api/pending-entries", data={
            "client_name": "PADARIA CENTRAL DE TESTES",
            "equipment_type": "Balança Toledo Prix",
            "equipment_model": "Prix 5 Plus",
            "reported_defect": "Diferença de peso",
            "entry_photos": [(io.BytesIO(b"fake_pre_image"), "pre1.jpg")],
        }, content_type="multipart/form-data")
        self.assertEqual(r_pre.status_code, 200)
        pre_id = r_pre.get_json()["entry"]["id"]

        # 2. Criação da O.S. vinculando à pré-entrada
        r_create = self.client.post("/api/cards", data={
            "os_number": test_os,
            "client_name": "PADARIA CENTRAL DE TESTES",
            "equipment_type": "Balança Toledo Prix",
            "equipment_model": "Prix 5 Plus",
            "shelf_location": "Bancada 01",
            "reported_defect": "Diferença de peso",
            "pending_entry_id": str(pre_id),
            "entry_photos": [(io.BytesIO(b"fake_entry_image"), "ent1.jpg")],
        }, content_type="multipart/form-data")
        self.assertEqual(r_create.status_code, 200)
        card = r_create.get_json()["card"]
        card_id = card["id"]
        self.assertEqual(card["os_number"], test_os)
        self.assertEqual(card["quote_status"], "pending_claim")

        # 3. Atualização dos dados cadastrais
        r_upd = self.client.post(f"/api/cards/{card_id}/update", json={
            "client_name": "PADARIA CENTRAL MATRIZ",
            "serial_number": "SN-TOLEDO-7788",
            "shelf_location": "Prateleira A-02",
            "admin_notes": "Cliente solicitou urgência máxima para entrega amanhã cedo.",
            "reported_defect": "Diferença de peso e falha no teclado",
            "previous_service": "Troca de cabeça térmica em 2025",
        })
        self.assertEqual(r_upd.status_code, 200)
        updated_card = r_upd.get_json()["card"]
        self.assertEqual(updated_card["client_name"], "PADARIA CENTRAL MATRIZ")
        self.assertEqual(updated_card["admin_notes"], "Cliente solicitou urgência máxima para entrega amanhã cedo.")
        self.assertEqual(updated_card["shelf_location"], "Prateleira A-02")

        # 4. Impressões
        r_etiq = self.client.get(f"/etiqueta/{test_os}")
        self.assertEqual(r_etiq.status_code, 200)
        self.assertIn("PADARIA CENTRAL MATRIZ", r_etiq.get_data(as_text=True))

        r_folha = self.client.get(f"/folha/{test_os}")
        self.assertEqual(r_folha.status_code, 200)
        self.assertIn("PADARIA CENTRAL MATRIZ", r_folha.get_data(as_text=True))

        # 5. Técnico assume no celular
        r_claim = self.client.post("/api/saida/assumir", json={
            "os_number": test_os,
            "tech_name": "TEC. Enzo Gabriel",
            "phase": "quote",
        })
        self.assertEqual(r_claim.status_code, 200)
        claimed_card = r_claim.get_json()["card"]
        self.assertEqual(claimed_card["evaluator_tech"], "TEC. Enzo Gabriel")
        self.assertEqual(claimed_card["quote_status"], "in_progress")

        # 6. Técnico preenche Orçamento Digital
        quote_payload = {
            "weight_unit": "kg",
            "incoming_seal": {"type": "IPEM", "number": "12345678"},
            "incoming_stamp": {"type": "A5", "number": "00.123.456-7"},
            "weights_initial": {"1kg": "0.998", "5kg": "5.000", "15kg": "15.002"},
            "technical_report": "Balança com diferença de peso na primeira faixa e acúmulo de gordura no prato.",
            "parts_items": [{"qty": 1, "code": "3450042", "description": "Anel O'Ring 7,5mmx2,5mm"}],
            "service_checks": {"revisao_geral": True, "calibracao_afericao": True},
        }
        r_quote = self.client.post("/api/saida/orcamento", data={
            "os_number": test_os,
            "tech_name": "TEC. Enzo Gabriel",
            "finalize": "1",
            "quote_data_json": json.dumps(quote_payload),
            "label_before_photos": [(io.BytesIO(b"fake_label_before"), "label_before.jpg")],
            "quote_photos": [(io.BytesIO(b"fake_quote_photo"), "quote1.jpg")],
        }, content_type="multipart/form-data")
        self.assertEqual(r_quote.status_code, 200)
        q_card = r_quote.get_json()["card"]
        self.assertEqual(q_card["quote_status"], "done")

        # 7. Reabertura
        r_req_reopen = self.client.post(f"/api/cards/{card_id}/request-reopen", json={"actor": "TEC. Enzo Gabriel"})
        self.assertEqual(r_req_reopen.status_code, 200)
        self.assertEqual(r_req_reopen.get_json()["card"]["reopen_requested"], 1)

        r_lib_reopen = self.client.post(f"/api/cards/{card_id}/reopen-quote", json={"actor": "Priscila (Recepção)"})
        self.assertEqual(r_lib_reopen.status_code, 200)
        self.assertEqual(r_lib_reopen.get_json()["card"]["quote_status"], "in_progress")

        # Re-conclui
        self.client.post("/api/saida/orcamento", data={
            "os_number": test_os,
            "tech_name": "TEC. Enzo Gabriel",
            "finalize": "1",
            "quote_data_json": json.dumps(quote_payload),
        })

        # 8. Recepção envia orçamento ao cliente
        r_send = self.client.post(f"/api/cards/{card_id}/send-quote", json={"actor": "Priscila (Recepção)"})
        self.assertEqual(r_send.status_code, 200)
        c_sent = self.client.get(f"/api/cards/{test_os}").get_json()
        self.assertEqual(c_sent["list_title"], "ORÇAMENTOS ENVIADOS")

        # 9. Aprovação
        r_appr = self.client.post(f"/api/cards/{card_id}/approve-quote", json={"actor": "Priscila (Recepção)"})
        self.assertEqual(r_appr.status_code, 200)
        c_appr = self.client.get(f"/api/cards/{test_os}").get_json()
        self.assertEqual(c_appr["list_title"], "APROVADAS")
        self.assertEqual(c_appr["quote_status"], "approved")

        # 10. Cronômetro de Estufa e cancelamento
        r_timer = self.client.post("/api/timer/start", json={
            "os_number": test_os,
            "minutes": 45,
            "label": "Estufa Placa Principal",
        })
        self.assertEqual(r_timer.status_code, 200)
        self.assertTrue("end_time" in r_timer.get_json())

        r_cancel = self.client.post("/api/timer/cancel", json={"os_number": test_os})
        self.assertEqual(r_cancel.status_code, 200)

        # 11. Finalização mobile -> BALANÇAS PRONTAS
        r_finish = self.client.post("/api/saida/finalizar", data={
            "os_number": test_os,
            "tech_name": "TEC. Enzo Gabriel",
            "pop_calibration": "1",
            "pop_cleaning": "1",
            "inmetro_seal": "00.999.888-1",
            "parts_used": "1x [3450042] Anel O'Ring",
            "solution": "Calibração de peso concluída e limpeza completa realizada.",
            "shelf_location": "Prateleira Saída 01",
            "weights_final_json": json.dumps({"1kg": "1.000", "5kg": "5.000", "15kg": "15.000"}),
            "exit_photos": [(io.BytesIO(b"fake_exit_photo"), "exit1.jpg")],
        }, content_type="multipart/form-data")
        self.assertEqual(r_finish.status_code, 200)

        c_fin = self.client.get(f"/api/cards/{test_os}").get_json()
        self.assertEqual(c_fin["list_title"], "BALANÇAS PRONTAS")
        self.assertEqual(c_fin["inmetro_seal"], "00.999.888-1")

        # 12. Priscila confere e finaliza -> FINALIZADAS
        r_admin_fin = self.client.post(f"/api/cards/{card_id}/finalize-admin", json={"actor": "Priscila (Recepção)"})
        self.assertEqual(r_admin_fin.status_code, 200)
        c_arch = self.client.get(f"/api/cards/{test_os}").get_json()
        self.assertEqual(c_arch["list_title"], "FINALIZADAS")
        self.assertIsNotNone(c_arch["finished_at"])

        # 13. Cancelamento
        r_cancel = self.client.post(f"/api/cards/{card_id}/cancel", json={"reason": "Cliente desistiu da manutenção"})
        self.assertEqual(r_cancel.status_code, 200)
        c_canc = self.client.get(f"/api/cards/{test_os}").get_json()
        self.assertIn("NÃO AUTORIZADO", c_canc["list_title"])
        self.assertEqual(c_canc["quote_status"], "cancelled")

        # 14. Exclusão com autorização
        r_del_fail = self.client.delete(f"/api/cards/{card_id}")
        self.assertEqual(r_del_fail.status_code, 403)

        r_del_wrong = self.client.delete(f"/api/cards/{card_id}", json={"login": "admin", "senha": "123"})
        self.assertEqual(r_del_wrong.status_code, 403)

        r_del_ok = self.client.delete(f"/api/cards/{card_id}", json={"login": "admin", "senha": "admin"})
        self.assertEqual(r_del_ok.status_code, 200)

        r_get_deleted = self.client.get(f"/api/cards/{test_os}")
        self.assertEqual(r_get_deleted.status_code, 404)

    def test_06_analytics_and_csv_export(self):
        """Testa geração de métricas da gerência e exportação de CSV."""
        r_an = self.client.get("/api/analytics")
        self.assertEqual(r_an.status_code, 200)
        an = r_an.get_json()
        self.assertIn("daily_count", an)
        self.assertIn("tech_ranking", an)

        r_csv = self.client.get("/api/export/csv?period=all")
        self.assertEqual(r_csv.status_code, 200)
        csv_text = r_csv.get_data(as_text=True)
        self.assertIn("Nº O.S.", csv_text)
        self.assertIn("Cliente", csv_text)

    def test_07_websocket_events(self):
        """Testa eventos de WebSocket da TV e chamadas de bancada."""
        self.sio.emit("call_tech_reception", {"tech_name": "TEC. Enzo Gabriel", "reason": "Dúvida no orçamento"})
        self.sio.emit("director_call_tech", {"tech_name": "SR. JACSON", "message": "Comparecer na diretoria", "is_urgent": True})
        self.sio.emit("request_bench_support", {"tech_name": "TEC. Guilherme", "os_number": "026736"})
        self.sio.emit("panic_silence_tv", {"muted": True})

        recv = self.sio.get_received()
        names = [e["name"] for e in recv]
        self.assertIn("tv_announcement", names)
        self.assertIn("tv_mute_changed", names)

        # Restaura tv_muted para False para não deixar a TV mutada após o teste
        self.sio.emit("panic_silence_tv", {"muted": False})

        # Testa chamada REST da diretoria
        r_dir = self.client.post("/api/director/call", json={
            "tech_name": "TEC. ANTONIO",
            "message": "Favor trazer O.S.",
            "is_urgent": False
        })
        self.assertEqual(r_dir.status_code, 200)

    def test_08_cnpj_and_client_intake(self):
        """Testa busca de CNPJ, cadastro de cliente e comprovante A4 estilo Teorema."""
        # 1. Testa endpoint de CNPJ com formato inválido
        r_invalid = self.client.get("/api/cnpj/123")
        self.assertEqual(r_invalid.status_code, 400)

        # 2. Testa cadastro manual de cliente
        r_client = self.client.post("/api/clients", json={
            "cnpj_cpf": "84083807000125",
            "client_name": "A G TAVARES - EPP",
            "trade_name": "SUPERMERCADO BOM PRECO",
            "phone": "(92) 3011-9537",
            "city_state": "MANACAPURU / AM"
        })
        self.assertEqual(r_client.status_code, 200)
        c_data = r_client.get_json()["client"]
        self.assertEqual(c_data["client_name"], "A G TAVARES - EPP")

        # 3. Testa busca de autocompletar
        r_search = self.client.get("/api/clients/search?q=BOM+PRECO")
        self.assertEqual(r_search.status_code, 200)
        results = r_search.get_json()["clients"]
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["trade_name"], "SUPERMERCADO BOM PRECO")

        # 4. Testa criação de pré-entrada com CNPJ e acessórios
        r_pre = self.client.post("/api/pending-entries", data={
            "client_name": "A G TAVARES - EPP",
            "trade_name": "SUPERMERCADO BOM PRECO",
            "cnpj_cpf": "84083807000125",
            "equipment_type": "Balança Toledo Prix",
            "equipment_model": "Prix 4 Uno",
            "reported_defect": "Não liga",
            "accessories_json": json.dumps(["prato", "fonte"]),
            "entry_photos": [(io.BytesIO(b"fake_pre_image"), "pre1.jpg")]
        }, content_type="multipart/form-data")
        self.assertEqual(r_pre.status_code, 200)
        entry_id = r_pre.get_json()["entry"]["id"]

        # 5. Testa visualização do comprovante A4
        r_a4 = self.client.get(f"/comprovante-entrada/{entry_id}")
        self.assertEqual(r_a4.status_code, 200)
        html = r_a4.get_data(as_text=True)
        self.assertIn("A G TAVARES", html)
        self.assertIn("SUPERMERCADO BOM PRECO", html)
        self.assertIn("PRATO INOX", html)

        # 6. Testa rotas /recepcao e /recepcao-fotos
        for route in ["/recepcao", "/recepcao-fotos"]:
            r_page = self.client.get(route)
            self.assertEqual(r_page.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)

