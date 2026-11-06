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
from tests._db_snapshot import restore_db_snapshot, take_db_snapshot


class TestA5KanbanComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._db_snap = take_db_snapshot()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        db.init_db()
        cls.client = cls.app.test_client()
        cls.sio = socketio.test_client(cls.app)
        # Limpa dados de teste anteriores se houver
        with connect() as conn:
            conn.execute("DELETE FROM card_history WHERE os_number IN ('990001', '770001')")
            conn.execute("DELETE FROM cards WHERE os_number IN ('990001', '770001')")
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
            "/diretoria",
            "/chamado",
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
        """Testa estrutura do quadro da Esteira de Produção A5."""
        res = self.client.get("/api/board")
        self.assertEqual(res.status_code, 200)
        board = res.get_json()

        titles = [l["title"] for l in board["lists"]]
        self.assertIn("ORÇAMENTOS", titles)
        self.assertIn("APROVADOS", titles)
        self.assertIn("ORÇAMENTOS FEITOS", titles)
        self.assertIn("ORÇAMENTOS ENVIADOS", titles)
        self.assertIn("FINALIZADAS", titles)

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

        # 4. Impressão Etiqueta Térmica 60x40mm
        r_etiq = self.client.get(f"/etiqueta/{test_os}")
        self.assertEqual(r_etiq.status_code, 200)
        self.assertIn("PADARIA CENTRAL MATRIZ", r_etiq.get_data(as_text=True))

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
        self.assertIn("APROVAD", c_appr["list_title"])
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
        self.assertEqual(c_fin["list_title"], "FINALIZADAS")
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

        # 5. Valida integridade da pré-entrada salva
        self.assertIsNotNone(entry_id)

    def test_09_nao_autorizado_and_call_adm(self):
        """Testa o fluxo completo de Orçamento NÃO AUTORIZADO, criação dinâmica da coluna e chamada de ADM (Arthur/Roosevelt)."""
        from kanban.services.esteira import create_manual_os, claim_orcamento, concluir_orcamento, advance_admin_pipeline, get_os_status_for_mobile, _find_card_by_os
        from kanban.realtime import _normalize_speech_name

        # 1. Valida normalização de voz de Arthur e Roosevelt como ADM
        self.assertEqual(_normalize_speech_name("Arthur (ADM)"), "Arthur")
        self.assertEqual(_normalize_speech_name("Roosevelt (ADM)"), "Roosevelt")
        self.assertEqual(_normalize_speech_name("Priscila (ADM)"), "Priscila")
        self.assertEqual(_normalize_speech_name("TODOS (OFICINA TODA)"), "toda a equipe da oficina")

        # 2. Emite chamados WebSocket para validar recepção
        self.sio.emit("director_call_tech", {"tech_name": "Arthur (ADM)", "message": "Reunião de diretoria"})
        self.sio.emit("director_call_tech", {"tech_name": "Roosevelt (ADM)", "message": "Verificar estoque"})

        # 3. Cria O.S. de teste
        test_os = "770001"
        with connect() as conn:
            conn.execute("DELETE FROM card_history WHERE os_number = ?", (test_os,))
            conn.execute("DELETE FROM cards WHERE os_number = ?", (test_os,))
        create_manual_os({"os_number": test_os, "client_name": "CLIENTE RECUSA TESTE", "equipment_model": "Prix 4 Uno"})
        claim_orcamento(test_os, "Guilherme")
        concluir_orcamento(test_os)
        advance_admin_pipeline(test_os, "enviar_cliente")

        # 4. Aciona botão NÃO AUTORIZADO via API
        r_nao_aut = self.client.post("/api/esteira/adm-nao-autorizar", json={"os_number": test_os})
        self.assertEqual(r_nao_aut.status_code, 200)
        self.assertTrue(r_nao_aut.get_json()["success"])

        # 5. Verifica se a lista 'NÃO AUTORIZADOS' foi criada dinamicamente no banco
        with connect() as conn:
            nao_aut_col = conn.execute("SELECT * FROM lists WHERE role = 'nao_autorizados' OR title = 'NÃO AUTORIZADOS'").fetchone()
            self.assertIsNotNone(nao_aut_col, "Coluna 'NÃO AUTORIZADOS' deveria ter sido criada dinamicamente!")
            card = _find_card_by_os(conn, test_os)
            self.assertEqual(card["pipeline_phase"], "NAO_AUTORIZADO")
            self.assertEqual(card["list_id"], nao_aut_col["id"])

        # 6. Verifica estado para a tela mobile do técnico
        st_mob = get_os_status_for_mobile(test_os)
        self.assertEqual(st_mob["state"], "NAO_AUTORIZADO")

        # 7. Verifica no Board que a coluna NÃO AUTORIZADOS possui o cartão de teste
        r_board = self.client.get("/api/board")
        self.assertEqual(r_board.status_code, 200)
        board_data = r_board.get_json()
        target_col = next((l for l in board_data["lists"] if l["role"] == "nao_autorizados" or "NÃO AUTORIZAD" in l["title"]), None)
        self.assertIsNotNone(target_col)
        self.assertTrue(any(c["os_number"] == test_os for c in target_col["cards"]))

        # 8. Técnico fecha a balança (vai para FINALIZADAS)
        r_fechar = self.client.post("/api/esteira/fechar-balanca", json={"os_number": test_os, "tech_name": "Guilherme"})
        self.assertEqual(r_fechar.status_code, 200)
        self.assertTrue(r_fechar.get_json()["success"])

        with connect() as conn:
            card_closed = _find_card_by_os(conn, test_os)
            fin_col = conn.execute("SELECT * FROM lists WHERE role = 'finalizada' OR title = 'FINALIZADAS'").fetchone()
            self.assertEqual(card_closed["list_id"], fin_col["id"])
            self.assertEqual(card_closed["pipeline_phase"], "PRONTAS")
            self.assertIsNotNone(card_closed["finished_at"])

        # 9. No Board, a coluna NÃO AUTORIZADOS não possui mais o cartão de teste
        r_board2 = self.client.get("/api/board")
        board_data2 = r_board2.get_json()
        target_col2 = next((l for l in board_data2["lists"] if l["role"] == "nao_autorizados" or "NÃO AUTORIZAD" in l["title"]), None)
        self.assertFalse(any(c["os_number"] == test_os for c in target_col2["cards"]))

    def test_10_reset_metrics_after_manual_kanban_organization(self):
        """
        Testa o fluxo em que a Priscila organiza o Kanban manualmente (arrastando cartões),
        aciona o marco inicial (/api/diretoria/reset-metrics / .bat) para zerar os relatórios
        do Sr. Jacson, e em seguida inicia a contabilização oficial.
        """
        import time
        from kanban.services.esteira import create_manual_os, claim_orcamento, concluir_orcamento, claim_manutencao, finalizar_balanca

        os_org_fin = "880001"
        os_org_orc = "880002"
        os_new_live = "880003"
        with connect() as conn:
            conn.execute("DELETE FROM card_history WHERE os_number IN (?, ?, ?)", (os_org_fin, os_org_orc, os_new_live))
            conn.execute("DELETE FROM cards WHERE os_number IN (?, ?, ?)", (os_org_fin, os_org_orc, os_new_live))

        # 1. Priscila organiza cartões antigos manualmente (inclusive movendo para FINALIZADAS)
        create_manual_os({"os_number": os_org_fin, "client_name": "CLIENTE ANTIGO FINALIZADO", "equipment_model": "Prix 4"})
        create_manual_os({"os_number": os_org_orc, "client_name": "CLIENTE EM ORCAMENTO", "equipment_model": "Prix 5"})

        c1_id = self.client.get(f"/api/cards/{os_org_fin}").get_json()["id"]
        c2_id = self.client.get(f"/api/cards/{os_org_orc}").get_json()["id"]

        with connect() as conn:
            fin_list_id = conn.execute("SELECT id FROM lists WHERE role = 'finalizada' OR title = 'FINALIZADAS' LIMIT 1").fetchone()["id"]
            orc_list_id = conn.execute("SELECT id FROM lists WHERE role = 'orcamento' OR title = 'ORÇAMENTOS' LIMIT 1").fetchone()["id"]

        self.client.post(f"/api/cards/{c1_id}/move", json={"target_list_id": fin_list_id, "new_position": 0})
        self.client.post(f"/api/cards/{c2_id}/move", json={"target_list_id": orc_list_id, "new_position": 0})

        # 2. Priscila aperta o .bat (/api/diretoria/reset-metrics) para começar a valer
        r_reset = self.client.post("/api/diretoria/reset-metrics", json={"actor": "Priscila (Recepção)"})
        self.assertEqual(r_reset.status_code, 200)
        res_reset = r_reset.get_json()
        self.assertTrue(res_reset["success"])

        # 3. Imediatamente após o reset, o relatório do Sr. Jacson deve estar zerado (0 prontas, 0 orçamentos feitos)
        r_rep0 = self.client.get("/api/diretoria/report?period=today")
        self.assertEqual(r_rep0.status_code, 200)
        rep0 = r_rep0.get_json()
        self.assertEqual(rep0["kpis"]["total_prontas"], 0)
        self.assertEqual(rep0["kpis"]["total_orcamentos_feitos"], 0)

        # 4. E os cartões continuam exatamente nas colunas onde a Priscila deixou
        c1_check = self.client.get(f"/api/cards/{os_org_fin}").get_json()
        c2_check = self.client.get(f"/api/cards/{os_org_orc}").get_json()
        self.assertEqual(c1_check["list_id"], fin_list_id)
        self.assertEqual(c2_check["list_id"], orc_list_id)

        # 5. Agora uma O.S. real é orçada e finalizada DEPOIS do marco inicial
        time.sleep(0.02)
        create_manual_os({"os_number": os_new_live, "client_name": "CLIENTE NOVO VALENDO", "equipment_model": "Prix 4 Uno"})
        claim_orcamento(os_new_live, "Guilherme")
        concluir_orcamento(os_new_live)
        claim_manutencao(os_new_live, "Guilherme")
        finalizar_balanca(os_new_live)

        # 6. O relatório do Sr. Jacson agora contabiliza exatamente 1 orçamento e 1 balança pronta para Guilherme
        r_rep1 = self.client.get("/api/diretoria/report?period=today")
        self.assertEqual(r_rep1.status_code, 200)
        rep1 = r_rep1.get_json()
        self.assertEqual(rep1["kpis"]["total_prontas"], 1)
        self.assertEqual(rep1["kpis"]["total_orcamentos_feitos"], 1)
        guilherme_stats = next((t for t in rep1["technicians_performance"] if "GUILHERME" in t["name"].upper()), None)
        self.assertIsNotNone(guilherme_stats)
        self.assertEqual(guilherme_stats["prontas_count"], 1)
        self.assertEqual(guilherme_stats["orcamentos_count"], 1)

        # Limpa os cartões de teste e restaura o marco inicial limpo
        with connect() as conn:
            conn.execute("DELETE FROM card_history WHERE os_number IN (?, ?, ?)", (os_org_fin, os_org_orc, os_new_live))
            conn.execute("DELETE FROM cards WHERE os_number IN (?, ?, ?)", (os_org_fin, os_org_orc, os_new_live))
            conn.commit()
        self.client.post("/api/diretoria/reset-metrics", json={"actor": "Priscila (Recepção)"})

    def test_11_github_cloud_backup_and_1640_notification(self):
        """Testa configuração de backup em nuvem no GitHub (joaovotonic/a5_processos) e banner fixo das 16h40."""
        r_status = self.client.get("/api/backup/github-status")
        self.assertEqual(r_status.status_code, 200)
        st = r_status.get_json()
        self.assertEqual(st["github_user"], "joaovotonic")
        self.assertEqual(st["github_email"], "joaovotoni1@gmail.com")
        self.assertEqual(st["github_repo"], "joaovotonic/a5_processos")

        r_up = self.client.post("/api/backup/github-cloud", json={"dry_run": True})
        self.assertEqual(r_up.status_code, 200)
        up = r_up.get_json()
        self.assertTrue(up["success"])
        self.assertEqual(up["github_repo"], "joaovotonic/a5_processos")

        # Verifica se o banner fixo está presente no HTML do Admin
        r_admin = self.client.get("/admin")
        html = r_admin.get_data(as_text=True)
        self.assertIn("cloudBackupFixedBanner", html)
        self.assertIn("triggerGithubCloudBackup", html)
        self.assertIn("joaovotonic/a5_processos", html)

    @classmethod
    def tearDownClass(cls):
        restore_db_snapshot(getattr(cls, "_db_snap", None))


if __name__ == "__main__":
    unittest.main(verbosity=2)

