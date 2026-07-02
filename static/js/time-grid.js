(function () {
    'use strict';

    const HOUR_START = 6;
    const HOUR_END = 17;
    const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    const page = document.getElementById('timeGridPage');
    if (!page) {
        return;
    }

    const weekStart = page.dataset.weekStart;
    const gridEl = document.getElementById('timeGrid');
    const projectSearchEl = document.getElementById('timeGridProjectSearch');
    const projectListEl = document.getElementById('timeGridProjectList');
    const selectedProjectEl = document.getElementById('timeGridSelectedProject');
    const notesEl = document.getElementById('timeGridNotes');
    const submitBtn = document.getElementById('timeGridSubmitBtn');
    const clearBtn = document.getElementById('timeGridClearBtn');
    const mergePreviewEl = document.getElementById('timeGridMergePreview');
    const weekTotalEl = document.getElementById('weekTotalLabel');

    function focusProjectSearch() {
        if (projectSearchEl) {
            projectSearchEl.focus({ preventScroll: true });
        }
    }

    function scheduleFocusProjectSearch() {
        requestAnimationFrame(() => {
            requestAnimationFrame(focusProjectSearch);
        });
    }

    function focusNotes() {
        if (notesEl) {
            notesEl.focus({ preventScroll: true });
        }
    }

    function scheduleFocusNotes() {
        requestAnimationFrame(() => {
            requestAnimationFrame(focusNotes);
        });
    }

    function updateFlowHighlights() {
        const notesOk = notesEl.value.trim().length > 0;
        projectSearchEl.classList.toggle('time-grid-flow-highlight', !selectedProject);
        notesEl.classList.toggle('time-grid-flow-highlight', Boolean(selectedProject) && !notesOk);
    }

    let allProjects = [];
    let selectedProject = null;
    let weekData = null;
    const pendingSlots = new Set();
    const lockedKeys = new Set();

    function pad(n) {
        return String(n).padStart(2, '0');
    }

    function dateForDayIndex(dayIndex) {
        const parts = weekStart.split('-').map(Number);
        const dt = new Date(parts[0], parts[1] - 1, parts[2] + dayIndex);
        return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
    }

    function slotKey(dateStr, hour) {
        return `${dateStr}|${hour}`;
    }

    function parseSlotKey(key) {
        const [dateStr, hour] = key.split('|');
        return { date: dateStr, hour: parseInt(hour, 10) };
    }

    function hourLabel(hour) {
        if (hour === 12) {
            return '12–1p';
        }
        if (hour < 12) {
            return `${hour}–${hour + 1}a`;
        }
        return `${hour - 12}–${hour - 11}p`;
    }

    function computeMergedRanges(slots) {
        const byDate = {};
        slots.forEach((key) => {
            const { date, hour } = parseSlotKey(key);
            if (!byDate[date]) {
                byDate[date] = new Set();
            }
            byDate[date].add(hour);
        });

        const ranges = [];
        Object.keys(byDate).sort().forEach((date) => {
            const hours = Array.from(byDate[date]).sort((a, b) => a - b);
            if (!hours.length) {
                return;
            }
            let rangeStart = hours[0];
            let prev = hours[0];
            let count = 1;
            for (let i = 1; i < hours.length; i += 1) {
                const hour = hours[i];
                if (hour === prev + 1) {
                    count += 1;
                    prev = hour;
                } else {
                    ranges.push({ date, start_hour: rangeStart, hours: count });
                    rangeStart = hour;
                    prev = hour;
                    count = 1;
                }
            }
            ranges.push({ date, start_hour: rangeStart, hours: count });
        });
        return ranges;
    }

    function formatRangeSummary(ranges) {
        if (!ranges.length) {
            return '';
        }
        const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const parts = ranges.map((r) => {
            const d = new Date(r.date + 'T12:00:00');
            const dayIndex = (d.getDay() + 6) % 7;
            const endHour = r.start_hour + r.hours;
            return `${dayNames[dayIndex]} ${hourLabel(r.start_hour).split('–')[0]}–${hourLabel(endHour - 1).split('–')[1]}`;
        });
        return `Will create ${ranges.length} ${ranges.length === 1 ? 'entry' : 'entries'}: ${parts.join('; ')}`;
    }

    function updateSubmitState() {
        const notesOk = notesEl.value.trim().length > 0;
        const hasPending = pendingSlots.size > 0;
        const canSubmit = Boolean(selectedProject) && notesOk && hasPending;

        submitBtn.disabled = !canSubmit;
        clearBtn.disabled = !hasPending;

        if (hasPending && selectedProject && notesOk) {
            const ranges = computeMergedRanges(Array.from(pendingSlots));
            const totalHours = pendingSlots.size;
            submitBtn.textContent = `Submit ${totalHours} ${totalHours === 1 ? 'hour' : 'hours'} (${ranges.length} ${ranges.length === 1 ? 'entry' : 'entries'})`;
            mergePreviewEl.textContent = formatRangeSummary(ranges);
        } else {
            submitBtn.textContent = 'Submit';
            mergePreviewEl.textContent = '';
        }

        updateFlowHighlights();
    }

    function resetEntryForm() {
        selectedProject = null;
        projectSearchEl.value = '';
        notesEl.value = '';
        selectedProjectEl.textContent = 'No project selected';
        filterProjects();
        renderGrid();
        updateSubmitState();
        scheduleFocusProjectSearch();
    }

    function filterProjects() {
        const query = projectSearchEl.value.trim().toLowerCase();
        let filtered = allProjects;
        if (query) {
            filtered = allProjects.filter((p) =>
                p.name.toLowerCase().includes(query) ||
                (p.client_name || '').toLowerCase().includes(query) ||
                (p.display_name || '').toLowerCase().includes(query)
            );
        }
        const nonArchived = filtered.filter((p) => p.status !== 'Archived');
        const archived = query ? filtered.filter((p) => p.status === 'Archived') : [];
        renderProjectList(nonArchived, archived);
    }

    function renderProjectList(nonArchived, archived) {
        if (!nonArchived.length && !archived.length) {
            projectListEl.innerHTML = '<div class="text-muted small py-2 px-2">No projects found.</div>';
            return;
        }

        let html = '';
        nonArchived.forEach((p) => {
            html += projectItemHtml(p);
        });
        if (archived.length) {
            html += '<div class="text-muted small px-2 py-1 border-top">Archived</div>';
            archived.forEach((p) => {
                html += projectItemHtml(p);
            });
        }
        projectListEl.innerHTML = html;

        projectListEl.querySelectorAll('.time-grid-project-item').forEach((el) => {
            el.addEventListener('click', () => {
                const id = parseInt(el.dataset.projectId, 10);
                selectedProject = allProjects.find((p) => p.id === id) || null;
                projectListEl.querySelectorAll('.time-grid-project-item').forEach((item) => {
                    item.classList.toggle('selected', parseInt(item.dataset.projectId, 10) === id);
                });
                if (selectedProject) {
                    selectedProjectEl.textContent = `Selected: ${selectedProject.display_name || selectedProject.name}`;
                } else {
                    selectedProjectEl.textContent = 'No project selected';
                }
                renderGrid();
                updateSubmitState();
                if (selectedProject) {
                    scheduleFocusNotes();
                }
            });
        });
    }

    function projectItemHtml(project) {
        const selected = selectedProject && selectedProject.id === project.id ? ' selected' : '';
        return (
            `<div class="time-grid-project-item${selected}" data-project-id="${project.id}">` +
            `<div class="project-name">${escapeHtml(project.name)}</div>` +
            `<div class="client-name">${escapeHtml(project.client_name || '')}</div>` +
            '</div>'
        );
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function buildGridSkeleton() {
        let html = '<div class="time-grid-hour-label"></div>';
        for (let d = 0; d < 7; d += 1) {
            const dateStr = dateForDayIndex(d);
            const labelDate = new Date(dateStr + 'T12:00:00');
            html += `<div class="time-grid-header">${DAY_LABELS[d]}<br><span class="text-muted fw-normal">${labelDate.getMonth() + 1}/${labelDate.getDate()}</span></div>`;
        }

        for (let hour = HOUR_START; hour <= HOUR_END; hour += 1) {
            html += `<div class="time-grid-hour-label">${hourLabel(hour)}</div>`;
            for (let dayIndex = 0; dayIndex < 7; dayIndex += 1) {
                const dateStr = dateForDayIndex(dayIndex);
                const key = slotKey(dateStr, hour);
                html += `<div class="time-grid-cell disabled" data-key="${key}" data-date="${dateStr}" data-hour="${hour}" data-day="${dayIndex}"></div>`;
            }
        }

        html += '<div class="time-grid-section-label">Other hours</div>';
        for (let d = 0; d < 7; d += 1) {
            if (d === 0) {
                html += '<div class="time-grid-hour-label time-grid-other-row">Off-grid</div>';
            }
            html += `<div class="time-grid-cell disabled time-grid-other-row" data-other-day="${d}" id="otherDay${d}"></div>`;
        }

        html += '<div class="time-grid-hour-label">Day total</div>';
        for (let d = 0; d < 7; d += 1) {
            html += `<div class="time-grid-total-cell" id="dayTotal${d}">0.0</div>`;
        }

        gridEl.innerHTML = html;

        gridEl.querySelectorAll('.time-grid-cell[data-key]').forEach((cell) => {
            cell.addEventListener('click', () => onCellClick(cell));
        });
    }

    function onCellClick(cell) {
        if (cell.classList.contains('locked') || cell.classList.contains('disabled')) {
            return;
        }
        const key = cell.dataset.key;
        if (pendingSlots.has(key)) {
            pendingSlots.delete(key);
            cell.classList.remove('pending');
            cell.textContent = '';
        } else {
            pendingSlots.add(key);
            cell.classList.add('pending');
            if (selectedProject) {
                const label = selectedProject.client_name
                    ? `${selectedProject.client_name} - ${selectedProject.name}`
                    : selectedProject.name;
                cell.innerHTML = `<span class="cell-label">${escapeHtml(label)}</span>`;
            }
        }
        updateSubmitState();
    }

    function renderGrid() {
        lockedKeys.clear();
        const lockedByKey = {};
        if (weekData && weekData.cells) {
            weekData.cells.forEach((cellInfo) => {
                const dateStr = dateForDayIndex(cellInfo.day_index);
                const key = slotKey(dateStr, cellInfo.hour);
                lockedKeys.add(key);
                lockedByKey[key] = cellInfo;
            });
        }

        gridEl.querySelectorAll('.time-grid-cell[data-key]').forEach((cell) => {
            const key = cell.dataset.key;
            cell.className = 'time-grid-cell';
            cell.textContent = '';
            cell.removeAttribute('title');

            if (lockedByKey[key]) {
                if (pendingSlots.has(key)) {
                    pendingSlots.delete(key);
                }
                const cellInfo = lockedByKey[key];
                cell.classList.add('locked');
                const label = cellInfo.client_name
                    ? `${cellInfo.client_name} - ${cellInfo.project_name}`
                    : cellInfo.project_name;
                cell.innerHTML = `<span class="cell-label">${escapeHtml(label)}</span>`;
                cell.title = label;
                return;
            }

            if (pendingSlots.has(key)) {
                cell.classList.add('pending');
                if (selectedProject) {
                    const label = selectedProject.client_name
                        ? `${selectedProject.client_name} - ${selectedProject.name}`
                        : selectedProject.name;
                    cell.innerHTML = `<span class="cell-label">${escapeHtml(label)}</span>`;
                }
                return;
            }

            if (selectedProject) {
                cell.classList.add('selectable');
            } else {
                cell.classList.add('disabled');
            }
        });

        for (let d = 0; d < 7; d += 1) {
            const otherEl = document.getElementById(`otherDay${d}`);
            const totalEl = document.getElementById(`dayTotal${d}`);
            if (otherEl) {
                const items = (weekData && weekData.other_by_day && weekData.other_by_day[d]) || [];
                if (!items.length) {
                    otherEl.className = 'time-grid-cell disabled time-grid-other-row';
                    otherEl.textContent = '—';
                } else {
                    otherEl.className = 'time-grid-cell locked time-grid-other-row';
                    otherEl.innerHTML = items.map((item) =>
                        `<div class="time-grid-other-item">${escapeHtml(item.label)} (${item.hours}h)</div>`
                    ).join('');
                }
            }
            if (totalEl && weekData && weekData.day_totals) {
                totalEl.textContent = Number(weekData.day_totals[d] || 0).toFixed(1);
            }
        }

        if (weekData) {
            weekTotalEl.textContent = `Week total: ${Number(weekData.week_total_hours || 0).toFixed(1)} hrs`;
        }

        updateSubmitState();
    }

    async function loadProjects() {
        try {
            const response = await fetch('/api/projects_for_logging');
            const data = await response.json();
            allProjects = data.projects || [];
            filterProjects();
        } catch (err) {
            console.error(err);
            projectListEl.innerHTML = '<div class="text-danger small py-2 px-2">Failed to load projects.</div>';
        }
    }

    async function loadWeek() {
        try {
            const response = await fetch(`/api/time_grid/week?week=${encodeURIComponent(weekStart)}`);
            if (!response.ok) {
                throw new Error('Failed to load week');
            }
            weekData = await response.json();
            renderGrid();
        } catch (err) {
            console.error(err);
            weekTotalEl.textContent = 'Week total: error loading data';
        }
    }

    async function submitPending() {
        if (submitBtn.disabled) {
            return;
        }
        submitBtn.disabled = true;
        const slots = Array.from(pendingSlots).map(parseSlotKey);
        try {
            const response = await fetch('/api/time_grid/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: selectedProject.id,
                    slots,
                    notes: notesEl.value.trim(),
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                alert(data.error || 'Failed to save time logs.');
                updateSubmitState();
                return;
            }
            pendingSlots.clear();
            await loadWeek();
            resetEntryForm();
        } catch (err) {
            console.error(err);
            alert('Error saving time logs.');
            updateSubmitState();
        }
    }

    projectSearchEl.addEventListener('input', filterProjects);
    notesEl.addEventListener('input', updateSubmitState);
    submitBtn.addEventListener('click', submitPending);
    clearBtn.addEventListener('click', () => {
        pendingSlots.clear();
        renderGrid();
    });

    buildGridSkeleton();
    loadProjects();
    loadWeek();
    updateFlowHighlights();

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scheduleFocusProjectSearch, { once: true });
    } else {
        scheduleFocusProjectSearch();
    }
    window.addEventListener('load', scheduleFocusProjectSearch, { once: true });
    window.addEventListener('pageshow', scheduleFocusProjectSearch);
})();
