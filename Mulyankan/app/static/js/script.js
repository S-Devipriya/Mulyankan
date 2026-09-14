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
});