"""
NetDiag — Monitor de CFTV e Rede Local (Versão TCC)
Com Busca por IP/Nome/Status (Lupinha), Pastas/Grupos de Dispositivos (ex: Prédio 1, Prédio 2),
Registro Preciso de Quedas (Vermelho), Persistência JSON, Anti-Oscilação de Wi-Fi,
Reciclagem Visual Sem Travar a Interface e Notificações no Telegram.
"""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import socket
import subprocess
import ipaddress
import platform
import threading
import re
import json
import os
import time
import ssl
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ---------- Configurações e Arquivo de Persistência ----------
ARQUIVO_CONFIG = "netdiag_config.json"

# ---------- Temas (modo noturno / modo claro) ----------
# COR_VERDE = Conexão Estável | COR_AMARELO = Oscilação | COR_VERMELHO = Queda | COR_AZUL = Pastas/Grupos
TEMAS = {
    "escuro": {
        "BG_JANELA": "#0d1117",
        "BG_CARD": "#161b22",
        "BG_HEADER_TABELA": "#1c2128",
        "BORDA": "#30363d",
        "TEXTO_PRIMARIO": "#e6edf3",
        "TEXTO_SECUNDARIO": "#8b949e",
        "COR_VERDE": "#3fb950",
        "COR_AMARELO": "#d29922",
        "COR_VERMELHO": "#f85149",
        "COR_AZUL": "#58a6ff",
        "BG_HOVER": "#30363d",
        "BTN_BG": "#21262d",
        "BTN_BG_2": "#1f242c",
        "BTN_PERIGO_BG": "#3d2121",
        "BTN_PERIGO_HOVER": "#502828",
        "BTN_AZUL_BG": "#1f2a3d",
        "BTN_AZUL_HOVER": "#2a3b54",
        "TEXTO_SOBRE_AZUL": "#0d1117",
        "AZUL_HOVER": "#79b8ff",
        "BTN_VERDE_BG": "#238636",
        "BTN_VERDE_HOVER": "#2ea043",
    },
    "claro": {
        "BG_JANELA": "#f6f8fa",
        "BG_CARD": "#ffffff",
        "BG_HEADER_TABELA": "#eaeef2",
        "BORDA": "#d0d7de",
        "TEXTO_PRIMARIO": "#1f2328",
        "TEXTO_SECUNDARIO": "#57606a",
        "COR_VERDE": "#1a7f37",
        "COR_AMARELO": "#9a6700",
        "COR_VERMELHO": "#cf222e",
        "COR_AZUL": "#0969da",
        "BG_HOVER": "#d0d7de",
        "BTN_BG": "#eaeef2",
        "BTN_BG_2": "#eaeef2",
        "BTN_PERIGO_BG": "#ffebe9",
        "BTN_PERIGO_HOVER": "#ffcecb",
        "BTN_AZUL_BG": "#ddf4ff",
        "BTN_AZUL_HOVER": "#b6e3ff",
        "TEXTO_SOBRE_AZUL": "#ffffff",
        "AZUL_HOVER": "#0550ae",
        "BTN_VERDE_BG": "#1f883d",
        "BTN_VERDE_HOVER": "#1a7f37",
    },
}


def aplicar_tema(nome):
    """Atualiza as cores globais. As telas criadas depois já nascem com o novo tema."""
    globals().update(TEMAS.get(nome, TEMAS["escuro"]))


def detectar_tema_sistema():
    """Retorna 'claro' ou 'escuro' conforme o tema do sistema operacional (padrão: escuro)."""
    sistema = platform.system().lower()
    try:
        if sistema == "windows":
            import winreg
            caminho = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, caminho) as chave:
                valor, _ = winreg.QueryValueEx(chave, "AppsUseLightTheme")
                return "claro" if valor == 1 else "escuro"
        if sistema == "darwin":
            saida = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, timeout=2)
            return "escuro" if "dark" in saida.stdout.lower() else "claro"
    except Exception:
        pass
    return "escuro"


def resolver_tema(preferencia):
    """Converte a preferência salva ('escuro', 'claro' ou 'sistema') no tema que será aplicado."""
    if preferencia == "sistema":
        return detectar_tema_sistema()
    return preferencia if preferencia in TEMAS else "escuro"


def _normalizar_cor(cor):
    """Converte uma cor de status (verde/amarelo/vermelho/azul) de qualquer tema para a do tema atual."""
    for tema in TEMAS.values():
        for nome in ("COR_VERDE", "COR_AMARELO", "COR_VERMELHO", "COR_AZUL"):
            if cor == tema[nome]:
                return globals()[nome]
    return cor


aplicar_tema("escuro")

FONTE_BASE = "Segoe UI"

INTERVALO_VARREDURA_SEGUNDOS = 15
TIMEOUT_PING_MS = 800
MAX_THREADS = 35
MAX_FALHAS_CONSECUTIVAS = 2

# ---------- Telegram ----------
TELEGRAM_CONFIG_PADRAO = {
    "token": "",
    "chat_id": "",
    "ativo": False,
    "avisar_queda": True,
    "avisar_reconexao": True,
    "avisar_novos": False,
    "ignorar_ssl": False,   # só use se a rede/antivírus intercepta HTTPS (erro CERTIFICATE_VERIFY_FAILED)
}

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


def sondar_host_rede(ip):
    """Verifica se o host responde via ping ou por portas TCP comuns (caso ICMP esteja bloqueado)."""
    ok, ms = pingar_com_latencia(ip)
    if ok:
        return True, ms

    # Fallback TCP para dispositivos que bloqueiam ICMP (câmeras, smartphones, servidores)
    portas_comuns = [80, 443, 554, 8000, 37777, 22, 445, 8080, 5060]
    for porta in portas_comuns:
        try:
            inicio = time.perf_counter()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.25)
            res = s.connect_ex((ip, porta))
            s.close()
            if res == 0:
                latencia_tcp = max(1.0, (time.perf_counter() - inicio) * 1000.0)
                return True, latencia_tcp
        except Exception:
            pass
    return False, 0.0


def expandir_alvo_rede(entrada):
    """Converte uma entrada (ex: '192.168.19.', '192.168.19.0/24', '192.168.19.10') em lista de IPs."""
    texto = entrada.strip()
    if not texto:
        return []

    # Formato prefixo '192.168.19.'
    if texto.endswith("."):
        base = texto[:-1]
        partes = base.split(".")
        if len(partes) == 3 and all(p.isdigit() and 0 <= int(p) <= 255 for p in partes):
            return [f"{base}.{h}" for h in range(1, 255)]
        return []

    # Formato CIDR '192.168.19.0/24' (limitado a no máximo /20 = 4094 hosts para não travar)
    if "/" in texto:
        try:
            rede = ipaddress.ip_network(texto, strict=False)
            if rede.version == 4 and rede.num_addresses <= 4096:
                return [str(ip) for ip in rede.hosts()]
        except Exception:
            return []

    # Formato IP único '192.168.19.10'
    try:
        ip_obj = ipaddress.ip_address(texto)
        if ip_obj.version == 4:
            return [str(ip_obj)]
    except Exception:
        pass

    return []


def normalizar_alvo_rede(entrada):
    """Valida e normaliza a entrada de rede/IP para exibição e salvamento."""
    texto = entrada.strip()
    if not texto:
        return None
    if texto.endswith("."):
        base = texto[:-1]
        partes = base.split(".")
        if len(partes) == 3 and all(p.isdigit() and 0 <= int(p) <= 255 for p in partes):
            return f"{base}.0/24"
        return None
    if "/" in texto:
        try:
            rede = ipaddress.ip_network(texto, strict=False)
            if rede.version == 4 and rede.num_addresses <= 4096:
                return str(rede)
        except Exception:
            return None
    try:
        ip_obj = ipaddress.ip_address(texto)
        if ip_obj.version == 4:
            return str(ip_obj)
    except Exception:
        pass
    return None


