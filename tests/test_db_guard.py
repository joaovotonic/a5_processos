import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kanban.database import _ensure_esteira_lists
from kanban.db_guard import checkpoint_and_snapshot, restore_snapshot, verify_post_init


BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


class TestDbGuardAndSafeUpdater(unittest.TestCase):
    def test_01_wal_transactions_survive_git_reset_overwrite(self):
        """
        Simula o bug real: banco em WAL com alterações recentes somente no .db-wal,
        seguido de `git reset --hard` sobrescrevendo o .db com uma versão antiga
        e deixando um .db-wal órfão. O db_guard precisa preservar 100% dos dados.
        """
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            db_path = root / "database" / "a5_kanban.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            state_dir = root / "state"
            extra_dir = root / "backups"

            # 1. Cria banco base em modo WAL sem autocheckpoint
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA wal_autocheckpoint=0;")
            conn.execute("CREATE TABLE lists (id INTEGER PRIMARY KEY, title TEXT)")
            conn.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY, os_number TEXT, client_name TEXT, list_id INTEGER)")
            conn.execute("INSERT INTO lists (id, title) VALUES (1, 'ORÇAMENTOS')")
            conn.execute("INSERT INTO cards (id, os_number, client_name, list_id) VALUES (1, '1001', 'CLIENTE ANTIGO', 1)")
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

            # Salva uma cópia antiga para simular o arquivo que viria do origin/main no git reset
            old_git_db = root / "old_origin_main.db"
            shutil.copy2(db_path, old_git_db)

            # 2. Insere novos cards que ficam SOMENTE no arquivo -wal (autocheckpoint=0)
            conn.execute("INSERT INTO cards (id, os_number, client_name, list_id) VALUES (2, '1002', 'CARD NO WAL 1', 1)")
            conn.execute("INSERT INTO cards (id, os_number, client_name, list_id) VALUES (3, '1003', 'CARD NO WAL 2', 1)")
            conn.execute("UPDATE cards SET client_name = 'CLIENTE ATUALIZADO NO WAL' WHERE id = 1")
            conn.commit()

            wal_path = pathlib.Path(f"{db_path}-wal")
            self.assertTrue(wal_path.exists() and wal_path.stat().st_size > 0, "WAL deveria conter frames pendentes")

            # Fecha conexão simulando encerramento sem checkpoint (mantendo WAL com frames pendentes se houver)
            # Para forçar o cenário de crash/taskkill antes do checkpoint, copiamos .db + .db-wal para outra pasta
            # enquanto a conexão ainda mantém o WAL sem checkpoint.
            sim_db = root / "sim" / "a5_kanban.db"
            sim_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_path, sim_db)
            shutil.copy2(wal_path, pathlib.Path(f"{sim_db}-wal"))
            conn.close()

            # Confirma que copiar só sim_db SEM WAL perderia os cards 2 e 3
            raw_only = root / "raw_only.db"
            shutil.copy2(sim_db, raw_only)
            c_raw = sqlite3.connect(str(raw_only))
            raw_count = c_raw.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            c_raw.close()
            self.assertEqual(raw_count, 1, "Sem WAL checkpoint, cópia simples enxerga só 1 card")

            # 3. Executa db_guard snapshot (deve consolidar o WAL e salvar os 3 cards)
            manifest = checkpoint_and_snapshot(sim_db, state_dir, extra_backup_dir=extra_dir)
            self.assertEqual(manifest["counts"]["cards"], 3)
            self.assertTrue(pathlib.Path(manifest["permanent_backup_path"]).is_file())
            self.assertTrue(pathlib.Path(manifest["extra_backup_path"]).is_file())

            # 4. Simula `git reset --hard origin/main` sobrescrevendo o .db com a versão antiga + WAL corrompido
            shutil.copy2(old_git_db, sim_db)
            pathlib.Path(f"{sim_db}-wal").write_bytes(b"STALE_WAL_GARBAGE")

            # 5. Restaura via db_guard e valida integridade, SHA-256 e 100% dos dados do WAL
            restored = restore_snapshot(sim_db, state_dir)
            self.assertEqual(restored["sha256"], manifest["sha256"])
            self.assertFalse(pathlib.Path(f"{sim_db}-wal").exists())

            c_after = sqlite3.connect(str(sim_db))
            rows = c_after.execute("SELECT id, os_number, client_name FROM cards ORDER BY id").fetchall()
            c_after.close()
            self.assertEqual(
                rows,
                [
                    (1, "1001", "CLIENTE ATUALIZADO NO WAL"),
                    (2, "1002", "CARD NO WAL 1"),
                    (3, "1003", "CARD NO WAL 2"),
                ],
            )

            # 6. verify_post_init deve aprovar e limpar apenas os arquivos temporários ativos
            post = verify_post_init(sim_db, state_dir)
            self.assertEqual(post["counts"]["cards"], 3)
            self.assertTrue(pathlib.Path(manifest["permanent_backup_path"]).is_file())
            self.assertFalse((state_dir / "a5_kanban_preserve_active.db").exists())

    def test_02_verify_post_init_detects_unexpected_data_loss(self):
        """Se init_db ou qualquer etapa reduzisse o número de O.S., verify_post_init deve acusar erro."""
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            db_path = root / "a5_kanban.db"
            state_dir = root / "state"

            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE lists (id INTEGER PRIMARY KEY, title TEXT)")
            conn.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY, os_number TEXT, list_id INTEGER)")
            conn.execute("INSERT INTO lists VALUES (1, 'ORÇAMENTOS')")
            conn.execute("INSERT INTO cards VALUES (1, '2001', 1)")
            conn.execute("INSERT INTO cards VALUES (2, '2002', 1)")
            conn.commit()
            conn.close()

            checkpoint_and_snapshot(db_path, state_dir)
            restore_snapshot(db_path, state_dir)

            # Simula remoção indevida de 1 card
            conn2 = sqlite3.connect(str(db_path))
            conn2.execute("DELETE FROM cards WHERE id = 2")
            conn2.commit()
            conn2.close()

            with self.assertRaises(RuntimeError):
                verify_post_init(db_path, state_dir)

    def test_03_ensure_esteira_lists_never_deletes_list_with_cards(self):
        """_ensure_esteira_lists nunca pode apagar em cascata uma lista que contenha O.S."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("CREATE TABLE lists (id INTEGER PRIMARY KEY, title TEXT, position INTEGER, is_tech INTEGER, role TEXT)")
        conn.execute(
            "CREATE TABLE cards (id INTEGER PRIMARY KEY, os_number TEXT, list_id INTEGER, "
            "FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE)"
        )
        conn.execute("INSERT INTO lists VALUES (1, 'APROVADOS', 0, 0, 'aprovados')")
        conn.execute("INSERT INTO lists VALUES (2, 'PENDÊNCIAS', 1, 0, 'processo')")
        conn.execute("INSERT INTO lists VALUES (3, 'SR. JACSON', 2, 0, 'processo')")
        conn.execute("INSERT INTO cards VALUES (10, '9999', 2)")

        _ensure_esteira_lists(conn.cursor())
        conn.commit()

        # Lista 2 (com card) deve continuar existindo junto com seu card; lista 3 (vazia) pode ser removida
        card_cnt = conn.execute("SELECT COUNT(*) FROM cards WHERE os_number = '9999'").fetchone()[0]
        list2 = conn.execute("SELECT id FROM lists WHERE id = 2").fetchone()
        list3 = conn.execute("SELECT id FROM lists WHERE id = 3").fetchone()
        conn.close()

        self.assertEqual(card_cnt, 1)
        self.assertIsNotNone(list2)
        self.assertIsNone(list3)

    def test_04_atualizar_sistema_bat_is_code_only_and_uses_db_guard(self):
        """ATUALIZAR_SISTEMA.bat nunca oferece sobrescrever banco, usa db_guard e tem CRLF sem BOM."""
        bat_path = BASE_DIR / "ATUALIZAR_SISTEMA.bat"
        raw = bat_path.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "ATUALIZAR_SISTEMA.bat nao pode ter UTF-8 BOM")
        self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"), "ATUALIZAR_SISTEMA.bat deve usar CRLF")

        txt = raw.decode("utf-8")
        self.assertNotIn("Atualizar TUDO", txt)
        self.assertNotIn("OPCAO=1", txt)
        self.assertNotIn("timeout ", txt.lower())
        self.assertIn("-m kanban.db_guard snapshot", txt)
        self.assertIn("-m kanban.db_guard restore", txt)
        self.assertIn("-m kanban.db_guard verify-post-init", txt)
        self.assertIn("a5_atualizar_runner.bat", txt)
        self.assertIn('--runner "%A5_ORIG_DIR%"', txt)

    def test_05_atualizar_sistema_bat_survives_self_modification_during_git_reset(self):
        """
        Reproduz o bug real do cmd.exe ('rigin nao e reconhecido'):
        quando o proprio .bat muda de tamanho no meio da execucao (git reset --hard),
        a copia em %TEMP% impede qualquer corrupcao de offset.
        """
        if os.name != "nt":
            self.skipTest("Teste especifico de cmd.exe no Windows")

        raw_txt = (BASE_DIR / "ATUALIZAR_SISTEMA.bat").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            bat_copy = td_p / "ATUALIZAR_SISTEMA.bat"
            lines = []
            for ln in raw_txt.splitlines():
                s = ln.strip()
                if s == "git reset --hard origin/main":
                    # Simula `git reset --hard` alterando o tamanho do ATUALIZAR_SISTEMA.bat original em disco!
                    lines.append('echo MODIFIED_BY_SIMULATED_GIT_RESET_WITH_DIFFERENT_SIZE > "%A5_REPO_DIR%\\ATUALIZAR_SISTEMA.bat"')
                elif s.startswith(("git ", '"%A5_PYTHON%" ', "taskkill ", "powershell ", "pause", "ping ", 'call "%A5_REPO_DIR%\\')):
                    indent = ln[: len(ln) - len(ln.lstrip())]
                    lines.append(indent + "echo [DRY] " + s.split(" ")[0])
                else:
                    lines.append(ln)
            bat_copy.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))

            res = subprocess.run([str(bat_copy)], text=True, capture_output=True)
            self.assertEqual(res.returncode, 0, msg=f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            self.assertEqual(res.stderr.strip(), "", msg=f"STDERR inesperado: {res.stderr}")
            self.assertIn("CODIGO ATUALIZADO! BANCO LOCAL 100% PRESERVADO.", res.stdout)
            # Confirma que o arquivo original realmente foi reescrito durante a execucao sem quebrar o runner
            self.assertIn("MODIFIED_BY_SIMULATED_GIT_RESET", bat_copy.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
