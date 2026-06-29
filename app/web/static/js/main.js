(function () {
    function setupSearchForm(form) {
        const titleInput = form.querySelector(".js-title-input");
        const yearInput = form.querySelector(".js-year-input");
        const submitButton = form.querySelector(".js-submit-button");
        const errorBox = form.querySelector(".js-form-error");

        if (!titleInput || !submitButton) {
            return;
        }

        function updateButtonState() {
            submitButton.disabled = titleInput.value.trim().length === 0;
        }

        titleInput.addEventListener("input", updateButtonState);
        updateButtonState();

        form.addEventListener("submit", function (event) {
            const cleanTitle = titleInput.value.trim();

            if (!cleanTitle) {
                event.preventDefault();
                titleInput.focus();
                if (errorBox) {
                    errorBox.textContent = "Introduce un titulo antes de buscar.";
                }
                updateButtonState();
                return;
            }

            titleInput.value = cleanTitle;

            if (yearInput && yearInput.value.trim() === "") {
                yearInput.disabled = true;
            }

            if (errorBox) {
                errorBox.textContent = "";
            }

            submitButton.disabled = true;
            submitButton.textContent = "Buscando...";
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".js-search-form").forEach(setupSearchForm);
    });
}());
