function initToasts() {
    const toastElements = document.querySelectorAll('.toast');
    toastElements.forEach(toastEl => {
        try {
            const toast = new bootstrap.Toast(toastEl);
            toast.show();
        } catch (e) {
            console.error('Toast initialization error:', e);
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initToasts();

    const evaluatorSelect = document.getElementById('evaluatorSelect');
    const courseCheckboxes = document.querySelectorAll('input[name="course_ids"]');

    if (evaluatorSelect) {
        const rawMapData = evaluatorSelect.getAttribute('data-expertise-map');
        let expertiseMap = {};

        try {
            expertiseMap = JSON.parse(rawMapData || '{}');
        } catch (e) {
            console.error('Failed to parse evaluator expertise map JSON:', e);
        }

        evaluatorSelect.addEventListener('change', function() {
            const selectedEvaluatorId = parseInt(this.value, 10);
            const assignedCourseIds = expertiseMap[selectedEvaluatorId] || [];

            courseCheckboxes.forEach(checkbox => {
                const courseId = parseInt(checkbox.value, 10);
                checkbox.checked = assignedCourseIds.includes(courseId);
            });
        });
    }

    const schemeSelect = document.getElementById('schemeCourseSelect');
    const schemeContainer = document.getElementById('schemeDetailContainer');

    if (schemeSelect && schemeContainer) {
        const rawSchemes = schemeSelect.getAttribute('data-schemes');
        let schemesMap = {};

        try {
            schemesMap = JSON.parse(rawSchemes || '{}');
        } catch (e) {
            console.error('Error parsing schemes JSON:', e);
        }

        schemeSelect.addEventListener('change', function() {
            const selectedCode = this.value;
            const schemeData = schemesMap[selectedCode];

            if (!schemeData) {
                schemeContainer.innerHTML = `
                    <div class="empty-state-box">
                        <span class="empty-text">No scheme found for ${selectedCode}.</span>
                    </div>`;
                return;
            }

            let questionsHtml = '';
            for (const [qNum, qDetails] of Object.entries(schemeData.questions || {})) {
                questionsHtml += `
                    <tr>
                        <td class="cell-primary">Q${qNum}</td>
                        <td class="cell-secondary">${qDetails.max_marks}</td>
                        <td class="cell-secondary">${qDetails.question_text}</td>
                    </tr>`;
            }

            schemeContainer.innerHTML = `
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <span class="user-msg">Total Marks: <strong>${schemeData.total_marks}</strong></span>
                    <span class="badge-pending px-2 py-1 rounded">${Object.keys(schemeData.questions || {}).length} Questions</span>
                </div>
                <div class="table-responsive">
                    <table class="table dashboard-table align-middle">
                        <thead>
                            <tr>
                                <th scope="col" style="width: 15%;">Q#</th>
                                <th scope="col" style="width: 20%;">Max Marks</th>
                                <th scope="col">Question Text</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${questionsHtml}
                        </tbody>
                    </table>
                </div>`;
        });
    }

    const questionsContainer = document.getElementById('questionsContainer');
    const addQuestionRowBtn = document.getElementById('addQuestionRowBtn');

    if (questionsContainer && addQuestionRowBtn) {
        addQuestionRowBtn.addEventListener('click', function() {
            const rowCount = questionsContainer.querySelectorAll('.question-row').length + 1;
            const newRow = document.createElement('div');
            newRow.className = 'question-row border rounded bg-white p-2 mb-2';
            newRow.innerHTML = `
                <div class="row g-2 mb-2">
                    <div class="col-4">
                        <input type="text" name="question_keys[]" class="form-control form-control-sm" placeholder="e.g. ${rowCount}" required>
                    </div>
                    <div class="col-6">
                        <input type="number" step="0.5" name="max_marks_list[]" class="form-control form-control-sm" placeholder="Marks" required>
                    </div>
                    <div class="col-2 d-flex align-items-end">
                        <button type="button" class="btn btn-sm btn-danger w-100 remove-q-btn">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                </div>
                <div>
                    <input type="text" name="question_texts[]" class="form-control form-control-sm" placeholder="Enter question statement..." required>
                </div>
            `;

            questionsContainer.appendChild(newRow);
            updateRemoveButtons();
        });

        questionsContainer.addEventListener('click', function(e) {
            if (e.target.closest('.remove-q-btn')) {
                const row = e.target.closest('.question-row');
                if (questionsContainer.querySelectorAll('.question-row').length > 1) {
                    row.remove();
                    updateRemoveButtons();
                }
            }
        });

        function updateRemoveButtons() {
            const rows = questionsContainer.querySelectorAll('.question-row');
            rows.forEach(row => {
                const btn = row.querySelector('.remove-q-btn');
                if (btn) btn.disabled = (rows.length === 1);
            });
        }
    }

    // Results Tab: Search & Sort Logic
    const searchInput = document.getElementById('resultsSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase().trim();
            const rows = document.querySelectorAll('.result-row');

            rows.forEach(row => {
                const enrollment = row.querySelector('.enrollment-cell')?.textContent.toLowerCase() || '';
                const course = row.querySelector('.course-cell')?.textContent.toLowerCase() || '';
                
                if (enrollment.includes(query) || course.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // Sorting by Score
    document.querySelectorAll('.sort-score-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const batchId = this.getAttribute('data-batch-id');
            const currentOrder = this.getAttribute('data-order');
            const nextOrder = currentOrder === 'desc' ? 'asc' : 'desc';
            this.setAttribute('data-order', nextOrder);

            const icon = this.querySelector('i');
            if (icon) {
                icon.className = nextOrder === 'desc' ? 'bi bi-sort-numeric-down' : 'bi bi-sort-numeric-up-alt';
            }

            const table = document.getElementById(`table-batch-${batchId}`);
            if (!table) return;

            const tbody = table.querySelector('.batch-table-body');
            const rows = Array.from(tbody.querySelectorAll('.result-row'));

            rows.sort((a, b) => {
                const valA = parseFloat(a.querySelector('.score-cell')?.textContent.trim()) || -1;
                const valB = parseFloat(b.querySelector('.score-cell')?.textContent.trim()) || -1;
                return nextOrder === 'desc' ? valB - valA : valA - valB;
            });

            rows.forEach(row => tbody.appendChild(row));
        });
    });

    const globalSearchInput = document.getElementById('globalResultsSearchInput');
    if (globalSearchInput) {
        globalSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase().trim();
            const rows = document.querySelectorAll('.global-result-row');

            rows.forEach(row => {
                const textContent = row.textContent.toLowerCase();
                if (textContent.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
});