def obter_tabela_arp():
    """Lê a tabela ARP do Windows eliminando IPs inválidos e multicast/broadcast."""
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
                primeiro_octeto = int(ip_f.split(".")[0])
                if primeiro_octeto >= 224:
                    continue
                if mac_f == "FF:FF:FF:FF:FF:FF":
                    continue
                tabela[ip_f] = mac_f
    except Exception:
        pass
    return tabela


def identificar_marca_ou_mac(ip, mac, tem_cftv=False):
    if tem_cftv:
        return "Câmera IP / DVR (CFTV Detectado)"

    if not mac:
        return "Dispositivo de Rede (MAC não capturado)"

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


# ---------- Funções do Telegram (sem dependências externas) ----------
def _criar_contexto_ssl(ignorar_verificacao=False):
    """Contexto SSL padrão (usa os certificados do sistema). Se pedido, desliga a verificação."""
    contexto = ssl.create_default_context()
    if ignorar_verificacao:
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE
    return contexto


def telegram_enviar_mensagem(token, chat_id, texto, timeout=10, ignorar_ssl=False):
    """Envia uma mensagem pela API do Telegram. Retorna (ok, detalhe)."""
    if not token or not chat_id:
        return False, "Token ou Chat ID não configurado."
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    dados = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": texto,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=dados, method="POST")
        with urllib.request.urlopen(req, timeout=timeout, context=_criar_contexto_ssl(ignorar_ssl)) as resp:
            corpo = json.loads(resp.read().decode("utf-8"))
            if corpo.get("ok"):
                return True, "Mensagem enviada."
            return False, corpo.get("description", "Resposta inesperada do Telegram.")
    except urllib.error.HTTPError as e:
        try:
            corpo = json.loads(e.read().decode("utf-8"))
            return False, corpo.get("description", f"Erro HTTP {e.code}")
        except Exception:
            return False, f"Erro HTTP {e.code}"
    except Exception as e:
        return False, f"Falha de conexão: {e}"


def telegram_detectar_chat_id(token, timeout=10, ignorar_ssl=False):
    """Lê as últimas mensagens recebidas pelo bot e devolve o chat_id mais recente."""
    if not token:
        return None, "Informe o token primeiro."
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=_criar_contexto_ssl(ignorar_ssl)) as resp:
            corpo = json.loads(resp.read().decode("utf-8"))
        if not corpo.get("ok"):
            return None, corpo.get("description", "Resposta inesperada do Telegram.")
        for item in reversed(corpo.get("result", [])):
            msg = item.get("message") or item.get("channel_post") or item.get("my_chat_member")
            if msg and "chat" in msg:
                return str(msg["chat"]["id"]), "Chat ID encontrado."
        return None, "Nenhuma mensagem encontrada. Abra o bot no Telegram, envie /start e tente de novo."
    except urllib.error.HTTPError as e:
        return None, "Token inválido." if e.code in (401, 404) else f"Erro HTTP {e.code}"
    except Exception as e:
        return None, f"Falha de conexão: {e}"


