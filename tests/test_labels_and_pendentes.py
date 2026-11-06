import unittest
import json
from kanban import create_app
from kanban.database import connect, init_db
from kanban.services import cards as cards_service
from kanban.services import esteira as esteira_service
from kanban import rules


class TestLabelsAndBalancasPendentes(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        init_db()

    def test_labels_rules_and_tv_notifications(self):
        with connect() as conn:
            orc_list = conn.execute("SELECT id FROM lists WHERE role = 'orcamento' LIMIT 1").fetchone()
            apr_list = conn.execute("SELECT id FROM lists WHERE role = 'aprovados' LIMIT 1").fetchone()
            pend_list = conn.execute("SELECT id FROM lists WHERE role = 'balancas_pendentes' LIMIT 1").fetchone()
            tech_list = conn.execute("SELECT id FROM lists WHERE is_tech = 1 LIMIT 1").fetchone()

            self.assertIsNotNone(orc_list)
            self.assertIsNotNone(apr_list)
            self.assertIsNotNone(pend_list)
            self.assertIsNotNone(tech_list)

            test_os = "999901"
            conn.execute("DELETE FROM cards WHERE os_number = ?", (test_os,))
            conn.execute("""
                INSERT INTO cards (os_number, client_name, equipment_type, list_id, position, labels_json, created_at, updated_at, moved_at)
                VALUES (?, 'Cliente Teste Etiquetas', 'Balança Prix 4', ?, 0, '[]', datetime('now'), datetime('now'), datetime('now'))
            """, (test_os, orc_list["id"]))
            card_row = conn.execute("SELECT id FROM cards WHERE os_number = ?", (test_os,)).fetchone()
            card_id = card_row["id"]

        # 1. Em ORÇAMENTOS: Bloqueia qualquer etiqueta que não seja URGÊNCIA ou EM GARANTIA
        with self.assertRaises(Exception):
            cards_service.toggle_card_label(card_id, "AGUARDANDO")

        with self.assertRaises(Exception):
            cards_service.toggle_card_label(card_id, "FALTA PEÇA")

        # Testa via API REST também
        res_fail = self.client.post(f"/api/cards/{card_id}/toggle-label", json={"name": "AGUARDANDO"})
        self.assertEqual(res_fail.status_code, 400)

        # 2. Em ORÇAMENTOS: Permite URGENTE e EM GARANTIA (via API)
        res_urg = self.client.post(f"/api/cards/{card_id}/toggle-label", json={"name": "URGENTE", "color": "#EF4444"})
        self.assertEqual(res_urg.status_code, 200)
        data_urg = json.loads(res_urg.data)
        self.assertTrue(data_urg["active"])
        self.assertTrue(any(l["name"] == "URGENTE" for l in data_urg["labels"]))

        res_gar = self.client.post(f"/api/cards/{card_id}/toggle-label", json={"name": "EM GARANTIA", "color": "#8B5CF6"})
        self.assertEqual(res_gar.status_code, 200)
        data_gar = json.loads(res_gar.data)
        self.assertTrue(data_gar["active"])
        self.assertTrue(any(l["name"] == "EM GARANTIA" for l in data_gar["labels"]))

        # 3. Fora de ORÇAMENTOS (na bancada do técnico): Libera outras opções
        cards_service.move_card(card_id, tech_list["id"], 0, "Test Actor")
        res_aguard = self.client.post(f"/api/cards/{card_id}/toggle-label", json={"name": "AGUARDANDO", "color": "#F59E0B"})
        self.assertEqual(res_aguard.status_code, 200)
        data_aguard = json.loads(res_aguard.data)
        self.assertTrue(data_aguard["active"])
        self.assertTrue(any(l["name"] == "AGUARDANDO" for l in data_aguard["labels"]))

        # 4. Ao aprovar: remove temporárias (AGUARDANDO), mantendo estritamente URGENTE e EM GARANTIA
        esteira_service.adm_aprovar(test_os)
        with connect() as conn:
            c_row = conn.execute("SELECT labels_json, list_id FROM cards WHERE id = ?", (card_id,)).fetchone()
            labels_after_apr = [l["name"] for l in json.loads(c_row["labels_json"])]
            self.assertIn("URGENTE", labels_after_apr)
            self.assertIn("EM GARANTIA", labels_after_apr)
            self.assertNotIn("AGUARDANDO", labels_after_apr)
            self.assertEqual(c_row["list_id"], apr_list["id"])

        # 5. Em APROVADOS: Permite marcar FALTA PEÇA
        res_falta = self.client.post(f"/api/cards/{card_id}/toggle-label", json={"name": "FALTA PEÇA", "color": "#F97316"})
        self.assertEqual(res_falta.status_code, 200)
        data_falta = json.loads(res_falta.data)
        self.assertTrue(data_falta["active"])

        # 6. Mover para BALANÇAS PENDENTES
        move_res = self.client.post(f"/api/cards/{card_id}/move", json={
            "target_list_id": pend_list["id"],
            "new_position": 0,
            "actor": "Priscila (Recepção)"
        })
        self.assertEqual(move_res.status_code, 200)

        with connect() as conn:
            c_row = conn.execute("SELECT list_id, pipeline_phase FROM cards WHERE id = ?", (card_id,)).fetchone()
            self.assertEqual(c_row["list_id"], pend_list["id"])
            self.assertEqual(c_row["pipeline_phase"], "BALANCAS_PENDENTES")

            # Limpeza do card de teste
            conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            conn.execute("DELETE FROM card_history WHERE card_id = ?", (card_id,))


if __name__ == "__main__":
    unittest.main()
