"""
ABOUTME: Email (EML/MSG) extraction with thread structure and attachments
ABOUTME: Preserves email metadata, body, and attachment information
"""

import email
import email.utils
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.message import EmailMessage as StdEmailMessage
from email.parser import BytesParser
from typing import Dict, List, Optional

from app.utils.logging import logger


@dataclass
class EmailAttachment:
    """Email attachment metadata"""

    filename: str
    content_type: str
    size_bytes: int
    content: Optional[bytes] = None  # Optional: include actual content


@dataclass
class ExtractedEmail:
    """Extracted email message (renamed to avoid conflict with stdlib)"""

    subject: str
    sender: str
    recipients: List[str]
    date: Optional[datetime]
    body_text: str
    body_html: Optional[str]
    attachments: List[EmailAttachment]
    message_id: Optional[str]
    in_reply_to: Optional[str]
    references: List[str]


class EmailExtractor:
    """
    Extract structured data from EML files
    Handles email threads, attachments, and metadata
    """

    def extract_message(self, file_content: bytes) -> ExtractedEmail:
        """
        Extract complete email message

        Args:
            file_content: EML file bytes

        Returns:
            ExtractedEmail object
        """
        try:
            # Parse email
            msg: StdEmailMessage = BytesParser(policy=policy.default).parsebytes(file_content)

            # Extract headers
            subject = msg.get("Subject", "")
            sender = msg.get("From", "")
            recipients = msg.get_all("To", [])
            cc = msg.get_all("Cc", [])
            all_recipients = recipients + cc

            # Parse date
            date_str = msg.get("Date")
            date = None
            if date_str:
                try:
                    date = email.utils.parsedate_to_datetime(date_str)
                except Exception:
                    pass

            # Extract threading info
            message_id = msg.get("Message-ID")
            in_reply_to = msg.get("In-Reply-To")
            references = msg.get_all("References", [])

            # Extract body
            body_text = ""
            body_html = None
            attachments = []

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))

                    # Extract text body
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        body_text += part.get_content()

                    # Extract HTML body
                    elif content_type == "text/html" and "attachment" not in content_disposition:
                        if body_html is None:
                            body_html = part.get_content()

                    # Extract attachments
                    elif "attachment" in content_disposition or part.get_filename():
                        filename = part.get_filename() or "unknown"
                        content = part.get_payload(decode=True)

                        # Convert content to bytes if needed
                        content_bytes: Optional[bytes] = (
                            content if isinstance(content, bytes) else None
                        )

                        attachments.append(
                            EmailAttachment(
                                filename=filename,
                                content_type=content_type,
                                size_bytes=len(content) if content else 0,
                                content=content_bytes,  # Store for potential processing
                            )
                        )
            else:
                # Non-multipart message
                body_text = msg.get_content()

            logger.info(f"Extracted email: {subject} with {len(attachments)} attachments")

            return ExtractedEmail(
                subject=subject,
                sender=sender,
                recipients=all_recipients,
                date=date,
                body_text=body_text.strip(),
                body_html=body_html,
                attachments=attachments,
                message_id=message_id,
                in_reply_to=in_reply_to,
                references=references,
            )

        except Exception as e:
            logger.error(f"Email extraction failed: {str(e)}")
            return ExtractedEmail(
                subject="",
                sender="",
                recipients=[],
                date=None,
                body_text="",
                body_html=None,
                attachments=[],
                message_id=None,
                in_reply_to=None,
                references=[],
            )

    def extract_text_only(self, file_content: bytes) -> str:
        """
        Extract plain text from email (for simple use cases)

        Args:
            file_content: EML file bytes

        Returns:
            Plain text string
        """
        message = self.extract_message(file_content)

        # Format email as readable text
        lines = []

        if message.subject:
            lines.append(f"Subject: {message.subject}")
        if message.sender:
            lines.append(f"From: {message.sender}")
        if message.recipients:
            lines.append(f"To: {', '.join(message.recipients)}")
        if message.date:
            lines.append(f"Date: {message.date.strftime('%Y-%m-%d %H:%M:%S')}")

        lines.append("")  # Blank line
        lines.append(message.body_text)

        return "\n".join(lines)

    def extract_thread_structure(self, file_content: bytes) -> Dict:
        """
        Extract email thread structure

        Args:
            file_content: EML file bytes

        Returns:
            Dict with thread metadata
        """
        message = self.extract_message(file_content)

        return {
            "message_id": message.message_id,
            "in_reply_to": message.in_reply_to,
            "references": message.references,
            "subject": message.subject,
            "date": message.date.isoformat() if message.date else None,
            "is_reply": message.in_reply_to is not None,
            "is_forward": "Fwd:" in message.subject or "FW:" in message.subject,
        }

    def clean_email_text(self, text: str) -> str:
        """
        Clean email text (remove quotes, signatures, etc.)

        Args:
            text: Raw email body text

        Returns:
            Cleaned text
        """
        lines = text.split("\n")
        cleaned = []

        # Remove quoted replies (lines starting with >)
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith(">"):
                cleaned.append(line)

        text = "\n".join(cleaned)

        # Remove common signature markers
        signature_markers = [
            "-- ",
            "___",
            "Sent from",
            "Get Outlook for",
            "Von meinem iPhone gesendet",
            "Von meinem Android-Gerät gesendet",
        ]

        for marker in signature_markers:
            if marker in text:
                text = text.split(marker)[0]

        return text.strip()

    def extract_attachments_metadata(self, file_content: bytes) -> List[Dict]:
        """
        Extract attachment metadata only (without content)

        Args:
            file_content: EML file bytes

        Returns:
            List of attachment metadata dicts
        """
        message = self.extract_message(file_content)

        return [
            {
                "filename": att.filename,
                "content_type": att.content_type,
                "size_bytes": att.size_bytes,
            }
            for att in message.attachments
        ]


# Global instance
email_extractor = EmailExtractor()
