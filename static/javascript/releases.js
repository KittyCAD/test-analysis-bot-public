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
    const TIMELINE_MIN_GAP = 100;
    const GRAPH_PADDING = 24;
    const TIMELINE_RESERVE = 88;
    // Hour labels are ~9px; skip them when they would collide with day ticks or each other.
    const MIN_HOUR_GAP_FROM_DAY = 20;
    const MIN_HOUR_GAP_BETWEEN = 14;
    const MIN_DAY_GAP_FOR_HOURS = 56;
    const HOUR_MS = 60 * 60 * 1000;
    const DAY_MS = 24 * HOUR_MS;
    // Collapsed gaps occupy this much "time weight" on the compressed axis.
    const BREAK_DISPLAY_MS = 8 * HOUR_MS;

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
            stagger: Math.min(COLUMN_STAGGER, columnWidth * 0.12),
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
        // Collapse outliers while keeping same-day activity on a linear scale.
        return Math.max(median * 5, DAY_MS);
    }

    // Map real timestamps onto a Y axis that compresses large empty gaps.
    function buildCompressedTimeScale(times, firstRowY, pixelHeight) {
        const sortedAsc = uniqueSortedTimes(times);
        if (!sortedAsc.length) {
            return {
                timeToY: function () {
                    return firstRowY;
                },
                breaks: [],
            };
        }
        if (sortedAsc.length === 1) {
            return {
                timeToY: function () {
                    return firstRowY;
                },
                breaks: [],
            };
        }

        const threshold = gapThresholdMs(sortedAsc);
        const compressedAt = {};
        const breakMids = [];
        let cursor = 0;
        compressedAt[sortedAsc[0]] = 0;

        for (let i = 1; i < sortedAsc.length; i++) {
            const prev = sortedAsc[i - 1];
            const next = sortedAsc[i];
            const gap = next - prev;
            if (gap > threshold) {
                const breakStart = cursor;
                cursor += BREAK_DISPLAY_MS;
                breakMids.push(breakStart + BREAK_DISPLAY_MS / 2);
            } else {
                cursor += gap;
            }
            compressedAt[next] = cursor;
        }

        const maxCompressed = Math.max(cursor, 1);

        function timeToCompressed(timestamp) {
            if (Object.prototype.hasOwnProperty.call(compressedAt, timestamp)) {
                return compressedAt[timestamp];
            }
            if (timestamp <= sortedAsc[0]) {
                return 0;
            }
            if (timestamp >= sortedAsc[sortedAsc.length - 1]) {
                return maxCompressed;
            }
            for (let i = 1; i < sortedAsc.length; i++) {
                if (timestamp <= sortedAsc[i]) {
                    const t0 = sortedAsc[i - 1];
                    const t1 = sortedAsc[i];
                    const c0 = compressedAt[t0];
                    const c1 = compressedAt[t1];
                    const ratio = (timestamp - t0) / Math.max(t1 - t0, 1);
                    return c0 + ratio * (c1 - c0);
                }
            }
            return maxCompressed;
        }

        function timeToY(timestamp) {
            const compressed = timeToCompressed(timestamp);
            return (
                firstRowY +
                ((maxCompressed - compressed) / maxCompressed) * pixelHeight
            );
        }

        return {
            timeToY: timeToY,
            breaks: breakMids.map(function (mid) {
                return (
                    firstRowY +
                    ((maxCompressed - mid) / maxCompressed) * pixelHeight
                );
            }),
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

        const timelineHeight = Math.max(
            data.nodes.length * TIMELINE_MIN_GAP,
            520
        );
        const axisX = layout.axisX;
        const firstRowY = TIMELINE_FIRST_ROW_Y;
        const scale = buildCompressedTimeScale(times, firstRowY, timelineHeight);

        data.nodes.forEach(function (node) {
            const column = node.column || 0;
            if (!groups[column]) {
                groups[column] = [];
            }
            groups[column].push(node);
        });

        const elements = [];
        let maxContentY = firstRowY + timelineHeight;

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
            position: { x: axisX, y: firstRowY + timelineHeight },
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
            const y = scale.timeToY(timestamp);
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

        scale.breaks.forEach(function (y, index) {
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
                const y = scale.timeToY(timestamp);
                const tooCloseToDay = dayYs.some(function (dayY) {
                    return Math.abs(dayY - y) < MIN_HOUR_GAP_FROM_DAY;
                });
                if (tooCloseToDay) {
                    return;
                }
                const tooCloseToBreak = scale.breaks.some(function (breakY) {
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

            const placed = [];
            nodes.forEach(function (node, row) {
                const createdAt = Date.parse(node.createdAt);
                let y = scale.timeToY(createdAt);

                // Keep cards in the same column from stacking on top of each other.
                placed.forEach(function (previousY) {
                    if (Math.abs(y - previousY) < TIMELINE_MIN_GAP) {
                        y = previousY + TIMELINE_MIN_GAP;
                    }
                });
                placed.push(y);
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
                    style: {
                        width: 2,
                        "line-color": "#adb5bd",
                        "target-arrow-color": "#adb5bd",
                        "target-arrow-shape": "triangle",
                        "curve-style": "unbundled-bezier",
                        "control-point-distances": 40,
                        "control-point-weights": 0.5,
                        "z-index-compare": "manual",
                        "z-index": 1,
                    },
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
        if (includeDependencies) {
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

        if (data.layout === "columns-timeline" || data.layout === "columns") {
            // Keep column thirds at full panel width; grow height instead of shrinking.
            fitWidthAndGrow(cy, container, layout);
        }

        function cardLinkAt(node, renderedY) {
            if (
                node.data("isHeader") ||
                node.data("isTimelineDot") ||
                node.data("isTimelineBreak") ||
                node.data("isSpacer")
            ) {
                return "";
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
            if (!links.length) {
                return "";
            }
            if (links.length === 1) {
                return links[0];
            }
            const bb = node.renderedBoundingBox({ includeLabels: true });
            const ratio = (renderedY - bb.y1) / Math.max(bb.y2 - bb.y1, 1);
            // Split the card into equal bands for each link, with a small
            // drag-only gap between bands so grab remains available.
            const band = 1 / links.length;
            const gap = Math.min(0.06, band * 0.2);
            for (let i = 0; i < links.length; i++) {
                const start = i * band;
                const end = (i + 1) * band;
                if (ratio >= start + gap && ratio <= end - gap) {
                    return links[i];
                }
            }
            return "";
        }

        function updateCardCursor(node, renderedY, dragging) {
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
            container.style.cursor = cardLinkAt(node, renderedY)
                ? "pointer"
                : "grab";
        }

        let draggingCard = false;

        cy.on("mousemove", "node", function (event) {
            updateCardCursor(event.target, event.renderedPosition.y, draggingCard);
        });
        cy.on("mouseover", "node", function (event) {
            updateCardCursor(event.target, event.renderedPosition.y, draggingCard);
        });
        cy.on("grab", "node", function () {
            draggingCard = true;
            container.style.cursor = "grabbing";
        });
        cy.on("free", "node", function (event) {
            draggingCard = false;
            updateCardCursor(event.target, event.renderedPosition.y, false);
        });
        cy.on("mouseout", "node", function () {
            if (!draggingCard) {
                container.style.cursor = "";
            }
        });

        // Tap fires only when the node was not dragged.
        cy.on("tap", "node", function (event) {
            const href = cardLinkAt(event.target, event.renderedPosition.y);
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
