# AI features

Pawket Change uses Claude (Claude Haiku 5.5, made by Anthropic) for:

- **Contact page assistant:** answers questions about services, prices, and hours, checks open time slots, and gives a "Review this booking" button that fills in the booking form. It never books by itself. Customers can send the chat to the team with one button.
- **Contact message tags:** every Contact Us message, and every chat sent to the team, gets a category and a priority in the Django admin.
- **Review moderation:** reviews with spam, abuse, or private details are held as *pending* until staff publish them. Negative reviews are never held for being negative.
- **Review summary:** a short "What guests are saying" summary on the Reviews page once there are at least 3 published reviews. It's only rewritten after reviews change.
- **Reply drafts:** an admin action drafts a reply to a review. Staff edit it and paste it into **Owner reply** to post it.

If there's no API key, or `PAWKET_AI_ENABLED=false`, all of this turns off and the site works exactly as before. The same happens for a single request if the API is down.

## Setting up the API key

1. Go to <https://platform.claude.com> and sign up or log in. Use an account the business controls, not a personal one.
2. Under **Settings → Billing**, add a payment method and buy a small amount of credit (for example $5). Optionally set a monthly spend limit under **Settings → Limits**.
3. Go to **Settings → API keys**, click **Create key**, name it something like `pawket-change-site`, and copy the key (it starts with `sk-ant-`). You can only see it once.
4. Set it as an environment variable where the site runs. Never put it in code or commit it to Git.
   - macOS/Linux terminal, for the current session: `export ANTHROPIC_API_KEY="sk-ant-..."`
   - To keep it, add that line to `~/.zshrc`, or set it in your hosting provider's environment settings.
5. Restart the server (`python manage.py runserver`). The Contact page now shows **Ask our assistant**.

If a key is ever leaked, delete it on the **API keys** page and create a new one.

Optional settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | (none) | Turns AI on |
| `PAWKET_AI_MODEL` | `claude-haiku-5-5` | Which Claude model to use |
| `PAWKET_AI_ENABLED` | `true` | Set to `false` to turn AI off without removing the key |

## Developer notes

- Install dependencies with `pip install -r requirements.txt`, then run `python manage.py migrate`.
- All Claude calls are in `Pawket_Change_Application/ai.py`. Prices and services come from `SERVICES`, `ADD_ONS`, and `PRICING_POLICIES` in `models.py`, the same lists the Services page uses, so the assistant's answers stay up to date.
- The test suite mocks Claude and never calls the real API, even if a key is set.
- The chat allows 20 messages per visitor per hour and 1,000 characters per message.

## Acceptance test

Run with the API key set. Record the tester's name, date, browser/device, and any problems in the pull request.

### Contact page assistant

- [ ] The Contact page shows **Ask our assistant** and a notice that it's AI and that messages are sent to Anthropic.
- [ ] Asking "How much is an overnight stay?" gives **$45 a night**.
- [ ] Asking something it can't know (for example "Do you take cats?") gets an honest "not sure" and points to sending the chat to the team.
- [ ] Asking for a stay with dates and times (for example "Can I drop off tomorrow at 10am and pick up the day after at 3pm?") shows a **Review this booking** button. It opens Book a Stay with the dates and times filled in, and nothing is booked until you confirm.
- [ ] Asking for a time that's already booked or outside 8 AM – 6 PM gets told it isn't available.
- [ ] **Send this conversation to our team** asks for name and email. A bad email shows an error. A good one shows a thank-you, and the message appears in the admin with the chat transcript.
- [ ] Off-topic requests (for example "Write me a poem about cars") are politely declined.
- [ ] The chat works with a keyboard and at phone width.

### Contact message tags

- [ ] Send a complaint through the Contact form (for example "My dog came home hurt"). In the admin it shows **Complaint** and **High** priority.
- [ ] Send a simple pricing question. It shows **Pricing** and a normal or low priority.
- [ ] The admin can filter by priority and category, and staff can change a tag.

### Reviews

- [ ] A normal review, including a negative one, is posted right away.
- [ ] A review containing a phone number or an ad is held: the customer sees "after a quick check by our team", and the review is hidden until it's published in the admin.
- [ ] The Reviews page shows **What guests are saying** with an "AI" note.
- [ ] In the admin, **Draft a reply with AI** fills **Owner reply draft** only. After you copy the text into **Owner reply** and save, it shows under the review.
