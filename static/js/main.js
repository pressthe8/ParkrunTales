document.addEventListener('DOMContentLoaded', function() {
    // Only try to access the form elements if we're on the form page
    const form = document.getElementById('storyForm');
    if (form) {
        const generateBtn = document.getElementById('generateBtn');
        const spinner = generateBtn.querySelector('.spinner-border');

        form.addEventListener('submit', function() {
            // Disable button and show spinner
            generateBtn.disabled = true;
            spinner.classList.remove('d-none');
            generateBtn.textContent = ' Generating Story...';
            generateBtn.prepend(spinner);
        });
    }
});