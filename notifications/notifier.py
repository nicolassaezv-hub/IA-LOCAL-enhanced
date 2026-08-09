"""
V.15 — Sistema Inteligente de Notificaciones
=============================================
Dispatcher multi-canal que envia alertas solo cuando el Reliability Score
supera el umbral configurado. Cada alerta incluye la explicacion completa
del Decision Engine.

Canales soportados:
  - Desktop (Windows/Linux)
  - Telegram (Bot API)
  - Discord (webhook)
  - Email (SMTP)
  - Console (fallback)

Integracion:
    from notifications.notifier import Notifier, NotificationConfig
    notifier = Notifier()
    notifier.send(
        pair="EURUSD", signal="BUY", reliability=88.5,
        explanation="...", sl=1.078, tp=1.092, regime="trending_bullish"
    )
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

try:
    from colorama import Fore, Style
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

if HAS_COLOR:
    _C = lambda s: f"{Fore.CYAN}{s}{Style.RESET_ALL}"
    _G = lambda s: f"{Fore.GREEN}{s}{Style.RESET_ALL}"
    _Y = lambda s: f"{Fore.YELLOW}{s}{Style.RESET_ALL}"
    _R = lambda s: f"{Fore.RED}{s}{Style.RESET_ALL}"
    _B = lambda s: f"{Fore.BLUE}{s}{Style.RESET_ALL}"
else:
    _C = _G = _Y = _R = _B = lambda s: s


class NotificationChannel(str, Enum):
    CONSOLE = "console"
    DESKTOP = "desktop"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NotificationMessage:
    pair: str = ""
    timeframe: str = ""
    signal: str = "HOLD"
    decision: str = "HOLD"
    reliability_score: float = 0.0
    explanation: str = ""
    stop_loss: float = 0.0
    take_profit: float = 0.0
    regime: str = ""
    risk_level: str = ""
    factors_for: list[str] = field(default_factory=list)
    factors_against: list[str] = field(default_factory=list)
    timestamp: str = ""
    priority: NotificationPriority = NotificationPriority.MEDIUM

    def to_dict(self) -> dict:
        return {k: v.value if isinstance(v, NotificationPriority) else v for k, v in self.__dict__.items()}

    def format_text(self) -> str:
        lines = [
            f"ASTRA Signal — {self.pair} {self.timeframe}",
            f"Decision: {self.decision} | Reliability: {self.reliability_score:.1f}/100",
        ]
        if self.stop_loss:
            lines.append(f"SL: {self.stop_loss:.5f} | TP: {self.take_profit:.5f}")
        if self.regime:
            lines.append(f"Regimen: {self.regime}")
        if self.risk_level:
            lines.append(f"Riesgo: {self.risk_level}")
        if self.explanation:
            lines.append(f"\n{self.explanation}")
        if self.factors_for:
            lines.append(f"\nFactores a favor: {', '.join(self.factors_for)}")
        if self.factors_against:
            lines.append(f"Factores en contra: {', '.join(self.factors_against)}")
        return "\n".join(lines)

    def format_html(self) -> str:
        signal_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "NO_OPERAR": "⛔"}.get(self.signal, "⚪")
        html = f"<b>{signal_emoji} ASTRA Signal — {self.pair} {self.timeframe}</b>\n"
        html += f"<b>Decision:</b> {self.decision} | <b>Reliability:</b> {self.reliability_score:.1f}/100\n"
        if self.stop_loss:
            html += f"<b>SL:</b> {self.stop_loss:.5f} | <b>TP:</b> {self.take_profit:.5f}\n"
        if self.regime:
            html += f"<b>Regimen:</b> {self.regime}\n"
        if self.explanation:
            html += f"\n{self.explanation}\n"
        if self.factors_for:
            html += f"\n✅ {', '.join(self.factors_for)}\n"
        if self.factors_against:
            html += f"⚠️ {', '.join(self.factors_against)}\n"
        return html


@dataclass
class NotificationResult:
    channel: str = ""
    success: bool = False
    error: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


DEFAULT_CONFIG = {
    "reliability_threshold": 85.0,
    "enabled_channels": ["console"],
    "telegram_token": "",
    "telegram_chat_id": "",
    "discord_webhook_url": "",
    "email_smtp_server": "",
    "email_smtp_port": 587,
    "email_sender": "",
    "email_password": "",
    "email_recipient": "",
    "cooldown_minutes": 30,
}


class Notifier:
    """Dispatcher multi-canal de notificaciones."""

    def __init__(self, db_path: str = "memoria.db", config: dict | None = None):
        self.db_path = db_path
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._last_notification: dict[str, datetime] = {}
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notification_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT,
                    signal TEXT,
                    reliability_score REAL,
                    channel TEXT,
                    success INTEGER,
                    error TEXT,
                    timestamp TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Check cooldown ──
    def _check_cooldown(self, pair: str) -> bool:
        last = self._last_notification.get(pair)
        if last is None:
            return True
        from datetime import timedelta
        elapsed = datetime.utcnow() - last
        return elapsed >= timedelta(minutes=self.config["cooldown_minutes"])

    # ── Determine priority ──
    def _get_priority(self, reliability: float, signal: str) -> NotificationPriority:
        if signal == "NO_OPERAR":
            return NotificationPriority.CRITICAL
        if reliability >= 90:
            return NotificationPriority.HIGH
        if reliability >= 85:
            return NotificationPriority.MEDIUM
        return NotificationPriority.LOW

    # ── Main send method ──
    def send(
        self,
        pair: str,
        signal: str = "HOLD",
        decision: str = "HOLD",
        reliability_score: float = 0.0,
        explanation: str = "",
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        regime: str = "",
        risk_level: str = "",
        factors_for: list[str] | None = None,
        factors_against: list[str] | None = None,
        timeframe: str = "H1",
        force: bool = False,
    ) -> list[NotificationResult]:
        if not force and reliability_score < self.config["reliability_threshold"]:
            return [NotificationResult(channel="skip", success=False, error="Below threshold", timestamp=datetime.utcnow().isoformat())]

        if not force and not self._check_cooldown(pair):
            return [NotificationResult(channel="skip", success=False, error="Cooldown active", timestamp=datetime.utcnow().isoformat())]

        priority = self._get_priority(reliability_score, signal)
        msg = NotificationMessage(
            pair=pair,
            timeframe=timeframe,
            signal=signal,
            decision=decision,
            reliability_score=reliability_score,
            explanation=explanation,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime=regime,
            risk_level=risk_level,
            factors_for=factors_for or [],
            factors_against=factors_against or [],
            timestamp=datetime.utcnow().isoformat(),
            priority=priority,
        )

        results = []
        for channel in self.config["enabled_channels"]:
            ch = NotificationChannel(channel)
            if ch == NotificationChannel.CONSOLE:
                results.append(self._send_console(msg))
            elif ch == NotificationChannel.DESKTOP:
                results.append(self._send_desktop(msg))
            elif ch == NotificationChannel.TELEGRAM:
                results.append(self._send_telegram(msg))
            elif ch == NotificationChannel.DISCORD:
                results.append(self._send_discord(msg))
            elif ch == NotificationChannel.EMAIL:
                results.append(self._send_email(msg))

        self._last_notification[pair] = datetime.utcnow()
        self._log_notification(pair, signal, reliability_score, results)
        return results

    # ── Console channel ──
    def _send_console(self, msg: NotificationMessage) -> NotificationResult:
        try:
            text = msg.format_text()
            signal_color = _G if msg.signal in ("BUY",) else _R if msg.signal == "SELL" else _Y
            print(f"\n{signal_color('════════════════════════════════════════')}")
            print(text)
            print(f"{signal_color('════════════════════════════════════════')}\n")
            return NotificationResult(channel="console", success=True, timestamp=datetime.utcnow().isoformat())
        except Exception as e:
            return NotificationResult(channel="console", success=False, error=str(e), timestamp=datetime.utcnow().isoformat())

    # ── Desktop channel ──
    def _send_desktop(self, msg: NotificationMessage) -> NotificationResult:
        try:
            import subprocess
            import platform
            title = f"ASTRA — {msg.pair} {msg.signal} (R={msg.reliability_score:.0f})"
            body = msg.format_text()

            system = platform.system()
            if system == "Linux":
                try:
                    subprocess.run(["notify-send", title, body], check=False, timeout=5)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            elif system == "Windows":
                try:
                    from ctypes import Structure, windll, c_int, sizeof
                    windll.user32.MessageBoxW(0, body, title, 0x40)
                except Exception:
                    pass
            elif system == "Darwin":
                try:
                    subprocess.run(["osascript", "-e", f'display notification "{body}" with title "{title}"'], check=False, timeout=5)
                except Exception:
                    pass

            return NotificationResult(channel="desktop", success=True, timestamp=datetime.utcnow().isoformat())
        except Exception as e:
            return NotificationResult(channel="desktop", success=False, error=str(e), timestamp=datetime.utcnow().isoformat())

    # ── Telegram channel ──
    def _send_telegram(self, msg: NotificationMessage) -> NotificationResult:
        token = self.config.get("telegram_token", "")
        chat_id = self.config.get("telegram_chat_id", "")
        if not token or not chat_id:
            return NotificationResult(channel="telegram", success=False, error="Token or chat_id not configured", timestamp=datetime.utcnow().isoformat())
        try:
            import urllib.request
            import urllib.parse

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": msg.format_text(),
                "parse_mode": "HTML",
            }).encode()
            req = urllib.request.Request(url, data=data)
            urllib.request.urlopen(req, timeout=10)
            return NotificationResult(channel="telegram", success=True, timestamp=datetime.utcnow().isoformat())
        except Exception as e:
            return NotificationResult(channel="telegram", success=False, error=str(e), timestamp=datetime.utcnow().isoformat())

    # ── Discord channel ──
    def _send_discord(self, msg: NotificationMessage) -> NotificationResult:
        webhook = self.config.get("discord_webhook_url", "")
        if not webhook:
            return NotificationResult(channel="discord", success=False, error="Webhook URL not configured", timestamp=datetime.utcnow().isoformat())
        try:
            import urllib.request
            import json as _json

            payload = _json.dumps({"content": msg.format_text()}).encode()
            req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            return NotificationResult(channel="discord", success=True, timestamp=datetime.utcnow().isoformat())
        except Exception as e:
            return NotificationResult(channel="discord", success=False, error=str(e), timestamp=datetime.utcnow().isoformat())

    # ── Email channel ──
    def _send_email(self, msg: NotificationMessage) -> NotificationResult:
        smtp_server = self.config.get("email_smtp_server", "")
        if not smtp_server:
            return NotificationResult(channel="email", success=False, error="SMTP not configured", timestamp=datetime.utcnow().isoformat())
        try:
            import smtplib
            from email.mime.text import MIMEText

            sender = self.config.get("email_sender", "")
            password = self.config.get("email_password", "")
            recipient = self.config.get("email_recipient", "")

            email_msg = MIMEText(msg.format_text())
            email_msg["Subject"] = f"ASTRA Signal — {msg.pair} {msg.signal} (R={msg.reliability_score:.0f})"
            email_msg["From"] = sender
            email_msg["To"] = recipient

            port = self.config.get("email_smtp_port", 587)
            server = smtplib.SMTP(smtp_server, port)
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [recipient], email_msg.as_string())
            server.quit()
            return NotificationResult(channel="email", success=True, timestamp=datetime.utcnow().isoformat())
        except Exception as e:
            return NotificationResult(channel="email", success=False, error=str(e), timestamp=datetime.utcnow().isoformat())

    # ── Log ──
    def _log_notification(self, pair: str, signal: str, reliability: float, results: list[NotificationResult]):
        try:
            conn = sqlite3.connect(self.db_path)
            for r in results:
                conn.execute(
                    "INSERT INTO notification_log (pair, signal, reliability_score, channel, success, error, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (pair, signal, reliability, r.channel, int(r.success), r.error, r.timestamp),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Get log ──
    def get_log(self, limit: int = 50) -> list[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT * FROM notification_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            cols = ["id", "pair", "signal", "reliability_score", "channel", "success", "error", "timestamp"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception:
            return []


# ── CLI ──
def cmd_notify_test(args: str = "") -> str:
    """Comando CLI: notify_test <pair> <signal> <reliability>"""
    parts = args.strip().split()
    if len(parts) < 3:
        return "Uso: notify_test <pair> <signal> <reliability>"
    pair = parts[0].upper()
    signal = parts[1].upper()
    reliability = float(parts[2])
    notifier = Notifier(config={"enabled_channels": ["console"], "reliability_threshold": 0})
    results = notifier.send(
        pair=pair, signal=signal, reliability_score=reliability,
        explanation="Notificacion de prueba desde CLI",
        regime="trending_bullish", force=True,
    )
    lines = [f"{_C('Notification Test')} — {pair} {signal} R={reliability}"]
    for r in results:
        icon = _G("OK") if r.success else _R("FAIL")
        lines.append(f"  {icon} {r.channel}: {r.error or 'sent'}")
    return "\n".join(lines)


def cmd_notify_log(args: str = "") -> str:
    """Comando CLI: notify_log [limit]"""
    parts = args.strip().split()
    limit = int(parts[0]) if parts else 20
    notifier = Notifier()
    log = notifier.get_log(limit=limit)
    if not log:
        return f"{_Y('Sin notificaciones registradas')}"
    lines = [f"{_C('Notification Log')} ({len(log)})"]
    for l in log:
        icon = _G("OK") if l["success"] else _R("FAIL")
        lines.append(
            f"  {l['timestamp'][:19]} | {l['pair']} {l['signal']} | R={l['reliability_score']:.1f} | "
            f"{l['channel']} | {icon}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(cmd_notify_test("EURUSD BUY 88.5"))
