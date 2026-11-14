# -*- coding: utf-8 -*-
"""
MecatroniCar v2.0 - calendar_sync.py
Módulo de Integração com Google Calendar para Agendamentos da Oficina MecatroniCar.

Este módulo prepara e engatilha a sincronização bidirecional com a Google Calendar API:
- Montagem do payload oficial de eventos do Google Calendar
- Gerenciamento de credenciais e status de conexão
- Fallback seguro quando credenciais ainda não foram configuradas
"""

import os
import json
import datetime
import logging
from typing import Dict, Any, Optional

log = logging.getLogger("mecatronicar.calendar_sync")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CONFIG_FILE = os.path.join(BASE_DIR, "gcalendar_config.json")

DEFAULT_TIMEZONE = "America/Sao_Paulo"

def get_gcal_config() -> Dict[str, Any]:
    """Carrega configuração da integração com o Google Calendar."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            log.warning("gcalendar_config.json ilegível, usando padrão: %s", e)
    return {
        "enabled": False,
        "calendar_id": "primary",
        "auto_sync": True,
        "credentials_path": CREDENTIALS_FILE,
        "token_path": TOKEN_FILE
    }

def save_gcal_config(cfg: Dict[str, Any]) -> bool:
    """Salva configurações do Google Calendar."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        log.error("Erro salvando gcalendar_config.json: %s", e)
        return False

def build_google_calendar_event(agendamento: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constrói a estrutura JSON compatível com a Google Calendar API v3 (Events: insert/patch).
    """
    title = agendamento.get("title") or "Atendimento Oficina"
    plate = agendamento.get("car_plate_display") or agendamento.get("car_plate") or "S/ Placa"
    car_model = agendamento.get("car_model") or "Veículo"
    client_name = agendamento.get("client_name") or "Cliente"
    phone = agendamento.get("phone") or "Não informado"
    description = agendamento.get("description") or "Sem descrição de sintomas."
    notes = agendamento.get("notes") or ""

    summary = f"MecatroniCar: {car_model} [{plate}] - {title}"

    desc_parts = [
        f"🚗 Veículo: {car_model} ({plate})",
        f"👤 Cliente: {client_name}",
        f"📞 Telefone: {phone}",
        f"🔧 Motivo / Sintomas: {description}"
    ]
    if notes:
        desc_parts.append(f"📝 Observações: {notes}")
    desc_parts.append("---")
    desc_parts.append("Agendado via MecatroniCar • Sistema Integrado da Oficina")

    # Tratamento da data e hora
    sched_date = agendamento.get("scheduled_date") or datetime.date.today().isoformat()
    sched_time = agendamento.get("scheduled_time") or "08:00"

    # Se a data estiver no formato DD/MM/AAAA, converte para YYYY-MM-DD
    if "/" in sched_date:
        parts = sched_date.split("/")
        if len(parts) == 3:
            sched_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

    # Formata início e término (duração padrão de 1 hora para atendimento)
    try:
        dt_start = datetime.datetime.strptime(f"{sched_date} {sched_time}", "%Y-%m-%d %H:%M")
        dt_end = dt_start + datetime.timedelta(hours=1)
        start_iso = dt_start.isoformat()
        end_iso = dt_end.isoformat()
    except ValueError:
        log.info("Data/hora de agendamento fora do padrão (%s %s); usando 08:00", sched_date, sched_time)
        start_iso = f"{sched_date}T08:00:00"
        end_iso = f"{sched_date}T09:00:00"

    event_payload = {
        "summary": summary,
        "description": "\n".join(desc_parts),
        "location": "MecatroniCar - Oficina Mecânica e Autopeças, Santos/SP",
        "start": {
            "dateTime": start_iso,
            "timeZone": DEFAULT_TIMEZONE
        },
        "end": {
            "dateTime": end_iso,
            "timeZone": DEFAULT_TIMEZONE
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 30},
                {"method": "popup", "minutes": 120}
            ]
        },
        "extendedProperties": {
            "private": {
                "agendamento_id": str(agendamento.get("id") or ""),
                "car_plate": plate,
                "client_name": client_name
            }
        }
    }
    return event_payload

def sync_agendamento_to_gcal(agendamento: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sincroniza um agendamento com o Google Calendar.
    Caso as credenciais não estejam presentes, mantém a integração engatilhada e
    retorna o payload pronto para quando as chaves de API forem vinculadas.
    """
    event_payload = build_google_calendar_event(agendamento)
    cfg = get_gcal_config()

    has_credentials = os.path.exists(CREDENTIALS_FILE) or os.path.exists(TOKEN_FILE)

    if not has_credentials or not cfg.get("enabled"):
        return {
            "success": True,
            "synced": False,
            "status": "prepared",
            "message": "Integração Google Calendar engatilhada. Pronto para receber credenciais do Google Cloud Console.",
            "event_payload": event_payload,
            "google_calendar_id": agendamento.get("google_calendar_id") or ""
        }

    # Se credenciais estiverem disponíveis no ambiente:
    try:
        # Importação condicional para não quebrar em ambientes sem google-api-python-client
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)
        service = build("calendar", "v3", credentials=creds)

        gcal_id = agendamento.get("google_calendar_id")
        calendar_target = cfg.get("calendar_id", "primary")

        if gcal_id:
            # Atualiza evento existente
            event = service.events().patch(calendarId=calendar_target, eventId=gcal_id, body=event_payload).execute()
        else:
            # Cria novo evento
            event = service.events().insert(calendarId=calendar_target, body=event_payload).execute()
            gcal_id = event.get("id")

        return {
            "success": True,
            "synced": True,
            "status": "synced",
            "google_calendar_id": gcal_id,
            "html_link": event.get("htmlLink", "")
        }
    except Exception as e:
        log.exception("Falha ao sincronizar agendamento com o Google Calendar")
        return {
            "success": False,
            "synced": False,
            "status": "error",
            "message": f"Erro na conexão com Google Calendar: {str(e)}",
            "event_payload": event_payload
        }

def get_gcal_status() -> Dict[str, Any]:
    """Retorna diagnóstico da integração com o Google Calendar."""
    cfg = get_gcal_config()
    has_creds = os.path.exists(CREDENTIALS_FILE)
    has_token = os.path.exists(TOKEN_FILE)
    
    return {
        "status": "active" if (has_creds and has_token and cfg.get("enabled")) else "prepared",
        "has_credentials": has_creds,
        "has_token": has_token,
        "config": cfg,
        "message": "Módulo engatilhado e pronto para vincular conta Google da oficina."
    }
