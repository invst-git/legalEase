import os
import base64
import datetime
from typing import Any, Iterable

try:
    from google.cloud import firestore
    from google.cloud import storage
except Exception:  # Keep import-time failures non-fatal if Firestore not used
    firestore = None
    storage = None


def is_firestore_enabled() -> bool:
    return (os.getenv("DB_BACKEND", "").lower() == "firestore") and firestore is not None


def _fs_client():
    if firestore is None:
        raise RuntimeError("google-cloud-firestore not installed/configured")
    project = os.getenv("GCP_PROJECT")
    db_id = os.getenv("FIRESTORE_DATABASE")
    # Let client pick up GOOGLE_APPLICATION_CREDENTIALS automatically
    if db_id:
        try:
            return firestore.Client(project=project, database=db_id) if project else firestore.Client(database=db_id)
        except TypeError:
            # Older library versions may not support the database kwarg; fallback to default database
            return firestore.Client(project=project) if project else firestore.Client()
    return firestore.Client(project=project) if project else firestore.Client()


def _st_client_bucket():
    if storage is None:
        raise RuntimeError("google-cloud-storage not installed/configured")
    bucket_name = os.getenv("GCS_BUCKET")
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET env var is required when using Firestore backend")
    st = storage.Client()
    bucket = st.bucket(bucket_name)
    return st, bucket


def _analyses_coll(db):
    return db.collection("analyses")


def _analysis_doc(db, analysis_id: int):
    return _analyses_coll(db).document(str(analysis_id))


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _next_analysis_id(db) -> int:
    """Atomically increments and returns the next integer analysis id."""
    counters = db.collection("counters").document("analyses")
    txn = db.transaction()

    @firestore.transactional
    def txn_op(transaction):
        snap = counters.get(transaction=transaction)
        if snap.exists:
            next_id = int(snap.get("next_id") or 1)
        else:
            next_id = 1
        transaction.set(counters, {"next_id": next_id + 1}, merge=True)
        return next_id

    return txn_op(txn)


def _decode_data_uri_png(data_uri: str) -> bytes:
    # Expected format: data:image/png;base64,<b64>
    if not data_uri.startswith("data:image"):
        return b""
    try:
        b64 = data_uri.split(",", 1)[1]
        return base64.b64decode(b64)
    except Exception:
        return b""


def create_analysis(owner_id: int, filename: str, assessment: str, key_info: list[dict], actions: list[dict]) -> dict:
    db = _fs_client()
    new_id = _next_analysis_id(db)
    created_at = _now_iso()
    doc = {
        "owner_id": int(owner_id or 0),
        "filename": filename or "",
        "assessment": assessment or "",
        "key_info": key_info or [],
        "identified_actions": actions or [],
        "risk_level": None,
        "risk_reason": None,
        "created_at": created_at,
        "content_hash": None,
    }
    _analysis_doc(db, new_id).set(doc)
    return {"id": new_id, "created_at": created_at}


def upload_original_pdf(analysis_id: int, content: bytes) -> str:
    """Uploads the original PDF to GCS and returns a public URL if available, else empty string."""
    st, bucket = _st_client_bucket()
    blob = bucket.blob(f"analyses/{analysis_id}/original.pdf")
    blob.upload_from_string(content, content_type="application/pdf")
    try:
        blob.make_public()
        return blob.public_url
    except Exception:
        return ""


def get_original_pdf_signed_url(analysis_id: int, expires_seconds: int = 600) -> str | None:
    """Returns a short-lived signed URL to the original PDF in GCS if it exists."""
    from datetime import timedelta
    st, bucket = _st_client_bucket()
    blob = bucket.blob(f"analyses/{analysis_id}/original.pdf")
    if not blob.exists():
        return None
    try:
        url = blob.generate_signed_url(expiration=timedelta(seconds=expires_seconds), method="GET", version="v4")
        return url
    except Exception:
        return None


def find_by_content_hash(owner_id: int, content_hash: str) -> int | None:
    db = _fs_client()
    q = (
        _analyses_coll(db)
        .where("owner_id", "==", int(owner_id or 0))
        .where("content_hash", "==", content_hash)
        .limit(1)
    )
    docs = list(q.stream())
    if not docs:
        return None
    return int(docs[0].id)