class NetDiagApp:
    def __init__(self, root):
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
        self.pastas = {}            # nome_da_pasta -> {"ips": [lista de ips]}
        self.ip_para_pasta = {}     # ip -> nome_da_pasta (indice reverso, p/ consulta rapida)
        self.redes_extras = []      # Lista de sub-redes/IPs extras (ex: ["192.168.19.0/24"])
        self.telegram = dict(TELEGRAM_CONFIG_PADRAO)
        self.primeira_varredura_concluida = False
        self.varrendo = False
        self.em_execucao = True
        self.historico_eventos = []      # (horario, mensagem, tag) — usado para redesenhar o histórico ao trocar de tema
        self.tema_preferido = "escuro"   # "escuro", "claro" ou "sistema"
        self.tema_atual = "escuro"

        self._carregar_configuracoes()
        self._aplicar_tema_salvo()

        self._montar_cabecalho()
        self._montar_resumo()
        self._montar_lista_dispositivos()
        self._montar_eventos()
        self._atualizar_cards_resumo()
        self._atualizar_relogio()

        self.disparar_varredura()
        self.root.after(1000, self._loop_varredura_automatica)
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # ---------- Persistência JSON ----------
    def _salvar_configuracoes(self):
        dados = {
            "nomes_personalizados": self.nomes_personalizados,
            "dispositivos_ignorados": self.dispositivos_ignorados,
            "pastas": self.pastas,
            "redes_extras": self.redes_extras,
            "telegram": self.telegram,
            "tema": self.tema_preferido,
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
                    self.pastas = dados.get("pastas", {})
                    self.redes_extras = dados.get("redes_extras", [])
                    self.telegram.update(dados.get("telegram", {}))
                    self.tema_preferido = dados.get("tema", "escuro")
            except Exception:
                pass

        self.ip_para_pasta = {}
        for nome_pasta, info_pasta in self.pastas.items():
            for ip in info_pasta.get("ips", []):
                self.ip_para_pasta[ip] = nome_pasta

    # ---------- Notificações Telegram ----------
    def notificar_telegram(self, texto, tipo="queda"):
        """Dispara a mensagem em thread separada para não travar a interface.

        tipo: 'queda', 'reconexao' ou 'novo' — cada um pode ser ligado/desligado na janela do Telegram.
        """
        cfg = self.telegram
        if not cfg.get("ativo") or not cfg.get("token") or not cfg.get("chat_id"):
            return
        if tipo == "queda" and not cfg.get("avisar_queda", True):
            return
        if tipo == "reconexao" and not cfg.get("avisar_reconexao", True):
            return
        if tipo == "novo" and not cfg.get("avisar_novos", False):
            return

        token = cfg["token"]
        chat_id = cfg["chat_id"]
        ignorar_ssl = cfg.get("ignorar_ssl", False)

        def _enviar():
            ok, detalhe = telegram_enviar_mensagem(token, chat_id, texto, ignorar_ssl=ignorar_ssl)
            if not ok and self.em_execucao:
                agora = datetime.now().strftime("%H:%M:%S")
                self.root.after(0, lambda: self.adicionar_evento(
                    f"Falha ao enviar Telegram: {detalhe}", agora, COR_AMARELO))

        threading.Thread(target=_enviar, daemon=True).start()

    def _descricao_dispositivo_telegram(self, ip, nome):
        pasta = self.ip_para_pasta.get(ip)
        linhas = [f"IP: {ip}", f"Nome: {nome}"]
        if pasta:
            linhas.append(f"Local/Pasta: {pasta}")
        return "\n".join(linhas)

    # ---------- Temas (escuro / claro / sistema) ----------
    def _aplicar_tema_salvo(self):
        """Aplica o tema escolhido nas cores globais e no estilo dos widgets ttk."""
        self.tema_atual = resolver_tema(self.tema_preferido)
        aplicar_tema(self.tema_atual)
        self.root.configure(bg=BG_JANELA)
        self._configurar_estilo_ttk()

    def _configurar_estilo_ttk(self):
        """Barras de rolagem e abas (ttk) seguem as cores do tema."""
        estilo = ttk.Style(self.root)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("Vertical.TScrollbar", background=BTN_BG, troughcolor=BG_JANELA,
                         bordercolor=BG_JANELA, arrowcolor=TEXTO_SECUNDARIO,
                         lightcolor=BTN_BG, darkcolor=BTN_BG, relief="flat")
        estilo.map("Vertical.TScrollbar", background=[("active", BG_HOVER)])
        estilo.configure("TNotebook", background=BG_JANELA, borderwidth=0)
        estilo.configure("TNotebook.Tab", background=BTN_BG, foreground=TEXTO_SECUNDARIO,
                         padding=(18, 8), borderwidth=0, font=(FONTE_BASE, 9, "bold"))
        estilo.map("TNotebook.Tab",
                   background=[("selected", BG_CARD)],
                   foreground=[("selected", TEXTO_PRIMARIO)])

    def _trocar_tema(self):
        """Aplica o tema escolhido e reconstrói a tela principal, mantendo dados e histórico."""
        self._aplicar_tema_salvo()
        for dados in self.dispositivos.values():
            dados["cor"] = _normalizar_cor(dados["cor"])
        self._reconstruir_interface()

    def _reconstruir_interface(self):
        texto_busca = self.entry_busca.get()
        texto_status = self.status_varredura_label.cget("text")

        for widget in self.root.winfo_children():
            if not isinstance(widget, tk.Toplevel):
                widget.destroy()
        self.linhas_widgets = {}

        self._montar_cabecalho()
        self._montar_resumo()
        self._montar_lista_dispositivos()
        self._montar_eventos()

        if texto_busca:
            self.entry_busca.insert(0, texto_busca)
        self.status_varredura_label.config(text=texto_status)
        if self.varrendo:
            self.botao_varrer_agora.config(state="disabled", text="Varrendo...")
        self.relogio_label.config(text=datetime.now().strftime("%H:%M:%S"))

        self._renderizar_historico()
        self._atualizar_interface_tabela()
        self._atualizar_cards_resumo()

    def _renderizar_historico(self):
        """Redesenha o histórico de ocorrências (mais recente no topo) após reconstruir a tela."""
        self.txt_eventos.config(state="normal")
        self.txt_eventos.delete("1.0", "end")
        for horario, mensagem, tag in self.historico_eventos:
            self.txt_eventos.insert("1.0", f"[{horario}] {mensagem}\n", tag)
        self.txt_eventos.config(state="disabled")

    # ---------- Janela de Configurações (abas: Aparência e Telegram) ----------
    def abrir_janela_configuracoes(self, aba_inicial=0):
        janela = tk.Toplevel(self.root)
        janela.title("Configurações")
        janela.geometry("640x720")
        janela.minsize(600, 660)
        janela.configure(bg=BG_JANELA)
        janela.transient(self.root)
        janela.grab_set()
        janela.bind("<Escape>", lambda e: janela.destroy())

        tk.Label(janela, text="CONFIGURAÇÕES", font=(FONTE_BASE, 10, "bold"),
                 bg=BG_JANELA, fg=TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 8))

        # O rodapé é empacotado antes das abas para os botões nunca ficarem cortados
        rodape = tk.Frame(janela, bg=BG_JANELA)
        rodape.pack(side="bottom", fill="x", padx=16, pady=(6, 16))

        notebook = ttk.Notebook(janela)
        notebook.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        aba_aparencia = tk.Frame(notebook, bg=BG_JANELA)
        aba_telegram = tk.Frame(notebook, bg=BG_JANELA)
        notebook.add(aba_aparencia, text="🎨  Aparência")
        notebook.add(aba_telegram, text="📱  Telegram")
        notebook.select(aba_aparencia if aba_inicial == 0 else aba_telegram)

        # ================= ABA APARÊNCIA =================
        tk.Label(aba_aparencia, text="TEMA DA INTERFACE", font=(FONTE_BASE, 9, "bold"),
                 bg=BG_JANELA, fg=TEXTO_PRIMARIO).pack(anchor="w", padx=4, pady=(16, 4))
        tk.Label(
            aba_aparencia,
            text=("Escolha o modo noturno (escuro), o modo claro ou deixe o NetDiag acompanhar o tema do "
                  "sistema. A mudança é aplicada ao clicar em Salvar. O tema do sistema é lido quando o "
                  "programa abre e quando você salva."),
            font=(FONTE_BASE, 8), bg=BG_JANELA, fg=TEXTO_SECUNDARIO, justify="left", wraplength=560
        ).pack(anchor="w", padx=4, pady=(0, 12))

        var_tema = tk.StringVar(value=self.tema_preferido)
        card_tema = tk.Frame(aba_aparencia, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
        card_tema.pack(fill="x", padx=4)

        for valor, texto in (("escuro", "🌙  Modo noturno (escuro)"),
                             ("claro", "☀️  Modo claro"),
                             ("sistema", "🖥️  Seguir o tema do sistema")):
            tk.Radiobutton(
                card_tema, text=texto, value=valor, variable=var_tema,
                bg=BG_CARD, fg=TEXTO_PRIMARIO, selectcolor=BG_CARD,
                activebackground=BG_CARD, activeforeground=TEXTO_PRIMARIO,
                font=(FONTE_BASE, 10), anchor="w", bd=0, highlightthickness=0, cursor="hand2"
            ).pack(fill="x", padx=14, pady=8)

        tk.Label(aba_aparencia, text=f"Tema do sistema detectado agora: {detectar_tema_sistema()}",
                 font=(FONTE_BASE, 8), bg=BG_JANELA, fg=TEXTO_SECUNDARIO).pack(anchor="w", padx=4, pady=(10, 0))

        # ================= ABA TELEGRAM =================
        tk.Label(aba_telegram, text="NOTIFICAÇÕES NO TELEGRAM", font=(FONTE_BASE, 9, "bold"),
                 bg=BG_JANELA, fg=TEXTO_PRIMARIO).pack(anchor="w", padx=4, pady=(16, 4))
        tk.Label(
            aba_telegram,
            text=("1) No Telegram, converse com @BotFather, envie /newbot e copie o token.\n"
                  "2) Abra o seu bot no Telegram e envie /start (ou adicione-o ao grupo).\n"
                  "3) Cole o token abaixo e clique em \"Detectar Chat ID\"."),
            font=(FONTE_BASE, 8), bg=BG_JANELA, fg=TEXTO_SECUNDARIO, justify="left", wraplength=560
        ).pack(anchor="w", padx=4, pady=(0, 12))

        card = tk.Frame(aba_telegram, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
        card.pack(fill="x", padx=4, pady=(0, 10))

        def campo(rotulo, valor, oculto=False):
            tk.Label(card, text=rotulo, font=(FONTE_BASE, 8, "bold"), bg=BG_CARD,
                     fg=TEXTO_SECUNDARIO).pack(anchor="w", padx=12, pady=(10, 2))
            entry = tk.Entry(card, font=(FONTE_BASE, 9), bg=BG_JANELA, fg=TEXTO_PRIMARIO,
                             insertbackground=TEXTO_PRIMARIO, relief="flat", bd=0,
                             show="•" if oculto else "")
            entry.pack(fill="x", padx=12, ipady=5)
            entry.insert(0, valor)
            return entry

        entry_token = campo("TOKEN DO BOT", self.telegram.get("token", ""), oculto=True)
        entry_chat = campo("CHAT ID", self.telegram.get("chat_id", ""))
        tk.Frame(card, bg=BG_CARD, height=10).pack()

        var_ativo = tk.BooleanVar(value=self.telegram.get("ativo", False))
        var_queda = tk.BooleanVar(value=self.telegram.get("avisar_queda", True))
        var_reconexao = tk.BooleanVar(value=self.telegram.get("avisar_reconexao", True))
        var_novos = tk.BooleanVar(value=self.telegram.get("avisar_novos", False))
        var_ssl = tk.BooleanVar(value=self.telegram.get("ignorar_ssl", False))

        opcoes = tk.Frame(aba_telegram, bg=BG_JANELA)
        opcoes.pack(fill="x", padx=4, pady=(0, 6))

        def check(texto, var, destaque=False):
            tk.Checkbutton(
                opcoes, text=texto, variable=var, bg=BG_JANELA,
                fg=TEXTO_PRIMARIO if destaque else TEXTO_SECUNDARIO,
                selectcolor=BG_CARD, activebackground=BG_JANELA, activeforeground=TEXTO_PRIMARIO,
                font=(FONTE_BASE, 9, "bold" if destaque else "normal"), anchor="w", bd=0, highlightthickness=0
            ).pack(anchor="w", pady=1)

        check("Ativar notificações no Telegram", var_ativo, destaque=True)
        check("Avisar quando um dispositivo cair (🔴)", var_queda)
        check("Avisar quando um dispositivo voltar (🟢)", var_reconexao)
        check("Avisar quando um dispositivo novo aparecer (🆕)", var_novos)
        check("Ignorar verificação SSL (só se der erro de certificado — menos seguro)", var_ssl)

        label_resultado = tk.Label(aba_telegram, text="", font=(FONTE_BASE, 8), bg=BG_JANELA,
                                   fg=TEXTO_SECUNDARIO, wraplength=560, justify="left")
        label_resultado.pack(anchor="w", padx=4, pady=(8, 4))

        def mostrar(texto, cor):
            if janela.winfo_exists():
                label_resultado.config(text=texto, fg=cor)

        def detectar_chat():
            token = entry_token.get().strip()
            ignorar = var_ssl.get()
            mostrar("Procurando Chat ID...", TEXTO_SECUNDARIO)

            def tarefa():
                chat_id, detalhe = telegram_detectar_chat_id(token, ignorar_ssl=ignorar)

                def concluir():
                    if chat_id:
                        entry_chat.delete(0, "end")
                        entry_chat.insert(0, chat_id)
                        mostrar(f"✔ {detalhe} ({chat_id})", COR_VERDE)
                    else:
                        mostrar(f"✖ {detalhe}", COR_VERMELHO)
                try:
                    janela.after(0, concluir)
                except Exception:
                    pass  # janela foi fechada enquanto a consulta rodava

            threading.Thread(target=tarefa, daemon=True).start()

        def enviar_teste():
            token = entry_token.get().strip()
            chat_id = entry_chat.get().strip()
            ignorar = var_ssl.get()
            mostrar("Enviando mensagem de teste...", TEXTO_SECUNDARIO)

            def tarefa():
                ok, detalhe = telegram_enviar_mensagem(
                    token, chat_id,
                    f"✅ NetDiag conectado ao Telegram!\nHost: {self.ip_local}\nHorário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                    ignorar_ssl=ignorar
                )
                try:
                    janela.after(0, lambda: mostrar(
                        ("✔ " if ok else "✖ ") + detalhe, COR_VERDE if ok else COR_VERMELHO))
                except Exception:
                    pass  # janela foi fechada enquanto o envio rodava

            threading.Thread(target=tarefa, daemon=True).start()

        botoes_telegram = tk.Frame(aba_telegram, bg=BG_JANELA)
        botoes_telegram.pack(fill="x", padx=4, pady=(4, 0))
        tk.Button(botoes_telegram, text="Detectar Chat ID", font=(FONTE_BASE, 8, "bold"),
                  bg=BTN_BG, fg=TEXTO_PRIMARIO, activebackground=BG_HOVER,
                  activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=detectar_chat).pack(side="left", padx=(0, 6))
        tk.Button(botoes_telegram, text="Enviar teste", font=(FONTE_BASE, 8, "bold"),
                  bg=BTN_BG, fg=COR_AZUL, activebackground=BG_HOVER,
                  activeforeground=COR_AZUL, relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=enviar_teste).pack(side="left")

        # ================= RODAPÉ (vale para as duas abas) =================
        def salvar():
            self.telegram["token"] = entry_token.get().strip()
            self.telegram["chat_id"] = entry_chat.get().strip()
            self.telegram["ativo"] = var_ativo.get()
            self.telegram["avisar_queda"] = var_queda.get()
            self.telegram["avisar_reconexao"] = var_reconexao.get()
            self.telegram["avisar_novos"] = var_novos.get()
            self.telegram["ignorar_ssl"] = var_ssl.get()
            self.tema_preferido = var_tema.get()
            self._salvar_configuracoes()
            janela.destroy()

            if resolver_tema(self.tema_preferido) != self.tema_atual:
                # Reconstrói a tela principal depois que esta janela fechar
                self.root.after(50, self._trocar_tema)
            else:
                self._atualizar_cards_resumo()

        tk.Button(rodape, text="Salvar", font=(FONTE_BASE, 9, "bold"),
                  bg=BTN_VERDE_BG, fg="#ffffff", activebackground=BTN_VERDE_HOVER,
                  activeforeground="#ffffff", relief="flat", bd=0, padx=22, pady=7,
                  cursor="hand2", command=salvar).pack(side="right")
        tk.Button(rodape, text="Cancelar", font=(FONTE_BASE, 9),
                  bg=BTN_BG, fg=TEXTO_PRIMARIO, activebackground=BG_HOVER,
                  activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0, padx=16, pady=7,
                  cursor="hand2", command=janela.destroy).pack(side="right", padx=(0, 8))

    # ---------- Interface Visual ----------
    def _montar_cabecalho(self):
        frame = tk.Frame(self.root, bg=BG_JANELA)
        frame.pack(fill="x", padx=24, pady=(20, 10))

        titulo_frame = tk.Frame(frame, bg=BG_JANELA)
        titulo_frame.pack(side="left")

        tk.Label(titulo_frame, text="● NetDiag CFTV", font=(FONTE_BASE, 18, "bold"),
                 bg=BG_JANELA, fg=TEXTO_PRIMARIO).pack(anchor="w")

        extras_txt = f"  |  Extras: {', '.join(self.redes_extras)}" if self.redes_extras else ""
        info_rede = f"Rede: {self.prefixo_rede}0/24{extras_txt}  —  Gateway: {self.ip_gateway}  —  Host: {self.ip_local}"
        self.label_info_rede = tk.Label(titulo_frame, text=info_rede, font=(FONTE_BASE, 9), bg=BG_JANELA, fg=TEXTO_SECUNDARIO)
        self.label_info_rede.pack(anchor="w")

        direita_frame = tk.Frame(frame, bg=BG_JANELA)
        direita_frame.pack(side="right")

        self.relogio_label = tk.Label(direita_frame, text="", font=(FONTE_BASE, 10),
                                     bg=BG_JANELA, fg=TEXTO_SECUNDARIO)
        self.relogio_label.pack(anchor="e")

        self.status_varredura_label = tk.Label(direita_frame, text="", font=(FONTE_BASE, 8),
                                               bg=BG_JANELA, fg=TEXTO_SECUNDARIO)
        self.status_varredura_label.pack(anchor="e")

        self.telegram_status_label = tk.Label(direita_frame, text="", font=(FONTE_BASE, 8),
                                              bg=BG_JANELA, fg=TEXTO_SECUNDARIO)
        self.telegram_status_label.pack(anchor="e")

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
            bg=BTN_BG, fg=TEXTO_PRIMARIO, activebackground=BG_HOVER,
            activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0,
            cursor="hand2", command=self.disparar_varredura
        )
        self.botao_varrer_agora.pack(side="top", expand=True, fill="both", pady=(0, 2))

        linha_botoes_extra = tk.Frame(botoes_frame, bg=BG_JANELA)
        linha_botoes_extra.pack(side="bottom", expand=True, fill="both", pady=(2, 0))

        self.botao_ignorados = tk.Button(
            linha_botoes_extra, text="⚙️ Ignorados", font=(FONTE_BASE, 8, "bold"),
            bg=BTN_BG_2, fg=TEXTO_SECUNDARIO, activebackground=BG_HOVER,
            activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0,
            cursor="hand2", command=self.abrir_janela_ignorados
        )
        self.botao_ignorados.pack(side="left", expand=True, fill="both", padx=(0, 2))

        self.botao_pastas = tk.Button(
            linha_botoes_extra, text="📁 Pastas", font=(FONTE_BASE, 8, "bold"),
            bg=BTN_BG_2, fg=COR_AZUL, activebackground=BG_HOVER,
            activeforeground=COR_AZUL, relief="flat", bd=0,
            cursor="hand2", command=self.abrir_janela_gerenciar_pastas
        )
        self.botao_pastas.pack(side="left", expand=True, fill="both", padx=2)

        self.botao_redes = tk.Button(
            linha_botoes_extra, text="🌐 Sub-redes", font=(FONTE_BASE, 8, "bold"),
            bg=BTN_BG_2, fg=COR_VERDE, activebackground=BG_HOVER,
            activeforeground=COR_VERDE, relief="flat", bd=0,
            cursor="hand2", command=self.abrir_janela_redes_extras
        )
        self.botao_redes.pack(side="left", expand=True, fill="both", padx=2)

        self.botao_config = tk.Button(
            linha_botoes_extra, text="🔧 Config", font=(FONTE_BASE, 8, "bold"),
            bg=BTN_BG_2, fg=TEXTO_PRIMARIO, activebackground=BG_HOVER,
            activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0,
            cursor="hand2", command=self.abrir_janela_configuracoes
        )
        self.botao_config.pack(side="left", expand=True, fill="both", padx=(2, 0))

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
        frame_titulo_busca = tk.Frame(self.root, bg=BG_JANELA)
        frame_titulo_busca.pack(fill="x", padx=24, pady=(14, 6))

        tk.Label(frame_titulo_busca, text="DISPOSITIVOS E CÂMERAS EM MONITORAMENTO", font=(FONTE_BASE, 8, "bold"),
                 bg=BG_JANELA, fg=TEXTO_SECUNDARIO).pack(side="left")

        frame_busca = tk.Frame(frame_titulo_busca, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
        frame_busca.pack(side="right")

        tk.Label(frame_busca, text="🔍", font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_SECUNDARIO).pack(side="left", padx=(8, 2))

        self.entry_busca = tk.Entry(
            frame_busca, font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_PRIMARIO,
            insertbackground=TEXTO_PRIMARIO, relief="flat", bd=0, width=22
        )
        self.entry_busca.pack(side="left", padx=(0, 8), pady=3)
        self.entry_busca.bind("<KeyRelease>", lambda e: self._atualizar_interface_tabela())

        frame_externo = tk.Frame(self.root, bg=BG_JANELA)
        frame_externo.pack(fill="x", padx=24)

        cabecalho = tk.Frame(frame_externo, bg=BG_HEADER_TABELA)
        cabecalho.pack(fill="x")
        tk.Label(cabecalho, text="", bg=BG_HEADER_TABELA, width=2).pack(side="left", padx=(10, 0), pady=6)
        tk.Label(cabecalho, text="IP", font=(FONTE_BASE, 8, "bold"), bg=BG_HEADER_TABELA,
                 fg=TEXTO_SECUNDARIO, width=15, anchor="w").pack(side="left", pady=6)
        tk.Label(cabecalho, text="IDENTIFICAÇÃO", font=(FONTE_BASE, 8, "bold"), bg=BG_HEADER_TABELA,
                 fg=TEXTO_SECUNDARIO, width=28, anchor="w").pack(side="left", pady=6)
        tk.Label(cabecalho, text="SITUAÇÃO / CONECTIVIDADE", font=(FONTE_BASE, 8, "bold"), bg=BG_HEADER_TABELA,
                 fg=TEXTO_SECUNDARIO, width=24, anchor="w").pack(side="left", pady=6)
        tk.Label(cabecalho, text="AÇÕES", font=(FONTE_BASE, 8, "bold"), bg=BG_HEADER_TABELA,
                 fg=TEXTO_SECUNDARIO, anchor="e").pack(side="right", padx=20, pady=6)

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

    def _obter_ips_para_varrer(self):
        """Monta a lista única de todos os IPs da rede local + sub-redes/IPs extras configurados."""
        alvos = set(f"{self.prefixo_rede}{h}" for h in range(1, 255))
        for item in self.redes_extras:
            for ip in expandir_alvo_rede(item):
                alvos.add(ip)
        for ip in self.dispositivos.keys():
            if ip not in self.dispositivos_ignorados:
                alvos.add(ip)
        return sorted(alvos, key=lambda ip: tuple(int(p) for p in ip.split(".")))

    def _varrer_rede_thread(self):
        try:
            pings_respostas = {}
            lista_ips = self._obter_ips_para_varrer()
            workers = min(60, max(MAX_THREADS, len(lista_ips) // 8 + 1))

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futuros = {
                    executor.submit(sondar_host_rede, ip): ip
                    for ip in lista_ips
                }
                for futuro in futuros:
                    ip = futuros[futuro]
                    try:
                        pings_respostas[ip] = futuro.result(timeout=3.5)
                    except Exception:
                        pings_respostas[ip] = (False, 0.0)

            time.sleep(0.5)

            tabela_arp = obter_tabela_arp()
            gateway_online, _ = pings_respostas.get(self.ip_gateway, (False, 0.0))
            resultados_finais = {}

            for ip, (ping_ok, ms) in pings_respostas.items():
                if ip in self.dispositivos_ignorados:
                    continue

                if ping_ok:
                    mac = tabela_arp.get(ip, "")

                    if ip == self.ip_local:
                        nome_detectado = "Este Computador (Servidor NetDiag)"
                    elif ip == self.ip_gateway:
                        nome_detectado = "Roteador / Gateway"
                    else:
                        cftv_ok = testar_portas_cftv(ip)
                        nome_detectado = identificar_marca_ou_mac(ip, mac, tem_cftv=cftv_ok)
                        if not ip.startswith(self.prefixo_rede) and not mac and not cftv_ok:
                            nome_detectado = "Dispositivo em Sub-rede Remota"

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
            data_hora_completa = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            # Se o tema mudou durante a varredura, converte as cores para as do tema atual
            for info in resultados.values():
                info["cor"] = _normalizar_cor(info["cor"])

            for ip, info in resultados.items():
                if info["ativo"]:
                    estava_offline = (ip in self.dispositivos and not self.dispositivos[ip]["ativo"])
                    self.falhas_consecutivas[ip] = 0
                    nome_exibido = self.nomes_personalizados.get(ip, info["nome_detectado"])

                    if ip not in self.dispositivos:
                        self.adicionar_evento(f"Dispositivo Encontrado: {ip} — {nome_exibido}", agora_str, info["cor"])
                        # Só avisa "novo" depois da 1ª varredura, para não mandar a rede inteira de uma vez
                        if self.primeira_varredura_concluida:
                            self.notificar_telegram(
                                f"🆕 NOVO DISPOSITIVO NA REDE\n"
                                f"{self._descricao_dispositivo_telegram(ip, nome_exibido)}\n"
                                f"Horário: {data_hora_completa}",
                                tipo="novo"
                            )
                    elif estava_offline:
                        self.adicionar_evento(f"Dispositivo Reconectado: {ip} — {nome_exibido}", agora_str, COR_VERDE)
                        self.notificar_telegram(
                            f"🟢 DISPOSITIVO RECONECTADO\n"
                            f"{self._descricao_dispositivo_telegram(ip, nome_exibido)}\n"
                            f"Status: {info['status']}\n"
                            f"Horário: {data_hora_completa}",
                            tipo="reconexao"
                        )

                    self.dispositivos[ip] = {
                        "nome": nome_exibido,
                        "status": info["status"],
                        "cor": info["cor"],
                        "ativo": True
                    }

            for ip in list(self.dispositivos.keys()):
                info_scan = resultados.get(ip)

                if not info_scan or not info_scan["ativo"]:
                    self.falhas_consecutivas[ip] = self.falhas_consecutivas.get(ip, 0) + 1

                    if self.falhas_consecutivas[ip] >= MAX_FALHAS_CONSECUTIVAS:
                        if self.dispositivos[ip]["ativo"]:
                            motivo_queda = info_scan["status"] if info_scan else "Caiu: Conexão Perdida"

                            self.dispositivos[ip]["ativo"] = False
                            self.dispositivos[ip]["cor"] = COR_VERMELHO
                            self.dispositivos[ip]["status"] = motivo_queda

                            self.adicionar_evento(
                                f"⚠️ QUEDA CONFIRMADA: {ip} ({self.dispositivos[ip]['nome']}) — {motivo_queda}",
                                agora_str, COR_VERMELHO
                            )
                            self.notificar_telegram(
                                f"🔴 QUEDA CONFIRMADA\n"
                                f"{self._descricao_dispositivo_telegram(ip, self.dispositivos[ip]['nome'])}\n"
                                f"Motivo: {motivo_queda}\n"
                                f"Horário: {data_hora_completa}",
                                tipo="queda"
                            )

            self.primeira_varredura_concluida = True

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
                    bg=BTN_VERDE_BG, fg="#ffffff", activebackground=BTN_VERDE_HOVER,
                    activeforeground="#ffffff", relief="flat", bd=0, padx=10, pady=2,
                    cursor="hand2", command=restaurar
                ).pack(side="right", padx=8, pady=4)

        redesenhar_lista_ignorados()

    # ---------- Gerenciamento de Sub-redes / IPs Extras ----------
    def abrir_janela_redes_extras(self):
        janela = tk.Toplevel(self.root)
        janela.title("Sub-redes e IPs Extras")
        janela.geometry("620x460")
        janela.configure(bg=BG_JANELA)
        janela.transient(self.root)
        janela.grab_set()
        janela.bind("<Escape>", lambda e: janela.destroy())

        tk.Label(janela, text="SUB-REDES E IPs EXTRAS MONITORADOS", font=(FONTE_BASE, 10, "bold"),
                 bg=BG_JANELA, fg=TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(
            janela,
            text=(f"A rede local ({self.prefixo_rede}0/24) já é varrida automaticamente. Adicione aqui outras "
                  "sub-redes ou IPs específicos (ex: 192.168.19.0/24 ou 192.168.19.10)."),
            font=(FONTE_BASE, 8), bg=BG_JANELA, fg=TEXTO_SECUNDARIO, wraplength=580, justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 12))

        frame_add = tk.Frame(janela, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
        frame_add.pack(fill="x", padx=16, pady=(0, 12))

        entry_alvo = tk.Entry(
            frame_add, font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_PRIMARIO,
            insertbackground=TEXTO_PRIMARIO, relief="flat", bd=0
        )
        entry_alvo.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        def adicionar_alvo():
            bruto = entry_alvo.get().strip()
            normalizado = normalizar_alvo_rede(bruto)
            if not normalizado:
                messagebox.showwarning(
                    "Formato inválido",
                    "Informe um IP válido (ex: 192.168.19.10) ou sub-rede CIDR (ex: 192.168.19.0/24).",
                    parent=janela
                )
                return
            if normalizado == f"{self.prefixo_rede}0/24":
                messagebox.showinfo(
                    "Rede já incluída",
                    f"A sub-rede {normalizado} já é a rede principal deste computador.",
                    parent=janela
                )
                return
            if normalizado in self.redes_extras:
                messagebox.showwarning("Já cadastrado", f'"{normalizado}" já está na lista.', parent=janela)
                return

            self.redes_extras.append(normalizado)
            self._salvar_configuracoes()
            self._atualizar_cards_resumo()
            entry_alvo.delete(0, "end")
            redesenhar_lista()
            self.disparar_varredura()

        entry_alvo.bind("<Return>", lambda e: adicionar_alvo())

        tk.Button(
            frame_add, text="+ Adicionar", font=(FONTE_BASE, 8, "bold"),
            bg=BTN_VERDE_BG, fg="#ffffff", activebackground=BTN_VERDE_HOVER,
            activeforeground="#ffffff", relief="flat", bd=0, padx=14, pady=4,
            cursor="hand2", command=adicionar_alvo
        ).pack(side="right", padx=8, pady=6)

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

        def redesenhar_lista():
            for w in conteudo_frame.winfo_children():
                w.destroy()

            # Linha fixa da rede principal
            linha_local = tk.Frame(conteudo_frame, bg=BG_JANELA, highlightbackground=BORDA, highlightthickness=1)
            linha_local.pack(fill="x", pady=3, padx=6)
            tk.Label(linha_local, text=f"🏠 {self.prefixo_rede}0/24", font=(FONTE_BASE, 9, "bold"),
                     bg=BG_JANELA, fg=TEXTO_PRIMARIO, anchor="w").pack(side="left", padx=10, pady=8)
            tk.Label(linha_local, text="Rede principal (automática)", font=(FONTE_BASE, 8),
                     bg=BG_JANELA, fg=TEXTO_SECUNDARIO).pack(side="right", padx=10, pady=8)

            if not self.redes_extras:
                tk.Label(conteudo_frame, text="Nenhuma sub-rede extra cadastrada ainda.\nExemplos: 192.168.19.0/24 ou 192.168.19.10",
                         font=(FONTE_BASE, 8), bg=BG_CARD, fg=TEXTO_SECUNDARIO, justify="center").pack(pady=30)
                return

            for alvo in list(self.redes_extras):
                qtd_ips = len(expandir_alvo_rede(alvo))
                linha = tk.Frame(conteudo_frame, bg=BG_JANELA, highlightbackground=BORDA, highlightthickness=1)
                linha.pack(fill="x", pady=3, padx=6)

                tk.Label(linha, text=f"🌐 {alvo}", font=(FONTE_BASE, 9, "bold"), bg=BG_JANELA,
                         fg=COR_VERDE, anchor="w").pack(side="left", padx=10, pady=8)
                tk.Label(linha, text=f"{qtd_ips} host(s)", font=(FONTE_BASE, 8), bg=BG_JANELA,
                         fg=TEXTO_SECUNDARIO).pack(side="left", padx=6, pady=8)

                def remover(item=alvo):
                    if item in self.redes_extras:
                        self.redes_extras.remove(item)
                        self._salvar_configuracoes()
                        self._atualizar_cards_resumo()
                        redesenhar_lista()

                tk.Button(
                    linha, text="Remover", font=(FONTE_BASE, 8),
                    bg=BTN_PERIGO_BG, fg=COR_VERMELHO, activebackground=BTN_PERIGO_HOVER,
                    activeforeground=COR_VERMELHO, relief="flat", bd=0, padx=10, pady=2,
                    cursor="hand2", command=remover
                ).pack(side="right", padx=8, pady=6)

        redesenhar_lista()

    # ---------- Gerenciamento de Pastas / Grupos ----------
    def criar_pasta(self, nome):
        nome = nome.strip()
        if not nome:
            return False
        if nome in self.pastas:
            messagebox.showwarning("Pasta já existe", f'Já existe uma pasta chamada "{nome}".', parent=self.root)
            return False
        self.pastas[nome] = {"ips": []}
        self._salvar_configuracoes()
        return True

    def excluir_pasta(self, nome):
        if nome not in self.pastas:
            return
        confirmar = messagebox.askyesno(
            "Excluir pasta",
            f'Excluir a pasta "{nome}"?\n\nOs dispositivos dela voltam para a lista principal.',
            parent=self.root,
        )
        if not confirmar:
            return

        ips_da_pasta = self.pastas[nome].get("ips", [])
        for ip in ips_da_pasta:
            self.ip_para_pasta.pop(ip, None)

        del self.pastas[nome]
        self._salvar_configuracoes()
        self._atualizar_interface_tabela()

    def mover_para_pasta(self, ip, nome_pasta):
        """Move um dispositivo da lista principal para dentro de uma pasta."""
        if nome_pasta not in self.pastas:
            return

        pasta_antiga = self.ip_para_pasta.get(ip)
        if pasta_antiga and pasta_antiga in self.pastas:
            if ip in self.pastas[pasta_antiga]["ips"]:
                self.pastas[pasta_antiga]["ips"].remove(ip)

        self.pastas[nome_pasta]["ips"].append(ip)
        self.ip_para_pasta[ip] = nome_pasta

        if ip in self.linhas_widgets:
            self.linhas_widgets[ip]["frame"].destroy()
            del self.linhas_widgets[ip]

        nome_dispositivo = self.dispositivos.get(ip, {}).get("nome", ip)
        agora_str = datetime.now().strftime("%H:%M:%S")
        self.adicionar_evento(f'Dispositivo movido: {ip} ({nome_dispositivo}) — para a pasta "{nome_pasta}"', agora_str, TEXTO_SECUNDARIO)

        self._salvar_configuracoes()
        self._atualizar_interface_tabela()

    def retirar_da_pasta(self, ip, nome_pasta):
        """Devolve um dispositivo da pasta para a lista principal."""
        if nome_pasta in self.pastas and ip in self.pastas[nome_pasta]["ips"]:
            self.pastas[nome_pasta]["ips"].remove(ip)
        self.ip_para_pasta.pop(ip, None)
        self._salvar_configuracoes()
        self._atualizar_interface_tabela()

    def abrir_menu_mover_pasta(self, ip, widget_botao):
        """Mostra um menu suspenso com as pastas existentes para escolher onde mover o IP."""
        if not self.pastas:
            resposta = messagebox.askyesno(
                "Nenhuma pasta criada",
                "Você ainda não criou nenhuma pasta.\n\nDeseja criar uma pasta agora?",
                parent=self.root,
            )
            if resposta:
                self.abrir_janela_gerenciar_pastas()
            return

        menu = tk.Menu(self.root, tearoff=0, bg=BG_CARD, fg=TEXTO_PRIMARIO,
                        activebackground=BG_HOVER, activeforeground=TEXTO_PRIMARIO)
        for nome_pasta in sorted(self.pastas.keys()):
            menu.add_command(
                label=f"📁 {nome_pasta}",
                command=lambda n=nome_pasta: self.mover_para_pasta(ip, n)
            )

        try:
            menu.tk_popup(widget_botao.winfo_rootx(), widget_botao.winfo_rooty() + widget_botao.winfo_height())
        finally:
            menu.grab_release()

    def abrir_janela_gerenciar_pastas(self):
        janela = tk.Toplevel(self.root)
        janela.title("Pastas de Dispositivos")
        janela.geometry("600x450")
        janela.configure(bg=BG_JANELA)
        janela.transient(self.root)
        janela.grab_set()

        tk.Label(janela, text="PASTAS DE DISPOSITIVOS (EX: PRÉDIO 1, LABORATÓRIO A)", font=(FONTE_BASE, 10, "bold"),
                 bg=BG_JANELA, fg=TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(janela, text="Crie pastas para organizar dispositivos por local. Clique numa pasta para ver e gerenciar o conteúdo.",
                 font=(FONTE_BASE, 8), bg=BG_JANELA, fg=TEXTO_SECUNDARIO, wraplength=560, justify="left").pack(anchor="w", padx=16, pady=(0, 12))

        frame_criar = tk.Frame(janela, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
        frame_criar.pack(fill="x", padx=16, pady=(0, 12))

        entry_nova_pasta = tk.Entry(
            frame_criar, font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_PRIMARIO,
            insertbackground=TEXTO_PRIMARIO, relief="flat", bd=0
        )
        entry_nova_pasta.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        entry_nova_pasta.insert(0, "")

        def criar_e_redesenhar():
            nome = entry_nova_pasta.get().strip()
            if self.criar_pasta(nome):
                entry_nova_pasta.delete(0, "end")
                redesenhar_lista_pastas()

        entry_nova_pasta.bind("<Return>", lambda e: criar_e_redesenhar())

        tk.Button(
            frame_criar, text="+ Criar pasta", font=(FONTE_BASE, 8, "bold"),
            bg=COR_AZUL, fg=TEXTO_SOBRE_AZUL, activebackground=AZUL_HOVER,
            activeforeground=TEXTO_SOBRE_AZUL, relief="flat", bd=0, padx=12, pady=4,
            cursor="hand2", command=criar_e_redesenhar
        ).pack(side="right", padx=8, pady=6)

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

        def redesenhar_lista_pastas():
            for w in conteudo_frame.winfo_children():
                w.destroy()

            if not self.pastas:
                tk.Label(conteudo_frame, text="Nenhuma pasta criada ainda.",
                         font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_SECUNDARIO).pack(pady=40)
                return

            for nome_pasta in sorted(self.pastas.keys()):
                qtd = len(self.pastas[nome_pasta]["ips"])

                linha = tk.Frame(conteudo_frame, bg=BG_JANELA, highlightbackground=BORDA, highlightthickness=1)
                linha.pack(fill="x", pady=3, padx=6)

                tk.Label(linha, text=f"📁 {nome_pasta}", font=(FONTE_BASE, 9, "bold"), bg=BG_JANELA,
                         fg=TEXTO_PRIMARIO, anchor="w").pack(side="left", padx=10, pady=8, fill="x", expand=True)
                tk.Label(linha, text=f"{qtd} dispositivo(s)", font=(FONTE_BASE, 8), bg=BG_JANELA,
                         fg=TEXTO_SECUNDARIO).pack(side="left", padx=(0, 10), pady=8)

                tk.Button(
                    linha, text="Excluir", font=(FONTE_BASE, 8),
                    bg=BTN_PERIGO_BG, fg=COR_VERMELHO, activebackground=BTN_PERIGO_HOVER,
                    activeforeground=COR_VERMELHO, relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2", command=lambda n=nome_pasta: (self.excluir_pasta(n), redesenhar_lista_pastas())
                ).pack(side="right", padx=(2, 8), pady=6)

                tk.Button(
                    linha, text="Abrir", font=(FONTE_BASE, 8, "bold"),
                    bg=COR_AZUL, fg=TEXTO_SOBRE_AZUL, activebackground=AZUL_HOVER,
                    activeforeground=TEXTO_SOBRE_AZUL, relief="flat", bd=0, padx=10, pady=2,
                    cursor="hand2", command=lambda n=nome_pasta: self.abrir_conteudo_pasta(n, redesenhar_lista_pastas)
                ).pack(side="right", padx=2, pady=6)

        redesenhar_lista_pastas()

    def abrir_conteudo_pasta(self, nome_pasta, callback_atualizar_lista_pastas=None):
        """Abre uma janela mostrando os dispositivos dentro de uma pasta especifica."""
        janela = tk.Toplevel(self.root)
        janela.title(f"Pasta: {nome_pasta}")
        janela.geometry("650x450")
        janela.configure(bg=BG_JANELA)
        janela.transient(self.root)
        janela.grab_set()

        tk.Label(janela, text=f"📁 {nome_pasta.upper()}", font=(FONTE_BASE, 12, "bold"),
                 bg=BG_JANELA, fg=COR_AZUL).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(janela, text="Dispositivos desta pasta continuam sendo monitorados normalmente.",
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

        def redesenhar_conteudo():
            for w in conteudo_frame.winfo_children():
                w.destroy()

            ips_da_pasta = self.pastas.get(nome_pasta, {}).get("ips", [])

            if not ips_da_pasta:
                tk.Label(conteudo_frame, text="Esta pasta ainda não tem dispositivos.\n\nVá até a lista principal e clique em \"Mover p/ pasta\".",
                         font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_SECUNDARIO, justify="center").pack(pady=40)
                return

            def chave_ordenacao(ip):
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
                    return tuple(int(p) for p in ip.split("."))
                return (0, 0, 0, 0)

            ips_ordenados = sorted(ips_da_pasta, key=chave_ordenacao)

            for ip in ips_ordenados:
                info = self.dispositivos.get(ip)
                cor = info["cor"] if info else TEXTO_SECUNDARIO
                nome = info["nome"] if info else self.nomes_personalizados.get(ip, "Offline / fora do ar")
                status = info["status"] if info else "Sem dados nesta varredura"

                linha = tk.Frame(conteudo_frame, bg=BG_JANELA, highlightbackground=BORDA, highlightthickness=1)
                linha.pack(fill="x", pady=3, padx=6)

                tk.Label(linha, text="●", font=(FONTE_BASE, 10), bg=BG_JANELA, fg=cor, width=2).pack(side="left", padx=(8, 0), pady=8)
                tk.Label(linha, text=ip, font=(FONTE_BASE, 9, "bold"), bg=BG_JANELA, fg=TEXTO_PRIMARIO, width=14, anchor="w").pack(side="left", pady=8)

                info_texto = tk.Frame(linha, bg=BG_JANELA)
                info_texto.pack(side="left", fill="x", expand=True, pady=8)
                tk.Label(info_texto, text=nome, font=(FONTE_BASE, 9), bg=BG_JANELA, fg=TEXTO_PRIMARIO, anchor="w").pack(anchor="w")
                tk.Label(info_texto, text=status, font=(FONTE_BASE, 8), bg=BG_JANELA, fg=cor, anchor="w").pack(anchor="w")

                def retirar(ip_target=ip):
                    self.retirar_da_pasta(ip_target, nome_pasta)
                    redesenhar_conteudo()
                    if callback_atualizar_lista_pastas:
                        callback_atualizar_lista_pastas()

                tk.Button(
                    linha, text="Retirar da pasta", font=(FONTE_BASE, 8),
                    bg=BTN_BG, fg=TEXTO_PRIMARIO, activebackground=BG_HOVER,
                    activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2", command=retirar
                ).pack(side="right", padx=10, pady=6)

        redesenhar_conteudo()

    # ---------- Renderização Visual Otimizada + Filtro de Busca ----------
    def _atualizar_cards_resumo(self):
        estaveis = sum(1 for d in self.dispositivos.values() if d["cor"] == COR_VERDE and d["ativo"])
        instaveis = sum(1 for d in self.dispositivos.values() if d["cor"] == COR_AMARELO and d["ativo"])
        quedas = sum(1 for d in self.dispositivos.values() if not d["ativo"])

        self.card_estavel.config(text=str(estaveis))
        self.card_instavel.config(text=str(instaveis))
        self.card_caiu.config(text=str(quedas))

        qtd_ignorados = len(self.dispositivos_ignorados)
        self.botao_ignorados.config(text=f"⚙️ Ignorados ({qtd_ignorados})")

        qtd_pastas = len(self.pastas)
        self.botao_pastas.config(text=f"📁 Pastas ({qtd_pastas})")

        qtd_redes = len(self.redes_extras)
        self.botao_redes.config(text=f"🌐 Sub-redes ({qtd_redes})")

        if hasattr(self, "label_info_rede") and self.label_info_rede.winfo_exists():
            extras_txt = f"  |  Extras: {', '.join(self.redes_extras)}" if self.redes_extras else ""
            self.label_info_rede.config(
                text=f"Rede: {self.prefixo_rede}0/24{extras_txt}  —  Gateway: {self.ip_gateway}  —  Host: {self.ip_local}"
            )

        telegram_ligado = bool(self.telegram.get("ativo") and self.telegram.get("token") and self.telegram.get("chat_id"))
        self.telegram_status_label.config(
            text="📱 Telegram: ativo" if telegram_ligado else "📱 Telegram: desativado",
            fg=COR_VERDE if telegram_ligado else TEXTO_SECUNDARIO
        )

    def _atualizar_interface_tabela(self):
        if not self.dispositivos:
            for w in list(self.linhas_widgets.keys()):
                self.linhas_widgets[w]["frame"].destroy()
                del self.linhas_widgets[w]
            return

        termo_busca = getattr(self, "entry_busca", None)
        termo = termo_busca.get().strip().lower() if termo_busca else ""

        ips_visiveis = [ip for ip in self.dispositivos.keys() if ip not in self.ip_para_pasta]
        ips_ordenados = sorted(ips_visiveis, key=lambda ip: tuple(int(p) for p in ip.split(".")))

        for ip in ips_ordenados:
            info = self.dispositivos[ip]

            corresponde_busca = (
                not termo or
                termo in ip.lower() or
                termo in info["nome"].lower() or
                termo in info["status"].lower()
            )

            if not corresponde_busca:
                if ip in self.linhas_widgets:
                    self.linhas_widgets[ip]["frame"].pack_forget()
                continue

            if ip not in self.linhas_widgets:
                linha = tk.Frame(self.frame_dispositivos, bg=BG_CARD, highlightbackground=BORDA, highlightthickness=1)
                linha.pack(fill="x", pady=2, padx=2)

                dot = tk.Label(linha, text="●", font=(FONTE_BASE, 11), bg=BG_CARD, fg=info["cor"], width=2)
                dot.pack(side="left", padx=(8, 0), pady=8)

                ip_lbl = tk.Label(linha, text=ip, font=(FONTE_BASE, 9, "bold"), bg=BG_CARD, fg=TEXTO_PRIMARIO, width=15, anchor="w")
                ip_lbl.pack(side="left", pady=8)

                nome_lbl = tk.Label(linha, text=info["nome"], font=(FONTE_BASE, 9), bg=BG_CARD, fg=TEXTO_PRIMARIO, width=28, anchor="w")
                nome_lbl.pack(side="left", pady=8)

                status_lbl = tk.Label(linha, text=info["status"], font=(FONTE_BASE, 8, "bold"), bg=BG_CARD, fg=info["cor"], width=24, anchor="w")
                status_lbl.pack(side="left", pady=8)

                btn_ignorar = tk.Button(
                    linha, text="Ignorar", font=(FONTE_BASE, 8),
                    bg=BTN_PERIGO_BG, fg=COR_VERMELHO, activebackground=BTN_PERIGO_HOVER,
                    activeforeground=COR_VERMELHO, relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2", command=lambda i=ip: self.ignorar_dispositivo(i)
                )
                btn_ignorar.pack(side="right", padx=(4, 10), pady=6)

                btn_renomear = tk.Button(
                    linha, text="Renomear", font=(FONTE_BASE, 8),
                    bg=BTN_BG, fg=TEXTO_PRIMARIO, activebackground=BG_HOVER,
                    activeforeground=TEXTO_PRIMARIO, relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2", command=lambda i=ip: self.renomear_dispositivo(i)
                )
                btn_renomear.pack(side="right", padx=2, pady=6)

                btn_mover = tk.Button(
                    linha, text="📁 Mover p/ pasta", font=(FONTE_BASE, 8),
                    bg=BTN_AZUL_BG, fg=COR_AZUL, activebackground=BTN_AZUL_HOVER,
                    activeforeground=COR_AZUL, relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2"
                )
                btn_mover.config(command=lambda i=ip, b=btn_mover: self.abrir_menu_mover_pasta(i, b))
                btn_mover.pack(side="right", padx=2, pady=6)

                self.linhas_widgets[ip] = {
                    "frame": linha,
                    "dot": dot,
                    "nome_lbl": nome_lbl,
                    "status_lbl": status_lbl
                }
            else:
                w = self.linhas_widgets[ip]
                w["frame"].pack(fill="x", pady=2, padx=2)
                w["dot"].config(fg=info["cor"])
                w["nome_lbl"].config(text=info["nome"])
                w["status_lbl"].config(text=info["status"], fg=info["cor"])

        for ip_existente in list(self.linhas_widgets.keys()):
            if ip_existente not in self.dispositivos or ip_existente in self.ip_para_pasta:
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
        cor_tag = _normalizar_cor(cor_tag)
        tag_nome = "cinza"
        if cor_tag == COR_VERDE:
            tag_nome = "verde"
        elif cor_tag == COR_AMARELO:
            tag_nome = "amarelo"
        elif cor_tag == COR_VERMELHO:
            tag_nome = "vermelho"

        # Guarda o histórico (limitado) para poder redesenhar ao trocar de tema
        self.historico_eventos.append((horario, mensagem, tag_nome))
        if len(self.historico_eventos) > 500:
            self.historico_eventos = self.historico_eventos[-500:]

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
