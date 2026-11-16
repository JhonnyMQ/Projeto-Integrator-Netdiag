"""
NetDiag — Monitor de CFTV e Rede Local (Versão TCC)
Com Registro Preciso de Quedas (Vermelho), Persistência JSON,
Anti-Oscilação de Wi-Fi e Reciclagem Visual Sem Travar a Interface.
"""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import socket
import subprocess
import platform
import threading
import re
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ---------- Configurações e Arquivo de Persistência ----------
ARQUIVO_CONFIG = "netdiag_config.json"

BG_JANELA = "#0d1117"
BG_CARD = "#161b22"
BG_HEADER_TABELA = "#1c2128"
BORDA = "#30363d"
TEXTO_PRIMARIO = "#e6edf3"
TEXTO_SECUNDARIO = "#8b949e"

COR_VERDE = "#3fb950"    # Conexão Estável
COR_AMARELO = "#d29922"  # Oscilação / Instável
COR_VERMELHO = "#f85149" # Queda / Indisponível

FONTE_BASE = "Segoe UI"

INTERVALO_VARREDURA_SEGUNDOS = 15
TIMEOUT_PING_MS = 800
MAX_THREADS = 35
MAX_FALHAS_CONSECUTIVAS = 2

# ---------- Base de Prefixo MAC de Fabricantes ----------
FABRICANTES_MAC = {
    "SAMSUNG": [
        "00:12:FB", "00:15:B9", "00:21:19", "00:24:54", "08:08:C2", "10:30:47", "18:1E:B0", "1C:62:B8",
        "20:0C:C8", "24:4B:03", "28:27:BF", "30:19:66", "34:23:87", "38:0B:40", "3C:8B:CD", "40:0E:85",
        "44:1A:C8", "48:44:F7", "4C:BC:A5", "50:01:D9", "50:77:05", "50:CC:F8", "54:88:0E", "5C:0E:8B",
        "60:AF:6D", "64:B5:C6", "68:27:37", "6C:83:36", "70:28:8A", "74:04:2B", "78:25:AD", "7C:91:22",
        "80:4E:81", "84:25:DB", "84:38:35", "88:32:9B", "90:00:DB", "94:63:D1", "98:0D:2E", "98:52:B1",
        "A0:0B:BA", "A0:21:95", "A0:82:1F", "A4:77:33", "A8:06:00", "A8:7B:39", "AC:5F:3E", "B0:47:BF",
        "B4:79:A7", "B8:5E:7B", "BC:14:85", "C0:BD:D1", "C4:3A:9F", "C8:19:F7", "CC:3A:61", "D0:17:C2",
        "D0:22:BE", "D4:87:D8", "D8:57:EF", "DC:71:44", "DC:E5:5B", "E0:99:71", "E4:12:1D", "E4:70:B8"
    ],
    "APPLE": [
        "00:03:93", "00:05:02", "00:0A:27", "00:0D:93", "00:10:FA", "00:11:24", "00:14:A5", "00:16:CB",
        "00:17:F2", "00:19:E3", "00:1B:63", "00:1C:B3", "00:1D:4F", "00:1E:52", "00:1F:5B", "08:00:07",
        "08:66:A5", "0C:15:C4", "10:1C:0C", "10:40:F3", "14:10:9F", "18:20:32", "1C:1A:C0", "20:7D:74"
    ],
    "MOTOROLA": [
        "00:0A:28", "00:0C:E5", "00:11:AE", "00:14:9A", "00:1A:66", "00:1C:11", "00:1E:5A", "00:22:A1",
        "08:00:2E", "14:30:04", "18:3B:D2", "20:00:81", "24:DA:9B", "2C:19:B6", "38:1C:1A", "40:78:6A"
    ],
    "LG": [
        "00:05:C9", "00:0E:6D", "00:19:A9", "00:1E:B6", "00:22:A9", "00:24:83", "00:25:E5", "08:26:97",
        "10:68:3F", "14:C9:12", "18:26:66", "1C:48:F9", "20:34:FB", "2C:54:CF", "30:FD:38", "38:8C:50"
    ],
    "INTELBRAS": [
        "00:1A:3F", "00:26:5A", "10:1A:3F", "14:52:95", "18:1B:EB", "24:19:B1", "28:80:23", "2C:9A:80",
        "3C:80:61", "48:87:C7", "4C:82:CF", "54:30:19", "60:21:01", "6C:61:90", "80:8E:B0", "90:A4:DE"
    ],
    "HIKVISION": [
        "00:12:12", "00:18:04", "00:19:40", "00:30:54", "00:40:8C", "10:59:32", "10:A4:BE", "18:68:CB",
        "24:73:F2", "28:57:BE", "34:25:2A", "38:A3:BB", "40:10:20", "44:19:B7", "4C:BD:8F", "54:C4:15"
    ]
}


