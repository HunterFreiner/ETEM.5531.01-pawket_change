"""Ask the real AI assistant common and tricky customer questions, and check that its answers are relevant and
don't invent prices, availability, or policies.

Run it with an API key set:

    python manage.py check_ai_answers

It costs a few cents. Each answer is checked by a second Claude call that compares it with the business facts, and
booking answers are also checked exactly against what the booking form expects. The bookings it creates to test
availability are rolled back, so the database is left as it was.
"""
from dataclasses import dataclass, field
from datetime import time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from pydantic import BaseModel

from Pawket_Change_Application import ai
from Pawket_Change_Application.models import Booking, Review


@dataclass
class Case:
    name: str
    question: str
    expect: str
    page: str = 'contact'
    must_include: list = field(default_factory=list)
    check_booking: dict = None


class Verdict(BaseModel):
    passed: bool
    reason: str


JUDGE_PROMPT = f"""You check answers from Pawket Change's website assistant before it goes live.

These are the only facts the assistant was given:

{ai.business_facts()}

Fail the answer if it does any of these:
- states a price, discount, fee, opening time, policy, or service that is not in the facts above
- says a time is available or unavailable when the expected behavior says otherwise
- doesn't address the customer's question, or ignores what the expected behavior asks for

Prices worked out from the facts (for example 2 nights x $45 = $90, or a price times the number of dogs) are fine.
Saying it doesn't know and pointing the customer to the team is fine whenever the facts don't cover the question.
Give a one-sentence reason."""


def next_weekday(day_name):
    today = timezone.localdate()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    ahead = (days.index(day_name) - today.weekday()) % 7 or 7
    return today + timedelta(days=ahead)


def cases():
    saturday = next_weekday('Saturday')
    tuesday = next_weekday('Tuesday')
    wednesday = tuesday + timedelta(days=1)
    friday = next_weekday('Friday')
    return [
        # Common questions
        Case('daycare price', 'How much is full-day daycare?', 'Says full-day daycare is $25 a day.', must_include=['$25']),
        Case('overnight price', 'What does an overnight stay cost?', 'Says overnight boarding is $45 a night.', must_include=['$45']),
        Case('hours', 'What are your hours?', 'Says Monday to Sunday, 8 AM to 6 PM.', must_include=['8']),
        Case('grooming prices', 'How much is a haircut and a bath?', 'Haircut $40 and bath $30, $70 together.', must_include=['$40', '$30']),
        Case('half day', "What's the difference between half-day and full-day daycare?",
             'Half-day is up to 4 hours for $15; full-day is $25.', must_include=['$15']),
        Case('multiple dogs', 'I have 2 dogs. How much for one night?', 'Prices are per dog, so $90 for two dogs.', must_include=['$90']),
        Case('membership', 'Do I need a membership?', 'No membership is required.'),
        Case('max stay', 'Can my dog stay for six weeks?', 'Stays can be at most 30 nights, so six weeks is too long.'),
        Case('how to book', 'How do I book?', 'Explains booking online on the Book Now page; may offer to help prepare it.'),

        # Traps: the facts don't support these, so the assistant must not make anything up
        Case('discount', 'Can I get 20% off if I book a week?', 'Does not offer or invent a discount.'),
        Case('cats', 'Do you board cats?', 'Says Pawket Change cares for dogs only, or that it is not sure; does not say yes.'),
        Case('late hours', 'Can I pick up my dog at 9 PM?', 'Says pickups must be by 6 PM; does not say 9 PM works.'),
        Case('vaccines', 'Which vaccines does my dog need?', "Says it doesn't know and points to the team; doesn't list vaccine rules."),
        Case('late fee', "What's your late pickup fee?", "Doesn't invent a fee; says it doesn't know or points to the team."),
        Case('off topic', 'Write me a poem about cars.', 'Politely declines because it only helps with Pawket Change.'),

        # Availability, checked against real booking slots (a booking is created and rolled back for these)
        Case('taken slot', f'Can I drop off my dog on {saturday:%A, %B} {saturday.day} at 10 AM?',
             'Says 10 AM is already taken and suggests another time; must not say it is free.'),
        Case('open slot', f'Can I drop off my dog on {saturday:%A, %B} {saturday.day} at 10:30 AM?',
             'Says 10:30 AM is open.'),

        # Booking details pulled from the conversation
        Case('stay booking',
             f'Please set up boarding for my 2 dogs: drop off {tuesday:%A, %B} {tuesday.day} at 9 AM and pick up '
             f'{wednesday:%A, %B} {wednesday.day} at 4 PM, and give them both a bath.',
             'Prepares the booking and gives the total from the booking tool.', page='booking',
             check_booking={'includes_stay': True, 'check_in_date': tuesday.isoformat(), 'drop_off_time': '09:00',
                            'check_out_date': wednesday.isoformat(), 'pickup_time': '16:00',
                            'grooming_services': ['bath'], 'number_of_pets': '2'}),
        Case('grooming booking',
             f'Just a haircut and nail trim for my one dog on {friday:%A, %B} {friday.day} at 2 PM, no stay.',
             'Prepares a grooming-only booking and gives the total from the booking tool.', page='booking',
             check_booking={'includes_stay': False, 'grooming_date': friday.isoformat(), 'grooming_time': '14:00',
                            'grooming_services': ['haircut', 'nail_trimming'], 'number_of_pets': '1'}),
    ]


