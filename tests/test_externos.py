"""
Testes automatizados do módulo de Chamados Externos e Gestão de Rotas de Rua (A5 Tecnologia).
Valida parsing de dados, fluxo de montagem de rotas pela Diretoria,
formatação de mensagens para WhatsApp e exportação de CSV compatível com Excel.
"""
import unittest
from datetime import datetime

from kanban import create_app
from kanban.database import connect, init_db
from kanban.services.externos import (
    parse_external_os_pdf,
    create_external_order,
    list_external_orders,
    update_external_order,
    delete_external_order,
    notify_director_pending_routes,
    save_route_assignments,
    get_grouped_routes,
    format_whatsapp_route_message,
    export_external_routes_csv
)


class TestExternalRoutes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def setUp(self):
        # Limpa dados de chamados de teste anteriores
        with connect() as conn:
            conn.execute("DELETE FROM external_orders WHERE os_number LIKE 'TEST%' OR client_name LIKE 'TEST%'")
            conn.execute("DELETE FROM external_routes WHERE route_date = '2026-11-04'")

    def test_01_create_and_list_orders(self):
        """Testa criação e listagem de chamados externos."""
        order = create_external_order({
            "client_name": "TEST DB ALLEGRO",
            "open_date": "04/11/2026",
            "open_time": "09:24",
            "os_number": "TEST26802",
            "sector": "ROTISSERIE",
            "equipment_model": "PRIX 6",
            "reported_defect": "TECLADO TRAVANDO",
            "tasks_notes": "PEDIDO: 937/ EMBARQUE PORTO DO DEMÉTRIO",
            "route_date": "2026-11-04"
        })
        self.assertIsNotNone(order.get("id"))
        self.assertEqual(order["client_name"], "TEST DB ALLEGRO")
        self.assertEqual(order["status"], "pending_route")

        orders = list_external_orders(date_filter="2026-11-04")
        found = [o for o in orders if o["client_name"] == "TEST DB ALLEGRO"]
        self.assertEqual(len(found), 1)

    def test_02_update_and_delete_order(self):
        """Testa atualização e exclusão de chamados."""
        order = create_external_order({
            "client_name": "TEST ATACADAO JAPIIM",
            "open_date": "04/11/2026",
            "open_time": "09:36",
            "os_number": "TEST26803",
            "sector": "RECEBIMENTO",
            "equipment_model": "PL 3000",
            "reported_defect": "PRAZO DE CALIBRAÇÃO VENCIDO",
            "route_date": "2026-11-04"
        })
        oid = order["id"]

        updated = update_external_order(oid, {
            "tasks_notes": "ATENDER COM PRIORIDADE",
            "technician": "EDSON"
        })
        self.assertIsNotNone(updated)
        self.assertEqual(updated["tasks_notes"], "ATENDER COM PRIORIDADE")
        self.assertEqual(updated["technician"], "EDSON")

        deleted = delete_external_order(oid)
        self.assertTrue(deleted)

    def test_03_notify_director(self):
        """Testa notificação da recepção (Priscila) para a diretoria (Sr. Jacson)."""
        create_external_order({
            "client_name": "TEST DB CAMPOS ELISEOS",
            "open_date": "04/11/2026",
            "open_time": "09:37",
            "os_number": "TEST26804",
            "sector": "PEIXARIA",
            "equipment_model": "PRIX 5 PTA",
            "reported_defect": "NÃO ESTÁ LIGANDO",
            "route_date": "2026-11-04"
        })

        res = notify_director_pending_routes("2026-11-04")
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["total_calls"], 1)

        orders = list_external_orders(date_filter="2026-11-04")
        target = [o for o in orders if o["client_name"] == "TEST DB CAMPOS ELISEOS"][0]
        self.assertEqual(target["status"], "pending_director")

    def test_04_save_and_finalize_routes(self):
        """Testa montagem de rota pelo Sr. Jacson com sequenciamento e finalização."""
        o1 = create_external_order({
            "client_name": "TEST DB MAX TEIXEIRA",
            "open_date": "03/11/2026",
            "open_time": "11:08",
            "os_number": "TEST26787",
            "sector": "TODAS AS BALANÇAS",
            "reported_defect": "AFERIÇÃO",
            "route_date": "2026-11-04"
        })
        o2 = create_external_order({
            "client_name": "TEST VITORIA GDE CIRCULAR",
            "open_date": "03/11/2026",
            "open_time": "13:55",
            "os_number": "TEST26792",
            "sector": "CAIXA 104",
            "equipment_model": "8217 LIGHT",
            "reported_defect": "PESANDO C/VALORES DIVERGENTES",
            "route_date": "2026-11-04"
        })

        assignments = [
            {
                "id": o1["id"],
                "technician": "EDSON",
                "route_order": 1,
                "tasks_notes": "ATENDER QUARTA"
            },
            {
                "id": o2["id"],
                "technician": "EDSON",
                "route_order": 2,
                "tasks_notes": ""
            }
        ]

        res = save_route_assignments(
            route_date="2026-11-04",
            assignments=assignments,
            finalize=True,
            director_name="Sr. Jacson"
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["finalized"])

        summary = get_grouped_routes("2026-11-04")
        self.assertEqual(summary["status"], "finalized")
        self.assertIn("EDSON", summary["technicians"])
        edson_stops = [s for s in summary["technicians"]["EDSON"] if s["client_name"].startswith("TEST")]
        self.assertEqual(len(edson_stops), 2)
        self.assertEqual(edson_stops[0]["route_order"], 1)
        self.assertEqual(edson_stops[0]["tasks_notes"], "ATENDER QUARTA")
        self.assertEqual(edson_stops[1]["route_order"], 2)

    def test_05_whatsapp_text_formatting(self):
        """Testa formatação de texto para o WhatsApp."""
        stops = [
            {
                "client_name": "DB MAX TEIXEIRA",
                "os_number": "26787",
                "open_time": "11:08",
                "sector": "TODAS AS BALANÇAS",
                "equipment_model": "PRIX 4",
                "reported_defect": "AFERIÇÃO",
                "tasks_notes": "ATENDER QUARTA",
                "route_order": 1
            }
        ]
        msg = format_whatsapp_route_message("04/11/2026", "EDSON", stops, shift="manha")
        self.assertIn("ROTA DE EXTERNOS - MANHÃ - 04/11/2026", msg)
        self.assertIn("EDSON", msg)
        self.assertIn("1ª PARADA: DB MAX TEIXEIRA", msg)
        self.assertIn("ATENDER QUARTA", msg)
        self.assertIn("Retorno à Firma", msg)

    def test_06_csv_export(self):
        """Testa exportação CSV com ponto e vírgula e BOM UTF-8."""
        create_external_order({
            "client_name": "TEST VITÓRIA CENTRO",
            "open_date": "04/11/2026",
            "open_time": "11:19",
            "os_number": "TEST26808",
            "sector": "AÇOUGUE",
            "equipment_model": "PRIX 6",
            "reported_defect": "TECLADO COM DEFEITO",
            "technician": "ANTONIO",
            "route_date": "2026-11-04"
        })

        csv_str = export_external_routes_csv(date_filter="2026-11-04")
        # Verifica BOM UTF-8 para Excel
        self.assertTrue(csv_str.startswith("\ufeff"))
        # Verifica colunas exatas
        expected_header = "Cliente;Data Abertura de O.S.;Horário;O.S.;Setor;Mod. Equip.;Defeito;Técnico;Tarefas a serem realizadas"
        self.assertIn(expected_header, csv_str)
        self.assertIn("TEST VITÓRIA CENTRO", csv_str)
        self.assertIn("ANTONIO", csv_str)

    def test_07_http_api_endpoints(self):
        """Testa requisições HTTP REST nos novos endpoints /api/externos/."""
        # 1. POST /api/externos/orders
        r = self.client.post("/api/externos/orders", json={
            "client_name": "TEST SUP RESENDE",
            "open_date": "04/11/2026",
            "open_time": "09:02",
            "os_number": "TEST26801",
            "sector": "CAIXA 105",
            "equipment_model": "8217 LP",
            "reported_defect": "NÃO ESTÁ ZERANDO",
            "tasks_notes": "DEVOLVER BALANÇA DO BARATEIRO TEFÉ",
            "route_date": "2026-11-04"
        })
        self.assertEqual(r.status_code, 201)
        created_id = r.get_json()["order"]["id"]

        # 2. GET /api/externos/orders
        r = self.client.get("/api/externos/orders?date=2026-11-04")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.get_json()["count"], 1)

        # 3. GET /api/externos/routes/summary
        r = self.client.get("/api/externos/routes/summary?date=2026-11-04")
        self.assertEqual(r.status_code, 200)
        self.assertIn("summary", r.get_json())

        # 4. GET /api/externos/whatsapp-text
        r = self.client.get("/api/externos/whatsapp-text?date=2026-11-04")
        self.assertEqual(r.status_code, 200)

        # 5. GET /api/externos/history
        r = self.client.get("/api/externos/history")
        self.assertEqual(r.status_code, 200)
        self.assertIn("history", r.get_json())

        # 6. GET /api/externos/export/csv
        r = self.client.get("/api/externos/export/csv?date=2026-11-04")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_08_shift_and_image_saving(self):
        """Testa rotas de turno (manha/tarde), texto conjunto e salvamento de imagem."""
        import base64
        # 1. Teste whatsapp conjunta
        from kanban.services.externos import format_whatsapp_conjunta_message
        techs = {
            "EDSON": [{"client_name": "DB DISTRITO", "route_order": 1, "os_number": "1001", "sector": "BALCÃO", "equipment_model": "PRIX 5", "reported_defect": "OK", "tasks_notes": ""}],
            "ANTONIO": [{"client_name": "DB CONSTANTINO", "route_order": 1, "os_number": "1002", "sector": "AÇOUGUE", "equipment_model": "PRIX 6", "reported_defect": "FALHA", "tasks_notes": "LEVAR CABO"}]
        }
        msg = format_whatsapp_conjunta_message("04/11/2026", techs, shift="tarde")
        self.assertIn("ROTA GERAL DE EXTERNOS (CONJUNTA) - TARDE - 04/11/2026", msg)
        self.assertIn("EDSON", msg)
        self.assertIn("ANTONIO", msg)
        self.assertIn("DB CONSTANTINO", msg)

        # 2. Teste API salvar imagem PNG base64
        # 1x1 pixel PNG transparente em base64
        tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        r = self.client.post("/api/externos/save-image", json={
            "image_base64": f"data:image/png;base64,{tiny_png}",
            "filename": "ROTA_EDSON_TARDE_04-11-2026.png"
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["success"])

        # 3. Teste listar imagens salvas
        r_list = self.client.get("/api/externos/saved-images")
        self.assertEqual(r_list.status_code, 200)
        names = [f["filename"] for f in r_list.get_json()["images"]]
        self.assertIn("ROTA_EDSON_TARDE_04-11-2026.png", names)

        # 4. Teste recuperar imagem salva
        r_img = self.client.get("/api/externos/images/ROTA_EDSON_TARDE_04-11-2026.png")
        self.assertEqual(r_img.status_code, 200)
        self.assertEqual(r_img.content_type, "image/png")
        r_img.close()

    def test_09_os_pdf_parsing_sector_and_defect(self):
        """Testa parametrização do parser de O.S. externa do Teorema (O.S. sem zeros, setor no defeito, defeito sem solicitante)."""
        from unittest.mock import patch
        from kanban.services.externos import parse_external_os_pdf, format_external_os_number

        # 1. Teste format_external_os_number
        self.assertEqual(format_external_os_number("0000026803"), "26803")
        self.assertEqual(format_external_os_number("026803"), "26803")
        self.assertEqual(format_external_os_number("26803"), "26803")

        # 2. Teste texto real do PDF da O.S. 26803 enviado pelo usuário
        sample_pdf_text = """
Situação: Aberta
A5 TECNOLOGIA E AUTOMAÇÃO DE PESAGENS LTDA - ME - (92) 3342-2315 Ordem de Serviço:
Previsão de entrega:
Data de abertura: RUA COMENDADOR CLEMENTINO, 379 - Bairro: CENTRO CEP: 69025000
0000026803
04/11/2026
Tipo da OS : EXTERNO
Cliente : 0001890 - ATACADAO S.A.
Fantasia : ATACADÃO JAPIIM
MARCA / MODELO : TOLEDO - PL - 3000/6
Defeito :
BALANÇA DO ATACADÃO JAPIIM, SETOR RECEBIMENTO, ELA ESTÁ INOPERANTE, POIS O CLIENTE DEIXOU O PRAZO DE CALIBRAÇÃO 
EXPIRAR. CHAMADO SOLICITADO PELO ADM LUIZ.
.
Reduzido Descrição:
"""
        with patch("kanban.services.externos.extract_text_from_pdf", return_value=sample_pdf_text):
            result = parse_external_os_pdf("dummy.pdf")

            self.assertEqual(result["os_number"], "26803")
            self.assertEqual(result["client_name"], "ATACADÃO JAPIIM")
            self.assertEqual(result["equipment_model"], "PL 3000")
            self.assertEqual(result["sector"], "RECEBIMENTO")
            self.assertEqual(result["reported_defect"], "ELA ESTÁ INOPERANTE, POIS O CLIENTE DEIXOU O PRAZO DE CALIBRAÇÃO EXPIRAR")
            self.assertNotIn("LUIZ", result["reported_defect"])
            self.assertNotIn("SOLICITADO", result["reported_defect"])

    def test_10_reschedule_and_attendance_flow(self):
        """Testa fluxo completo de marcar como atendido/não atendido, remarcar para tarde/outro dia, editar e excluir."""
        from kanban.services.externos import create_external_order, get_grouped_routes, save_route_assignments

        # 1. Cria chamado inicial
        order = create_external_order({
            "os_number": "26999",
            "client_name": "SUPERMERCADO TESTE REMARCAR",
            "sector": "AÇOUGUE",
            "equipment_model": "PRIX 6",
            "reported_defect": "TECLADO PAROU",
            "route_date": "2026-11-04",
            "route_shift": "manha"
        })
        order_id = order["id"]
        self.assertEqual(order.get("attendance_status"), "pending")

        # 2. Atribui na rota do Edson e finaliza
        save_route_assignments(
            route_date="2026-11-04",
            assignments=[{
                "technician": "EDSON",
                "orders": [{"id": order_id, "tasks_notes": "TESTAR TECLAS"}]
            }],
            finalize=True,
            director_name="Jacson",
            route_shift="manha"
        )

        # 3. Priscila marca como atendido via API
        r_att = self.client.put(f"/api/externos/orders/{order_id}", json={
            "attendance_status": "attended"
        })
        self.assertEqual(r_att.status_code, 200)
        self.assertEqual(r_att.get_json()["order"]["attendance_status"], "attended")

        # 4. Priscila marca chamado como não atendido com motivo digitado: retorna automaticamente para 'chamados externos aguardando rota'
        r_not = self.client.put(f"/api/externos/orders/{order_id}", json={
            "attendance_status": "not_attended",
            "unattended_reason": "Cliente fechado para almoço"
        })
        self.assertEqual(r_not.status_code, 200)
        order_not = r_not.get_json()["order"]
        self.assertEqual(order_not["attendance_status"], "not_attended")
        self.assertEqual(order_not["unattended_reason"], "Cliente fechado para almoço")
        self.assertIsNone(order_not["technician"])
        self.assertEqual(order_not["status"], "pending_route")

        # Verifica que retornou automaticamente para aguardando rota (unassigned) com o motivo
        summary_manha = get_grouped_routes("2026-11-04", "manha")
        unassigned_ids = [o["id"] for o in summary_manha["unassigned"]]
        self.assertIn(order_id, unassigned_ids)
        not_order = [o for o in summary_manha["unassigned"] if o["id"] == order_id][0]
        self.assertEqual(not_order["unattended_reason"], "Cliente fechado para almoço")

        # Também deve estar visível no turno da tarde se ainda não distribuído
        summary_tarde = get_grouped_routes("2026-11-04", "tarde")
        unassigned_tarde = [o["id"] for o in summary_tarde["unassigned"]]
        self.assertIn(order_id, unassigned_tarde)

        # 7. Priscila edita chamado mesmo após ter sido manipulado
        r_edit = self.client.put(f"/api/externos/orders/{order_id}", json={
            "client_name": "SUPERMERCADO TESTE ALTERADO",
            "reported_defect": "NOVO DEFEITO INFORMADO",
            "technician": "ANTONIO"
        })
        self.assertEqual(r_edit.status_code, 200)
        edited = r_edit.get_json()["order"]
        self.assertEqual(edited["client_name"], "SUPERMERCADO TESTE ALTERADO")
        self.assertEqual(edited["reported_defect"], "NOVO DEFEITO INFORMADO")
        self.assertEqual(edited["technician"], "ANTONIO")

        # 8. Priscila exclui chamado cancelado de última hora
        r_del = self.client.delete(f"/api/externos/orders/{order_id}")
        self.assertEqual(r_del.status_code, 200)
        self.assertTrue(r_del.get_json()["success"])

        # Verifica que foi excluído
        r_del_again = self.client.delete(f"/api/externos/orders/{order_id}")
        self.assertEqual(r_del_again.status_code, 404)

    def test_09_doorbell_sound_assets_and_templates(self):
        """Valida que o som de campainha existe, é servido estaticamente e está integrado nos painéis."""
        import os
        wav_path = os.path.join('static', 'sounds', 'campainha.wav')
        self.assertTrue(os.path.exists(wav_path), 'Arquivo campainha.wav deve existir em static/sounds')
        self.assertGreater(os.path.getsize(wav_path), 1000)

        resp = self.client.get('/static/sounds/campainha.wav')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('audio', resp.content_type.lower())
        resp.close()

        with open('templates/admin.html', 'r', encoding='utf-8') as f:
            admin_src = f.read()
        self.assertIn('playDoorbellSound', admin_src)
        self.assertIn('campainha.wav', admin_src)
        self.assertNotIn('modalRemarcarChamados', admin_src)
        self.assertNotIn('openRescheduleModal', admin_src)
        self.assertIn('modalNaoAtendido', admin_src)
        self.assertIn('openNaoAtendidoModal', admin_src)

        with open('templates/diretoria.html', 'r', encoding='utf-8') as f:
            dir_src = f.read()
        self.assertIn('playDoorbellSound', dir_src)

    def test_11_folder_consumption_scale_and_external_pdfs(self):
        """
        Testa o consumo real de arquivos PDF nas duas pastas:
        1) entrada_pdfs (Entrada de Balança -> coluna ORÇAMENTOS, inclusive re-consumo do mesmo nome de arquivo)
        2) entrada_chamados_externos (Entrada de Chamado Externo -> data de hoje e turno atual, inclusive re-consumo)
        """
        import os
        from unittest.mock import patch
        from kanban.config import ENTRADA_PDFS_DIR, ENTRADA_EXTERNOS_DIR, ARQUIVADOS_PDFS_DIR, ARQUIVADOS_EXTERNOS_DIR
        from kanban.services.pdf_watcher import scan_pending_input_folders

        os.makedirs(ENTRADA_PDFS_DIR, exist_ok=True)
        os.makedirs(ENTRADA_EXTERNOS_DIR, exist_ok=True)

        sample_scale_text = """
        Ordem de Serviço: 0000998877
        Data de abertura: 04/11/2026 09:15
        Fantasia : SUPERMERCADO TESTE WATCHER
        MARCA / MODELO : TOLEDO PRIX 5 PLUS
        Defeito : BALANÇA NÃO LIGA E TECLADO TRAVANDO.
        """

        sample_ext_text = """
        Ordem de Serviço: 0000887766
        Data de abertura: 04/11/2026 08:40
        Fantasia : ATACADÃO TESTE EXTERNO
        MARCA / MODELO : TOLEDO - PL - 3000/6
        Defeito : BALANÇA DO ATACADÃO, SETOR RECEBIMENTO, PRAZO DE CALIBRAÇÃO VENCIDO. CHAMADO SOLICITADO PELO ADM JOAO.
        """

        scale_pdf_path = os.path.join(ENTRADA_PDFS_DIR, "O.S._998877_Teste_Balanca.pdf")
        ext_pdf_path = os.path.join(ENTRADA_EXTERNOS_DIR, "O.S._887766_Teste_Externo.pdf")

        with patch("kanban.services.pdf_parser.extract_text_from_pdf", return_value=sample_scale_text), \
             patch("kanban.services.externos.extract_text_from_pdf", return_value=sample_ext_text):

            # 1ª rodada: cria os arquivos nas pastas de entrada e varre
            with open(scale_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4 dummy scale pdf content")
            with open(ext_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4 dummy external pdf content")

            scan_pending_input_folders()
            self.assertFalse(os.path.exists(scale_pdf_path), "PDF de balança deveria ter sido movido de entrada_pdfs")
            self.assertFalse(os.path.exists(ext_pdf_path), "PDF externo deveria ter sido movido de entrada_chamados_externos")

            # Verifica que o card da balança entrou no topo da coluna ORÇAMENTOS (mesmo se existisse antes)
            with connect() as conn:
                card = conn.execute("SELECT * FROM cards WHERE os_number = '998877'").fetchone()
                self.assertIsNotNone(card)
                self.assertEqual(card["pipeline_phase"], "ORCAMENTOS_A_FAZER")
                self.assertEqual(card["position"], 0)

                # Simula que o card estava em FINALIZADAS e o usuário joga o mesmo PDF novamente na pasta
                fin_list = conn.execute("SELECT id FROM lists WHERE role = 'finalizada' LIMIT 1").fetchone()
                if fin_list:
                    conn.execute("UPDATE cards SET list_id = ?, pipeline_phase = 'FINALIZADAS' WHERE id = ?", (fin_list["id"], card["id"]))

            # 2ª rodada: joga novamente arquivos com O MESMO NOME nas pastas (valida correção do bug de _processed_files)
            with open(scale_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4 dummy scale pdf content 2")
            with open(ext_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4 dummy external pdf content 2")

            scan_pending_input_folders()
            self.assertFalse(os.path.exists(scale_pdf_path), "Deve re-consumir arquivo com mesmo nome em entrada_pdfs")
            self.assertFalse(os.path.exists(ext_pdf_path), "Deve re-consumir arquivo com mesmo nome em entrada_chamados_externos")

            today_str = datetime.now().strftime("%Y-%m-%d")
            with connect() as conn:
                card_re = conn.execute("SELECT * FROM cards WHERE os_number = '998877'").fetchone()
                orc_list = conn.execute("SELECT id FROM lists WHERE role = 'orcamento' LIMIT 1").fetchone()
                self.assertEqual(card_re["list_id"], orc_list["id"], "Card re-importado deve voltar para a coluna ORÇAMENTOS")
                self.assertEqual(card_re["pipeline_phase"], "ORCAMENTOS_A_FAZER")

                ext_order = conn.execute("SELECT * FROM external_orders WHERE os_number = '887766'").fetchone()
                self.assertIsNotNone(ext_order)
                self.assertEqual(ext_order["open_date"], "04/11/2026", "Deve preservar a data de abertura original do PDF")
                self.assertEqual(ext_order["route_date"], today_str, "A data da rota deve ser a data de hoje em que o PDF entrou na pasta")
                self.assertEqual(ext_order["sector"], "RECEBIMENTO")

        # Limpa os arquivos e registros de teste criados
        month_str = datetime.now().strftime("%Y-%m")
        for p in [
            os.path.join(ARQUIVADOS_PDFS_DIR, month_str, "OS_998877_O.S._998877_Teste_Balanca.pdf"),
            os.path.join(ARQUIVADOS_EXTERNOS_DIR, month_str, "OS_887766_O.S._887766_Teste_Externo.pdf"),
        ]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

        with connect() as conn:
            conn.execute("DELETE FROM card_history WHERE os_number = '998877'")
            conn.execute("DELETE FROM cards WHERE os_number = '998877'")
            conn.execute("DELETE FROM external_orders WHERE os_number = '887766'")

    @classmethod
    def tearDownClass(cls):
        with connect() as conn:
            conn.execute("DELETE FROM external_orders WHERE os_number IN ('26999', '887766') OR os_number LIKE 'TEST%' OR client_name LIKE '%TESTE%' OR client_name LIKE 'TEST%'")
            conn.execute("UPDATE external_orders SET route_date = ? WHERE id IN (115, 116)", (datetime.now().strftime("%Y-%m-%d"),))
            conn.commit()


if __name__ == "__main__":
    unittest.main()

