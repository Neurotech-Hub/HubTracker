(function () {
    'use strict';

    const BAR_COLORS = [
        '#0d6efd', '#198754', '#fd7e14', '#6f42c1', '#dc3545',
        '#20c997', '#ffc107', '#6610f2', '#0dcaf0', '#6c757d',
    ];

    const page = document.getElementById('timeMachinePage');
    if (!page) {
        return;
    }

    const currentUserId = Number(page.dataset.currentUserId);
    const rawSelectedUser = page.dataset.selectedUserId;
    let selectedUserId = rawSelectedUser === 'all' ? 'all' : Number(rawSelectedUser || currentUserId);
    let rangeKey = page.dataset.range || '30d';
    let mode = 'effort';
    let machineData = null;
    let chart = null;

    const userSelectEl = document.getElementById('timeMachineUserSelect');
    const rangeSelectEl = document.getElementById('timeMachineRangeSelect');
    const backLinkEl = document.getElementById('timeMachineBackLink');
    const legendEl = document.getElementById('timeMachineLegend');
    const chartEl = document.getElementById('timeMachineChart');
    const plotEmptyEl = document.getElementById('timeMachinePlotEmpty');
    const plotContentEl = document.getElementById('timeMachinePlotContent');
    const heatmapEl = document.getElementById('timeMachineHeatmap');
    const heatmapEmptyEl = document.getElementById('timeMachineHeatmapEmpty');
    const breakdownEmptyEl = document.getElementById('timeMachineBreakdownEmpty');
    const breakdownContentEl = document.getElementById('timeMachineBreakdownContent');
    const breakdownBodyEl = document.getElementById('timeMachineBreakdownBody');
    const rangeHeaderEl = document.getElementById('timeMachineRangeHeader');
    const rangeTotalEl = document.getElementById('timeMachineRangeTotal');
    const weeklyAvgTotalEl = document.getElementById('timeMachineWeeklyAvgTotal');

    function projectKey(projectId) {
        return projectId == null || projectId === '' ? 'null' : String(projectId);
    }

    function escapeHtml(text) {
        return String(text == null ? '' : text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function fadeColor(hex) {
        const value = String(hex || '#6c757d').replace('#', '');
        const r = parseInt(value.slice(0, 2), 16);
        const g = parseInt(value.slice(2, 4), 16);
        const b = parseInt(value.slice(4, 6), 16);
        return `rgba(${r}, ${g}, ${b}, 0.15)`;
    }

    function weekLabel(isoDate) {
        const parts = String(isoDate).split('-').map(Number);
        const dt = new Date(parts[0], parts[1] - 1, parts[2], 12);
        return `${dt.getMonth() + 1}/${dt.getDate()}`;
    }

    function weekTotals() {
        return (machineData && machineData.week_totals) || [];
    }

    function totalHoursAxisMax() {
        const peak = weekTotals().reduce((max, value) => Math.max(max, Number(value) || 0), 0);
        return peak > 0 ? peak : 1;
    }

    const totalHoursBarsPlugin = {
        id: 'totalHoursBars',
        beforeDatasetsDraw(chartInstance) {
            if (mode !== 'hours') {
                return;
            }
            const totals = weekTotals();
            const xScale = chartInstance.scales.x;
            const yScale = chartInstance.scales.y1;
            const { ctx, chartArea } = chartInstance;
            if (!xScale || !yScale || !totals.length || !chartArea) {
                return;
            }
            const slot = totals.length > 1
                ? Math.abs(xScale.getPixelForTick(1) - xScale.getPixelForTick(0))
                : chartArea.width;
            const barWidth = Math.max(4, slot * 0.62);
            const base = yScale.getPixelForValue(0);
            ctx.save();
            ctx.beginPath();
            ctx.rect(chartArea.left, chartArea.top, chartArea.right - chartArea.left, chartArea.bottom - chartArea.top);
            ctx.clip();
            ctx.fillStyle = 'rgba(173, 181, 189, 0.55)';
            totals.forEach((total, index) => {
                const x = xScale.getPixelForTick(index);
                const y = yScale.getPixelForValue(Number(total) || 0);
                const top = Math.min(y, base);
                ctx.fillRect(x - barWidth / 2, top, barWidth, Math.abs(base - y));
            });
            ctx.restore();
        },
    };

    const HEAT = [
        [255, 255, 255],
        [68, 1, 84],
        [72, 40, 120],
        [62, 73, 137],
        [49, 104, 142],
        [38, 130, 142],
        [31, 158, 137],
        [53, 183, 121],
        [110, 206, 88],
        [253, 231, 37],
    ];

    function heatColor(t) {
        const clamped = Math.max(0, Math.min(1, t));
        const scaled = clamped * (HEAT.length - 1);
        const index = Math.floor(scaled);
        const mix = scaled - index;
        const start = HEAT[index];
        const end = HEAT[Math.min(index + 1, HEAT.length - 1)];
        const channels = start.map((channel, i) => Math.round(channel + (end[i] - channel) * mix));
        return {
            css: `rgb(${channels[0]}, ${channels[1]}, ${channels[2]})`,
            text: (channels[0] * 299 + channels[1] * 587 + channels[2] * 114) / 1000 > 160 ? '#1a1a1a' : '#fff',
        };
    }

    function heatmapValue(project, index) {
        const hours = Number((project.weekly_hours || [])[index] || 0);
        if (hours <= 0) {
            return 0;
        }
        if (mode === 'hours') {
            return hours;
        }
        const total = Number(weekTotals()[index] || 0);
        if (total <= 0) {
            return 0;
        }
        return hours / total * 100;
    }

    function heatmapTicks(scaleMax) {
        const maxLabel = Math.max(1, Math.round(scaleMax));
        const rough = Math.max(maxLabel / 4, 1);
        const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
        const ratio = rough / magnitude;
        const step = (ratio >= 7.5 ? 10 : ratio >= 3.5 ? 5 : ratio >= 1.5 ? 2 : 1) * magnitude;
        const ticks = [];
        for (let value = 0; value < maxLabel; value += step) {
            ticks.push(value);
        }
        ticks.push(maxLabel);
        return ticks;
    }

    function renderHeatmap(projects) {
        if (!heatmapEl) {
            return;
        }
        const weeks = (machineData && machineData.weeks) || [];
        const hoursMode = mode === 'hours';
        const matrix = projects.map((project) => weeks.map((_, index) => heatmapValue(project, index)));
        const peak = matrix.reduce((max, row) => Math.max(max, ...row), 0);
        const scaleMax = peak > 0 ? peak : 1;
        const ticks = heatmapTicks(scaleMax);
        const columns = `minmax(12rem, 18rem) repeat(${weeks.length}, minmax(2.75rem, 1fr))`;
        const weekHeaders = weeks.map((week) => (
            `<div class="time-machine-heatmap-week">${escapeHtml(weekLabel(week))}</div>`
        )).join('');
        const rows = projects.map((project, rowIndex) => {
            const name = project.client_name
                ? `${project.client_name} — ${project.project_name}`
                : (project.project_name || 'No project');
            const cells = matrix[rowIndex].map((value) => {
                const color = heatColor(value <= 0 ? 0 : value / scaleMax);
                let label = '';
                if (value > 0) {
                    label = hoursMode
                        ? (value >= 10 ? value.toFixed(0) : value.toFixed(1))
                        : (Math.round(value) >= 1 ? `${Math.round(value)}%` : '');
                }
                const detail = hoursMode ? `${value.toFixed(1)} hrs` : `${value.toFixed(1)}%`;
                return (
                    `<div class="time-machine-heatmap-cell" style="background:${color.css};color:${color.text}" title="${escapeHtml(name)}: ${detail}">${label}</div>`
                );
            }).join('');
            return (
                `<div class="time-machine-heatmap-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>` +
                cells
            );
        }).join('');
        const tickHtml = ticks.slice().reverse().map((tick) => `<span>${tick}</span>`).join('');
        const scaleTitle = hoursMode ? 'Hours' : 'Effort (%)';
        let totalRow = '';
        if (hoursMode) {
            const totals = weekTotals();
            const totalCells = weeks.map((_, index) => {
                const value = Number(totals[index] || 0);
                return (
                    `<div class="time-machine-heatmap-cell time-machine-heatmap-total" title="Total: ${value.toFixed(1)} hrs">${value.toFixed(1)}</div>`
                );
            }).join('');
            totalRow = `<div class="time-machine-heatmap-name time-machine-heatmap-total">Total</div>${totalCells}`;
        }
        heatmapEl.innerHTML = (
            `<div class="time-machine-heatmap-scroll">` +
            `<div class="time-machine-heatmap-grid" style="grid-template-columns:${columns}">` +
            `<div class="time-machine-heatmap-corner"></div>` +
            weekHeaders +
            rows +
            totalRow +
            `</div></div>` +
            `<div class="time-machine-heatmap-scale${hoursMode ? ' has-total' : ''}" aria-hidden="true">` +
            `<div class="time-machine-heatmap-scale-title">${scaleTitle}</div>` +
            `<div class="time-machine-heatmap-scale-track">` +
            `<div class="time-machine-heatmap-scale-bar"></div>` +
            `<div class="time-machine-heatmap-scale-ticks">${tickHtml}</div>` +
            `</div></div>`
        );
    }

    function seriesFor(project) {
        const hours = project.weekly_hours || [];
        const totals = weekTotals();
        if (mode === 'hours') {
            return hours.map((value) => Number(value) || 0);
        }
        return hours.map((value, index) => {
            const total = Number(totals[index] || 0);
            if (total <= 0) {
                return 0;
            }
            return (Number(value) || 0) / total * 100;
        });
    }

    function syncUrl() {
        const url = new URL(window.location.href);
        url.searchParams.set('user', String(selectedUserId));
        url.searchParams.set('range', rangeKey);
        window.history.replaceState({}, '', url.pathname + url.search);
        if (backLinkEl) {
            const back = new URL(backLinkEl.href, window.location.origin);
            back.searchParams.set('user', String(selectedUserId === 'all' ? currentUserId : selectedUserId));
            backLinkEl.href = back.pathname + back.search;
        }
    }

    function setMode(nextMode) {
        mode = nextMode;
        const effortOn = mode === 'effort';
        document.querySelectorAll('.time-machine-mode-effort').forEach((button) => {
            button.classList.toggle('btn-primary', effortOn);
            button.classList.toggle('btn-outline-primary', !effortOn);
            button.setAttribute('aria-pressed', effortOn ? 'true' : 'false');
        });
        document.querySelectorAll('.time-machine-mode-hours').forEach((button) => {
            button.classList.toggle('btn-primary', !effortOn);
            button.classList.toggle('btn-outline-primary', effortOn);
            button.setAttribute('aria-pressed', effortOn ? 'false' : 'true');
        });
        if (!machineData) {
            return;
        }
        const projects = machineData.projects || [];
        renderHeatmap(projects);
        if (!chart) {
            return;
        }
        chart.data.datasets.forEach((dataset, index) => {
            dataset.data = seriesFor(projects[index] || {});
        });
        chart.options.scales.y.title.text = mode === 'effort' ? 'Effort (%)' : 'Hours';
        chart.options.scales.y.ticks.callback = (value) => (
            mode === 'effort' ? `${Number(value).toFixed(0)}%` : Number(value).toFixed(1)
        );
        if (chart.options.scales.y1) {
            chart.options.scales.y1.display = mode === 'hours';
            chart.options.scales.y1.max = totalHoursAxisMax();
        }
        chart.update();
    }

    function isolateProject(key) {
        if (!chart) {
            return;
        }
        chart.data.datasets.forEach((dataset) => {
            const focused = dataset.projectKey === key;
            dataset.borderColor = focused ? dataset.baseColor : fadeColor(dataset.baseColor);
            dataset.backgroundColor = dataset.borderColor;
            dataset.borderWidth = focused ? 3 : 1;
            dataset.pointRadius = focused ? 3 : 0;
        });
        chart.update('none');
        document.querySelectorAll('[data-project-key]').forEach((el) => {
            el.classList.toggle('is-isolated', el.dataset.projectKey === key);
        });
    }

    function clearIsolation() {
        if (chart) {
            chart.data.datasets.forEach((dataset) => {
                dataset.borderColor = dataset.baseColor;
                dataset.backgroundColor = dataset.baseColor;
                dataset.borderWidth = 2;
                dataset.pointRadius = 2;
            });
            chart.update('none');
        }
        document.querySelectorAll('[data-project-key].is-isolated').forEach((el) => {
            el.classList.remove('is-isolated');
        });
    }

    function bindHover(el, key) {
        el.addEventListener('mouseenter', () => isolateProject(key));
        el.addEventListener('mouseleave', () => clearIsolation());
    }

    function renderLegend(projects) {
        if (!legendEl) {
            return;
        }
        legendEl.innerHTML = projects.map((project, index) => {
            const color = BAR_COLORS[index % BAR_COLORS.length];
            const label = project.client_name
                ? `${project.client_name} — ${project.project_name}`
                : (project.project_name || 'No project');
            return (
                `<div class="time-machine-legend-item" data-project-key="${escapeHtml(projectKey(project.project_id))}">` +
                `<span class="time-machine-legend-swatch" style="background:${color}"></span>` +
                `<span class="time-machine-legend-label">${escapeHtml(label)}</span>` +
                `</div>`
            );
        }).join('');
        legendEl.querySelectorAll('[data-project-key]').forEach((el) => {
            bindHover(el, el.dataset.projectKey);
        });
    }

    function renderChart(projects) {
        if (!chartEl || typeof Chart === 'undefined') {
            return;
        }
        const labels = (machineData.weeks || []).map(weekLabel);
        const datasets = projects.map((project, index) => {
            const color = BAR_COLORS[index % BAR_COLORS.length];
            return {
                label: project.project_name || 'No project',
                projectKey: projectKey(project.project_id),
                baseColor: color,
                data: seriesFor(project),
                borderColor: color,
                backgroundColor: color,
                borderWidth: 2,
                pointRadius: 2,
                tension: 0,
                fill: false,
            };
        });

        if (chart) {
            chart.destroy();
            chart = null;
        }
        chart = new Chart(chartEl, {
            type: 'line',
            plugins: [totalHoursBarsPlugin],
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'nearest', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'nearest',
                        intersect: false,
                        callbacks: {
                            label: (context) => {
                                const value = Number(context.parsed.y) || 0;
                                const suffix = mode === 'effort' ? '%' : ' hrs';
                                return `${context.dataset.label}: ${value.toFixed(1)}${suffix}`;
                            },
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: mode === 'effort' ? 'Effort (%)' : 'Hours',
                        },
                        ticks: {
                            callback: (value) => (
                                mode === 'effort' ? `${Number(value).toFixed(0)}%` : Number(value).toFixed(1)
                            ),
                        },
                    },
                    y1: {
                        position: 'right',
                        display: mode === 'hours',
                        beginAtZero: true,
                        min: 0,
                        max: totalHoursAxisMax(),
                        title: {
                            display: true,
                            text: 'Total hours',
                        },
                        grid: { drawOnChartArea: false },
                        ticks: {
                            callback: (value) => Number(value).toFixed(0),
                        },
                    },
                    x: {
                        grid: { display: false },
                    },
                },
            },
        });
    }

    function renderTable(projects) {
        if (!breakdownBodyEl) {
            return;
        }
        if (rangeHeaderEl && machineData) {
            rangeHeaderEl.textContent = machineData.range_label || 'Last 30 Days';
        }
        breakdownBodyEl.innerHTML = projects.map((project, index) => {
            const pct = Math.max(0, Math.min(100, Number(project.range_percent || 0)));
            const color = BAR_COLORS[index % BAR_COLORS.length];
            return (
                `<tr data-project-key="${escapeHtml(projectKey(project.project_id))}">` +
                `<td class="time-grid-breakdown-bar-col">` +
                `<span class="time-grid-breakdown-bar-track" title="${pct.toFixed(1)}% of range">` +
                `<span class="time-grid-breakdown-bar-fill" style="width:${pct}%;background:${color}"></span>` +
                `</span>` +
                `</td>` +
                `<td>${escapeHtml(project.client_name || '—')}</td>` +
                `<td>${escapeHtml(project.project_name || '—')}</td>` +
                `<td class="text-end"><strong>${pct.toFixed(1)}%</strong> (${Number(project.range_hours || 0).toFixed(1)} hrs)</td>` +
                `<td class="text-end">${Number(project.weekly_avg || 0).toFixed(1)} hrs</td>` +
                `</tr>`
            );
        }).join('');
        breakdownBodyEl.querySelectorAll('[data-project-key]').forEach((el) => {
            bindHover(el, el.dataset.projectKey);
        });
        if (rangeTotalEl) {
            const total = Number((machineData && machineData.range_total_hours) || 0);
            rangeTotalEl.innerHTML = `<strong>100%</strong> (${total.toFixed(1)} hrs)`;
        }
        if (weeklyAvgTotalEl) {
            const totals = weekTotals();
            const weeklyAvgTotal = totals.length
                ? totals.reduce((sum, hours) => sum + Number(hours || 0), 0) / totals.length
                : 0;
            weeklyAvgTotalEl.textContent = `${weeklyAvgTotal.toFixed(1)} hrs`;
        }
    }

    function render() {
        const projects = (machineData && machineData.projects) || [];
        const empty = projects.length === 0;
        if (heatmapEmptyEl && heatmapEl) {
            heatmapEmptyEl.classList.toggle('d-none', !empty);
            heatmapEl.classList.toggle('d-none', empty);
        }
        if (plotEmptyEl && plotContentEl) {
            plotEmptyEl.classList.toggle('d-none', !empty);
            plotContentEl.classList.toggle('d-none', empty);
        }
        if (breakdownEmptyEl && breakdownContentEl) {
            breakdownEmptyEl.classList.toggle('d-none', !empty);
            breakdownContentEl.classList.toggle('d-none', empty);
        }
        if (empty) {
            if (chart) {
                chart.destroy();
                chart = null;
            }
            if (heatmapEl) {
                heatmapEl.innerHTML = '';
            }
            if (legendEl) {
                legendEl.innerHTML = '';
            }
            if (breakdownBodyEl) {
                breakdownBodyEl.innerHTML = '';
            }
            return;
        }
        renderHeatmap(projects);
        renderLegend(projects);
        renderChart(projects);
        renderTable(projects);
    }

    async function load() {
        try {
            const params = new URLSearchParams({
                range: rangeKey,
                user: String(selectedUserId),
            });
            const response = await fetch(`/api/time_machine?${params.toString()}`);
            if (!response.ok) {
                throw new Error('Failed to load time machine');
            }
            machineData = await response.json();
            render();
        } catch (err) {
            console.error(err);
            machineData = null;
            render();
        }
    }

    if (userSelectEl) {
        userSelectEl.addEventListener('change', () => {
            selectedUserId = userSelectEl.value === 'all' ? 'all' : (Number(userSelectEl.value) || currentUserId);
            syncUrl();
            load();
        });
    }
    if (rangeSelectEl) {
        rangeSelectEl.addEventListener('change', () => {
            rangeKey = rangeSelectEl.value || '30d';
            syncUrl();
            load();
        });
    }
    document.querySelectorAll('.time-machine-mode-effort').forEach((button) => {
        button.addEventListener('click', () => setMode('effort'));
    });
    document.querySelectorAll('.time-machine-mode-hours').forEach((button) => {
        button.addEventListener('click', () => setMode('hours'));
    });

    syncUrl();
    load();
})();
