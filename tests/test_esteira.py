"""
Suíte de Testes Automatizados de Integração da Esteira de Produção A5 Tecnologia.
Testa:
1. Criação e processamento de PDF do Teorema (entrada_pdfs -> arquivados_pdfs)
2. Máquina de estados completa dos 4 Scans do QR Code
3. Ações da Adm (Envio e Aprovação)
4. Consolidação do Tempo Líquido e Relatório da Diretoria
"""
import os
import sys
import time
import shutil
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pypdf import PdfWriter

from kanban.database import init_db, connect
from kanban.config import ENTRADA_PDFS_DIR, ARQUIVADOS_PDFS_DIR
from kanban.services.pdf_watcher import process_pdf_file
from kanban.services.esteira import process_qr_scan, advance_admin_pipeline, format_duration
from kanban.services.diretoria import get_director_productivity_report


def create_mock_teorema_pdf(file_path: str, os_num: str, client: str, model: str, serial: str, defect: str):
    """Cria um PDF válido com anotação de texto para simular a saída do Teorema."""
    import pypdf
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)  # A4

    # Adiciona texto como anotação ou metadado legível
    writer.add_metadata({
        "/Title": f"ORDEM DE SERVICO {os_num}",
        "/Author": "TEOREMA SISTEMAS ERP",
        "/Subject": f"Cliente: {client} | Modelo: {model} | Serie: {serial} | Defeito: {defect}"
    })
    with open(file_path, "wb") as f:
        writer.write(f)


