import resend
from worker.config import RECEIVING_ADDRESS


def send_reply(email, subject, html):
    """
    Send a reply to the original sender.
    """

    sender = email["from"]
    message_id = email["message_id"]

    params = {
        "from": RECEIVING_ADDRESS,

        "to": [
            sender
        ],

        "subject": subject,

        "html": html,

        "headers": {
            "In-Reply-To": message_id,
            "References": message_id,
        },
    }

    return resend.Emails.send(params)