def persist_meta(analysis_id: int, owner_id: int, pages: list[str], page_images: list[str], risk_level: str, risk_reason: str, content_hash: str) -> None:
    db = _fs_client()
    doc_ref = _analysis_doc(db, analysis_id)
    # Upsert scalar metadata
    doc_ref.set(
        {
            "owner_id": int(owner_id or 0),
            "risk_level": risk_level,
            "risk_reason": risk_reason or "",
            "content_hash": content_hash,
        },
        merge=True,
    )

    # Persist pages as subcollection
    pages_coll = doc_ref.collection("pages")
    # Clear any existing pages (best-effort)
    for p in pages_coll.stream():
        p.reference.delete()

    # Upload images to GCS if provided
    urls: list[str] = []
    if page_images:
        st, bucket = _st_client_bucket()
        for idx, data_uri in enumerate(page_images):
            png_bytes = _decode_data_uri_png(data_uri)
            if not png_bytes:
                urls.append("")
                continue
            blob = bucket.blob(f"analyses/{analysis_id}/page_{idx+1}.png")
            blob.upload_from_string(png_bytes, content_type="image/png")
            # Make public if desired; otherwise, app could use signed URLs
            try:
                blob.make_public()
                url = blob.public_url
            except Exception:
                url = blob.path
            urls.append(url)

    # Write page docs covering both text pages and image pages
    pg_list = pages or []
    total = max(len(pg_list), len(urls)) if urls else len(pg_list)
    for i in range(total):
        txt = pg_list[i] if i < len(pg_list) else ""
        payload = {"index": i + 1, "text": txt or ""}
        if urls and i < len(urls) and urls[i]:
            payload["image_url"] = urls[i]
        pages_coll.document(str(i + 1)).set(payload)


def list_dashboard(owner_id: int) -> list[dict]:
    db = _fs_client()
    q = _analyses_coll(db).where("owner_id", "==", int(owner_id or 0))
    items = []
    for doc in q.stream():
        d = doc.to_dict() or {}
        items.append(
            {
                "id": int(doc.id),
                "filename": d.get("filename", ""),
                "created_at": d.get("created_at"),
                "risk_level": d.get("risk_level"),
            }
        )
    # Sort by created_at desc if present
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items


def get_full_analysis(analysis_id: int, owner_id: int) -> dict:
    db = _fs_client()
    snap = _analysis_doc(db, analysis_id).get()
    if not snap.exists:
        raise ValueError("Analysis not found")
    d = snap.to_dict() or {}
    if int(d.get("owner_id", 0)) != int(owner_id or 0):
        raise ValueError("Analysis not found")

    # Pages
    pages_coll = snap.reference.collection("pages")
    page_docs = list(pages_coll.stream())
    # Sort by page index
    page_docs.sort(key=lambda p: int(p.id))
    extracted_text = [(p.to_dict() or {}).get("text", "") for p in page_docs]
    # Build accessible image URLs (prefer stored http URLs; else generate signed URLs)
    image_urls: list[str] = []
    try:
        st, bucket = _st_client_bucket()
    except Exception:
        st = bucket = None
    for p in page_docs:
        pd = p.to_dict() or {}
        url = (pd.get("image_url") or "").strip()
        if url.startswith("http://") or url.startswith("https://"):
            image_urls.append(url)
            continue
        # Fallback: generate signed URL for known object path
        if bucket is not None:
            try:
                from datetime import timedelta as _td
                idx = int(p.id)
                blob = bucket.blob(f"analyses/{analysis_id}/page_{idx}.png")
                if blob.exists():
                    su = blob.generate_signed_url(expiration=_td(seconds=600), method="GET", version="v4")
                    image_urls.append(su)
            except Exception:
                pass

    # Conversation
    convo_coll = snap.reference.collection("conversation")
    messages = []
    # Ensure deterministic order by timestamp if available
    try:
        convo_stream = convo_coll.order_by("ts").stream()
    except Exception:
        convo_stream = convo_coll.stream()
    for m in convo_stream:
        md = m.to_dict() or {}
        role = md.get("role", "user")
        content = md.get("content", "")
        messages.append({"role": role, "content": content})

    # Timeline
    timeline_coll = snap.reference.collection("timeline_events")
    events = []
    for ev in timeline_coll.stream():
        ed = ev.to_dict() or {}
        events.append({
            "id": None,  # Firestore has no numeric id requirement for events
            "date": ed.get("date", ""),
            "label": ed.get("label", ""),
            "kind": ed.get("kind", "key_date"),
            "description": ed.get("description", ""),
        })

    return {
        "id": analysis_id,
        "filename": d.get("filename", ""),
        "assessment": d.get("assessment", ""),
        "key_info": d.get("key_info", []),
        "identified_actions": d.get("identified_actions", []),
        "extracted_text": extracted_text,
        "page_images": image_urls,
        "created_at": d.get("created_at"),
        "risk_level": d.get("risk_level"),
        "risk_reason": d.get("risk_reason"),
        "conversation": messages,
        "events": events,
    }


