
document.addEventListener("DOMContentLoaded", function () {
    const chatInput = document.getElementById("chat-input");
    const sendButton = document.getElementById("chat-send");
    const chatMessages = document.getElementById("chat-messages");

    if (!chatInput || !sendButton || !chatMessages) {
        return;
    }

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

    // Display an assistant response and an Apply button.
    function displayAssistantResponse(response) {
        const messageDiv = addMessage(
            "Pawket Assistant",
            response.message
        );

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

    function sendMessage() {
        const message = chatInput.value.trim();

        if (!message) {
            return;
        }

        addMessage("You", message);
        chatInput.value = "";

        // TEMPORARY RESPONSE FOR TESTING
        // Your teammate will replace this with a real AI response.
        const testResponse = {
            message:
                "Based on your pet's needs, I recommend " +
                "a bath and nail trimming. Would you like " +
                "me to add those services to your booking?",
            recommendations: {
                includes_stay: false,
                grooming_services: [
                    "bath",
                    "nail_trimming"
                ]
            }
        };

        displayAssistantResponse(testResponse);
    }

    sendButton.addEventListener("click", sendMessage);

    chatInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            sendMessage();
        }
    });
});
