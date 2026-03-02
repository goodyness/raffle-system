from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import uuid
import hashlib

from raffle.models import Raffle, RaffleTicket

class Command(BaseCommand):
    help = 'Generates fake participants for load testing a raffle'

    def add_arguments(self, parser):
        parser.add_argument('raffle_id', type=str, help='The custom_id of the raffle')
        parser.add_argument('--count', type=int, default=5000, help='Number of tickets/participants to generate')
        parser.add_argument('--amount', type=float, default=500.00, help='Amount paid per ticket')

    def handle(self, *args, **options):
        raffle_id = options['raffle_id']
        count = options['count']
        amount = options['amount']

        try:
            raffle = Raffle.objects.get(custom_id=raffle_id)
        except Raffle.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Raffle with ID {raffle_id} does not exist."))
            return

        import string
        import random

        self.stdout.write(self.style.WARNING(f"Generating {count} tickets for '{raffle.title}'..."))

        tickets_to_create = []
        batch_size = 1000
        total_created = 0

        for i in range(count):
            ref = str(uuid.uuid4())
            ticket = RaffleTicket(
                raffle=raffle,
                name=f"Test User {total_created + 1}",
                email=f"loadtest{total_created + 1}_{ref[:8]}@example.com",
                is_paid=True,
                amount_paid=amount,
                payment_reference=f"LOAD_TEST_{ref}",
                purchased_at=timezone.now(),
                ticket_number=''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            )
            tickets_to_create.append(ticket)
            total_created += 1

            if len(tickets_to_create) >= batch_size:
                with transaction.atomic():
                    RaffleTicket.objects.bulk_create(tickets_to_create)
                self.stdout.write(f"Inserted {total_created} tickets...")
                tickets_to_create = []

        if tickets_to_create:
            with transaction.atomic():
                RaffleTicket.objects.bulk_create(tickets_to_create)
            self.stdout.write(f"Inserted remaining {len(tickets_to_create)} tickets. Total: {total_created}.")

        self.stdout.write("Running auto-lock checks (Bypassing emails)...")
        paid_count = raffle.tickets.filter(is_paid=True).count()
        if paid_count >= raffle.target_participants and raffle.status == 'active':
            raffle.status = 'locked'
            raffle.locked_at = timezone.now()
            
            p_ids = sorted([str(t.id) for t in raffle.tickets.filter(is_paid=True)])
            raffle.participants_hash = hashlib.sha256(",".join(p_ids).encode()).hexdigest()
            raffle.notification_sent = True # Bypass the readiness email
            raffle.save()
            self.stdout.write(self.style.SUCCESS(f"Raffle {raffle.title} target reached! Status set to LOCKED."))

        self.stdout.write(self.style.SUCCESS(f"Successfully generated {count} paid participants for {raffle.title}."))


# python manage.py load_test_raffle RAF-RAFFLE-ILDMZI --count 5000 --amount 500.00
