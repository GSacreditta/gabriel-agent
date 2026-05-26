"""
Gmail Inventory Service - Read-only enumeration of emails under the Finanzas label.

Produces CSV inventories + raw thread JSON in GCS. No local file writes.
No Gmail mutations. No attachment downloads. Subject + snippet only for LLM.
LLM entity tagging runs on a private Ollama instance (Cloud Run or local) —
no data sent to public APIs.
"""

import logging
import asyncio
import csv
import gzip
import io
import json
import os
import re
import yaml
import httpx
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set

from google.auth.transport.requests import Request as AuthRequest
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import storage
import google.auth
import google.auth.transport.requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class InventoryService:
    """
    Read-only Gmail inventory pass for family office financial email corpus.

    Scope: ONLY emails under the 'Finanzas' Gmail label.
    LLM: Private Ollama instance (no public API exposure).
    Output: GCS bucket (no local files).
    """

    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(self, bucket_name: str, entities_file: str = "config/entities.txt",
                 queries_file: str = "config/inventory_queries.yaml",
                 prompt_file: str = "config/entity_prompt.txt",
                 ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "phi3:mini"):
        self.settings = get_settings()
        self.bucket_name = bucket_name
        self.entities_file = entities_file
        self.queries_file = queries_file
        self.prompt_file = prompt_file
        self.ollama_url = ollama_url.rstrip('/')
        self.ollama_model = ollama_model

        self.gmail_service = None
        self.gcs_client = None
        self.gcs_bucket = None

        # Run state
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.seen_message_ids: Set[str] = set()
        self.discovered_senders: Set[str] = set()

        # Loaded config
        self.queries_config: Dict = {}
        self.entity_list: List[str] = []
        self.prompt_template: str = ""
        self.label_scope: str = "Finanzas"

    # ─── Initialization ───────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """Initialize all service dependencies."""
        try:
            self._load_config()
            await self._authenticate_gmail()
            self._initialize_gcs()
            await self._verify_ollama()
            logger.info(f"✅ InventoryService initialized. Run ID: {self.run_id}")
            logger.info(f"   📦 GCS bucket: {self.bucket_name}")
            logger.info(f"   🏷️ Label scope: {self.label_scope}")
            logger.info(f"   📋 Entities loaded: {len(self.entity_list)}")
            logger.info(f"   🤖 Ollama: {self.ollama_url} ({self.ollama_model})")
            return True
        except Exception as e:
            logger.error(f"❌ InventoryService initialization failed: {e}")
            raise

    def _load_config(self):
        """Load queries, entities, and prompt template."""
        # Load queries
        with open(self.queries_file, 'r') as f:
            self.queries_config = yaml.safe_load(f)

        self.label_scope = self.queries_config.get('label_scope', 'Finanzas')

        # Load entities
        self.entity_list = []
        if os.path.exists(self.entities_file):
            with open(self.entities_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.entity_list.append(line)

        # Load prompt template
        with open(self.prompt_file, 'r') as f:
            self.prompt_template = f.read()

    async def _authenticate_gmail(self):
        """Authenticate with Gmail API (read-only scope) for sternbergg@gmail.com."""
        creds = None
        credentials_dir = os.getenv('GMAIL_CREDENTIALS_DIR', 'config/credentials')
        token_file = os.path.join(credentials_dir, 'gmail_token_inventory.json')

        client_id = os.getenv('GMAIL_CLIENT_ID') or self.settings.GMAIL_CLIENT_ID
        client_secret = os.getenv('GMAIL_CLIENT_SECRET') or self.settings.GMAIL_CLIENT_SECRET

        if not client_id or not client_secret:
            raise ValueError("GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET required")

        # Load existing token
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)

        # Refresh or re-auth
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(AuthRequest())
            else:
                logger.info("🌐 OAuth flow required — authenticate as sternbergg@gmail.com")
                client_config = {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["http://localhost"]
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                creds = flow.run_local_server(port=0)

            os.makedirs(os.path.dirname(token_file), exist_ok=True)
            with open(token_file, 'w') as token:
                token.write(creds.to_json())

        self.gmail_service = build('gmail', 'v1', credentials=creds)

        # Verify connection
        profile = self.gmail_service.users().getProfile(userId='me').execute()
        connected_email = profile.get('emailAddress')
        logger.info(f"✅ Gmail connected: {connected_email}")

        if connected_email != 'sternbergg@gmail.com':
            logger.warning(f"⚠️ Connected to {connected_email}, expected sternbergg@gmail.com")
            logger.warning("   Delete config/credentials/gmail_token_inventory.json and re-auth")

    def _initialize_gcs(self):
        """Initialize GCS client and verify bucket exists."""
        self.gcs_client = storage.Client()
        self.gcs_bucket = self.gcs_client.bucket(self.bucket_name)
        if not self.gcs_bucket.exists():
            raise ValueError(f"GCS bucket '{self.bucket_name}' does not exist. Create it first.")
        logger.info(f"✅ GCS bucket verified: {self.bucket_name}")

    async def _verify_ollama(self):
        """Verify Ollama is reachable and model is available."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    models = [m['name'] for m in resp.json().get('models', [])]
                    if self.ollama_model in models or any(self.ollama_model in m for m in models):
                        logger.info(f"✅ Ollama verified: {self.ollama_model} available")
                    else:
                        logger.warning(f"⚠️ Model {self.ollama_model} not found. Available: {models}")
                        logger.warning(f"   Pull it: ollama pull {self.ollama_model}")
                else:
                    logger.warning(f"⚠️ Ollama returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Ollama not reachable at {self.ollama_url}: {e}")
            logger.warning("   Entity tagging will be skipped unless Ollama becomes available.")

    # ─── Main Execution ───────────────────────────────────────────────────

    async def run_inventory(self, skip_entity_tagging: bool = False) -> Dict[str, Any]:
        """
        Execute the full inventory pass.

        Scope: ONLY emails under the Finanzas label.
        Returns summary statistics.
        """
        logger.info(f"🚀 Starting inventory pass: {self.run_id}")
        logger.info(f"   Scope: label:{self.label_scope}")

        # Load resume state if exists
        state = self._load_state()
        all_messages: List[Dict] = state.get('messages', [])
        self.seen_message_ids = set(state.get('seen_ids', []))

        # ── Single pass: Everything under Finanzas label ──
        if not state.get('enumeration_complete'):
            query = f"label:{self.label_scope}"

            # Add date filters if configured
            date_after = self.queries_config.get('date_after', '')
            date_before = self.queries_config.get('date_before', '')
            if date_after:
                query += f" after:{date_after}"
            if date_before:
                query += f" before:{date_before}"

            logger.info(f"📬 Querying: {query}")
            new_msgs = await self._execute_query(query)
            all_messages.extend(new_msgs)
            logger.info(f"   Found {len(new_msgs)} messages under label:{self.label_scope}")

            state['enumeration_complete'] = True
            self._save_state(state, all_messages)

        logger.info(f"📊 Total messages: {len(all_messages)}")

        # ── Entity tagging (private Ollama) ──
        if not skip_entity_tagging and self.entity_list:
            if await self._ollama_available():
                logger.info(f"🏷️ Entity tagging {len(all_messages)} messages via Ollama ({self.ollama_model})...")
                all_messages = await self._tag_entities(all_messages)
                self._save_state(state, all_messages)
            else:
                logger.warning("⏭️ Skipping entity tagging — Ollama not available")
        elif not self.entity_list:
            logger.info("⏭️ Skipping entity tagging (no entities in config/entities.txt)")
        elif skip_entity_tagging:
            logger.info("⏭️ Skipping entity tagging (--skip-entity-tagging flag)")

        # ── Write outputs to GCS ──
        logger.info("📤 Writing outputs to GCS...")
        await self._write_messages_csv(all_messages)
        await self._write_attachments_csv(all_messages)
        await self._write_senders_summary(all_messages)
        await self._write_stats_md(all_messages)

        # ── Write raw thread JSON ──
        logger.info("📤 Writing raw thread JSON to GCS...")
        await self._write_raw_threads(all_messages)

        # Mark complete
        state['complete'] = True
        state['completed_at'] = datetime.now(timezone.utc).isoformat()
        self._save_state(state, all_messages)

        summary = {
            "run_id": self.run_id,
            "total_messages": len(all_messages),
            "unique_senders": len(self.discovered_senders),
            "messages_with_attachments": sum(1 for m in all_messages if m.get('attachment_count', 0) > 0),
            "entity_tagged": sum(1 for m in all_messages if m.get('entity_guess') and m['entity_guess'] != ''),
            "gcs_path": f"gs://{self.bucket_name}/inventory/{self.run_id}/"
        }
        logger.info(f"✅ Inventory pass complete: {json.dumps(summary, indent=2)}")
        return summary

    # ─── Gmail Enumeration ────────────────────────────────────────────────

    async def _execute_query(self, query: str) -> List[Dict]:
        """Execute a Gmail query and return message metadata (no body/attachment download)."""
        messages = []
        page_token = None
        max_per_page = self.queries_config.get('max_results_per_page', 500)

        while True:
            try:
                result = self.gmail_service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=max_per_page,
                    pageToken=page_token
                ).execute()

                msg_stubs = result.get('messages', [])
                logger.info(f"   Page: {len(msg_stubs)} messages (total seen: {len(self.seen_message_ids)})")

                for msg_stub in msg_stubs:
                    msg_id = msg_stub['id']
                    if msg_id in self.seen_message_ids:
                        continue
                    self.seen_message_ids.add(msg_id)

                    msg_data = await self._fetch_message_metadata(msg_id)
                    if msg_data:
                        messages.append(msg_data)
                        # Track discovered senders
                        from_email = msg_data.get('from_email', '')
                        domain = self._extract_domain(from_email)
                        if domain:
                            self.discovered_senders.add(domain)

                page_token = result.get('nextPageToken')
                if not page_token:
                    break

            except HttpError as e:
                logger.error(f"Gmail API error: {e}")
                break

        return messages

    async def _fetch_message_metadata(self, message_id: str) -> Optional[Dict]:
        """Fetch message metadata without downloading body/attachments."""
        try:
            # Get full format to access attachment metadata
            msg = self.gmail_service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}

            # Parse sender
            from_raw = headers.get('From', '')
            from_name, from_email = self._parse_sender(from_raw)

            # Extract attachment metadata (no content download)
            attachments = self._extract_attachment_metadata(msg)

            return {
                'message_id': message_id,
                'thread_id': msg.get('threadId', ''),
                'date_iso': headers.get('Date', ''),
                'from_email': from_email,
                'from_name': from_name,
                'to': headers.get('To', ''),
                'subject': headers.get('Subject', ''),
                'labels': ','.join(msg.get('labelIds', [])),
                'has_attachments': len(attachments) > 0,
                'attachment_count': len(attachments),
                'attachment_total_bytes': sum(a.get('size_bytes', 0) for a in attachments),
                'snippet': msg.get('snippet', '')[:200],
                'attachments': attachments,
                # Entity fields (populated by LLM later)
                'entity_guess': '',
                'entity_confidence': '',
                'entity_reasoning': ''
            }
        except HttpError as e:
            logger.warning(f"Failed to fetch message {message_id}: {e}")
            return None

    def _extract_attachment_metadata(self, msg_data: Dict) -> List[Dict]:
        """Extract attachment metadata (no content download)."""
        attachments = []

        def scan_parts(parts):
            for part in parts:
                filename = part.get('filename', '')
                if filename:
                    body = part.get('body', {})
                    attachments.append({
                        'attachment_id': body.get('attachmentId', ''),
                        'filename': filename,
                        'mime_type': part.get('mimeType', 'application/octet-stream'),
                        'size_bytes': body.get('size', 0)
                    })
                if 'parts' in part:
                    scan_parts(part['parts'])

        payload = msg_data.get('payload', {})
        if 'parts' in payload:
            scan_parts(payload['parts'])

        return attachments

    # ─── Entity Tagging (Private Ollama) ──────────────────────────────────

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get auth headers for private Cloud Run endpoints (if URL is https)."""
        if not self.ollama_url.startswith("https://"):
            return {}  # Local Ollama, no auth needed
        try:
            # Get ID token for the Cloud Run service
            creds, _ = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)
            # Fetch ID token for the target audience (the Cloud Run URL)
            token = google_id_token.fetch_id_token(auth_req, self.ollama_url)
            return {"Authorization": f"Bearer {token}"}
        except Exception as e:
            logger.warning(f"⚠️ Could not get auth token for Cloud Run: {e}")
            return {}

    async def _ollama_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            headers = self._get_auth_headers()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags", headers=headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def _tag_entities(self, messages: List[Dict]) -> List[Dict]:
        """Tag each message with a candidate entity using private Ollama."""
        entity_list_str = "\n".join(f"- {e}" for e in self.entity_list)
        tagged_count = 0
        skipped_count = 0

        headers = self._get_auth_headers()

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i, msg in enumerate(messages):
                # Skip if already tagged
                if msg.get('entity_guess'):
                    skipped_count += 1
                    continue

                try:
                    prompt = self.prompt_template.format(
                        entity_list=entity_list_str,
                        from_name=msg.get('from_name', ''),
                        from_email=msg.get('from_email', ''),
                        subject=msg.get('subject', ''),
                        snippet=msg.get('snippet', '')
                    )

                    # Call Ollama generate API (private — local or Cloud Run)
                    resp = await client.post(
                        f"{self.ollama_url}/api/generate",
                        headers=headers,
                        json={
                            "model": self.ollama_model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.1,
                                "num_predict": 150
                            }
                        }
                    )

                    if resp.status_code == 200:
                        result_text = resp.json().get('response', '').strip()
                        # Try to parse JSON from response
                        result = self._parse_llm_response(result_text)
                        msg['entity_guess'] = result.get('entity', 'UNKNOWN')
                        msg['entity_confidence'] = result.get('confidence', 'low')
                        msg['entity_reasoning'] = result.get('reasoning', '')
                        tagged_count += 1
                    else:
                        logger.warning(f"Ollama returned {resp.status_code} for {msg['message_id']}")
                        msg['entity_guess'] = 'ERROR'
                        msg['entity_confidence'] = 'low'
                        msg['entity_reasoning'] = f"Ollama HTTP {resp.status_code}"

                except Exception as e:
                    logger.warning(f"Entity tagging failed for {msg['message_id']}: {e}")
                    msg['entity_guess'] = 'ERROR'
                    msg['entity_confidence'] = 'low'
                    msg['entity_reasoning'] = str(e)[:100]

                # Progress logging every 50 messages
                if (i + 1) % 50 == 0:
                    logger.info(f"   Tagged {i + 1}/{len(messages)} messages...")

        logger.info(f"🏷️ Entity tagging complete: {tagged_count} tagged, {skipped_count} skipped")
        return messages

    def _parse_llm_response(self, text: str) -> Dict:
        """Parse JSON from LLM response, handling common formatting issues."""
        # Try direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback
        return {'entity': 'PARSE_ERROR', 'confidence': 'low', 'reasoning': text[:100]}

    # ─── GCS Output Writers ───────────────────────────────────────────────

    def _gcs_prefix(self) -> str:
        return f"inventory/{self.run_id}"

    def _upload_to_gcs(self, path: str, content: bytes, content_type: str = "text/csv"):
        """Upload bytes to GCS."""
        blob = self.gcs_bucket.blob(f"{self._gcs_prefix()}/{path}")
        blob.upload_from_string(content, content_type=content_type)
        logger.info(f"   ☁️  gs://{self.bucket_name}/{self._gcs_prefix()}/{path}")

    async def _write_messages_csv(self, messages: List[Dict]):
        """Write messages.csv to GCS."""
        output = io.StringIO()
        fieldnames = [
            'message_id', 'thread_id', 'date_iso', 'from_email', 'from_name',
            'to', 'subject', 'labels', 'has_attachments', 'attachment_count',
            'attachment_total_bytes', 'snippet', 'entity_guess',
            'entity_confidence', 'entity_reasoning'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for msg in messages:
            writer.writerow(msg)

        self._upload_to_gcs("messages.csv", output.getvalue().encode('utf-8'))

    async def _write_attachments_csv(self, messages: List[Dict]):
        """Write attachments.csv to GCS."""
        output = io.StringIO()
        fieldnames = ['message_id', 'attachment_id', 'filename', 'mime_type', 'size_bytes']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for msg in messages:
            for att in msg.get('attachments', []):
                writer.writerow({
                    'message_id': msg['message_id'],
                    'attachment_id': att.get('attachment_id', ''),
                    'filename': att.get('filename', ''),
                    'mime_type': att.get('mime_type', ''),
                    'size_bytes': att.get('size_bytes', 0)
                })

        self._upload_to_gcs("attachments.csv", output.getvalue().encode('utf-8'))

    async def _write_senders_summary(self, messages: List[Dict]):
        """Write senders_summary.csv to GCS."""
        domain_stats: Dict[str, Dict] = defaultdict(lambda: {
            'message_count': 0,
            'attachment_count': 0,
            'attachment_bytes': 0,
            'first_date': '',
            'last_date': '',
            'entity_guesses': defaultdict(int),
            'subjects': []
        })

        for msg in messages:
            domain = self._extract_domain(msg.get('from_email', ''))
            if not domain:
                domain = 'unknown'

            stats = domain_stats[domain]
            stats['message_count'] += 1
            stats['attachment_count'] += msg.get('attachment_count', 0)
            stats['attachment_bytes'] += msg.get('attachment_total_bytes', 0)

            date = msg.get('date_iso', '')
            if date:
                if not stats['first_date'] or date < stats['first_date']:
                    stats['first_date'] = date
                if not stats['last_date'] or date > stats['last_date']:
                    stats['last_date'] = date

            entity = msg.get('entity_guess', '')
            if entity:
                stats['entity_guesses'][entity] += 1

            if len(stats['subjects']) < 3:
                stats['subjects'].append(msg.get('subject', '')[:60])

        # Write CSV
        output = io.StringIO()
        fieldnames = ['domain', 'message_count', 'attachment_count', 'attachment_bytes',
                      'first_date', 'last_date', 'top_entity_guesses', 'sample_subjects']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for domain, stats in sorted(domain_stats.items(), key=lambda x: x[1]['message_count'], reverse=True):
            top_entities = sorted(stats['entity_guesses'].items(), key=lambda x: x[1], reverse=True)[:3]
            writer.writerow({
                'domain': domain,
                'message_count': stats['message_count'],
                'attachment_count': stats['attachment_count'],
                'attachment_bytes': stats['attachment_bytes'],
                'first_date': stats['first_date'],
                'last_date': stats['last_date'],
                'top_entity_guesses': '; '.join(f"{e}({c})" for e, c in top_entities),
                'sample_subjects': ' | '.join(stats['subjects'])
            })

        self._upload_to_gcs("senders_summary.csv", output.getvalue().encode('utf-8'))

    async def _write_stats_md(self, messages: List[Dict]):
        """Write human-readable stats.md to GCS."""
        lines = []
        lines.append(f"# Gmail Inventory Stats — Run {self.run_id}\n")
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"Scope: label:{self.label_scope}\n")

        # Summary
        lines.append("## Summary\n")
        lines.append(f"- **Total messages**: {len(messages)}")
        lines.append(f"- **Unique senders**: {len(self.discovered_senders)}")
        att_count = sum(m.get('attachment_count', 0) for m in messages)
        att_bytes = sum(m.get('attachment_total_bytes', 0) for m in messages)
        lines.append(f"- **Total attachments**: {att_count}")
        lines.append(f"- **Total attachment size**: {att_bytes / 1024 / 1024:.1f} MB")
        lines.append("")

        # Top senders
        sender_counts: Dict[str, int] = defaultdict(int)
        for msg in messages:
            domain = self._extract_domain(msg.get('from_email', ''))
            sender_counts[domain or 'unknown'] += 1

        lines.append("## Top 20 Senders\n")
        lines.append("| Domain | Messages |")
        lines.append("|--------|----------|")
        for domain, count in sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
            lines.append(f"| {domain} | {count} |")
        lines.append("")

        # Entity distribution
        entity_counts: Dict[str, int] = defaultdict(int)
        for msg in messages:
            entity = msg.get('entity_guess', 'UNTAGGED')
            if not entity:
                entity = 'UNTAGGED'
            entity_counts[entity] += 1

        lines.append("## Entity Distribution\n")
        lines.append("| Entity | Messages | % |")
        lines.append("|--------|----------|---|")
        for entity, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / len(messages) * 100) if messages else 0
            lines.append(f"| {entity} | {count} | {pct:.1f}% |")
        lines.append("")

        # MIME type breakdown
        mime_counts: Dict[str, int] = defaultdict(int)
        for msg in messages:
            for att in msg.get('attachments', []):
                mime_counts[att.get('mime_type', 'unknown')] += 1

        lines.append("## Attachment MIME Types\n")
        lines.append("| MIME Type | Count |")
        lines.append("|----------|-------|")
        for mime, count in sorted(mime_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {mime} | {count} |")
        lines.append("")

        # Low confidence entity tags (for review)
        low_conf = [m for m in messages if m.get('entity_confidence') == 'low' and m.get('entity_guess')]
        if low_conf:
            lines.append("## Low-Confidence Entity Tags (Review These)\n")
            lines.append("| From | Subject | Guess | Reasoning |")
            lines.append("|------|---------|-------|-----------|")
            for msg in low_conf[:30]:
                lines.append(
                    f"| {msg.get('from_email', '')[:30]} "
                    f"| {msg.get('subject', '')[:40]} "
                    f"| {msg.get('entity_guess', '')} "
                    f"| {msg.get('entity_reasoning', '')[:50]} |"
                )
            lines.append("")

        # Suspected duplicates
        lines.append("## Suspected Duplicates\n")
        sig_groups: Dict[str, List[Dict]] = defaultdict(list)
        for msg in messages:
            sig = f"{msg.get('from_email', '')}|{msg.get('attachment_total_bytes', 0)}"
            sig_groups[sig].append(msg)

        dup_count = 0
        for sig, group in sig_groups.items():
            if len(group) > 1:
                dup_count += len(group)
                if dup_count <= 20:
                    lines.append(f"- **{group[0].get('from_email', '')}** ({len(group)} msgs, {group[0].get('attachment_total_bytes', 0)} bytes)")
                    for m in group[:3]:
                        lines.append(f"  - {m.get('subject', '')[:60]}")
        lines.append(f"\n*Total suspected duplicate messages: {dup_count}*\n")

        content = "\n".join(lines)
        self._upload_to_gcs("stats.md", content.encode('utf-8'), content_type="text/markdown")

    async def _write_raw_threads(self, messages: List[Dict]):
        """Write gzipped raw thread JSON to GCS (metadata only)."""
        thread_ids = set(m.get('thread_id', '') for m in messages if m.get('thread_id'))

        uploaded = 0
        for thread_id in thread_ids:
            try:
                thread_data = self.gmail_service.users().threads().get(
                    userId='me',
                    id=thread_id,
                    format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()

                json_bytes = json.dumps(thread_data).encode('utf-8')
                compressed = gzip.compress(json_bytes)
                blob = self.gcs_bucket.blob(f"{self._gcs_prefix()}/raw/threads/{thread_id}.json.gz")
                blob.upload_from_string(compressed, content_type="application/gzip")
                uploaded += 1

            except HttpError as e:
                logger.warning(f"Failed to fetch thread {thread_id}: {e}")

        logger.info(f"   ☁️  Uploaded {uploaded} raw thread files")

    # ─── State Management ─────────────────────────────────────────────────

    def _state_path(self) -> str:
        return f"{self._gcs_prefix()}/state.json"

    def _load_state(self) -> Dict:
        """Load state from GCS (for resumability)."""
        try:
            blob = self.gcs_bucket.blob(self._state_path())
            if blob.exists():
                content = blob.download_as_text()
                state = json.loads(content)
                self.seen_message_ids = set(state.get('seen_ids', []))
                self.discovered_senders = set(state.get('discovered_senders', []))
                logger.info(f"📂 Resumed from state: {len(self.seen_message_ids)} messages already seen")
                return state
        except Exception as e:
            logger.debug(f"No existing state (starting fresh): {e}")
        return {}

    def _save_state(self, state: Dict, messages: List[Dict]):
        """Save state to GCS for resumability."""
        state['seen_ids'] = list(self.seen_message_ids)
        state['messages'] = messages
        state['last_saved'] = datetime.now(timezone.utc).isoformat()
        state['discovered_senders'] = list(self.discovered_senders)

        content = json.dumps(state).encode('utf-8')
        blob = self.gcs_bucket.blob(self._state_path())
        blob.upload_from_string(content, content_type="application/json")

    # ─── Utilities ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_sender(from_raw: str):
        """Parse 'Name <email>' into (name, email)."""
        match = re.match(r'^"?([^"<]*)"?\s*<?([^>]*)>?$', from_raw.strip())
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return '', from_raw.strip()

    @staticmethod
    def _extract_domain(email: str) -> str:
        """Extract domain from email address."""
        if '@' in email:
            return email.split('@')[1].lower().strip()
        return ''
