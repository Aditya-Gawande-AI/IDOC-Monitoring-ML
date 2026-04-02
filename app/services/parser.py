from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List
import xml.etree.ElementTree as ET

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
}


def _to_float(value: str | None) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _text_or_empty(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def parse_atom_xml(payload: str) -> List[Dict[str, object]]:
    root = ET.fromstring(payload)
    now = datetime.now(timezone.utc)

    records: List[Dict[str, object]] = []
    for entry in root.findall("atom:entry", NS):
        props = entry.find("atom:content/m:properties", NS)
        if props is None:
            continue

        raw: Dict[str, str] = {}
        for child in list(props):
            tag_name = child.tag.split("}")[-1]
            raw[tag_name] = _text_or_empty(child)

        event_time = entry.find("atom:updated", NS)
        updated_ts = _text_or_empty(event_time) or now.isoformat()

        event_id = f"{raw.get('E_IDocNo', '')}|{updated_ts}|{raw.get('E_Status', '')}|{raw.get('E_Receiver', '')}"
        event_hash = hashlib.sha256(event_id.encode("utf-8")).hexdigest()

        records.append(
            {
                "event_hash": event_hash,
                "ingested_at": now.isoformat(),
                "entry_updated_at": updated_ts,
                "idoc_no": raw.get("E_IDocNo", ""),
                "error_info": raw.get("E_Errorinfo", ""),
                "receiver_port": raw.get("E_Rcvpor", ""),
                "receiver_port_type": raw.get("E_Rcvprt", ""),
                "receiver": raw.get("E_Receiver", ""),
                "flag": raw.get("E_Flag", ""),
                "sender_port": raw.get("E_Sndpor", ""),
                "message_type": raw.get("E_Msgtype", ""),
                "sender_port_type": raw.get("E_Sndprt", ""),
                "idoc_type": raw.get("E_Idoctp", ""),
                "total_count": _to_float(raw.get("E_Totcount")),
                "sender": raw.get("E_Sender", ""),
                "serial": raw.get("E_Serial", ""),
                "success_count": _to_float(raw.get("E_Succount")),
                "failure_count": _to_float(raw.get("E_Failcount")),
                "status_text": raw.get("E_Statxt", ""),
                "process_time": _to_float(raw.get("E_Processtime")),
                "status_code": raw.get("E_Status", ""),
                "direction": raw.get("E_Direct", ""),
                "crt_date": raw.get("E_Crtdate", ""),
                "crt_time": raw.get("E_Crttime", ""),
            }
        )

    return records