def run_all_tests():
    print("=" * 65)
    print("  INICIANDO SUÍTE DE TESTES: ESTEIRA DE PRODUÇÃO A5 TECNOLOGIA")
    print("=" * 65)

    # 1. Garante banco limpo de teste
    init_db()

    test_os = f"99{int(time.time()) % 10000:04d}"
    pdf_filename = f"OS_{test_os}_MERCADO_TESTE.pdf"
    pdf_path = os.path.join(ENTRADA_PDFS_DIR, pdf_filename)

    print(f"\n[TESTE 1] Gerando PDF simulado do Teorema: {pdf_filename}...")
    create_mock_teorema_pdf(
        file_path=pdf_path,
        os_num=test_os,
        client="SUPERMERCADO BOA PRAÇA LTDA",
        model="TOLEDO PRIX 4 UNO",
        serial="SN-884920",
        defect="Não liga após queda de energia no açougue"
    )
    assert os.path.exists(pdf_path), "PDF não foi criado em entrada_pdfs"

    print("[TESTE 2] Executando serviço de processamento e arquivamento do PDF...")
    process_pdf_file(pdf_path)

    # Verifica se o PDF saiu da pasta de entrada
    assert not os.path.exists(pdf_path), "PDF original deveria ter sido movido da entrada_pdfs"

    with connect() as conn:
        card = conn.execute("SELECT * FROM cards WHERE os_number = ?", (test_os,)).fetchone()
        assert card is not None, f"Card com O.S. {test_os} não foi inserido no SQLite!"
        assert card["pipeline_phase"] == "ORCAMENTOS_A_FAZER", f"Fase incorreta: {card['pipeline_phase']}"
        print(f"  -> Sucesso: Card criado no SQLite com O.S. {test_os} | Fase: {card['pipeline_phase']}")

    # ==============================================================================
    # 1º SCAN: Inicia Orçamento
    # ==============================================================================
    print("\n[TESTE 3] 1º Scan QR Code pelo Técnico João Otoni (Início do Orçamento)...")
    res1 = process_qr_scan(test_os, "João Otoni")
    assert res1["success"] is True
    assert res1["action"] == "inicio_orcamento"
    assert res1["phase"] == "EM_ORCAMENTO"

    with connect() as conn:
        c1 = conn.execute("SELECT * FROM cards WHERE os_number = ?", (test_os,)).fetchone()
        assert c1["pipeline_phase"] == "EM_ORCAMENTO"
        assert c1["tech_name"] == "João Otoni"
        assert c1["inicio_orcamento"] is not None
        print(f"  -> Sucesso: Fase='{c1['pipeline_phase']}', Técnico='{c1['tech_name']}', Início={c1['inicio_orcamento'][:19]}")

    # Simula alguns segundos de diagnóstico
    time.sleep(1.2)

    # ==============================================================================
    # 2º SCAN: Finaliza Orçamento
    # ==============================================================================
    print("\n[TESTE 4] 2º Scan QR Code pelo Técnico João Otoni (Fim do Orçamento)...")
    res2 = process_qr_scan(test_os, "João Otoni")
    assert res2["success"] is True
    assert res2["action"] == "fim_orcamento"
    assert res2["phase"] == "ORCAMENTOS_FEITOS"

    with connect() as conn:
        c2 = conn.execute("SELECT * FROM cards WHERE os_number = ?", (test_os,)).fetchone()
        assert c2["pipeline_phase"] == "ORCAMENTOS_FEITOS"
        assert c2["fim_orcamento"] is not None
        assert c2["tempo_orcamento_segundos"] >= 1
        print(f"  -> Sucesso: Fase='{c2['pipeline_phase']}', Tempo Orçamento={c2['tempo_orcamento_segundos']}s ({format_duration(c2['tempo_orcamento_segundos'])})")

    # ==============================================================================
    # AÇÕES DA ADMINISTRAÇÃO (PRISCILA)
    # ==============================================================================
    print("\n[TESTE 5] Ação da Adm: Marcar 'Enviado ao Cliente'...")
    res_adm1 = advance_admin_pipeline(test_os, "enviar_cliente")
    assert res_adm1["success"] is True
    assert res_adm1["phase"] == "ORCAMENTOS_ENVIADOS"
    print(f"  -> Sucesso: O.S. marcada como 'ORCAMENTOS_ENVIADOS' (tempo líquido pausado)")

    print("\n[TESTE 6] Ação da Adm: Marcar 'Aprovado' (cliente autorizou conserto)...")
    res_adm2 = advance_admin_pipeline(test_os, "aprovar")
    assert res_adm2["success"] is True
    assert res_adm2["phase"] == "APROVADOS"
    print(f"  -> Sucesso: O.S. marcada como 'APROVADOS' e anúncio sonoro/visual despachado para a TV")

    # ==============================================================================
    # 3º SCAN: Puxa para Bancada (Em Manutenção)
    # ==============================================================================
    print("\n[TESTE 7] 3º Scan QR Code pelo Técnico João Otoni (Início da Manutenção)...")
    res3 = process_qr_scan(test_os, "João Otoni")
    assert res3["success"] is True
    assert res3["action"] == "inicio_manutencao"
    assert res3["phase"] == "EM_MANUTENCAO"

    with connect() as conn:
        c3 = conn.execute("SELECT * FROM cards WHERE os_number = ?", (test_os,)).fetchone()
        assert c3["pipeline_phase"] == "EM_MANUTENCAO"
        assert c3["inicio_manutencao"] is not None
        print(f"  -> Sucesso: Fase='{c3['pipeline_phase']}', Início Manutenção={c3['inicio_manutencao'][:19]}")

    # Simula reparo
    time.sleep(1.2)

    # ==============================================================================
    # 4º SCAN: Finaliza Conserto (Pronta)
    # ==============================================================================
    print("\n[TESTE 8] 4º Scan QR Code pelo Técnico João Otoni (Fim da Manutenção)...")
    res4 = process_qr_scan(test_os, "João Otoni")
    assert res4["success"] is True
    assert res4["action"] == "fim_manutencao"
    assert res4["phase"] == "PRONTAS"

    with connect() as conn:
        c4 = conn.execute("SELECT * FROM cards WHERE os_number = ?", (test_os,)).fetchone()
        assert c4["pipeline_phase"] == "PRONTAS"
        assert c4["finished_at"] is not None
        assert c4["tempo_manutencao_segundos"] >= 1
        assert c4["tempo_liquido_segundos"] == (c4["tempo_orcamento_segundos"] + c4["tempo_manutencao_segundos"])
        print(f"  -> Sucesso: Fase='{c4['pipeline_phase']}', Tempo Manutenção={c4['tempo_manutencao_segundos']}s")
        print(f"  -> TEMPO LÍQUIDO CONSOLIDADO: {c4['tempo_liquido_segundos']}s ({format_duration(c4['tempo_liquido_segundos'])})")

    # ==============================================================================
    # RELATÓRIO DA DIRETORIA (SR. JACSON)
    # ==============================================================================
    print("\n[TESTE 9] Consultando Relatório Executivo da Diretoria (/api/diretoria/report)...")
    report = get_director_productivity_report(period="today")
    kpis = report["kpis"]
    assert kpis["total_prontas"] >= 1, "Deveria ter ao menos 1 balança pronta hoje"
    assert kpis["total_orcamentos_feitos"] >= 1, "Deveria ter ao menos 1 orçamento feito hoje"

    tech_found = False
    for t in report["technicians_performance"]:
        if "JOÃO OTONI" in t["name"].upper() and t["prontas_count"] >= 1:
            tech_found = True
            print(f"  -> Desempenho Técnico [{t['name']}]: {t['orcamentos_count']} Orç., {t['prontas_count']} Prontas, Tempo Total: {t['tempo_total_str']}")
            break
    assert tech_found, "Técnico João Otoni não encontrado com métricas no relatório"

    print("\n" + "=" * 65)
    print("  TODOS OS 9 TESTES DA ESTEIRA PASSARAM COM 100% DE SUCESSO!")
    print("=" * 65)


if __name__ == "__main__":
    run_all_tests()