def append_conversation_message(analysis_id: int, owner_id: int, user_message: dict, assistant_message: dict) -> None:
    db = _fs_client()
    snap = _analysis_doc(db, analysis_id).get()
    if not snap.exists:
        return
    if int((snap.to_dict() or {}).get("owner_id", 0)) != int(owner_id or 0):
        return
    convo = snap.reference.collection("conversation")
    # We don't guarantee ordering; Firestore timestamps can be added if needed
    convo.add({"role": user_message.get("role", "user"), "content": user_message.get("content", ""), "ts": _now_iso()})
    convo.add({"role": assistant_message.get("role", "assistant"), "content": assistant_message.get("content", ""), "ts": _now_iso()})


def replace_timeline(analysis_id: int, owner_id: int, events: Iterable[dict], lifecycle_summary: str) -> list[dict]:
    db = _fs_client()
    snap = _analysis_doc(db, analysis_id).get()
    if not snap.exists:
        return []
    if int((snap.to_dict() or {}).get("owner_id", 0)) != int(owner_id or 0):
        return []
    coll = snap.reference.collection("timeline_events")
    # Delete existing
    for ev in coll.stream():
        ev.reference.delete()
    stored = []
    for e in events or []:
        date_str = (e.get("date") or "").strip()
        if not date_str:
            continue
        payload = {
            "date": date_str,
            "label": (e.get("label") or "").strip(),
            "kind": (e.get("kind") or "key_date").strip() or "key_date",
            "description": (e.get("description") or "").strip(),
        }
        ref = coll.document()
        ref.set(payload)
        stored.append(payload)
    # Store lifecycle summary at root
    snap.reference.set({"lifecycle_summary": lifecycle_summary or ""}, merge=True)
    return stored


def list_timeline(analysis_id: int, owner_id: int) -> tuple[str, list[dict]]:
    db = _fs_client()
    snap = _analysis_doc(db, analysis_id).get()
    if not snap.exists:
        return "", []
    if int((snap.to_dict() or {}).get("owner_id", 0)) != int(owner_id or 0):
        return "", []
    d = snap.to_dict() or {}
    coll = snap.reference.collection("timeline_events")
    items = []
    for ev in coll.stream():
        ed = ev.to_dict() or {}
        items.append({
            "id": None,
            "date": ed.get("date", ""),
            "label": ed.get("label", ""),
            "kind": ed.get("kind", "key_date"),
            "description": ed.get("description", ""),
        })
    return d.get("lifecycle_summary", ""), items


def check_owner(analysis_id: int, owner_id: int) -> bool:
    """Lightweight ownership/existence check without loading subcollections."""
    db = _fs_client()
    ref = _analysis_doc(db, analysis_id)
    snap = ref.get()
    if not snap.exists:
        return False
    try:
        doc_owner = int((snap.to_dict() or {}).get("owner_id", 0))
    except Exception:
        doc_owner = 0
    return doc_owner == int(owner_id or 0)

def delete_analysis(analysis_id: int) -> bool:
    """Delete an analysis and its subcollections efficiently using batched writes."""
    db = _fs_client()
    ref = _analysis_doc(db, analysis_id)
    snap = ref.get()
    if not snap.exists:
        return True
    # Batched delete for subcollections to reduce round-trips
    for coll_name in ("pages", "timeline_events", "conversation"):
        coll = ref.collection(coll_name)
        batch = db.batch()
        count = 0
        for d in coll.stream():
            batch.delete(d.reference)
            count += 1
            if count >= 450:  # stay below Firestore 500 ops limit
                batch.commit()
                batch = db.batch()
                count = 0
        if count:
            batch.commit()
    ref.delete()
    return True
