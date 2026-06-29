(function () {
    const CHAT_ENDPOINT = "/api/chat";

    function scrollToLastMessage(messagesBox) {
        messagesBox.scrollTop = messagesBox.scrollHeight;
    }

    function createMessage(text, variant) {
        const message = document.createElement("article");
        message.className = `chat-message chat-message-${variant}`;
        message.textContent = text;
        return message;
    }

    function setLoadingState(state, input, sendButton) {
        input.disabled = state;
        sendButton.disabled = state;
        sendButton.textContent = state ? "..." : "Enviar";
    }

    function extractAnswer(payload) {
        if (!payload || typeof payload !== "object") {
            return "No he podido leer la respuesta del asistente.";
        }

        return payload.answer || "No he podido generar una respuesta.";
    }

    async function sendMessage(message) {
        const response = await fetch(CHAT_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body: JSON.stringify({ message }),
        });

        let payload = null;

        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }

        if (!response.ok) {
            throw new Error(extractAnswer(payload));
        }

        return extractAnswer(payload);
    }

    function setupChatbot() {
        const widget = document.querySelector(".chatbot-widget");

        if (!widget) {
            return;
        }

        const panel = widget.querySelector("#chatbot-panel");
        const toggleButton = widget.querySelector("[data-chatbot-toggle]");
        const closeButton = widget.querySelector("[data-chatbot-close]");
        const form = widget.querySelector("[data-chatbot-form]");
        const input = widget.querySelector("[data-chatbot-input]");
        const sendButton = widget.querySelector("[data-chatbot-send]");
        const messagesBox = widget.querySelector("[data-chatbot-messages]");

        if (!panel || !toggleButton || !form || !input || !sendButton || !messagesBox) {
            return;
        }

        function openChat() {
            panel.hidden = false;
            toggleButton.setAttribute("aria-expanded", "true");
            toggleButton.setAttribute("aria-label", "Cerrar chat");
            window.setTimeout(function () {
                input.focus();
                scrollToLastMessage(messagesBox);
            }, 0);
        }

        function closeChat() {
            panel.hidden = true;
            toggleButton.setAttribute("aria-expanded", "false");
            toggleButton.setAttribute("aria-label", "Abrir chat");
            toggleButton.focus();
        }

        function toggleChat() {
            if (panel.hidden) {
                openChat();
            } else {
                closeChat();
            }
        }

        async function handleSubmit(event) {
            event.preventDefault();

            if (sendButton.disabled) {
                return;
            }

            const message = input.value.trim();

            if (!message) {
                input.focus();
                return;
            }

            messagesBox.appendChild(createMessage(message, "user"));
            input.value = "";
            input.style.height = "";

            const loadingMessage = createMessage("Pensando...", "bot");
            loadingMessage.classList.add("chat-message-loading");
            messagesBox.appendChild(loadingMessage);
            scrollToLastMessage(messagesBox);
            setLoadingState(true, input, sendButton);

            try {
                const answer = await sendMessage(message);
                loadingMessage.remove();
                messagesBox.appendChild(createMessage(answer, "bot"));
            } catch (error) {
                loadingMessage.remove();
                messagesBox.appendChild(
                    createMessage("Ahora mismo no puedo responder. Prueba de nuevo en unos segundos.", "bot")
                );
            } finally {
                setLoadingState(false, input, sendButton);
                input.focus();
                scrollToLastMessage(messagesBox);
            }
        }

        function resizeInput() {
            input.style.height = "";
            input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
        }

        toggleButton.addEventListener("click", toggleChat);

        if (closeButton) {
            closeButton.addEventListener("click", closeChat);
        }

        form.addEventListener("submit", handleSubmit);

        input.addEventListener("input", resizeInput);

        input.addEventListener("keydown", function (event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                form.requestSubmit();
            }
        });
    }

    document.addEventListener("DOMContentLoaded", setupChatbot);
}());
