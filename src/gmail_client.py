"""Gmail API client for reading Classroom notifications."""

import base64
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


@dataclass
class EmailMessage:
    """Represents an email message from Classroom."""

    id: str
    thread_id: str
    subject: str
    from_address: str
    date: datetime
    body: str
    snippet: str
    link: str | None = None


class GmailClient:
    """Client for interacting with Gmail API."""

    def __init__(self, credentials_file: str, token_file: str):
        """Initialize the client with OAuth credentials."""
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self._service = None
        self._credentials = None
        self._token_loaded = False

    def _get_service(self):
        """Get or create the Gmail service with OAuth."""
        if self._service is not None:
            return self._service

        # Load existing token
        self._credentials = None
        token_load_success = False
        
        if self.token_file.exists():
            try:
                import json
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                self._credentials = Credentials.from_authorized_user_info(
                    token_data,
                    SCOPES,
                )
                token_load_success = True
                logger.info("Token loaded successfully")
                logger.info(f"Token valid: {self._credentials.valid}, expired: {getattr(self._credentials, 'expired', 'N/A')}")
            except Exception as e:
                logger.warning(f"Failed to load token: {e}")

        # Mark token as loaded (even if failed, to avoid repeated attempts)
        self._token_loaded = True

        # Check if we need to refresh or get new credentials
        if self._credentials:
            try:
                if self._credentials.expired and self._credentials.refresh_token:
                    logger.info("Token expired, refreshing...")
                    self._credentials.refresh(Request())
                    self._save_token()
                elif not self._credentials.valid:
                    logger.warning("Token invalid, need new auth")
                    self._run_oauth_flow()
            except Exception as e:
                logger.warning(f"Token validation failed: {e}")
                self._run_oauth_flow()
        else:
            # No credentials loaded
            self._run_oauth_flow()

        # Build the service
        self._service = discovery.build("gmail", "v1", credentials=self._credentials)
        return self._service

    def _run_oauth_flow(self):
        """Run OAuth 2.0 flow to get new credentials."""
        if not self.credentials_file.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_file}\n"
                "Please download OAuth credentials from Google Cloud Console."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_file), SCOPES
        )

        # Run local server flow
        self._credentials = flow.run_local_server(
            port=0,
            prompt="consent",
            success_message="Authentication successful! You can close this window.",
        )

        self._save_token()
        logger.info("OAuth authentication completed")

    def _save_token(self):
        """Save the token to file."""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert credentials to dict and save
        token_info = {
            "token": self._credentials.token,
            "refresh_token": self._credentials.refresh_token,
            "token_uri": self._credentials.token_uri,
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "scopes": list(self._credentials.scopes),
        }

        import json

        with open(self.token_file, "w") as f:
            json.dump(token_info, f)

        logger.info(f"Token saved to {self.token_file}")
        self._token_loaded = True

    def get_all_emails(self, max_results: int = 20) -> list[EmailMessage]:
        """Get recent emails (for debugging)."""
        service = self._get_service()

        messages = []
        page_token = None

        while len(messages) < max_results:
            response = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    maxResults=min(100, max_results - len(messages)),
                    pageToken=page_token,
                )
                .execute()
            )

            msg_ids = response.get("messages", [])

            # Get details for each message
            for msg_id in msg_ids:
                try:
                    msg = (
                        service.users()
                        .messages()
                        .get(userId="me", id=msg_id["id"], format="full")
                        .execute()
                    )

                    email = self._parse_message(msg)
                    if email:
                        messages.append(email)

                except Exception as e:
                    logger.warning(f"Failed to get message {msg_id['id']}: {e}")

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Retrieved {len(messages)} emails total")
        return messages

    def get_classroom_emails(self, max_results: int = 50, unread_only: bool = True) -> list[EmailMessage]:
        """Get emails from noreply@classroom.google.com.
        
        Args:
            max_results: Maximum number of emails to retrieve
            unread_only: If True, only get unread emails
        """
        service = self._get_service()

        # Build search query
        base_queries = [
            "from:no-reply@classroom.google.com",  # no-reply with hyphen
            "from:s5.ukr.education",  # Forwarded from school email
            "from:ukr.education",      # Any ukr.education domain
        ]
        
        # Add unread filter if requested
        if unread_only:
            base_queries = [q + " is:unread" for q in base_queries]
        
        messages = []
        seen_ids = set()
        
        for query in base_queries:
            logger.info(f"Searching with query: {query}")
            
            page_token = None
            while len(messages) < max_results:
                try:
                    response = (
                        service.users()
                        .messages()
                        .list(
                            userId="me",
                            q=query,
                            maxResults=min(100, max_results - len(messages)),
                            pageToken=page_token,
                        )
                        .execute()
                    )

                    msg_ids = response.get("messages", [])

                    # Get details for each message
                    for msg_id in msg_ids:
                        if msg_id["id"] in seen_ids:
                            continue
                        seen_ids.add(msg_id["id"])
                        
                        try:
                            # Get raw message for proper text/plain extraction
                            msg = (
                                service.users()
                                .messages()
                                .get(userId="me", id=msg_id["id"], format="raw")
                                .execute()
                            )

                            email = self._parse_raw_message(msg)
                            if email:
                                messages.append(email)

                        except Exception as e:
                            logger.warning(f"Failed to get message {msg_id['id']}: {e}")

                    page_token = response.get("nextPageToken")
                    if not page_token:
                        break
                        
                except Exception as e:
                    logger.warning(f"Query failed: {query} - {e}")
                    break
        
        logger.info(f"Retrieved {len(messages)} Classroom emails")
        return messages

    def mark_as_read(self, message_ids: list[str]):
        """Mark emails as read.
        
        Args:
            message_ids: List of message IDs to mark as read
        """
        if not message_ids:
            return
            
        service = self._get_service()
        
        # Batch modification to mark as read
        try:
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': message_ids,
                    'removeLabelIds': ['UNREAD'],
                }
            ).execute()
            logger.info(f"Marked {len(message_ids)} emails as read")
        except Exception as e:
            logger.warning(f"Failed to mark emails as read: {e}")
            # If permission denied, try to add new scope to credentials
            # The user will need to re-authenticate

    def _parse_message(self, msg: dict) -> EmailMessage | None:
        """Parse a Gmail message into EmailMessage."""
        try:
            # Headers can be in payload.headers or at top level
            headers = {}
            
            # Try payload headers first (for format='full')
            if "payload" in msg and "headers" in msg["payload"]:
                headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
            # Fall back to top-level headers
            elif "headers" in msg:
                headers = {h["name"].lower(): h["value"] for h in msg.get("headers", [])}

            # Get basic info
            msg_id = msg.get("id", "")
            thread_id = msg.get("threadId", "")
            subject = headers.get("subject", "")
            from_addr = headers.get("from", "")
            date_str = headers.get("date", "")

            # Parse date
            try:
                # Try multiple date formats
                date = self._parse_date(date_str)
            except Exception:
                date = datetime.now()

            # Get body
            body = ""
            snippet = msg.get("snippet", "")

            # Try to get full body from different parts
            if "payload" in msg:
                payload = msg["payload"]
                body = self._get_body_from_payload(payload)

            return EmailMessage(
                id=msg_id,
                thread_id=thread_id,
                subject=subject,
                from_address=from_addr,
                date=date,
                body=body,
                snippet=snippet,
            )

        except Exception as e:
            logger.warning(f"Failed to parse message: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats."""
        from email.utils import parsedate_to_datetime

        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            pass

        # Try common formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S %z",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except Exception:
                continue

        return datetime.now()

    def _decode_body_data(self, data: str) -> str:
        """Decode base64url-encoded body data with multiple encoding attempts."""
        try:
            raw = base64.urlsafe_b64decode(data + "==")
        except Exception:
            return ""

        # Try multiple encodings
        encodings = ["utf-8", "windows-1251", "koi8-u", "iso-8859-5"]

        for encoding in encodings:
            try:
                return raw.decode(encoding)
            except Exception:
                continue

        # Fallback with replacement
        return raw.decode("utf-8", errors="replace")

    def _get_body_from_payload(self, payload: dict) -> str:
        """Extract body text from email payload."""
        # Handle multipart messages
        if "parts" in payload:
            parts = payload["parts"]

            # Try text/plain first
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data")
                    if data:
                        result = self._decode_body_data(data)
                        if result:
                            return result

                # Check nested parts
                if "parts" in part:
                    result = self._get_body_from_payload(part)
                    if result:
                        return result

            # Fall back to text/html if no text/plain
            for part in parts:
                if part.get("mimeType") == "text/html":
                    data = part.get("body", {}).get("data")
                    if data:
                        html = self._decode_body_data(data)
                        if html:
                            # Try to extract readable text from HTML
                            import re
                            # Remove HTML tags
                            text = re.sub(r'<[^>]+>', ' ', html)
                            text = re.sub(r'\s+', ' ', text)
                            return text.strip()

        # Try body directly (non-multipart)
        if "body" in payload:
            data = payload["body"].get("data")
            if data:
                return self._decode_body_data(data)

        return ""

    def _parse_raw_message(self, raw_msg: dict) -> EmailMessage | None:
        """Parse a raw Gmail message into EmailMessage."""
        try:
            import base64
            import email
            from email import policy
            
            raw_data = raw_msg.get("raw", "")
            if not raw_data:
                return None
            
            # Decode base64url
            raw_bytes = base64.urlsafe_b64decode(raw_data.encode('ASCII'))
            msg = email.message_from_bytes(raw_bytes, policy=policy.default)
            
            # Extract headers
            subject = msg.get("Subject", "")
            from_addr = msg.get("From", "")
            date_str = msg.get("Date", "")
            
            # Parse date
            try:
                date = self._parse_date(date_str)
            except Exception:
                date = datetime.now()
            
            # Get body - prefer text/plain
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_content() or ""
                        if body:
                            break
            else:
                body = msg.get_content() or ""
            
            return EmailMessage(
                id=raw_msg.get("id", ""),
                thread_id=raw_msg.get("threadId", ""),
                subject=subject,
                from_address=from_addr,
                date=date,
                body=body,
                snippet="",
            )
        except Exception as e:
            logger.warning(f"Failed to parse raw message: {e}")
            return None

    def get_new_emails_since(self, since: datetime) -> list[EmailMessage]:
        """Get Classroom emails newer than a specific datetime."""
        all_emails = self.get_classroom_emails()
        return [e for e in all_emails if e.date >= since]

    def get_recent_emails(self, hours: int = 24, limit: int = 50) -> list[EmailMessage]:
        """Get Classroom emails from the last N hours."""
        cutoff = datetime.now() - __import__("timedelta", fromlist=["timedelta"]).timedelta(hours=hours)
        return self.get_new_emails_since(cutoff)