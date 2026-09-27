"""
Check that WhatsApp alerts reach the admins, without registering a fake student.

    python manage.py test_whatsapp_alert
"""

from django.core.management.base import BaseCommand

from users.notifications import get_admin_recipients, send_to_one


def hide_key(apikey):
    """483920 -> 48***20, so the key never appears in full on screen or in logs."""
    return apikey if len(apikey) < 5 else f'{apikey[:2]}***{apikey[-2:]}'


class Command(BaseCommand):
    help = 'Send a test WhatsApp message to every admin listed in WHATSAPP_ALERTS.'

    def handle(self, *args, **options):
        recipients = get_admin_recipients()

        if not recipients:
            self.stderr.write(self.style.ERROR('WHATSAPP_ALERTS is empty, so nobody would be messaged.'))
            self.stderr.write('')
            self.stderr.write('Add this to your .env on the server, then restart the container:')
            self.stderr.write('  WHATSAPP_ALERTS=+971501111111:483920,+971502222222:771244')
            return

        self.stdout.write(f'Sending a test message to {len(recipients)} admin(s)...')
        self.stdout.write('')

        worked = 0
        for phone, apikey in recipients:
            self.stdout.write(f'  {phone}  (key {hide_key(apikey)}) ... ', ending='')
            if send_to_one(phone, apikey, 'Thinkora LMS test message. Alerts are working.'):
                self.stdout.write(self.style.SUCCESS('sent'))
                worked += 1
            else:
                self.stdout.write(self.style.ERROR('FAILED'))

        self.stdout.write('')
        if worked == len(recipients):
            self.stdout.write(self.style.SUCCESS(f'All {worked} message(s) sent. Check the phones now.'))
            return

        self.stdout.write(self.style.WARNING(f'{worked} of {len(recipients)} sent.'))
        self.stdout.write('')
        self.stdout.write('A failure usually means one of these:')
        self.stdout.write('  - that admin never messaged CallMeBot, so they have no permission')
        self.stdout.write('  - the key does not match that phone number')
        self.stdout.write('  - the server cannot reach the internet')
