# Booking confirmation and notifications

Prepared for the Pawket Change team by Jinkai Li. Implements the Sprint 3 booking confirmation story on develop commit `641a9d255bd3214631ee3dd48c62c4060fc67242`.

## What changed

- The saved booking has an explicit Awaiting approval or Confirmed status. New requests await staff approval; this follows the existing page's statement that availability is confirmed separately.
- The confirmation page shows the reference, status, service, selected dates and times, grooming details, existing pet information and price breakdown. All times are labeled America/Chicago using the project's time zone setting.
- A receipt email is queued with the saved booking and pets. Sending happens only after the transaction commits. The email includes booking details and configured contact information, without medication or dietary notes.
- Staff can change Status in Django admin. Saving a changed status queues a new notification. Saving an unchanged status does not send another email. Direct database updates bypass this admin workflow and must not be used to approve bookings.
- Failed email attempts do not undo the booking. An outbox stores delivery state and supports manual retries. Sent means accepted by the mail backend, not verified inbox delivery. Console, file and in-memory backends are labeled development previews.
- Confirmation details are visible only in the submitting browser session or to a user with the view_booking permission. Other sessions get 404; responses are marked no-store. Do not share confirmation URLs as public links. A customer whose session expires should use the contact form and booking reference.
- Identical final submissions in the same session return the existing booking instead of creating another. Different submissions remain separate. This is not a guarantee across different browser sessions. A customer intentionally requesting an identical booking should contact staff.

## Apply the patch

Use a clean working tree or commit your existing work first. Do not overwrite another teammate's uncommitted edits.

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feature/jinkai-booking-confirmation
git apply --check /path/to/booking-confirmation.patch
git apply /path/to/booking-confirmation.patch
```

If `--check` fails, the target branch has changed. Review and merge the relevant files manually; do not force the patch or replace whole files blindly.

From the repository root, use the team's Python virtual environment:

```bash
python -m pip install -r requirements.txt
python Pawket_Change/manage.py migrate
python Pawket_Change/manage.py test
python Pawket_Change/manage.py createsuperuser
python Pawket_Change/manage.py runserver
```

The migration adds two Booking fields and a BookingNotification outbox table. Existing bookings are assigned Awaiting approval, and no historical emails are sent. Staff must review historical booking statuses before using this on an existing live database. Back up that database before applying migrations.

## Development email preview

The default backend writes messages to the local server console. Set `PAWKET_DEFAULT_FROM_EMAIL=preview@example.com` for local preview only. Without a sender address the attempt is safely recorded as failed.

Submit a booking through `/book`, then inspect the confirmation page and terminal output. Log in at `/admin/`, open the booking, change Status to Confirmed and save. Inspect the new email preview and refresh the confirmation page in the original browser session.

No customer email is actually sent in preview mode. Do not use example addresses for live sending.

## Real email configuration

Set environment variables in the server's environment or deployment platform. This change does not add a dotenv loader; merely creating a `.env` file does not configure the app. Never commit passwords or provider keys.

| Variable | Value required |
| --- | --- |
| PAWKET_EMAIL_BACKEND | django.core.mail.backends.smtp.EmailBackend |
| PAWKET_EMAIL_HOST | Team's SMTP hostname |
| PAWKET_EMAIL_PORT | Provider's port, commonly 587 for STARTTLS |
| PAWKET_EMAIL_HOST_USER | Provider-issued username |
| PAWKET_EMAIL_HOST_PASSWORD | Provider-issued password or SMTP credential |
| PAWKET_EMAIL_USE_TLS | true for STARTTLS; match provider requirements |
| PAWKET_EMAIL_USE_SSL | true only for implicit TLS; never true together with USE_TLS |
| PAWKET_DEFAULT_FROM_EMAIL | Verified sender address allowed by the provider |
| PAWKET_CONTACT_EMAIL | Real monitored business email, also used as Reply-To |
| PAWKET_CONTACT_PHONE | Real business phone |

Restart the application after changing these settings. Test only with a team-controlled recipient address, then verify actual receipt, spam placement, dates, status and reply/contact information. The Contact Us form remains available if contact details are unset, but real business contact details should be configured before acceptance.

## Failed notifications

Inspect Booking notifications in admin. After correcting configuration or a temporary outage:

```bash
python Pawket_Change/manage.py retry_booking_notifications
```

This processes pending and failed items only. It skips obsolete status messages and never resends sent or preview entries. A preview is not a live delivery; use a new test booking after configuring SMTP. The command is manual: no recurring worker has been installed.

An item left in Sending after a process crash requires staff investigation of provider logs before any reset. SMTP cannot guarantee exactly-once delivery if a server accepts a message but the app loses the acknowledgement. Retrying an ambiguous failure can duplicate an email. The app avoids routine double sends but does not promise exactly-once transport. Sending is synchronous after commit with a 10-second network timeout; consider a background worker for production volume.

## Acceptance testing

1. Submit a stay booking and verify the page and email show the same service, reference, dates, times and Awaiting approval status.
2. Submit grooming-only and combined stay/grooming bookings. Only applicable date fields should appear; combined grooming is described as occurring during the stay.
3. Approve a booking in admin. Verify Confirmed on the page and in a new email. Save it again without changing status and verify no extra email.
4. Confirm real inbox receipt using configured SMTP. Local previews and mocked SMTP tests do not satisfy this step.
5. Verify the Contact Us link and real email/phone. Check desktop and narrow mobile layouts.
6. Simulate email failure in a test environment. The saved booking must remain and the page must explain the failure. Repair the backend and retry once.
7. Repeat the same submission and refresh the page. Verify one booking and one receipt notification.
8. Open the numbered confirmation URL in a different browser session. It must return 404, not customer details.
9. Have someone other than the developer test the feature, and raise a GitHub PR before marking the story Done.

## Verification and remaining work

147 automated tests passed: 134 existing tests plus 13 new notification tests. Django system checks and migration consistency checks passed. Failure messages in the test output are intentional mocked error-path tests, not live provider calls.

No live email credentials were used, no customer email was sent, and no production deployment was performed. This branch is for code review; teammate acceptance testing and live email verification are still required before marking the story Done.

Browser visual testing was not completed because the local test browser download failed. Template responses and page content are covered by automated tests; desktop and mobile visual checks remain part of teammate acceptance.

The project pins Django 4.2.16. This patch preserves the team's dependency versions, but Django 4.2 documentation now marks that branch unsupported. Plan a separately tested framework upgrade before public production deployment. Existing project-wide production settings and unrelated review/AI features were not audited by this change.

References: https://docs.djangoproject.com/en/4.2/topics/email/ and https://docs.djangoproject.com/en/4.2/topics/db/transactions/
