document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('storyForm');
    const generateBtn = document.getElementById('generateBtn');
    const spinner = generateBtn.querySelector('.spinner-border');

    if (form) {
        form.addEventListener('submit', function() {
            // Disable button and show spinner
            generateBtn.disabled = true;
            spinner.classList.remove('d-none');
            generateBtn.textContent = ' Generating Story...';
            generateBtn.prepend(spinner);
        });
    }
});
