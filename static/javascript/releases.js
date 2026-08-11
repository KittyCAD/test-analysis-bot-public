document.addEventListener("DOMContentLoaded", function () {
    if (typeof cytoscape === "undefined") {
        return;
    }

    if (typeof cytoscapeDagre !== "undefined") {
        cytoscape.use(cytoscapeDagre);
    }

    const DEFAULT_ROW_HEIGHT = 110;
    const HEADER_Y = 0;
    const FIRST_ROW_Y = 90;
    const TIMELINE_FIRST_ROW_Y = 24;
    const COLUMN_STAGGER = 56;
    // Change History needs a wider left/right offset so a center taxi spine
    // can run between staggered cards instead of scraping their edges.
    const TIMELINE_COLUMN_STAGGER = 80;
    const TIMELINE_MIN_GAP = 125;
    const GRAPH_PADDING = 24;
    const TIMELINE_RESERVE = 88;
    // Hour labels are ~9px; skip them when they would collide with day ticks or each other.
    const MIN_HOUR_GAP_FROM_DAY = 20;
    const MIN_HOUR_GAP_BETWEEN = 14;
    const MIN_DAY_GAP_FOR_HOURS = 56;
    const HOUR_MS = 60 * 60 * 1000;
    const DAY_MS = 24 * HOUR_MS;
    // Extra vertical space (on top of TIMELINE_MIN_GAP) when inserting a break marker.
    const BREAK_EXTRA_PX = 32;

    // Column x positions depend only on container width + column count — never on nodes.
    function computeColumnLayout(container, columnCount, options) {
        const withTimeline = !!(options && options.withTimeline);
        const count = Math.max(columnCount, 1);
        const avail = Math.max(container.clientWidth - GRAPH_PADDING * 2, 300);
        const leftReserve = withTimeline ? TIMELINE_RESERVE : 0;
        const columnsArea = Math.max(avail - leftReserve, count * 120);
        const columnWidth = columnsArea / count;
        return {
            columnWidth: columnWidth,
            // Equal-width columns; optional left gutter for the Change History timeline.
            columnX: function (index) {
                return leftReserve + (index + 0.5) * columnWidth;
            },
            axisX: 12,
            columnsRight: leftReserve + columnsArea,
            // Alternate cards left/right within the column so edges fan apart.
            // Timeline uses a larger stagger so left/right stacks leave a center
            // corridor; still capped by column width to limit cross-column overlap.
            stagger: withTimeline
                ? Math.min(TIMELINE_COLUMN_STAGGER, columnWidth * 0.2)
                : Math.min(COLUMN_STAGGER, columnWidth * 0.12),
            panX: GRAPH_PADDING,
        };
    }

    function formatTickLabel(timestamp) {
        const date = new Date(timestamp);
        return date.getMonth() + 1 + "/" + date.getDate();
    }

    function formatHourTickLabel(timestamp) {
        const date = new Date(timestamp);
        const hour = date.getHours();
        const suffix = hour < 12 ? "am" : "pm";
        const hour12 = hour % 12 || 12;
        return hour12 + " " + suffix;
    }

    function dayKey(timestamp) {
        const date = new Date(timestamp);
        return (
            date.getFullYear() + "-" + date.getMonth() + "-" + date.getDate()
        );
    }

    function hourKey(timestamp) {
        const date = new Date(timestamp);
        return dayKey(timestamp) + "-" + date.getHours();
    }

    function uniqueDayTimestamps(times) {
        const seen = {};
        const days = [];
        times
            .slice()
            .sort(function (a, b) {
                return b - a;
            })
            .forEach(function (timestamp) {
                const key = dayKey(timestamp);
                if (!seen[key]) {
                    seen[key] = true;
                    days.push(timestamp);
                }
            });
        return days;
    }

    function uniqueHourTimestamps(times) {
        const seen = {};
        const hours = [];
        times
            .slice()
            .sort(function (a, b) {
                return b - a;
            })
            .forEach(function (timestamp) {
                const key = hourKey(timestamp);
                if (!seen[key]) {
                    seen[key] = true;
                    hours.push(timestamp);
                }
            });
        return hours;
    }

    function uniqueSortedTimes(times) {
        const seen = {};
        const unique = [];
        times.forEach(function (timestamp) {
            if (!seen[timestamp]) {
                seen[timestamp] = true;
                unique.push(timestamp);
            }
        });
        unique.sort(function (a, b) {
            return a - b;
        });
        return unique;
    }

    function gapThresholdMs(sortedAsc) {
        if (sortedAsc.length < 2) {
            return Number.POSITIVE_INFINITY;
        }
        const gaps = [];
        for (let i = 1; i < sortedAsc.length; i++) {
            gaps.push(sortedAsc[i] - sortedAsc[i - 1]);
        }
        gaps.sort(function (a, b) {
            return a - b;
        });
        const median = gaps[Math.floor(gaps.length / 2)];
        // Only break on clear outliers (at least a week), not routine multi-day gaps.
        return Math.max(median * 5, 7 * DAY_MS);
    }

    // Newest-first Y positions with min card spacing; large time gaps get a break.
    function assignTimelinePositions(nodes) {
        const sorted = nodes
            .slice()
            .map(function (node) {
                return {
                    node: node,
                    time: Date.parse(node.createdAt),
                };
            })
            .filter(function (entry) {
                return !Number.isNaN(entry.time);
            })
            .sort(function (a, b) {
                return b.time - a.time;
            });

        const times = sorted.map(function (entry) {
            return entry.time;
        });
        const threshold = gapThresholdMs(uniqueSortedTimes(times));
        const yById = {};
        const timeToY = {};
        const breakYs = [];
        let y = TIMELINE_FIRST_ROW_Y;
        let prevTime = null;

        sorted.forEach(function (entry) {
            if (prevTime !== null && entry.time === prevTime) {
                yById[entry.node.id] = y;
                return;
            }
            if (prevTime !== null) {
                y += TIMELINE_MIN_GAP;
                if (prevTime - entry.time > threshold) {
                    breakYs.push(y + BREAK_EXTRA_PX / 2);
                    y += BREAK_EXTRA_PX;
                }
            }
            yById[entry.node.id] = y;
            if (!Object.prototype.hasOwnProperty.call(timeToY, entry.time)) {
                timeToY[entry.time] = y;
            }
            prevTime = entry.time;
        });

        return {
            yById: yById,
            timeToY: function (timestamp) {
                if (Object.prototype.hasOwnProperty.call(timeToY, timestamp)) {
                    return timeToY[timestamp];
                }
                // Snap day/hour ticks to the nearest placed event.
                let best = null;
                let bestDelta = Number.POSITIVE_INFINITY;
                Object.keys(timeToY).forEach(function (key) {
                    const time = Number(key);
                    const delta = Math.abs(time - timestamp);
                    if (delta < bestDelta) {
                        bestDelta = delta;
                        best = timeToY[time];
                    }
                });
                return best === null ? TIMELINE_FIRST_ROW_Y : best;
            },
            breaks: breakYs,
            maxY: sorted.length ? y : TIMELINE_FIRST_ROW_Y,
        };
    }

    function buildColumnElements(data, layout) {
        const columns = data.columns || [];
        const rowHeight = data.rowHeight || DEFAULT_ROW_HEIGHT;
        const groups = {};

        data.nodes.forEach(function (node) {
            const column = node.column || 0;
            if (!groups[column]) {
                groups[column] = [];
            }
            groups[column].push(node);
        });

        Object.keys(groups).forEach(function (column) {
            groups[column].sort(function (a, b) {
                return a.label.localeCompare(b.label);
            });
        });

        const elements = columns.map(function (column, index) {
            return {
                group: "nodes",
                data: {
                    id: "column-" + column.id,
                    label: column.label,
                    color: column.color,
                    href: "",
                    isHeader: true,
                    isTimeline: false,
                    isSpacer: false,
                },
                position: { x: layout.columnX(index), y: HEADER_Y },
                grabbable: false,
                selectable: false,
            };
        });

        Object.keys(groups).forEach(function (columnKey) {
            const column = Number(columnKey);
            const nodes = groups[columnKey];
            nodes.forEach(function (node, row) {
                const stagger =
                    nodes.length <= 1
                        ? 0
                        : row % 2 === 0
                          ? -layout.stagger
                          : layout.stagger;
                elements.push({
                    group: "nodes",
                    data: {
                        id: node.id,
                        label: node.subtitle
                            ? node.label + "\n\n" + node.subtitle
                            : node.label,
                        subtitle: node.subtitle,
                        color: node.color,
                        href: node.href || "",
                        projectHref: node.projectHref || "",
                        column: column,
                        isHeader: false,
                        isTimeline: false,
                        isSpacer: false,
                    },
                    position: {
                        x: layout.columnX(column) + stagger,
                        y: FIRST_ROW_Y + row * rowHeight,
                    },
                });
            });
        });

        // Right-edge spacer so width stays locked to the panel.
        elements.push({
            group: "nodes",
            data: {
                id: "layout-width-spacer",
                label: "",
                color: "#000000",
                href: "",
                isHeader: true,
                isTimeline: false,
                isSpacer: true,
            },
            position: {
                x: layout.columnsRight,
                y: FIRST_ROW_Y,
            },
            grabbable: false,
            selectable: false,
        });

        data.edges.forEach(function (edge) {
            elements.push({
                group: "edges",
                data: {
                    id: edge.id,
                    source: edge.source,
                    target: edge.target,
                },
            });
        });

        return elements;
    }

    function buildTimelineColumnElements(data, layout, options) {
        const groups = {};
        const times = data.nodes
            .map(function (node) {
                return Date.parse(node.createdAt);
            })
            .filter(function (value) {
                return !Number.isNaN(value);
            });

        if (!times.length) {
            return buildColumnElements(data, layout);
        }

        const axisX = layout.axisX;
        const firstRowY = TIMELINE_FIRST_ROW_Y;
        const positions = assignTimelinePositions(data.nodes);

        data.nodes.forEach(function (node) {
            const column = node.column || 0;
            if (!groups[column]) {
                groups[column] = [];
            }
            groups[column].push(node);
        });

        const elements = [];
        let maxContentY = positions.maxY;

        // Continuous axis line via unlabeled endpoints.
        const axisStartId = "timeline-axis-start";
        const axisEndId = "timeline-axis-end";
        const axisEndElement = {
            group: "nodes",
            data: {
                id: axisEndId,
                label: "",
                color: "#6c757d",
                href: "",
                isHeader: false,
                isTimeline: true,
                isTimelineDot: true,
                isTimelineEndpoint: true,
            },
            position: { x: axisX, y: maxContentY },
            grabbable: false,
            selectable: false,
        };
        elements.push({
            group: "nodes",
            data: {
                id: axisStartId,
                label: "",
                color: "#6c757d",
                href: "",
                isHeader: false,
                isTimeline: true,
                isTimelineDot: true,
                isTimelineEndpoint: true,
            },
            position: { x: axisX, y: firstRowY },
            grabbable: false,
            selectable: false,
        });
        elements.push(axisEndElement);
        elements.push({
            group: "edges",
            data: {
                id: "timeline-axis-edge",
                source: axisStartId,
                target: axisEndId,
                isTimeline: true,
            },
        });

        const dayTimes = uniqueDayTimestamps(times);
        const dayHourKeys = {};
        const dayYs = [];
        dayTimes.forEach(function (timestamp) {
            dayHourKeys[hourKey(timestamp)] = true;
        });

        dayTimes.forEach(function (timestamp, index) {
            const y = positions.timeToY(timestamp);
            dayYs.push(y);
            elements.push({
                group: "nodes",
                data: {
                    id: "timeline-tick-" + index,
                    label: formatTickLabel(timestamp),
                    color: "#6c757d",
                    href: "",
                    isHeader: false,
                    isTimeline: true,
                    isTimelineDot: true,
                    isTimelineHour: false,
                },
                position: {
                    x: axisX,
                    y: y,
                },
                grabbable: false,
                selectable: false,
            });
        });

        positions.breaks.forEach(function (y, index) {
            elements.push({
                group: "nodes",
                data: {
                    id: "timeline-break-" + index,
                    label: "⫽",
                    color: "#6c757d",
                    href: "",
                    isHeader: false,
                    isTimeline: true,
                    isTimelineDot: false,
                    isTimelineBreak: true,
                },
                position: { x: axisX, y: y },
                grabbable: false,
                selectable: false,
            });
        });

        let minDayGap = Infinity;
        for (let i = 1; i < dayYs.length; i++) {
            minDayGap = Math.min(minDayGap, Math.abs(dayYs[i] - dayYs[i - 1]));
        }
        const showHourTicks =
            dayYs.length < 2 || minDayGap >= MIN_DAY_GAP_FOR_HOURS;

        // Lighter hour marks between day ticks, only when labels have room.
        if (showHourTicks) {
            const placedHourYs = [];
            uniqueHourTimestamps(times).forEach(function (timestamp, index) {
                if (dayHourKeys[hourKey(timestamp)]) {
                    return;
                }
                const y = positions.timeToY(timestamp);
                const tooCloseToDay = dayYs.some(function (dayY) {
                    return Math.abs(dayY - y) < MIN_HOUR_GAP_FROM_DAY;
                });
                if (tooCloseToDay) {
                    return;
                }
                const tooCloseToBreak = positions.breaks.some(function (breakY) {
                    return Math.abs(breakY - y) < MIN_HOUR_GAP_FROM_DAY;
                });
                if (tooCloseToBreak) {
                    return;
                }
                const tooCloseToHour = placedHourYs.some(function (hourY) {
                    return Math.abs(hourY - y) < MIN_HOUR_GAP_BETWEEN;
                });
                if (tooCloseToHour) {
                    return;
                }
                placedHourYs.push(y);
                elements.push({
                    group: "nodes",
                    data: {
                        id: "timeline-hour-" + index,
                        label: formatHourTickLabel(timestamp),
                        color: "#adb5bd",
                        href: "",
                        isHeader: false,
                        isTimeline: true,
                        isTimelineDot: true,
                        isTimelineHour: true,
                    },
                    position: {
                        x: axisX,
                        y: y,
                    },
                    grabbable: false,
                    selectable: false,
                });
            });
        }

        Object.keys(groups).forEach(function (columnKey) {
            const column = Number(columnKey);
            const nodes = groups[columnKey]
                .slice()
                .sort(function (a, b) {
                    return Date.parse(b.createdAt) - Date.parse(a.createdAt);
                });

            nodes.forEach(function (node, row) {
                const y = positions.yById[node.id];
                if (y === undefined) {
                    return;
                }
                if (y > maxContentY) {
                    maxContentY = y;
                }

                const stagger =
                    nodes.length <= 1
                        ? 0
                        : row % 2 === 0
                          ? -layout.stagger
                          : layout.stagger;
                const label = node.subtitle
                    ? node.label + "\n\n" + node.subtitle
                    : node.label;
                elements.push({
                    group: "nodes",
                    data: {
                        id: node.id,
                        label: label,
                        subtitle: node.subtitle,
                        color: node.color,
                        href: node.href || "",
                        projectHref: node.projectHref || "",
                        urlHref: node.urlHref || node.subtitle || "",
                        column: column,
                        isHeader: false,
                        isTimeline: false,
                        isTimelineDot: false,
                    },
                    position: {
                        x: layout.columnX(column) + stagger,
                        y: y,
                    },
                });
            });
        });

        // Keep the axis at least as tall as the cards; when truncated, run it
        // through the bottom fade so the line doesn't stop short.
        const fadeExtension = data.truncated ? 120 : 40;
        axisEndElement.position.y = maxContentY + fadeExtension;

        if (!options || options.includeDependencies !== false) {
            data.edges.forEach(function (edge) {
                elements.push({
                    group: "edges",
                    data: {
                        id: edge.id,
                        source: edge.source,
                        target: edge.target,
                        isTimeline: false,
                    },
                });
            });
        }

        return elements;
    }

    function buildDagreElements(data) {
        return data.nodes
            .map(function (node) {
                return {
                    data: {
                        id: node.id,
                        label: node.label,
                        subtitle: node.subtitle,
                        color: node.color,
                        href: node.href,
                        isHeader: false,
                        isTimeline: false,
                    },
                };
            })
            .concat(
                data.edges.map(function (edge) {
                    return {
                        data: {
                            id: edge.id,
                            source: edge.source,
                            target: edge.target,
                        },
                    };
                })
            );
    }

    // zoom=1 with pixel-space columns; height grows so the page scrolls.
    function fitWidthAndGrow(cy, container, layout) {
        const bb = cy.elements().boundingBox({ includeLabels: true });
        container.style.height =
            Math.ceil(bb.h + GRAPH_PADDING * 2) + "px";
        cy.resize();
        cy.zoom(1);
        cy.pan({
            x: layout.panX,
            y: GRAPH_PADDING - bb.y1,
        });
    }

    function buildElements(data, layout, options) {
        if (data.layout === "columns-timeline") {
            return buildTimelineColumnElements(data, layout, options);
        }
        if (data.layout === "columns") {
            return buildColumnElements(data, layout);
        }
        return buildDagreElements(data);
    }

    function dependencyLinesEnabled() {
        const toggle = document.getElementById("show-dependency-lines");
        return !toggle || toggle.checked;
    }

    function renderGraph(container, data) {
        if (container._cy) {
            container._cy.destroy();
            container._cy = null;
        }
        container
            .querySelectorAll(".releases-graph-link-hover")
            .forEach(function (el) {
                el.remove();
            });

        const usePreset =
            data.layout === "columns" || data.layout === "columns-timeline";
        const layout = usePreset
            ? computeColumnLayout(container, (data.columns || []).length, {
                  withTimeline: data.layout === "columns-timeline",
              })
            : null;
        const includeDependencies =
            data.layout !== "columns-timeline" || dependencyLinesEnabled();
        const elements = buildElements(data, layout, {
            includeDependencies: includeDependencies,
        });

        const cy = cytoscape({
            container: container,
            elements: elements,
            style: [
                {
                    selector: "node",
                    style: {
                        label: "data(label)",
                        "text-wrap": "wrap",
                        "text-max-width": 220,
                        "text-valign": "center",
                        "text-halign": "center",
                        "font-size": 11,
                        "font-family":
                            'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
                        color: "#212529",
                        "background-color": "#ffffff",
                        // Mostly opaque so edges sit under the card; a little
                        // transparency keeps under-card segments readable.
                        "background-opacity": 0.82,
                        "border-width": 2,
                        "border-color": "data(color)",
                        shape: "round-rectangle",
                        width: "label",
                        height: "label",
                        padding: "14px",
                        "overlay-padding": 4,
                        "z-index-compare": "manual",
                        "z-index": 10,
                    },
                },
                {
                    selector: "node[?isHeader]",
                    style: {
                        "font-size": 18,
                        "font-weight": 600,
                        "background-opacity": 0,
                        "border-width": 0,
                        "text-valign": "center",
                        "text-halign": "center",
                        color: "data(color)",
                        padding: "8px",
                        shape: "rectangle",
                        events: "no",
                        "z-index": 11,
                    },
                },
                {
                    selector: "node[?isSpacer]",
                    style: {
                        width: 1,
                        height: 1,
                        padding: 0,
                        opacity: 0,
                        label: "",
                        events: "no",
                        "z-index": 0,
                    },
                },
                {
                    selector: "node[?isTimelineDot]",
                    style: {
                        shape: "ellipse",
                        width: 10,
                        height: 10,
                        padding: 0,
                        "background-color": "#6c757d",
                        "background-opacity": 1,
                        "border-width": 2,
                        "border-color": "#ffffff",
                        label: "data(label)",
                        "font-size": 11,
                        "font-weight": 500,
                        "text-halign": "right",
                        "text-valign": "center",
                        "text-margin-x": 8,
                        "text-wrap": "none",
                        "text-max-width": 48,
                        color: "#6c757d",
                        events: "no",
                        "z-index": 10,
                    },
                },
                {
                    selector: "node[?isTimelineHour]",
                    style: {
                        shape: "ellipse",
                        width: 5,
                        height: 5,
                        padding: 0,
                        "background-color": "#ced4da",
                        "background-opacity": 1,
                        "border-width": 0,
                        label: "data(label)",
                        "font-size": 9,
                        "font-weight": 400,
                        "text-halign": "right",
                        "text-valign": "center",
                        "text-margin-x": 8,
                        "text-wrap": "none",
                        "text-max-width": 48,
                        "text-opacity": 0.75,
                        color: "#adb5bd",
                        events: "no",
                        "z-index": 9,
                    },
                },
                {
                    selector: "node[?isTimelineEndpoint]",
                    style: {
                        width: 1,
                        height: 1,
                        padding: 0,
                        opacity: 0,
                        "background-opacity": 0,
                        "border-width": 0,
                        label: "",
                        "z-index": 0,
                    },
                },
                {
                    selector: "node[?isTimelineBreak]",
                    style: {
                        shape: "rectangle",
                        width: 24,
                        height: 20,
                        padding: 0,
                        "background-color": "#f8f9fa",
                        "background-opacity": 1,
                        "border-width": 0,
                        label: "data(label)",
                        "font-size": 16,
                        "font-weight": 600,
                        "text-halign": "center",
                        "text-valign": "center",
                        "text-margin-x": 0,
                        color: "#6c757d",
                        events: "no",
                        "z-index": 12,
                    },
                },
                {
                    selector: "node:selected",
                    style: {
                        "border-width": 3,
                        "background-opacity": 0.9,
                    },
                },
                {
                    selector: "edge",
                    style: Object.assign(
                        {
                            width: 2,
                            "line-color": "#adb5bd",
                            "target-arrow-color": "#adb5bd",
                            "target-arrow-shape": "triangle",
                            "z-index-compare": "manual",
                            "z-index": 1,
                        },
                        // Change History: orthogonal taxi routes avoid the
                        // aggressive bezier fan-out on dense release graphs.
                        // Per-edge taxi-turn is set after layout for card clearance.
                        data.layout === "columns-timeline"
                            ? {
                                  "curve-style": "taxi",
                                  "edge-distances": "node-position",
                                  "taxi-direction": "horizontal",
                                  "taxi-turn": 40,
                                  "taxi-turn-min-distance": 16,
                                  "taxi-radius": 8,
                              }
                            : {
                                  "curve-style": "unbundled-bezier",
                                  "control-point-distances": 40,
                                  "control-point-weights": 0.5,
                              }
                    ),
                },
                {
                    selector: "edge[?isTimeline]",
                    style: {
                        width: 2,
                        "line-color": "#adb5bd",
                        "target-arrow-shape": "none",
                        "source-arrow-shape": "none",
                        "curve-style": "straight",
                        "line-style": "solid",
                        "z-index": 0,
                    },
                },
                {
                    selector: "node.faded",
                    style: {
                        opacity: 0.28,
                    },
                },
                {
                    selector: "edge.faded",
                    style: {
                        opacity: 0.1,
                        "z-index": 0,
                    },
                },
                {
                    selector: "node.highlighted",
                    style: {
                        "background-opacity": 1,
                        "border-width": 3,
                        "z-index": 20,
                    },
                },
                {
                    selector: "edge.highlighted",
                    style: {
                        width: 3,
                        "line-color": "#495057",
                        "target-arrow-color": "#495057",
                        opacity: 1,
                        "z-index": 15,
                    },
                },
            ],
            layout: usePreset
                ? {
                      name: "preset",
                      fit: false,
                      padding: GRAPH_PADDING,
                  }
                : {
                      name:
                          typeof cytoscapeDagre !== "undefined"
                              ? "dagre"
                              : "breadthfirst",
                      rankDir: "LR",
                      directed: true,
                      padding: 40,
                      spacingFactor: 1.2,
                      nodeSep: 48,
                      rankSep: 90,
                      animate: false,
                  },
            userZoomingEnabled: false,
            userPanningEnabled: false,
            boxSelectionEnabled: false,
            wheelSensitivity: 0,
        });

        // Fan edges that share a column corridor onto distinct bezier lanes.
        // Skip for Change History taxi edges — control-point styles are bezier-only.
        if (includeDependencies && data.layout !== "columns-timeline") {
            (function assignCorridorLanes() {
                const corridors = {};

                function columnKey(node) {
                    const column = node.data("column");
                    if (column !== undefined && column !== null && column !== "") {
                        return String(column);
                    }
                    return String(Math.round(node.position("x") / 80));
                }

                cy.edges().forEach(function (edge) {
                    if (edge.data("isTimeline")) {
                        return;
                    }
                    const key =
                        columnKey(edge.source()) +
                        "->" +
                        columnKey(edge.target());
                    if (!corridors[key]) {
                        corridors[key] = [];
                    }
                    corridors[key].push(edge);
                });

                Object.keys(corridors).forEach(function (key) {
                    const group = corridors[key];
                    group.sort(function (a, b) {
                        const aMid =
                            (a.source().position("y") +
                                a.target().position("y")) /
                            2;
                        const bMid =
                            (b.source().position("y") +
                                b.target().position("y")) /
                            2;
                        if (aMid !== bMid) {
                            return aMid - bMid;
                        }
                        return (
                            a.source().position("x") - b.source().position("x")
                        );
                    });

                    const n = group.length;
                    group.forEach(function (edge, index) {
                        const source = edge.source().position();
                        const target = edge.target().position();
                        const dy = target.y - source.y;
                        const dx = target.x - source.x;
                        const sameColumn = Math.abs(dx) < 48;
                        // Center lanes around 0 so corridors stay balanced.
                        const lane = index - (n - 1) / 2;
                        const laneSpacing = sameColumn ? 42 : 30;
                        const baseCurve = sameColumn ? 24 : 36;
                        const direction =
                            dy === 0
                                ? lane === 0
                                    ? 1
                                    : Math.sign(lane)
                                : Math.sign(dy);
                        const distance =
                            direction * baseCurve + lane * laneSpacing;
                        edge.style("control-point-distances", [distance]);
                        edge.style(
                            "control-point-weights",
                            [0.4 + (Math.abs(lane) % 3) * 0.08]
                        );
                    });
                });
            })();
        }

        // Route Change History same-column taxis down the column-center spine
        // opened by the wider timeline stagger; cross-column stays horizontal.
        function assignTaxiCorridors() {
            if (!includeDependencies || data.layout !== "columns-timeline") {
                return;
            }
            if (!layout) {
                return;
            }

            const LANE_SPACING = 14;
            const MIN_TURN = 24;

            const depEdges = cy.edges().filter(function (edge) {
                return !edge.data("isTimeline");
            });

            const corridors = {};
            depEdges.forEach(function (edge) {
                const key =
                    String(edge.source().data("column")) +
                    "->" +
                    String(edge.target().data("column"));
                if (!corridors[key]) {
                    corridors[key] = [];
                }
                corridors[key].push(edge);
            });

            Object.keys(corridors).forEach(function (key) {
                const group = corridors[key];
                group.sort(function (a, b) {
                    const aMid =
                        (a.source().position("y") + a.target().position("y")) /
                        2;
                    const bMid =
                        (b.source().position("y") + b.target().position("y")) /
                        2;
                    if (aMid !== bMid) {
                        return aMid - bMid;
                    }
                    return a.source().position("x") - b.source().position("x");
                });

                group.forEach(function (edge, index) {
                    const source = edge.source();
                    const target = edge.target();
                    const srcPos = source.position();
                    const lane = index - (group.length - 1) / 2;
                    const sameColumn =
                        String(source.data("column")) ===
                        String(target.data("column"));

                    if (!sameColumn) {
                        edge.style({
                            "taxi-direction": "horizontal",
                            "taxi-turn": Math.max(
                                48,
                                MIN_TURN + Math.abs(lane) * LANE_SPACING
                            ),
                            "taxi-turn-min-distance": 16,
                        });
                        return;
                    }

                    const column = Number(source.data("column"));
                    // Spine down the true column center, with small lane offsets
                    // for parallel same-column edges.
                    const spineX =
                        layout.columnX(column) + lane * LANE_SPACING;
                    const turn = Math.max(Math.abs(srcPos.x - spineX), MIN_TURN);
                    edge.style({
                        "taxi-direction":
                            srcPos.x >= spineX ? "leftward" : "rightward",
                        "taxi-turn": turn,
                        "taxi-turn-min-distance": 8,
                    });
                });
            });
        }

        assignTaxiCorridors();

        if (data.layout === "columns-timeline" || data.layout === "columns") {
            // Keep column thirds at full panel width; grow height instead of shrinking.
            fitWidthAndGrow(cy, container, layout);
            // Positions may shift slightly after fit — recompute taxi clearance.
            assignTaxiCorridors();
        }

        const CARD_PADDING = 14;
        const CARD_FONT =
            '11px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
        let measureCanvas = null;

        function measureLabelTextWidth(text) {
            if (!measureCanvas) {
                measureCanvas = document.createElement("canvas");
            }
            const ctx = measureCanvas.getContext("2d");
            ctx.font = CARD_FONT;
            return ctx.measureText(text).width;
        }

        function cardLinks(node) {
            if (
                !node ||
                node.data("isHeader") ||
                node.data("isTimelineDot") ||
                node.data("isTimelineBreak") ||
                node.data("isSpacer")
            ) {
                return [];
            }
            const projectHref = node.data("projectHref") || "";
            const href = node.data("href") || "";
            const urlHref = node.data("urlHref") || "";
            const links = [];
            if (projectHref) {
                links.push(projectHref);
            }
            if (href) {
                links.push(href);
            }
            if (urlHref && urlHref !== href) {
                links.push(urlHref);
            }
            return links;
        }

        // Map pointer to a link only when it sits on the label text itself
        // (per line, centered), not the full card padding/width.
        function cardLinkBandAt(node, renderedX, renderedY) {
            const links = cardLinks(node);
            if (!links.length) {
                return null;
            }

            const bb = node.renderedBoundingBox({ includeLabels: true });
            const zoom = cy.zoom();
            const pad = CARD_PADDING * zoom;
            const content = {
                x1: bb.x1 + pad,
                y1: bb.y1 + pad,
                x2: bb.x2 - pad,
                y2: bb.y2 - pad,
                w: Math.max(bb.w - pad * 2, 0),
                h: Math.max(bb.h - pad * 2, 0),
            };
            if (
                renderedX < content.x1 ||
                renderedX > content.x2 ||
                renderedY < content.y1 ||
                renderedY > content.y2
            ) {
                return null;
            }

            const lines = String(node.data("label") || "").split("\n");
            const lineCount = Math.max(lines.length, 1);
            const lineHeight = content.h / lineCount;
            const lineIndex = Math.min(
                lineCount - 1,
                Math.max(0, Math.floor((renderedY - content.y1) / lineHeight))
            );
            const lineText = lines[lineIndex] || "";
            if (!lineText.trim()) {
                return null;
            }

            const textWidth = measureLabelTextWidth(lineText) * zoom;
            const centerX = (content.x1 + content.x2) / 2;
            if (Math.abs(renderedX - centerX) > textWidth / 2 + 1 * zoom) {
                return null;
            }

            const nonEmptyIndexes = [];
            lines.forEach(function (line, index) {
                if (line.trim()) {
                    nonEmptyIndexes.push(index);
                }
            });
            const ordinal = nonEmptyIndexes.indexOf(lineIndex);
            if (ordinal < 0) {
                return null;
            }
            const linkIndex = Math.min(ordinal, links.length - 1);

            return {
                href: links[linkIndex],
                index: linkIndex,
                count: links.length,
                lineIndex: lineIndex,
                lineText: lineText,
                lineCount: lineCount,
                textWidth: textWidth,
                content: content,
                lineHeight: lineHeight,
                centerX: centerX,
            };
        }

        function cardLinkAt(node, renderedX, renderedY) {
            const band = cardLinkBandAt(node, renderedX, renderedY);
            return band ? band.href : "";
        }

        function updateCardCursor(node, renderedX, renderedY, dragging) {
            if (dragging) {
                container.style.cursor = "grabbing";
                return;
            }
            if (
                !node ||
                node.data("isHeader") ||
                node.data("isTimelineDot") ||
                node.data("isTimelineBreak") ||
                node.data("isSpacer")
            ) {
                container.style.cursor = "";
                return;
            }
            container.style.cursor = cardLinkAt(node, renderedX, renderedY)
                ? "pointer"
                : "grab";
        }

        let draggingCard = false;
        let hoveredCard = null;

        function isCardNode(node) {
            return (
                node &&
                node.isNode() &&
                !node.data("isHeader") &&
                !node.data("isSpacer") &&
                !node.data("isTimelineDot") &&
                !node.data("isTimelineHour") &&
                !node.data("isTimelineEndpoint") &&
                !node.data("isTimelineBreak")
            );
        }

        function cardNodes() {
            return cy.nodes().filter(isCardNode);
        }

        function dependencyEdges() {
            return cy.edges().filter(function (edge) {
                return !edge.data("isTimeline");
            });
        }

        function clearEmphasis() {
            if (!includeDependencies) {
                return;
            }
            cardNodes().removeClass("faded highlighted");
            dependencyEdges().removeClass("faded highlighted");
        }

        function emphasizeAround(focusNode) {
            if (!includeDependencies) {
                return;
            }
            cy.batch(function () {
                clearEmphasis();
                if (!isCardNode(focusNode)) {
                    return;
                }
                // Only the card's outgoing dependencies — not dependents that link to it.
                const outEdges = dependencyEdges().filter(function (edge) {
                    return edge.source().same(focusNode);
                });
                const outNodes = outEdges.targets().filter(isCardNode);
                const neighborhood = focusNode.union(outEdges).union(outNodes);
                cardNodes().difference(neighborhood.nodes()).addClass("faded");
                dependencyEdges()
                    .difference(neighborhood.edges())
                    .addClass("faded");
                neighborhood.addClass("highlighted");
            });
        }

        function refreshEmphasis() {
            if (!includeDependencies) {
                return;
            }
            // Hover wins while exploring; selection sticks after the pointer leaves.
            if (hoveredCard) {
                emphasizeAround(hoveredCard);
                return;
            }
            const selected = cy.$("node:selected").filter(isCardNode);
            if (selected.length) {
                emphasizeAround(selected[0]);
                return;
            }
            clearEmphasis();
        }

        cy.on("mousemove", "node", function (event) {
            updateCardCursor(
                event.target,
                event.renderedPosition.x,
                event.renderedPosition.y,
                draggingCard
            );
        });
        cy.on("mouseover", "node", function (event) {
            updateCardCursor(
                event.target,
                event.renderedPosition.x,
                event.renderedPosition.y,
                draggingCard
            );
            if (!draggingCard && isCardNode(event.target)) {
                hoveredCard = event.target;
                refreshEmphasis();
            }
        });
        cy.on("grab", "node", function () {
            draggingCard = true;
            container.style.cursor = "grabbing";
        });
        cy.on("free", "node", function (event) {
            draggingCard = false;
            updateCardCursor(
                event.target,
                event.renderedPosition.x,
                event.renderedPosition.y,
                false
            );
            assignTaxiCorridors();
            refreshEmphasis();
        });
        cy.on("mouseout", "node", function () {
            if (!draggingCard) {
                container.style.cursor = "";
            }
            hoveredCard = null;
            refreshEmphasis();
        });
        cy.on("select", "node", function () {
            refreshEmphasis();
        });
        cy.on("unselect", "node", function () {
            refreshEmphasis();
        });
        cy.on("tap", function (event) {
            if (event.target === cy) {
                cy.$("node:selected").unselect();
                refreshEmphasis();
            }
        });

        // Tap fires only when the node was not dragged.
        cy.on("tap", "node", function (event) {
            const href = cardLinkAt(
                event.target,
                event.renderedPosition.x,
                event.renderedPosition.y
            );
            if (href) {
                window.open(href, "_blank", "noopener,noreferrer");
            }
        });

        container._cy = cy;
        container.setAttribute("tabindex", "0");
        return cy;
    }

    function scheduleGraphRender(container, data) {
        container._graphData = data;
        if (container._cy || container._graphPending) {
            return;
        }
        container._graphPending = true;
        container.classList.add("is-loading");

        const start = function () {
            const run = function () {
                try {
                    renderGraph(container, data);
                } finally {
                    container.classList.remove("is-loading");
                    container._graphPending = false;
                }
            };
            // Yield so first paint / LCP can complete before Cytoscape work.
            if (typeof window.requestIdleCallback === "function") {
                window.requestIdleCallback(run, { timeout: 400 });
            } else {
                window.setTimeout(run, 0);
            }
        };

        if (typeof IntersectionObserver !== "function") {
            start();
            return;
        }

        const observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) {
                        return;
                    }
                    observer.disconnect();
                    start();
                });
            },
            { root: null, rootMargin: "240px 0px", threshold: 0 }
        );
        observer.observe(container);
    }

    document.querySelectorAll(".releases-graph[data-graph]").forEach(function (container) {
        const dataElement = document.getElementById(container.getAttribute("data-graph"));
        if (!dataElement) {
            return;
        }

        scheduleGraphRender(container, JSON.parse(dataElement.textContent));
    });

    (function bindDependencyLineToggle() {
        const toggle = document.getElementById("show-dependency-lines");
        const container = document.querySelector(
            '.releases-graph[data-graph="release-graph-data"]'
        );
        if (!toggle || !container) {
            return;
        }
        toggle.addEventListener("change", function () {
            if (!container._graphData) {
                return;
            }
            renderGraph(container, container._graphData);
        });
    })();
});
