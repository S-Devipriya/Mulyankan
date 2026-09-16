document.addEventListener('DOMContentLoaded', function() {
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
                    <span class="badge-warning px-2 py-1 rounded">${Object.keys(schemeData.questions || {}).length} Questions</span>
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
});