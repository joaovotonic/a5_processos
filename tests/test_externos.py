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


if __name__ == "__main__":
    unittest.main()

