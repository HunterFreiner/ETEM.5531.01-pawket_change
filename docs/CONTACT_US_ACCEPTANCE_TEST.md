# Contact Us acceptance test

This checklist is written for a non-developer. Complete it in a phone-sized window and on a laptop or desktop before merging the pull request.

## Test setup

1. Ask a developer for the test website link.
2. Open the home page in a private browser window.
3. Do not use the Django admin page during the test.

## User test

- [ ] The navigation has a visible **Contact Us** button. On a phone, open the navigation menu first.
- [ ] The button opens a separate Contact Us page.
- [ ] The page shows phone, email, address, and business hours.
- [ ] The phone is **314-555-0142**, the email is **hello@pawketchange.org**, and the address is **100 Treat Street, St. Louis, MO 63101**.
- [ ] The phone and email links open the appropriate calling or email application, and no pending-contact-details notice appears.
- [ ] Name, email address, and message are all required.
- [ ] Entering an invalid email such as `name@` shows an error and does not show a success message.
- [ ] Leaving a required field empty shows an error and does not show a success message.
- [ ] Entering a valid name, email, and message shows a confirmation after submission.
- [ ] The page remains readable and usable at phone and desktop sizes.
- [ ] A keyboard user can reach the navigation, every form field, and the Send message button in a sensible order.

Record the tester's name, test date, browser/device, and any problems in the pull request before approval.

## Developer setup notes

Run database migrations before testing so submitted messages can be stored:

```text
python manage.py migrate
```

The team-provided contact details are included by default and may be overridden at deployment time:

- `PAWKET_CONTACT_PHONE`
- `PAWKET_CONTACT_EMAIL`
- `PAWKET_CONTACT_ADDRESS`

Submitted messages are stored as `ContactMessage` records and can be reviewed in Django admin.