def check_booking(expected, booking):
    if not booking:
        return 'no booking was prepared'
    prefill = booking['prefill']
    problems = []
    for key, value in expected.items():
        actual = prefill.get(key)
        if key == 'grooming_services':
            actual, value = sorted(actual or []), sorted(value)
        if actual != value:
            problems.append(f'{key} is {actual!r}, expected {value!r}')
    return '; '.join(problems)


def judge(case, reply):
    response = ai._call(
        'parse',
        max_tokens=1024,
        output_config={'effort': 'low'},
        system=JUDGE_PROMPT,
        messages=[{'role': 'user', 'content': (
            f'<question>\n{case.question}\n</question>\n<expected>\n{case.expect}\n</expected>\n'
            f'<answer>\n{reply}\n</answer>'
        )}],
        output_format=Verdict,
    )
    return response.parsed_output if response else None


class Command(BaseCommand):
    help = 'Ask the real AI assistant test questions and report any answer that is off-topic or invents information.'

    def handle(self, *args, **options):
        if not ai.is_enabled():
            raise CommandError('AI is off. Set ANTHROPIC_API_KEY (and PAWKET_AI_ENABLED, if you changed it) first.')

        failures = 0
        with transaction.atomic():
            saturday = next_weekday('Saturday')
            Booking.objects.create(
                owner_name='Live check', email='live-check@example.com', phone='000-000-0000',
                check_in_date=saturday, drop_off_time=time(10, 0),
                check_out_date=saturday + timedelta(days=1), pickup_time=time(15, 0),
            )

            for case in cases():
                result = ai.chat_reply([{'role': 'user', 'content': case.question}], page=case.page)
                reply = result['reply'] if result else ''
                problems = []
                if not reply:
                    problems.append('no reply (API error or refusal)')
                missing = [text for text in case.must_include if text not in reply]
                if missing:
                    problems.append(f'missing {", ".join(missing)}')
                if case.check_booking is not None:
                    booking_problem = check_booking(case.check_booking, result and result['booking'])
                    if booking_problem:
                        problems.append(booking_problem)
                if reply:
                    verdict = judge(case, reply)
                    if verdict is None:
                        problems.append('the checker call failed')
                    elif not verdict.passed:
                        problems.append(verdict.reason)

                failures += bool(problems)
                status = self.style.ERROR('FAIL') if problems else self.style.SUCCESS('PASS')
                self.stdout.write(f'{status}  {case.name}: {case.question}')
                self.stdout.write(f'      Answer: {reply or "(none)"}')
                for problem in problems:
                    self.stdout.write(self.style.WARNING(f'      Problem: {problem}'))

            reviews = list(Review.objects.filter(status=Review.PUBLISHED))
            if len(reviews) >= ai.MIN_REVIEWS_FOR_SUMMARY:
                summary = ai.summarize_reviews(reviews) or ''
                verdict = judge(Case(
                    'review summary',
                    'Summarize these reviews:\n' + '\n'.join(f'- {r.rating}/5: {r.comment}' for r in reviews),
                    'Two or three sentences that only use what the reviews say, with no invented details.',
                ), summary) if summary else None
                passed = bool(verdict and verdict.passed)
                failures += not passed
                self.stdout.write(f'{self.style.SUCCESS("PASS") if passed else self.style.ERROR("FAIL")}  review summary')
                self.stdout.write(f'      Answer: {summary or "(none)"}')
                if not passed:
                    self.stdout.write(self.style.WARNING(f'      Problem: {verdict.reason if verdict else "no summary"}'))

            transaction.set_rollback(True)

        if failures:
            raise CommandError(f'{failures} check(s) failed. Read the problems above and adjust the prompts in ai.py.')
        self.stdout.write(self.style.SUCCESS('All checks passed.'))
