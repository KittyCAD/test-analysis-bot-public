// HTML legends for Chart.js with subtle info icons for series tips.
(function (global) {
    function tipMap(tips) {
        if (!tips) {
            return {};
        }
        if (Array.isArray(tips)) {
            return Object.fromEntries(
                tips
                    .filter(item => item && item.label && item.tip)
                    .map(item => [item.label, item.tip])
            );
        }
        return tips;
    }

    function disposeTooltips(container) {
        container.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            const existing = global.bootstrap?.Tooltip?.getInstance(el);
            if (existing) {
                existing.dispose();
            }
        });
    }

    function initTooltips(container) {
        if (!global.bootstrap?.Tooltip) {
            return;
        }
        container.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            global.bootstrap.Tooltip.getOrCreateInstance(el, {
                container: 'body',
                trigger: 'hover focus',
                placement: 'top',
            });
        });
    }

    function renderLegend(chart, container, tips, order) {
        const labels = Chart.defaults.plugins.legend.labels
            .generateLabels(chart)
            .map(function (item) {
                return Object.assign({}, item, { lineWidth: 0 });
            });
        if (order && order.length) {
            labels.sort(function (a, b) {
                return order.indexOf(a.text) - order.indexOf(b.text);
            });
        }

        disposeTooltips(container);
        container.replaceChildren();

        labels.forEach(function (item) {
            if (item.text == null) {
                return;
            }
            const row = document.createElement('div');
            row.className = 'chart-legend__item';

            const toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'chart-legend__toggle';
            if (item.hidden) {
                toggle.classList.add('is-hidden');
            }
            toggle.addEventListener('click', function () {
                chart.setDatasetVisibility(
                    item.datasetIndex,
                    !chart.isDatasetVisible(item.datasetIndex)
                );
                chart.update();
            });

            const swatch = document.createElement('span');
            swatch.className = 'chart-legend__swatch';
            swatch.style.backgroundColor = String(
                item.fillStyle || item.strokeStyle || '#999'
            );
            toggle.appendChild(swatch);

            const label = document.createElement('span');
            label.className = 'chart-legend__label';
            label.textContent = item.text;
            toggle.appendChild(label);
            row.appendChild(toggle);

            const tip = tips[item.text];
            if (tip) {
                const info = document.createElement('button');
                info.type = 'button';
                info.className = 'chart-legend__tip';
                info.setAttribute('data-bs-toggle', 'tooltip');
                info.setAttribute('data-bs-title', tip);
                info.setAttribute('aria-label', 'About ' + item.text);
                info.innerHTML =
                    '<i class="fa-solid fa-circle-info" aria-hidden="true"></i>';
                info.addEventListener('click', function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                });
                row.appendChild(info);
            }

            container.appendChild(row);
        });

        initTooltips(container);
    }

    /**
     * Chart.js plugin: render an HTML legend with info-icon tips into container.
     * tips: {Label: "…"} or [{label, tip}, …]
     */
    function htmlLegendPlugin(container, tips, order) {
        const resolvedTips = tipMap(tips);
        return {
            id: 'htmlLegend-' + (container.id || 'chart'),
            afterUpdate: function (chart) {
                renderLegend(chart, container, resolvedTips, order);
            },
        };
    }

    global.tabCharts = global.tabCharts || {};
    global.tabCharts.htmlLegendPlugin = htmlLegendPlugin;
})(window);
