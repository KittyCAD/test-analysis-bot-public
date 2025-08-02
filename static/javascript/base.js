// Base JavaScript functionality for the application

document.addEventListener('DOMContentLoaded', function () {

    // Copy button functionality
    const copyButtons = document.querySelectorAll('.copy-btn');
    copyButtons.forEach(button => {
        button.addEventListener('click', function () {
            const text = this.getAttribute('data-clipboard-text');
            navigator.clipboard.writeText(text).then(() => {
                const originalIcon = this.innerHTML;
                this.innerHTML = '<i class="fa-solid fa-check"></i>';
                setTimeout(() => {
                    this.innerHTML = originalIcon;
                }, 1000);
            });
        });
    });
});