def obter_ip_local():
    """Obtém o IP do computador local."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def obter_prefixo_rede(ip_local):
    """Retorna o prefixo da sub-rede (ex: '192.168.15.')."""
    partes = ip_local.split(".")
    return ".".join(partes[:3]) + "."


def obter_gateway_padrao():
    """Descobre o IP do Roteador via ipconfig."""
    sistema = platform.system().lower()
    try:
        if sistema == "windows":
            flags = subprocess.CREATE_NO_WINDOW
            out = subprocess.check_output(["ipconfig"], creationflags=flags, text=True, encoding="cp850", errors="ignore")
            for linha in out.splitlines():
                if "Gateway" in linha or "Default Gateway" in linha:
                    partes = linha.split(":")
                    if len(partes) > 1:
                        ip = partes[1].strip()
                        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip) and ip != "0.0.0.0":
                            return ip
        else:
            out = subprocess.check_output(["ip", "route"], text=True)
            match = re.search(r"default via ([\d\.]+)", out)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def _executar_ping_unico(ip):
    sistema = platform.system().lower()
    if sistema == "windows":
        comando = ["ping", "-n", "1", "-w", str(TIMEOUT_PING_MS), ip]
    else:
        comando = ["ping", "-c", "1", "-W", "1", ip]

    flags = subprocess.CREATE_NO_WINDOW if sistema == "windows" else 0

    try:
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.2,
            creationflags=flags,
        )
        if resultado.returncode == 0:
            match = re.search(r'(?:tempo|time)[=<]([\d\.]+)\s*ms', resultado.stdout, re.IGNORECASE)
            if match:
                return True, float(match.group(1))
            return True, 1.0
    except Exception:
        pass
    return False, 0.0


def pingar_com_latencia(ip):
    """Envia ping com re-teste imediato anti-oscilação do Wi-Fi."""
    ok, ms = _executar_ping_unico(ip)
    if not ok:
        ok, ms = _executar_ping_unico(ip)
    return ok, ms


def testar_portas_cftv(ip, timeout=0.3):
    """Testa portas comuns de CFTV: 554 (RTSP) e 37777/8000 (Intelbras/Hikvision)."""
    portas = [554, 37777, 8000]
    for porta in portas:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            res = s.connect_ex((ip, porta))
            s.close()
            if res == 0:
                return True
        except Exception:
            pass
    return False


def obter_tabela_arp():
    """Lê a tabela ARP do Windows eliminando IPs inválidos e multicast."""
    tabela = {}
    sistema = platform.system().lower()
    try:
        flags = subprocess.CREATE_NO_WINDOW if sistema == "windows" else 0
        out = subprocess.check_output(["arp", "-a"], creationflags=flags, text=True, errors="ignore")
        for linha in out.splitlines():
            match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([\da-f]{2}[-:][\da-f]{2}[-:][\da-f]{2}[-:][\da-f]{2}[-:][\da-f]{2}[-:][\da-f]{2})", linha, re.IGNORECASE)
            if match:
                ip_f = match.group(1)
                mac_f = match.group(2).replace("-", ":").upper()
                if not ip_f.startswith("224.") and not ip_f.startswith("239.") and mac_f != "FF:FF:FF:FF:FF:FF":
                    tabela[ip_f] = mac_f
    except Exception:
        pass
    return tabela


def identificar_marca_ou_mac(ip, mac, tem_cftv=False):
    if tem_cftv:
        return "Câmera IP / DVR (CFTV Detectado)"

    if not mac:
        return "Dispositivo de Rede"

    segundo_char = mac[1].upper() if len(mac) > 1 else ""
    eh_mac_privado = segundo_char in ["2", "6", "A", "E"]

    prefixo_3 = mac[:8]
    for marca, prefixos in FABRICANTES_MAC.items():
        if prefixo_3 in prefixos:
            if marca == "SAMSUNG":
                return "Samsung (Galaxy / TV)"
            elif marca == "APPLE":
                return "iPhone / iPad (Apple)"
            elif marca == "MOTOROLA":
                return "Celular Motorola"
            elif marca == "LG":
                return "Smart TV / LG"
            elif marca == "INTELBRAS":
                return "Intelbras (Câmera / DVR)"
            elif marca == "HIKVISION":
                return "Hikvision (Câmera / DVR)"

    if eh_mac_privado:
        return f"Celular / Smartphone (MAC Privado - {mac[-8:]})"

    return f"Dispositivo de Rede (MAC: {mac[-8:]})"


class NetDiagApp:
    def _init_(self, root):
        self.root = root
        self.root.title("NetDiag — Monitor de CFTV e Rede Local")
        self.root.geometry("1000x800")
        self.root.configure(bg=BG_JANELA)
        self.root.minsize(850, 620)

        # Configurações de Rede
        self.ip_local = obter_ip_local()
        self.prefixo_rede = obter_prefixo_rede(self.ip_local)
        self.ip_gateway = obter_gateway_padrao() or f"{self.prefixo_rede}1"

        # Estruturas de Dados
        self.dispositivos = {}           
        self.dispositivos_ignorados = {} 
        self.falhas_consecutivas = {}
        self.nomes_personalizados = {}
        self.linhas_widgets = {}         
        self.varrendo = False
        self.em_execucao = True

        self._carregar_configuracoes()

        self._montar_cabecalho()
        self._montar_resumo()
        self._montar_lista_dispositivos()
        self._montar_eventos()

        self.disparar_varredura()
        self.root.after(1000, self._loop_varredura_automatica)
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # ---------- Persistência JSON ----------
    def _salvar_configuracoes(self):
        dados = {
            "nomes_personalizados": self.nomes_personalizados,
            "dispositivos_ignorados": self.dispositivos_ignorados
        }
        try:
            with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def _carregar_configuracoes(self):
        if os.path.exists(ARQUIVO_CONFIG):
            try:
                with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    self.nomes_personalizados = dados.get("nomes_personalizados", {})
                    self.dispositivos_ignorados = dados.get("dispositivos_ignorados", {})
            except Exception:
                pass

    # ---------- Interface Visual ----------
    def _montar_cabecalho(self):
        frame = tk.Frame(self.root, bg=BG_JANELA)
        frame.pack(fill="x", padx=24, pady=(20, 10))

        titulo_frame = tk.Frame(frame, bg=BG_JANELA)
        titulo_frame.pack(side="left")

        tk.Label(titulo_frame, text="● NetDiag CFTV", font=(FONTE_BASE, 18, "bold"),
                 bg=BG_JANELA, fg=TEXTO_PRIMARIO).pack(anchor="w")
        
        info_rede = f"Rede: {self.prefixo_rede}0/24  —  Gateway/Roteador: {self.ip_gateway}  —  Host Local: {self.ip_local}"
        tk.Label(titulo_frame, text=info_rede, font=(FONTE_BASE, 9), bg=BG_JANELA, fg=TEXTO_SECUNDARIO).pack(anchor="w")

        direita_frame = tk.Frame(frame, bg=BG_JANELA)
        direita_frame.pack(side="right")

        self.relogio_label = tk.Label(direita_frame, text="", font=(FONTE_BASE, 10),
                                     bg=BG_JANELA, fg=TEXTO_SECUNDARIO)
        self.relogio_label.pack(anchor="e")
        self._atualizar_relogio()

        self.status_varredura_label = tk.Label(direita_frame, text="", font=(FONTE_BASE, 8),
                                               bg=BG_JANELA, fg=TEXTO_SECUNDARIO)
        self.status_varredura_label.pack(anchor="e")

    def _atualizar_relogio(self):
        agora = datetime.now().strftime("%H:%M:%S")
        self.relogio_label.config(text=agora)
        self.root.after(1000, self._atualizar_relogio)

    def _montar_resumo(self):
        frame = tk.Frame(self.root, bg=BG_JANELA)
        frame.pack(fill="x", padx=24, pady=8)

        self.card_estavel = self._criar_card(frame, "ESTÁVEIS (VERDE)", "0", COR_VERDE)
        self.card_instavel = self._criar_card(frame, "INSTÁVEIS (AMARELO)", "0", COR_AMARELO)
        self.card_caiu = self._criar_card(frame, "QUEDAS (VERMELHO)", "0", COR_VERMELHO)

        botoes_frame = tk.Frame(frame, bg=BG_JANELA)
        botoes_frame.pack(side="left", expand=True, fill="both", padx=4)

        self.botao_varrer_agora = tk.Button(
            botoes_frame, text="Varrer agora", font=(FONTE_BASE, 9, "bold"),
            bg="#21262d", fg=TEXTO_PRIMARIO, activebackground="#30363d",
            activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0,
            cursor="hand2", command=self.disparar_varredura
        )
        self.botao_varrer_agora.pack(side="top", expand=True, fill="both", pady=(0, 2))

        self.botao_ignorados = tk.Button(
            botoes_frame, text="⚙️ Dispositivos Ignorados", font=(FONTE_BASE, 8, "bold"),
            bg="#1f242c", fg=TEXTO_SECUNDARIO, activebackground="#30363d",
            activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0,
            cursor="hand2", command=self.abrir_janela_ignorados
        )
        self.botao_ignorados.pack(side="bottom", expand=True, fill="both", pady=(2, 0))

    def _criar_card(self, parent, titulo, valor_inicial, cor):
        card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
        card.pack(side="left", expand=True, fill="both", padx=4)

        tk.Label(card, text=titulo, font=(FONTE_BASE, 8, "bold"), bg=BG_CARD,
                 fg=TEXTO_SECUNDARIO).pack(anchor="w", padx=14, pady=(10, 2))
        valor_label = tk.Label(card, text=valor_inicial, font=(FONTE_BASE, 20, "bold"),
                                bg=BG_CARD, fg=cor)
        valor_label.pack(anchor="w", padx=14, pady=(0, 10))
        return valor_label

    def _montar_lista_dispositivos(self):
        tk.Label(self.root, text="DISPOSITIVOS E CÂMERAS EM MONITORAMENTO", font=(FONTE_BASE, 8, "bold"),
                 bg=BG_JANELA, fg=TEXTO_SECUNDARIO).pack(anchor="w", padx=24, pady=(14, 6))

        frame_externo = tk.Frame(self.root, bg=BG_JANELA)
        frame_externo.pack(fill="x", padx=24)

        cabecalho = tk.Frame(frame_externo, bg=BG_HEADER_TABELA)
        cabecalho.pack(fill="x")
        tk.Label(cabecalho, text="", bg=BG_HEADER_TABELA, width=2).pack(side="left", padx=(10, 0), pady=6)
        tk.Label(cabecalho, text="IP", font=(FONTE_BASE, 8, "bold"), bg=BG_HEADER_TABELA,
                 fg=TEXTO_SECUNDARIO, width=15, anchor="w").pack(side="left", pady=6)
        tk.Label(cabecalho, text="IDENTIFICAÇÃO", font=(FONTE_BASE, 8, "bold"), bg=BG_HEADER_TABELA,
                 fg=TEXTO_SECUNDARIO, width=32, anchor="w").pack(side="left", pady=6)
        tk.Label(cabecalho, text="SITUAÇÃO / CONECTIVIDADE", font=(FONTE_BASE, 8, "bold"), bg=BG_HEADER_TABELA,
                 fg=TEXTO_SECUNDARIO, width=28, anchor="w").pack(side="left", pady=6)
        tk.Label(cabecalho, text="AÇÕES", font=(FONTE_BASE, 8, "bold"), bg=BG_HEADER_TABELA,
                 fg=TEXTO_SECUNDARIO, anchor="e").pack(side="right", padx=30, pady=6)

        canvas = tk.Canvas(frame_externo, bg=BG_JANELA, highlightthickness=0, height=210)
        scrollbar = ttk.Scrollbar(frame_externo, orient="vertical", command=canvas.yview)
        self.frame_dispositivos = tk.Frame(canvas, bg=BG_JANELA)

        self.frame_dispositivos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        janela_id = canvas.create_window((0, 0), window=self.frame_dispositivos, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(janela_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _montar_eventos(self):
        tk.Label(self.root, text="HISTÓRICO DE OCORRÊNCIAS E DIAGNÓSTICOS", font=(FONTE_BASE, 8, "bold"),
                 bg=BG_JANELA, fg=TEXTO_SECUNDARIO).pack(anchor="w", padx=24, pady=(16, 6))

        frame_externo = tk.Frame(self.root, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
        frame_externo.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        scrollbar = ttk.Scrollbar(frame_externo, orient="vertical")
        self.txt_eventos = tk.Text(
            frame_externo, bg=BG_CARD, fg=TEXTO_PRIMARIO, font=(FONTE_BASE, 9),
            relief="flat", bd=0, yscrollcommand=scrollbar.set, state="disabled", height=8
        )
        scrollbar.config(command=self.txt_eventos.yview)

        scrollbar.pack(side="right", fill="y")
        self.txt_eventos.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.txt_eventos.tag_configure("verde", foreground=COR_VERDE)
        self.txt_eventos.tag_configure("amarelo", foreground=COR_AMARELO)
        self.txt_eventos.tag_configure("vermelho", foreground=COR_VERMELHO)
        self.txt_eventos.tag_configure("cinza", foreground=TEXTO_SECUNDARIO)

    # ---------- Varredura & Diagnóstico ----------
    def disparar_varredura(self):
        if self.varrendo:
            return
        self.varrendo = True
        self.botao_varrer_agora.config(state="disabled", text="Varrendo...")
        self.status_varredura_label.config(text="Analisando a rede...")
        thread = threading.Thread(target=self._varrer_rede_thread, daemon=True)
        thread.start()

    def _varrer_rede_thread(self):
        try:
            pings_respostas = {}

            # 1. Ping em paralelo
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                futuros = {
                    executor.submit(pingar_com_latencia, f"{self.prefixo_rede}{h}"): f"{self.prefixo_rede}{h}"
                    for h in range(1, 255)
                }
                for futuro in futuros:
                    ip = futuros[futuro]
                    try:
                        pings_respostas[ip] = futuro.result(timeout=2.2)
                    except Exception:
                        pings_respostas[ip] = (False, 0.0)

            tabela_arp = obter_tabela_arp()
            gateway_online, _ = pings_respostas.get(self.ip_gateway, (False, 0.0))
            resultados_finais = {}

            # 2. Processa os resultados de toda a rede
            for ip, (ping_ok, ms) in pings_respostas.items():
                if ip in self.dispositivos_ignorados:
                    continue

                if ping_ok:
                    mac = tabela_arp.get(ip, "")

                    if ip == self.ip_local:
                        nome_detectado = "Este Notebook (Servidor NetDiag)"
                    elif ip == self.ip_gateway:
                        nome_detectado = "Roteador / Celular (Gateway)"
                    else:
                        cftv_ok = testar_portas_cftv(ip)
                        nome_detectado = identificar_marca_ou_mac(ip, mac, tem_cftv=cftv_ok)

                    if ms < 120:
                        status_str = f"Conexão Estável ({ms:.0f} ms)"
                        cor_str = COR_VERDE
                    else:
                        status_str = f"Oscilando / Instável ({ms:.0f} ms)"
                        cor_str = COR_AMARELO

                    resultados_finais[ip] = {
                        "status": status_str,
                        "cor": cor_str,
                        "ativo": True,
                        "nome_detectado": nome_detectado
                    }
                else:
                    # Se o IP já estava monitorado e parou de responder, prepara diagnóstico de queda
                    if ip in self.dispositivos:
                        motivo = "Caiu: Cabo Desconectado / Sem Energia" if gateway_online else "Caiu: Queda Geral no Switch/Roteador"
                        resultados_finais[ip] = {
                            "status": motivo,
                            "cor": COR_VERMELHO,
                            "ativo": False,
                            "nome_detectado": self.dispositivos[ip]["nome"]
                        }

            self.root.after(0, lambda: self._processar_resultado_varredura(resultados_finais))

        except Exception:
            self.root.after(0, self._destravar_varredura)

    def _destravar_varredura(self):
        self.varrendo = False
        self.botao_varrer_agora.config(state="normal", text="Varrer agora")

    def _processar_resultado_varredura(self, resultados):
        try:
            agora_str = datetime.now().strftime("%H:%M:%S")

            # Processa os dispositivos que responderam (Online)
            for ip, info in resultados.items():
                if info["ativo"]:
                    estava_offline = (ip in self.dispositivos and not self.dispositivos[ip]["ativo"])
                    self.falhas_consecutivas[ip] = 0
                    nome_exibido = self.nomes_personalizados.get(ip, info["nome_detectado"])

                    if ip not in self.dispositivos:
                        self.adicionar_evento(f"Dispositivo Encontrado: {ip} — {nome_exibido}", agora_str, info["cor"])
                    elif estava_offline:
                        self.adicionar_evento(f"Dispositivo Reconectado: {ip} — {nome_exibido}", agora_str, COR_VERDE)

                    self.dispositivos[ip] = {
                        "nome": nome_exibido,
                        "status": info["status"],
                        "cor": info["cor"],
                        "ativo": True
                    }

            # Processa os dispositivos que pararam de responder (Offline)
            for ip in list(self.dispositivos.keys()):
                info_scan = resultados.get(ip)
                
                # Se o IP não respondeu no scan atual
                if not info_scan or not info_scan["ativo"]:
                    self.falhas_consecutivas[ip] = self.falhas_consecutivas.get(ip, 0) + 1

                    # Confirma a queda se falhar em 2 varreduras seguidas
                    if self.falhas_consecutivas[ip] >= MAX_FALHAS_CONSECUTIVAS:
                        if self.dispositivos[ip]["ativo"]:
                            # Transição oficial de ONLINE -> OFFLINE
                            motivo_queda = info_scan["status"] if info_scan else "Caiu: Conexão Perdida"
                            
                            self.dispositivos[ip]["ativo"] = False
                            self.dispositivos[ip]["cor"] = COR_VERMELHO
                            self.dispositivos[ip]["status"] = motivo_queda

                            self.adicionar_evento(
                                f"⚠️ QUEDA CONFIRMADA: {ip} ({self.dispositivos[ip]['nome']}) — {motivo_queda}",
                                agora_str, COR_VERMELHO
                            )

            self._atualizar_interface_tabela()
            self._atualizar_cards_resumo()

            self.status_varredura_label.config(text=f"Última checagem: {agora_str}")
        finally:
            self.varrendo = False
            self.botao_varrer_agora.config(state="normal", text="Varrer agora")

    def _loop_varredura_automatica(self):
        if not self.em_execucao:
            return
        if not self.varrendo:
            self.disparar_varredura()
        self.root.after(INTERVALO_VARREDURA_SEGUNDOS * 1000, self._loop_varredura_automatica)

    # ---------- Gerenciamento de Ignorados ----------
    def ignorar_dispositivo(self, ip):
        if ip in self.dispositivos:
            info = self.dispositivos.pop(ip)
            self.falhas_consecutivas.pop(ip, None)
            
            if ip in self.linhas_widgets:
                self.linhas_widgets[ip]["frame"].destroy()
                del self.linhas_widgets[ip]

            self.dispositivos_ignorados[ip] = {
                "nome": info["nome"],
                "data": datetime.now().strftime("%H:%M:%S")
            }

            agora_str = datetime.now().strftime("%H:%M:%S")
            self.adicionar_evento(f"Dispositivo Ignorado: {ip} ({info['nome']}) — Removido dos scans", agora_str, TEXTO_SECUNDARIO)

            self._salvar_configuracoes()
            self._atualizar_interface_tabela()
            self._atualizar_cards_resumo()

    def abrir_janela_ignorados(self):
        janela = tk.Toplevel(self.root)
        janela.title("Dispositivos Ignorados (Lista Negra)")
        janela.geometry("550x380")
        janela.configure(bg=BG_JANELA)
        janela.transient(self.root)
        janela.grab_set()

        tk.Label(janela, text="DISPOSITIVOS EXCLUÍDOS DO SCAN", font=(FONTE_BASE, 10, "bold"),
                 bg=BG_JANELA, fg=TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(janela, text="Dispositivos nesta lista não reaparecerão nas varreduras automáticas.",
                 font=(FONTE_BASE, 8), bg=BG_JANELA, fg=TEXTO_SECUNDARIO).pack(anchor="w", padx=16, pady=(0, 12))

        frame_lista = tk.Frame(janela, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
        frame_lista.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        canvas = tk.Canvas(frame_lista, bg=BG_CARD, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame_lista, orient="vertical", command=canvas.yview)
        conteudo_frame = tk.Frame(canvas, bg=BG_CARD)

        conteudo_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        janela_id = canvas.create_window((0, 0), window=conteudo_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(janela_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def redesenhar_lista_ignorados():
            for w in conteudo_frame.winfo_children():
                w.destroy()

            if not self.dispositivos_ignorados:
                tk.Label(conteudo_frame, text="Nenhum dispositivo sendo ignorado no momento.",
                         font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_SECUNDARIO).pack(pady=40)
                return

            for ip, item in list(self.dispositivos_ignorados.items()):
                linha = tk.Frame(conteudo_frame, bg=BG_JANELA, highlightbackground=BORDA, highlightthickness=1)
                linha.pack(fill="x", pady=3, padx=6)

                tk.Label(linha, text=ip, font=(FONTE_BASE, 9, "bold"), bg=BG_JANELA, fg=TEXTO_PRIMARIO, width=15, anchor="w").pack(side="left", padx=8, pady=6)
                tk.Label(linha, text=item["nome"], font=(FONTE_BASE, 8), bg=BG_JANELA, fg=TEXTO_SECUNDARIO, width=22, anchor="w").pack(side="left", pady=6)

                def restaurar(ip_target=ip):
                    self.dispositivos_ignorados.pop(ip_target, None)
                    self._salvar_configuracoes()
                    redesenhar_lista_ignorados()
                    self.disparar_varredura()

                tk.Button(
                    linha, text="Restaurar", font=(FONTE_BASE, 8, "bold"),
                    bg="#238636", fg="#ffffff", activebackground="#2ea043",
                    activeforeground="#ffffff", relief="flat", bd=0, padx=10, pady=2,
                    cursor="hand2", command=restaurar
                ).pack(side="right", padx=8, pady=4)

        redesenhar_lista_ignorados()

    # ---------- Renderização Visual Otimizada ----------
    def _atualizar_cards_resumo(self):
        estaveis = sum(1 for d in self.dispositivos.values() if d["cor"] == COR_VERDE and d["ativo"])
        instaveis = sum(1 for d in self.dispositivos.values() if d["cor"] == COR_AMARELO and d["ativo"])
        quedas = sum(1 for d in self.dispositivos.values() if not d["ativo"])

        self.card_estavel.config(text=str(estaveis))
        self.card_instavel.config(text=str(instaveis))
        self.card_caiu.config(text=str(quedas))

        qtd_ignorados = len(self.dispositivos_ignorados)
        self.botao_ignorados.config(text=f"⚙️ Dispositivos Ignorados ({qtd_ignorados})")

    def _atualizar_interface_tabela(self):
        if not self.dispositivos:
            for w in list(self.linhas_widgets.keys()):
                self.linhas_widgets[w]["frame"].destroy()
                del self.linhas_widgets[w]
            return

        ips_ordenados = sorted(self.dispositivos.keys(), key=lambda ip: tuple(int(p) for p in ip.split(".")))

        for ip in ips_ordenados:
            info = self.dispositivos[ip]

            if ip not in self.linhas_widgets:
                linha = tk.Frame(self.frame_dispositivos, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
                linha.pack(fill="x", pady=2, padx=2)

                dot = tk.Label(linha, text="●", font=(FONTE_BASE, 11), bg=BG_CARD, fg=info["cor"], width=2)
                dot.pack(side="left", padx=(8, 0), pady=8)

                ip_lbl = tk.Label(linha, text=ip, font=(FONTE_BASE, 9, "bold"), bg=BG_CARD, fg=TEXTO_PRIMARIO, width=15, anchor="w")
                ip_lbl.pack(side="left", pady=8)

                nome_lbl = tk.Label(linha, text=info["nome"], font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_PRIMARIO, width=32, anchor="w")
                nome_lbl.pack(side="left", pady=8)

                status_lbl = tk.Label(linha, text=info["status"], font=(FONTE_BASE, 8, "bold"), bg=BG_CARD, fg=info["cor"], width=28, anchor="w")
                status_lbl.pack(side="left", pady=8)

                btn_ignorar = tk.Button(
                    linha, text="Ignorar", font=(FONTE_BASE, 8),
                    bg="#3d2121", fg=COR_VERMELHO, activebackground="#502828",
                    activeforeground=COR_VERMELHO, relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2", command=lambda i=ip: self.ignorar_dispositivo(i)
                )
                btn_ignorar.pack(side="right", padx=(4, 10), pady=6)

                btn_renomear = tk.Button(
                    linha, text="Renomear", font=(FONTE_BASE, 8),
                    bg="#21262d", fg=TEXTO_PRIMARIO, activebackground="#30363d",
                    activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2", command=lambda i=ip: self.renomear_dispositivo(i)
                )
                btn_renomear.pack(side="right", padx=2, pady=6)

                self.linhas_widgets[ip] = {
                    "frame": linha,
                    "dot": dot,
                    "nome_lbl": nome_lbl,
                    "status_lbl": status_lbl
                }
            else:
                w = self.linhas_widgets[ip]
                w["dot"].config(fg=info["cor"])
                w["nome_lbl"].config(text=info["nome"])
                w["status_lbl"].config(text=info["status"], fg=info["cor"])

        for ip_existente in list(self.linhas_widgets.keys()):
            if ip_existente not in self.dispositivos:
                self.linhas_widgets[ip_existente]["frame"].destroy()
                del self.linhas_widgets[ip_existente]

    def renomear_dispositivo(self, ip):
        nome_atual = self.dispositivos.get(ip, {}).get("nome", "")
        novo_nome = simpledialog.askstring(
            "Identificar Câmera/Equipamento",
            f"Digite o nome ou local para {ip} (ex: Câmera Recepção):",
            initialvalue=nome_atual,
            parent=self.root,
        )
        if novo_nome and novo_nome.strip():
            novo_nome = novo_nome.strip()
            self.nomes_personalizados[ip] = novo_nome
            if ip in self.dispositivos:
                self.dispositivos[ip]["nome"] = novo_nome
            self._salvar_configuracoes()
            self._atualizar_interface_tabela()

    def adicionar_evento(self, mensagem, horario, cor_tag):
        tag_nome = "cinza"
        if cor_tag == COR_VERDE:
            tag_nome = "verde"
        elif cor_tag == COR_AMARELO:
            tag_nome = "amarelo"
        elif cor_tag == COR_VERMELHO:
            tag_nome = "vermelho"

        self.txt_eventos.config(state="normal")
        self.txt_eventos.insert("1.0", f"[{horario}] {mensagem}\n", tag_nome)
        self.txt_eventos.config(state="disabled")

    def _ao_fechar(self):
        self.em_execucao = False
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = NetDiagApp(root)
    root.mainloop()