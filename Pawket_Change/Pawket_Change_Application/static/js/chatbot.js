
document.addEventListener("DOMContentLoaded", function () {
    const chatInput = document.getElementById("chat-input");
    const sendButton = document.getElementById("chat-send");
    const chatMessages = document.getElementById("chat-messages");
    const chatbot = document.getElementById("pawket-chatbot");

    if (!chatInput || !sendButton || !chatMessages || !chatbot) {
        return;
    }

    // The booking form's CSRF token authorizes the chat requests.
    const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

    // The conversation so far, sent with each question so the assistant has context.
    const history = [];

    // Store the latest recommendations from the assistant.
    let currentRecommendations = null;

    function addMessage(sender, message) {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("mb-3");

        const senderLabel = document.createElement("strong");
        senderLabel.textContent = sender + ":";

        const messageText = document.createElement("p");
        messageText.classList.add("mb-0");
        messageText.textContent = message;

        messageDiv.appendChild(senderLabel);
        messageDiv.appendChild(messageText);

        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        return messageDiv;
    }

    // Add recommended services to the booking form.
    function applyRecommendations(recommendations) {
        if (!recommendations) {
            return;
        }

        const stayCheckbox = document.querySelector(
            'input[name="includes_stay"]'
        );

        // Add a stay only when the assistant recommends one.
        // Never remove an existing stay selection.
        if (
            recommendations.includes_stay === true &&
            stayCheckbox &&
            !stayCheckbox.checked
        ) {
            stayCheckbox.checked = true;

            stayCheckbox.dispatchEvent(
                new Event("change", { bubbles: true })
            );
        }

        // Add grooming services without removing existing ones.
        const groomingServices = recommendations.grooming_services;

        if (Array.isArray(groomingServices)) {
            groomingServices.forEach(function (service) {
                const checkboxes = document.querySelectorAll(
                    'input[name="grooming_services"]'
                );

                checkboxes.forEach(function (checkbox) {
                    if (
                        checkbox.value === service &&
                        !checkbox.checked
                    ) {
                        checkbox.checked = true;

                        checkbox.dispatchEvent(
                            new Event("change", { bubbles: true })
                        );
                    }
                });
            });
        }

        addMessage(
            "Pawket Assistant",
            "I've added my recommendations to your booking form! " +
            "You can review or change your selections below."
        );
    }

    function setField(name, value) {
        const field = document.querySelector(`[name="${name}"]`);

        if (!field || value === undefined) {
            return;
        }

        field.value = value;
        field.dispatchEvent(new Event("change", { bubbles: true }));
    }

    // Fill in the booking form from a booking the assistant prepared. The stay choice, number of dogs,
    // dates, and times are set to what the customer asked for; grooming services are only added, never
    // removed. The customer's name, contact, and dog details are left as they are.
    function applyBooking(prefill) {
        const stayCheckbox = document.querySelector('input[name="includes_stay"]');

        if (stayCheckbox && stayCheckbox.checked !== prefill.includes_stay) {
            stayCheckbox.checked = prefill.includes_stay;
            stayCheckbox.dispatchEvent(new Event("change", { bubbles: true }));
        }

        setField("number_of_pets", prefill.number_of_pets);

        (prefill.grooming_services || []).forEach(function (service) {
            const checkbox = document.querySelector(
                `input[name="grooming_services"][value="${service}"]`
            );

            if (checkbox && !checkbox.checked) {
                checkbox.checked = true;
                checkbox.dispatchEvent(new Event("change", { bubbles: true }));
            }
        });

        // Dates first: changing a date refreshes which times can be picked.
        ["check_in_date", "check_out_date", "grooming_date"].forEach(function (name) {
            setField(name, prefill[name]);
        });

        ["drop_off_time", "pickup_time", "grooming_time"].forEach(function (name) {
            setField(name, prefill[name]);
        });

        addMessage(
            "Pawket Assistant",
            "I've filled in the booking form below. Add your details and your dogs' " +
            "information, check everything, and then select Review Booking."
        );

        const firstEmpty = document.querySelector(
            'form [name="owner_name"]'
        );

        if (firstEmpty) {
            firstEmpty.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }

    // Display an assistant response, with a button to fill in the form when it prepared a booking.
    function displayAssistantResponse(response) {
        const messageDiv = addMessage(
            "Pawket Assistant",
            response.message
        );

        if (response.booking) {
            const bookingButton = document.createElement("button");
            bookingButton.type = "button";
            bookingButton.className = "btn btn-pawket btn-sm mt-2";
            bookingButton.textContent = `Fill in the booking form: ${response.booking.label}`;

            messageDiv.appendChild(bookingButton);

            bookingButton.addEventListener("click", function () {
                applyBooking(response.booking.prefill);

                bookingButton.disabled = true;
                bookingButton.textContent = "Booking form filled in";
            });
        }

        if (!response.recommendations) {
            return;
        }

        currentRecommendations = response.recommendations;

        const applyButton = document.createElement("button");
        applyButton.type = "button";
        applyButton.className = "btn btn-pawket btn-sm mt-2";
        applyButton.textContent = "Apply Recommendations";

        messageDiv.appendChild(applyButton);

        applyButton.addEventListener("click", function () {
            applyRecommendations(response.recommendations);

            applyButton.disabled = true;
            applyButton.textContent = "Recommendations Applied";
        });
    }

    async function sendMessage() {
        const message = chatInput.value.trim();

        if (!message) {
            return;
        }

        addMessage("You", message);
        history.push({ role: "user", content: message });
        chatInput.value = "";
        chatInput.disabled = true;
        sendButton.disabled = true;
        const pending = addMessage("Pawket Assistant", "Thinking…");

        let response = {
            message:
                "Sorry, something went wrong. You can send your " +
                "question to our team on the Contact Us page.",
            recommendations: null,
            booking: null
        };

        try {
            const result = await fetch(chatbot.dataset.chatUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({ messages: history })
            });
            const data = await result.json();

            if (data.reply) {
                response = {
                    message: data.reply,
                    recommendations: data.recommendations,
                    booking: data.booking
                };
            }
        } catch (error) {
            // Keep the fallback response.
        }

        pending.remove();
        history.push({ role: "assistant", content: response.message });
        displayAssistantResponse(response);

        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }

    sendButton.addEventListener("click", sendMessage);

    chatInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            sendMessage();
        }
    });
});
