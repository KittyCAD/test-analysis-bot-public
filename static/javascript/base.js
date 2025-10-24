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

    // Lazy-load result details modal content
    document.querySelectorAll('[id^="details-"]').forEach(modal => {
        modal.addEventListener('show.bs.modal', function (event) {
            const modalBody = this.querySelector('.modal-body');
            if (modalBody.dataset.loaded === 'true') {
                return;
            }

            const button = event.relatedTarget;
            const resultId = button ? button.getAttribute('data-result-id') : null;

            fetch(`/projects/_result-details/${resultId}`)
                .then(response => {
                    return response.text();
                })
                .then(html => {
                    modalBody.innerHTML = html;
                    modalBody.dataset.loaded = 'true';

                    // Re-initialize copy buttons in the loaded content
                    const newCopyButtons = modalBody.querySelectorAll('.copy-btn');
                    newCopyButtons.forEach(button => {
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
                })
        });
    });
});
