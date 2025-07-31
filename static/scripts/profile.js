    const undoModal = document.getElementById('undoModal');
    const passwordModal = document.getElementById('passwordModal');
    const modalOverlay = document.getElementById('modalOverlay');

    document.getElementById('undoButton').addEventListener('click', () => {
        showModal(undoModal);
    });

    document.getElementById('passwordButton').addEventListener('click', () => {
        showModal(passwordModal);
    });

    window.addEventListener('click', function(event) {
        if (event.target === modalOverlay) {
            closeModal();
        }
    });

    function showModal(modal) {
        modal.style.display = 'block';
        modalOverlay.style.display = 'block';
    }

    function closeModal() {
        undoModal.style.display = 'none';
        passwordModal.style.display = 'none';
        modalOverlay.style.display = 'none';
    }