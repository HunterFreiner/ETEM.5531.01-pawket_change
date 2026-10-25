// Contact page chat assistant. The conversation lives only in this page and is sent with each question.
// Replies are shown with textContent, never as HTML.
(() => {
    const panel = document.querySelector('[data-chat]');
    if (!panel) {
        return;
    }

    const log = panel.querySelector('[data-chat-log]');
    const form = panel.querySelector('[data-chat-form]');
    const input = panel.querySelector('[data-chat-input]');
    const sendButton = panel.querySelector('[data-chat-send]');
    const handoffOpen = panel.querySelector('[data-handoff-open]');
    const handoffForm = panel.querySelector('[data-handoff-form]');
    const handoffError = panel.querySelector('[data-handoff-error]');
    const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;
    const history = [];

    function addMessage(role, text, extraClass) {
        const message = document.createElement('p');
        message.className = `chat-message chat-message-${role}${extraClass ? ` ${extraClass}` : ''}`;
        message.textContent = text;
        log.appendChild(message);
        log.scrollTop = log.scrollHeight;
        return message;
    }

    function addBookingLink(booking) {
        const link = document.createElement('a');
        link.className = 'btn btn-pawket btn-sm chat-booking-link';
        link.href = booking.url;
        link.textContent = `Review this booking: ${booking.label} →`;
        log.appendChild(link);
        log.scrollTop = log.scrollHeight;
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
            body: JSON.stringify(body),
        });
    }

    form.addEventListener('submit', async event => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question) {
            return;
        }
        addMessage('user', question);
        history.push({role: 'user', content: question});
        input.value = '';
        input.disabled = true;
        sendButton.disabled = true;
        const pending = addMessage('assistant', 'Thinking…', 'chat-message-pending');

        let reply = "Sorry, something went wrong. You can send your question to our team with the form on this page.";
        let booking = null;
        try {
            const response = await postJson(panel.dataset.chatUrl, {messages: history});
            const data = await response.json();
            if (data.reply) {
                reply = data.reply;
                booking = data.booking;
            }
        } catch (error) {
            // Keep the fallback reply.
        }

        pending.remove();
        addMessage('assistant', reply);
        history.push({role: 'assistant', content: reply});
        if (booking) {
            addBookingLink(booking);
        }
        handoffOpen.hidden = false;
        input.disabled = false;
        sendButton.disabled = false;
        input.focus();
    });

    handoffOpen.addEventListener('click', () => {
        handoffForm.hidden = false;
        handoffOpen.hidden = true;
        handoffForm.querySelector('input[name=name]').focus();
    });

    handoffForm.addEventListener('submit', async event => {
        event.preventDefault();
        handoffError.hidden = true;
        const fields = new FormData(handoffForm);
        let data = {};
        try {
            const response = await postJson(panel.dataset.handoffUrl, {
                name: fields.get('name'),
                email: fields.get('email'),
                messages: history,
            });
            data = await response.json();
        } catch (error) {
            data = {errors: {__all__: ['We could not send this right now. Please try again later.']}};
        }

        if (data.ok) {
            handoffForm.hidden = true;
            handoffForm.reset();
            addMessage('assistant', "Thanks! Our team has your conversation and will email you back as soon as we can.");
            return;
        }
        handoffError.textContent = Object.values(data.errors || {}).flat().join(' ') || 'Please check your name and email.';
        handoffError.hidden = false;
        handoffError.focus();
    });
    handoffError.tabIndex = -1;
})();
