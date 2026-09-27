"""
WhatsApp alerts for admins, sent through the free CallMeBot service.

HOW IT WORKS
    Django does not talk to WhatsApp. It asks CallMeBot to send the message.
    CallMeBot only sends to a phone that messaged them first and said
    "I allow callmebot to send me messages" to +34 644 87 21 57. They reply
    with a key for that phone. Both the phone and its key are needed to send.
    Setup page: https://www.callmebot.com/blog/free-api-whatsapp-messages/

    NOTE: CallMeBot's free API is meant for personal use. It is fine for a few
    internal alerts a day; if Thinkora grows, move to the official WhatsApp
    Cloud API by replacing send_to_one() below. Nothing else needs to change.

SETUP (one environment variable, any number of admins)
    WHATSAPP_ALERTS=+971501111111:483920,+971502222222:771244
                    ^^^^^^^^^^^^^ ^^^^^^
                    phone         its key

    SITE_URL=https://your-site.com     (optional: adds a tappable link)

    When WHATSAPP_ALERTS is empty, nothing is sent and nothing breaks.

SAFETY
    Students are NEVER messaged. Only the admins listed above.
    A slow or broken CallMeBot can never break student registration.
"""

import logging
import os
import threading
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

CALLMEBOT_URL = 'https://api.callmebot.com/whatsapp.php'

# CallMeBot is a free service and can be slow. Give up rather than hang.
TIMEOUT_SECONDS = 8


# ---------------------------------------------------------------------------
# The message. Edit the words between the triple quotes to change what admins
# receive. Keep the {name}, {email}, ... parts: they are filled in for you.
# ---------------------------------------------------------------------------

NEW_STUDENT_MESSAGE = """\U0001F514 New student request

Name: {name}
Email: {email}
WhatsApp: {whatsapp}
{note}
Approve here:
{link}"""


def get_admin_recipients():
    """Read WHATSAPP_ALERTS into [(phone, key), ...]. Bad entries are skipped."""
    recipients = []
    for entry in os.environ.get('WHATSAPP_ALERTS', '').split(','):
        entry = entry.strip()
        if not entry:
            continue
        # rpartition: the phone number never contains ':', so the last one splits it.
        phone, separator, apikey = entry.rpartition(':')
        if not separator or not phone.strip() or not apikey.strip():
            logger.warning('WHATSAPP_ALERTS: skipping "%s" (expected phone:key)', entry)
            continue
        recipients.append((phone.strip(), apikey.strip()))
    return recipients


def send_to_one(phone, apikey, text):
    """Ask CallMeBot to send one message. Returns True when it worked."""
    query = urllib.parse.urlencode({'phone': phone, 'text': text, 'apikey': apikey})
    try:
        with urllib.request.urlopen(f'{CALLMEBOT_URL}?{query}', timeout=TIMEOUT_SECONDS) as response:
            response.read()
        logger.info('WhatsApp alert sent to %s', phone)
        return True
    except Exception as error:
        # Never raise: an alert failing must not affect the student.
        logger.warning('WhatsApp alert to %s failed: %s', phone, error)
        return False


def send_admin_alert(text):
    """Send the same message to every configured admin. Returns how many worked."""
    recipients = get_admin_recipients()
    if not recipients:
        logger.info('WHATSAPP_ALERTS is not set: no WhatsApp alert sent.')
        return 0
    return sum(send_to_one(phone, apikey, text) for phone, apikey in recipients)


def send_admin_alert_in_background(text):
    """
    Same as send_admin_alert, but the student does not wait for it.

    Without this, a student registering would stare at a frozen screen for as
    long as CallMeBot takes to answer.
    """
    thread = threading.Thread(target=send_admin_alert, args=(text,), daemon=True)
    thread.start()


def build_new_student_message(student):
    site_url = os.environ.get('SITE_URL', '').strip().rstrip('/')
    link = f'{site_url}/admin/requests' if site_url else 'Open the admin panel -> Student Requests'
    return NEW_STUDENT_MESSAGE.format(
        name=student.display_name,
        email=student.email or 'not given',
        whatsapp=student.whatsapp_number or 'not given',
        note=f'\nMessage: "{student.request_message}"\n' if student.request_message else '',
        link=link,
    )


def notify_new_student(student):
    """Tell the admins that this student asked for access."""
    send_admin_alert_in_background(build_new_student_message(student))
