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
    const currentUserId = Number(page.dataset.currentUserId);
    let selectedUserId = Number(page.dataset.selectedUserId || currentUserId);
    const gridEl = document.getElementById('timeGrid');
    const projectSearchEl = document.getElementById('timeGridProjectSearch');
    const projectListEl = document.getElementById('timeGridProjectList');
    const selectedProjectEl = document.getElementById('timeGridSelectedProject');
    const notesEl = document.getElementById('timeGridNotes');
    const submitBtn = document.getElementById('timeGridSubmitBtn');
    const clearBtn = document.getElementById('timeGridClearBtn');
    const mergePreviewEl = document.getElementById('timeGridMergePreview');
    const breakdownBodyEl = document.getElementById('timeGridBreakdownBody');
    const breakdownWeekTotalEl = document.getElementById('timeGridBreakdownWeekTotal');
    const breakdownEmptyEl = document.getElementById('timeGridBreakdownEmpty');
    const breakdownContentEl = document.getElementById('timeGridBreakdownContent');
    const inputCardEl = document.getElementById('timeGridInputCard');
    const userSelectEl = document.getElementById('timeGridUserSelect');

    const BAR_COLORS = [
        '#0d6efd', '#198754', '#fd7e14', '#6f42c1', '#dc3545',
        '#20c997', '#ffc107', '#6610f2', '#0dcaf0', '#6c757d',
    ];

    function isViewingSelf() {
        return selectedUserId === currentUserId;
    }

    function syncInputVisibility() {
        if (!inputCardEl) {
            return;
        }
        const show = isViewingSelf();
        inputCardEl.hidden = !show;
        if (!show) {
            selectedProject = null;
            pendingSlots.clear();
            if (notesEl) {
                notesEl.value = '';
            }
            if (selectedProjectEl) {
                selectedProjectEl.textContent = 'No project selected';
            }
            if (projectListEl) {
                projectListEl.querySelectorAll('.time-grid-project-item').forEach((item) => {
                    item.classList.remove('selected');
                });
            }
        }
        updateFlowHighlights();
        updateSubmitState();
    }

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
        if (!isViewingSelf() || !projectSearchEl || !notesEl) {
            if (projectSearchEl) {
                projectSearchEl.classList.remove('time-grid-flow-highlight');
            }
            if (notesEl) {
                notesEl.classList.remove('time-grid-flow-highlight');
            }
            return;
        }
        const notesOk = notesEl.value.trim().length > 0;
        projectSearchEl.classList.toggle('time-grid-flow-highlight', !selectedProject);
        notesEl.classList.toggle('time-grid-flow-highlight', Boolean(selectedProject) && !notesOk);
    }

    function updateWeekNavLinks() {
        document.querySelectorAll('a.btn[href*="time-grid"]').forEach((link) => {
            try {
                const url = new URL(link.href, window.location.origin);
                if (!url.pathname.includes('time-grid')) {
                    return;
                }
                url.searchParams.set('user', String(selectedUserId));
                link.href = url.pathname + url.search;
            } catch (err) {
                // ignore malformed hrefs
            }
        });
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

    function projectColorMap() {
        const map = {};
        const rows = (weekData && weekData.project_breakdown) || [];
        rows.forEach((row, index) => {
            const key = row.project_id == null ? 'null' : String(row.project_id);
            map[key] = BAR_COLORS[index % BAR_COLORS.length];
        });
        return map;
    }

    function colorForProjectId(projectId, colorMap) {
        const key = projectId == null ? 'null' : String(projectId);
        if (colorMap[key]) {
            return colorMap[key];
        }
        // Stable fallback for projects not yet in this week's breakdown.
        const n = projectId == null ? 0 : Number(projectId) || 0;
        return BAR_COLORS[Math.abs(n) % BAR_COLORS.length];
    }

    function clearCellOutline(cell) {
        cell.style.borderColor = '';
        cell.style.borderWidth = '';
        cell.style.backgroundColor = '';
    }

    function applyCellOutline(cell, color) {
        if (!color) {
            cell.removeAttribute('data-outline-color');
            clearCellOutline(cell);
            return;
        }
        cell.dataset.outlineColor = color;
        cell.style.borderColor = color;
        cell.style.borderWidth = '2px';
        cell.style.backgroundColor = `${color}14`;
    }

    function projectKey(projectId) {
        return projectId == null || projectId === '' ? 'null' : String(projectId);
    }

    function setGridProjectHighlight(focusProjectId) {
        const focusKey = focusProjectId === undefined ? null : projectKey(focusProjectId);
        gridEl.querySelectorAll('.time-grid-cell[data-key]').forEach((cell) => {
            const cellProject = cell.dataset.projectId;
            const savedColor = cell.dataset.outlineColor;
            if (!savedColor) {
                return;
            }
            if (focusKey === null || cellProject === focusKey) {
                cell.style.borderColor = savedColor;
                cell.style.borderWidth = '2px';
                cell.style.backgroundColor = `${savedColor}14`;
                cell.classList.remove('time-grid-cell-dimmed');
            } else {
                clearCellOutline(cell);
                cell.classList.add('time-grid-cell-dimmed');
            }
        });
    }

    function clearGridProjectHighlight() {
        gridEl.querySelectorAll('.time-grid-cell[data-key]').forEach((cell) => {
            cell.classList.remove('time-grid-cell-dimmed');
            const savedColor = cell.dataset.outlineColor;
            if (savedColor) {
                cell.style.borderColor = savedColor;
                cell.style.borderWidth = '2px';
                cell.style.backgroundColor = `${savedColor}14`;
            }
        });
    }

    function onCellClick(cell) {
        if (!isViewingSelf()) {
            return;
        }
        if (cell.classList.contains('locked') || cell.classList.contains('disabled')) {
            return;
        }
        const key = cell.dataset.key;
        const colorMap = projectColorMap();
        if (pendingSlots.has(key)) {
            pendingSlots.delete(key);
            cell.classList.remove('pending');
            cell.textContent = '';
            clearCellOutline(cell);
        } else {
            pendingSlots.add(key);
            cell.classList.add('pending');
            if (selectedProject) {
                const label = selectedProject.client_name
                    ? `${selectedProject.client_name} - ${selectedProject.name}`
                    : selectedProject.name;
                cell.innerHTML = `<span class="cell-label">${escapeHtml(label)}</span>`;
                applyCellOutline(cell, colorForProjectId(selectedProject.id, colorMap));
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

        const colorMap = projectColorMap();
        const canSelect = isViewingSelf() && selectedProject;

        gridEl.querySelectorAll('.time-grid-cell[data-key]').forEach((cell) => {
            const key = cell.dataset.key;
            cell.className = 'time-grid-cell';
            cell.textContent = '';
            cell.removeAttribute('title');
            cell.removeAttribute('data-project-id');
            cell.removeAttribute('data-outline-color');
            cell.classList.remove('time-grid-cell-dimmed');
            clearCellOutline(cell);

            if (lockedByKey[key]) {
                if (pendingSlots.has(key)) {
                    pendingSlots.delete(key);
                }
                const cellInfo = lockedByKey[key];
                cell.classList.add('locked');
                cell.dataset.projectId = projectKey(cellInfo.project_id);
                const label = cellInfo.client_name
                    ? `${cellInfo.client_name} - ${cellInfo.project_name}`
                    : cellInfo.project_name;
                cell.innerHTML = `<span class="cell-label">${escapeHtml(label)}</span>`;
                cell.title = label;
                applyCellOutline(cell, colorForProjectId(cellInfo.project_id, colorMap));
                return;
            }

            if (pendingSlots.has(key) && isViewingSelf()) {
                cell.classList.add('pending');
                if (selectedProject) {
                    cell.dataset.projectId = projectKey(selectedProject.id);
                    const label = selectedProject.client_name
                        ? `${selectedProject.client_name} - ${selectedProject.name}`
                        : selectedProject.name;
                    cell.innerHTML = `<span class="cell-label">${escapeHtml(label)}</span>`;
                    applyCellOutline(cell, colorForProjectId(selectedProject.id, colorMap));
                }
                return;
            }

            cell.removeAttribute('data-project-id');
            cell.removeAttribute('data-outline-color');

            if (canSelect) {
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

        renderBreakdown();
        updateSubmitState();
    }

    function renderBreakdown() {
        if (!breakdownBodyEl || !breakdownContentEl || !breakdownEmptyEl) {
            return;
        }

        const rows = (weekData && weekData.project_breakdown) || [];
        const weekTotal = Number((weekData && weekData.week_total_hours) || 0);

        if (!rows.length || weekTotal <= 0) {
            breakdownEmptyEl.classList.remove('d-none');
            breakdownContentEl.classList.add('d-none');
            breakdownBodyEl.innerHTML = '';
            if (breakdownWeekTotalEl) {
                breakdownWeekTotalEl.innerHTML = '<strong>0.0%</strong> (0.0 hrs)';
            }
            return;
        }

        breakdownEmptyEl.classList.add('d-none');
        breakdownContentEl.classList.remove('d-none');

        breakdownBodyEl.innerHTML = rows.map((row, index) => {
            const pct = Math.max(0, Math.min(100, Number(row.weekly_percent || 0)));
            const thisWeek = Number(row.weekly_hours || 0);
            const lastWeek = Number(row.last_week_hours || 0);
            const lastWeekPct = Math.max(0, Math.min(100, Number(row.last_week_percent || 0)));
            const allTime = Number(row.all_time_hours || 0);
            const color = BAR_COLORS[index % BAR_COLORS.length];
            const rowProjectKey = projectKey(row.project_id);
            return (
                `<tr data-project-id="${escapeHtml(rowProjectKey)}">` +
                `<td class="time-grid-breakdown-bar-col">` +
                `<span class="time-grid-breakdown-bar-track" title="${pct.toFixed(1)}% of week">` +
                `<span class="time-grid-breakdown-bar-fill" style="width:${pct}%;background:${color}"></span>` +
                `</span>` +
                `</td>` +
                `<td>${escapeHtml(row.client_name || '—')}</td>` +
                `<td>${escapeHtml(row.project_name || '—')}</td>` +
                `<td class="text-end"><strong>${pct.toFixed(1)}%</strong> (${thisWeek.toFixed(1)} hrs)</td>` +
                `<td class="text-end"><strong>${lastWeekPct.toFixed(1)}%</strong> (${lastWeek.toFixed(1)} hrs)</td>` +
                `<td class="text-end">${allTime.toFixed(1)} hrs</td>` +
                `</tr>`
            );
        }).join('');

        breakdownBodyEl.querySelectorAll('tr[data-project-id]').forEach((rowEl) => {
            rowEl.addEventListener('mouseenter', () => {
                setGridProjectHighlight(rowEl.dataset.projectId);
            });
            rowEl.addEventListener('mouseleave', () => {
                clearGridProjectHighlight();
            });
        });

        if (breakdownWeekTotalEl) {
            breakdownWeekTotalEl.innerHTML = `<strong>100%</strong> (${weekTotal.toFixed(1)} hrs)`;
        }
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
            const params = new URLSearchParams({
                week: weekStart,
                user: String(selectedUserId),
            });
            const response = await fetch(`/api/time_grid/week?${params.toString()}`);
            if (!response.ok) {
                throw new Error('Failed to load week');
            }
            weekData = await response.json();
            renderGrid();
        } catch (err) {
            console.error(err);
            weekData = null;
            renderBreakdown();
        }
    }

    async function submitPending() {
        if (!isViewingSelf() || submitBtn.disabled) {
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

    if (userSelectEl) {
        userSelectEl.addEventListener('change', () => {
            selectedUserId = Number(userSelectEl.value) || currentUserId;
            page.dataset.selectedUserId = String(selectedUserId);
            syncInputVisibility();
            updateWeekNavLinks();
            const url = new URL(window.location.href);
            url.searchParams.set('user', String(selectedUserId));
            window.history.replaceState({}, '', url.pathname + url.search);
            loadWeek();
        });
    }

    projectSearchEl.addEventListener('input', filterProjects);
    notesEl.addEventListener('input', updateSubmitState);
    submitBtn.addEventListener('click', submitPending);
    clearBtn.addEventListener('click', () => {
        pendingSlots.clear();
        renderGrid();
    });

    buildGridSkeleton();
    syncInputVisibility();
    updateWeekNavLinks();
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
