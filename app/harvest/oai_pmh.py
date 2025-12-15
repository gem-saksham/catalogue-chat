\
from __future__ import annotations
from typing import Any, Dict, List, Optional
from sickle import Sickle
from lxml import etree

def _text(el):
    return (el.text or "").strip()

def _first(xpath, root, ns=None):
    res = root.xpath(xpath, namespaces=ns or {})
    return res[0] if res else None

def harvest_records(
    base_url: str,
    metadata_prefix: str = "oai_dc",
    set_spec: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Harvest OAI-PMH records via ListRecords. Returns a normalized list of dicts.

    For Zenodo, `metadata_prefix=oai_datacite` yields richer fields.
    """
    sickle = Sickle(base_url)
    params = {"metadataPrefix": metadata_prefix}
    if set_spec:
        params["set"] = set_spec
    if since:
        params["from"] = since
    if until:
        params["until"] = until

    out: List[Dict[str, Any]] = []
    it = sickle.ListRecords(**params)
    for rec in it:
        if len(out) >= limit:
            break

        try:
            xml = rec.raw
            root = etree.fromstring(xml.encode("utf-8"))
        except Exception:
            continue

        # OAI wrapper namespaces
        ns = {
            "oai": "http://www.openarchives.org/OAI/2.0/",
            "dc": "http://purl.org/dc/elements/1.1/",
            "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
            "d": "http://datacite.org/schema/kernel-4",
        }

        # OAI identifier
        oai_id_el = _first("//oai:header/oai:identifier", root, ns)
        oai_id = _text(oai_id_el) if oai_id_el is not None else None

        # Try DataCite schema (Zenodo)
        title_el = _first("//d:title", root, ns)
        creators_els = root.xpath("//d:creator/d:creatorName", namespaces=ns)
        subjects_els = root.xpath("//d:subject", namespaces=ns)
        desc_el = _first("//d:description", root, ns)
        date_el = _first("//d:publicationYear", root, ns)
        url_el = _first("//d:identifier[@identifierType='URL']", root, ns)
        doi_el = _first("//d:identifier[@identifierType='DOI']", root, ns)

        # Fallback to oai_dc
        if title_el is None:
            title_el = _first("//dc:title", root, ns)
        if not creators_els:
            creators_els = root.xpath("//dc:creator", namespaces=ns)
        if not subjects_els:
            subjects_els = root.xpath("//dc:subject", namespaces=ns)
        if desc_el is None:
            desc_el = _first("//dc:description", root, ns)
        if date_el is None:
            date_el = _first("//dc:date", root, ns)
        if url_el is None:
            # dc:identifier may contain URL
            ids = [(_text(x) or "") for x in root.xpath("//dc:identifier", namespaces=ns)]
            url = next((x for x in ids if x.startswith("http")), None)
        else:
            url = _text(url_el)
        doi = _text(doi_el) if doi_el is not None else None

        title = _text(title_el) if title_el is not None else None
        creators = "; ".join(_text(x) for x in creators_els if _text(x))
        subjects = "; ".join(_text(x) for x in subjects_els if _text(x))
        description = _text(desc_el) if desc_el is not None else None
        date = _text(date_el) if date_el is not None else None

        rec_id = doi or oai_id

        out.append(
            {
                "oai_identifier": oai_id,
                "id": rec_id,
                "title": title,
                "creators": creators,
                "subjects": subjects,
                "description": description,
                "date": date,
                "url": url,
            }
        )

    return out
