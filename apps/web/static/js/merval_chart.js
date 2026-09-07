document.addEventListener('DOMContentLoaded', () => {
    const timelineTab = document.getElementById('timelineTab');
    const mervalTab = document.getElementById('mervalTab');
    const timelineView = document.getElementById('timelineView');
    const mervalView = document.getElementById('mervalView');
    const mervalElement = document.getElementById('mervalChart');
    const subtitle = document.getElementById('marketViewSubtitle');
    const expandButton = document.getElementById('marketExpandButton');
    const dialog = document.getElementById('marketChartDialog');
    const dialogTitle = document.getElementById('marketDialogTitle');
    const dialogSubtitle = document.getElementById('marketDialogSubtitle');
    const dialogClose = document.getElementById('marketDialogClose');
    const dialogHost = document.getElementById('marketDialogChartHost');

    if (!timelineTab || !mervalTab || !timelineView || !mervalView || !mervalElement || !dialog) {
        return;
    }

    const viewCopy = {
        timeline: {
            title: 'Trayectoria profesional y ciclos del mercado argentino',
            subtitle: 'Pasá el cursor —o tocá— sobre un puesto o evento. En pantallas angostas, deslizá para recorrer los años.'
        },
        merval: {
            title: 'Merval medido en dólares CCL',
            subtitle: 'Serie ilustrativa 2011–2026, todavía no validada como histórico real. Tocá un hito para ver su contexto.'
        }
    };

    const anchors = [
        [2011.00, 790], [2011.83, 610], [2012.50, 520], [2013.50, 690],
        [2014.08, 890], [2014.58, 760], [2015.92, 840], [2016.33, 1110],
        [2017.92, 1760], [2018.42, 960], [2018.75, 730], [2019.58, 1010],
        [2019.67, 510], [2020.25, 360], [2020.75, 430], [2021.50, 430],
        [2022.50, 330], [2022.92, 440], [2023.67, 690], [2023.92, 560],
        [2024.50, 1390], [2024.92, 1680], [2025.33, 1510], [2025.92, 1830],
        [2026.67, 1910]
    ];

    const marketEvents = [
        {
            year: 2011.83,
            date: 'Oct 2011',
            short: 'Primer cepo',
            title: 'Instauración del primer cepo cambiario',
            detail: 'Comienzan las restricciones para comprar divisas y ganan relevancia operativa el CCL y el MEP.',
            labelPosition: 'top'
        },
        {
            year: 2014.42,
            date: 'Ene–Jul 2014',
            short: 'Devaluación + default',
            title: 'Devaluación y default técnico',
            detail: 'El salto del tipo de cambio y el litigio con los holdouts elevaron la volatilidad de bonos y dólares financieros.',
            labelPosition: 'bottom'
        },
        {
            year: 2018.45,
            date: 'Abr–Sep 2018',
            short: 'Sudden stop + FMI',
            title: 'Sudden stop, corrida cambiaria y acuerdo con el FMI',
            detail: 'La salida de capitales, la crisis de LEBAC y el acuerdo Stand-By con el FMI reconfiguraron tasas, bonos y FX.',
            labelPosition: 'top'
        },
        {
            year: 2019.70,
            date: 'Ago–Oct 2019',
            short: 'PASO + reperfilamiento',
            title: 'Shock post-PASO y reperfilamiento',
            detail: 'El Merval en dólares sufrió una caída récord, se devaluó el peso y se reperfiló deuda local de corto plazo.',
            labelPosition: 'top'
        },
        {
            year: 2020.72,
            date: 'Ago–Sep 2020',
            short: 'Canje + supercepo',
            title: 'Reestructuración soberana y supercepo',
            detail: 'El canje emitió nuevos Globales y Bonares mientras se endurecían las restricciones cambiarias.',
            labelPosition: 'bottom'
        },
        {
            year: 2022.52,
            date: 'Jun–Jul 2022',
            short: 'Corrida deuda CER',
            title: 'Crisis de liquidez en la curva CER',
            detail: 'La salida de fondos golpeó la deuda en pesos y disparó la volatilidad de los dólares financieros.',
            labelPosition: 'top'
        },
        {
            year: 2023.86,
            date: 'Ago–Dic 2023',
            short: 'Devaluación + BOPREAL',
            title: 'Devaluaciones e inicio de BOPREAL',
            detail: 'Los saltos cambiarios post-PASO y de diciembre dieron paso a BOPREAL para ordenar deuda comercial importadora.',
            labelPosition: 'top'
        },
        {
            year: 2024.42,
            date: '1S 2024',
            short: 'Licuación + ancla fiscal',
            title: 'Licuación monetaria y ancla fiscal',
            detail: 'La baja de tasas, la licuación de pasivos remunerados y el ajuste fiscal redefinieron las valuaciones locales.',
            labelPosition: 'bottom'
        },
        {
            year: 2025.30,
            date: 'Abr 2025',
            short: 'Salida del cepo',
            title: 'Flexibilización del régimen cambiario',
            detail: 'La salida del cepo redujo distorsiones entre mercados y abrió una nueva etapa para los flujos de capital.',
            labelPosition: 'top'
        }
    ];

    const interpolateValue = year => {
        const upperIndex = anchors.findIndex(anchor => anchor[0] >= year);
        if (upperIndex <= 0) {
            return anchors[0][1];
        }
        const lower = anchors[upperIndex - 1];
        const upper = anchors[upperIndex];
        const progress = (year - lower[0]) / (upper[0] - lower[0]);
        return lower[1] + ((upper[1] - lower[1]) * progress);
    };

    const monthlySeries = Array.from({ length: 189 }, (_, index) => {
        const year = 2011 + (index / 12);
        const baseline = interpolateValue(year);
        const texture = Math.sin(index * 0.83) * 28 + Math.sin(index * 0.21) * 19;
        return [Number(year.toFixed(4)), Math.max(250, Math.round(baseline + texture))];
    });

    const formatYearMonth = year => {
        const wholeYear = Math.floor(year);
        const monthIndex = Math.min(11, Math.round((year - wholeYear) * 12));
        const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
        return `${months[monthIndex]} ${wholeYear}`;
    };

    const formatValue = value => Math.round(value).toLocaleString('es-AR');

    const visibleLabelIndexes = (expanded, width) => {
        if (expanded && width >= 850) {
            return new Set(marketEvents.map((_, index) => index));
        }
        if (width < 650) {
            return new Set([0, 3, 8]);
        }
        if (width < 1000) {
            return new Set([0, 2, 3, 6, 8]);
        }
        return new Set([0, 1, 2, 3, 5, 6, 8]);
    };

    const buildMervalOption = expanded => {
        const width = mervalElement.getBoundingClientRect().width || window.innerWidth;
        const visibleLabels = visibleLabelIndexes(expanded, width);
        const eventData = marketEvents.map((event, index) => ({
            ...event,
            value: [event.year, Math.round(interpolateValue(event.year))],
            label: {
                show: visibleLabels.has(index),
                position: event.labelPosition,
                distance: expanded ? 10 : 7
            }
        }));

        return {
            animationDuration: 650,
            animationEasing: 'cubicOut',
            backgroundColor: 'transparent',
            grid: expanded
                ? { top: 86, right: 32, bottom: 66, left: 72, containLabel: false }
                : { top: 62, right: 22, bottom: 42, left: 62, containLabel: false },
            tooltip: {
                trigger: 'item',
                confine: true,
                className: 'merval-tooltip-shell',
                backgroundColor: '#0c121c',
                borderColor: '#28516d',
                borderWidth: 1,
                padding: 11,
                textStyle: { color: '#cbd5e1', fontFamily: 'Inter, sans-serif', fontSize: 10 },
                formatter: rawParams => {
                    const params = Array.isArray(rawParams)
                        ? rawParams.find(item => item.seriesName === 'Eventos de mercado') || rawParams[0]
                        : rawParams;
                    if (!params) {
                        return '';
                    }
                    if (params.seriesName === 'Eventos de mercado') {
                        const event = params.data;
                        return `<div class="merval-tooltip"><div class="merval-tooltip__date">${event.date}</div><div class="merval-tooltip__title">${event.title}</div><div class="merval-tooltip__value">Merval ilustrativo: US$ ${formatValue(event.value[1])}</div><div class="merval-tooltip__detail">${event.detail}</div></div>`;
                    }
                    const value = Array.isArray(params.value) ? params.value : params.data;
                    if (!Array.isArray(value)) {
                        return '';
                    }
                    return `<div class="merval-tooltip"><div class="merval-tooltip__date">${formatYearMonth(value[0])}</div><div class="merval-tooltip__value">US$ ${formatValue(value[1])}</div><div class="merval-tooltip__detail">Valor ilustrativo en dólares CCL.</div></div>`;
                }
            },
            xAxis: {
                type: 'value',
                min: 2011,
                max: 2026.75,
                interval: expanded && width >= 850 ? 1 : 2,
                axisLine: { lineStyle: { color: '#334155' } },
                axisTick: { show: false },
                axisLabel: {
                    color: '#64748b',
                    fontSize: expanded ? 10 : 9,
                    formatter: value => value <= 2026 ? String(Math.round(value)) : ''
                },
                splitLine: { show: false },
                axisPointer: {
                    show: true,
                    snap: true,
                    lineStyle: { color: 'rgba(255,255,255,0.2)', type: 'dashed' },
                    label: { show: false }
                }
            },
            yAxis: {
                type: 'value',
                min: 200,
                max: 2100,
                name: 'Puntos USD CCL · ilustrativo',
                nameLocation: 'end',
                nameGap: 14,
                nameTextStyle: { color: '#64748b', fontSize: expanded ? 10 : 8, align: 'left' },
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: {
                    color: '#64748b',
                    fontSize: expanded ? 10 : 9,
                    formatter: value => `US$ ${formatValue(value)}`
                },
                splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.15)', type: 'dashed' } }
            },
            series: [
                {
                    name: 'Merval / CCL',
                    type: 'line',
                    data: monthlySeries,
                    showSymbol: false,
                    smooth: 0.22,
                    lineStyle: {
                        color: '#00f0ff',
                        width: expanded ? 3 : 2,
                        shadowBlur: 12,
                        shadowColor: 'rgba(0, 240, 255, 0.38)'
                    },
                    areaStyle: {
                        color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(0, 240, 255, 0.28)' },
                            { offset: 0.72, color: 'rgba(0, 240, 255, 0.05)' },
                            { offset: 1, color: 'rgba(0, 240, 255, 0)' }
                        ])
                    },
                    emphasis: { focus: 'series' },
                    markLine: {
                        silent: true,
                        symbol: 'none',
                        label: { show: false },
                        lineStyle: { color: 'rgba(255, 157, 0, 0.13)', type: 'dashed', width: 1 },
                        data: marketEvents.map(event => ({ xAxis: event.year }))
                    },
                    z: 2
                },
                {
                    name: 'Eventos de mercado',
                    type: 'scatter',
                    data: eventData,
                    symbol: 'diamond',
                    symbolSize: expanded ? 12 : 10,
                    itemStyle: {
                        color: '#ff9d00',
                        borderColor: '#171d29',
                        borderWidth: 2,
                        shadowBlur: 9,
                        shadowColor: 'rgba(255, 157, 0, 0.55)'
                    },
                    label: {
                        formatter: params => `{date|${params.data.date}}\n{event|${params.data.short}}`,
                        rich: {
                            date: { color: '#ffd18a', fontSize: expanded ? 9 : 8, fontWeight: 600, lineHeight: 12 },
                            event: { color: '#8f9caf', fontSize: expanded ? 9 : 8, lineHeight: 11, width: expanded ? 112 : 88, overflow: 'break' }
                        }
                    },
                    emphasis: {
                        scale: 1.45,
                        itemStyle: { color: '#ffffff', borderColor: '#00f0ff' }
                    },
                    z: 6
                }
            ]
        };
    };

    let activeView = 'timeline';
    let mervalChart = null;
    let expandedMerval = false;
    let movedChart = null;
    let restoreFocus = null;
    let resizeFrame = null;

    const updateMervalDetail = event => {
        const chartShell = mervalElement.closest('.merval-chart-shell');
        const detailDate = chartShell?.querySelector('.merval-detail__date');
        const detailCopy = chartShell?.querySelector('.merval-detail__copy');
        if (detailDate && detailCopy) {
            detailDate.textContent = event.date;
            detailCopy.textContent = `${event.title}. ${event.detail}`;
        }
    };

    const renderMerval = expanded => {
        if (!mervalChart) {
            mervalChart = window.echarts.init(mervalElement, null, { renderer: 'canvas' });
            mervalChart.on('click', params => {
                if (params.seriesName === 'Eventos de mercado') {
                    updateMervalDetail(params.data);
                }
            });
        }
        expandedMerval = expanded;
        mervalChart.setOption(buildMervalOption(expanded), true);
        mervalChart.resize();
    };

    const resizeActiveChart = () => {
        window.cancelAnimationFrame(resizeFrame);
        resizeFrame = window.requestAnimationFrame(() => {
            const timelineElement = document.getElementById('timelineChart');
            if (activeView === 'timeline' && timelineElement) {
                window.echarts.getInstanceByDom(timelineElement)?.resize();
            }
            if (activeView === 'merval' && mervalChart) {
                renderMerval(expandedMerval);
            }
        });
    };

    const selectView = viewName => {
        activeView = viewName;
        const timelineSelected = viewName === 'timeline';
        timelineTab.setAttribute('aria-selected', String(timelineSelected));
        timelineTab.tabIndex = timelineSelected ? 0 : -1;
        mervalTab.setAttribute('aria-selected', String(!timelineSelected));
        mervalTab.tabIndex = timelineSelected ? -1 : 0;
        timelineView.hidden = !timelineSelected;
        mervalView.hidden = timelineSelected;
        subtitle.textContent = viewCopy[viewName].subtitle;
        expandButton.setAttribute('aria-label', `Abrir ${viewName === 'timeline' ? 'Timeline' : 'Merval USD CCL'} en vista completa`);
        expandButton.title = expandButton.getAttribute('aria-label');

        window.requestAnimationFrame(() => {
            if (viewName === 'merval') {
                renderMerval(false);
            } else {
                resizeActiveChart();
            }
        });
    };

    const openDialog = () => {
        if (dialog.open) {
            return;
        }
        const wrapper = activeView === 'timeline'
            ? timelineView.querySelector('.timeline-layout-shell')
            : mervalView.querySelector('.merval-chart-shell');
        if (!wrapper) {
            return;
        }

        const placeholder = document.createComment(`${activeView}-chart-home`);
        wrapper.parentNode.insertBefore(placeholder, wrapper);
        movedChart = { wrapper, placeholder };
        restoreFocus = document.activeElement;
        dialogTitle.textContent = viewCopy[activeView].title;
        dialogSubtitle.textContent = viewCopy[activeView].subtitle;
        dialogHost.classList.toggle('market-dialog__chart-host--timeline', activeView === 'timeline');
        dialogHost.appendChild(wrapper);
        document.body.classList.add('market-dialog-open');
        dialog.showModal();

        window.requestAnimationFrame(() => {
            if (activeView === 'merval') {
                renderMerval(true);
            } else {
                resizeActiveChart();
            }
        });
    };

    const restoreChart = () => {
        if (!movedChart) {
            document.body.classList.remove('market-dialog-open');
            return;
        }
        const { wrapper, placeholder } = movedChart;
        placeholder.parentNode.insertBefore(wrapper, placeholder);
        placeholder.remove();
        movedChart = null;
        dialogHost.classList.remove('market-dialog__chart-host--timeline');
        document.body.classList.remove('market-dialog-open');

        window.requestAnimationFrame(() => {
            if (activeView === 'merval') {
                renderMerval(false);
            } else {
                resizeActiveChart();
            }
            if (restoreFocus instanceof HTMLElement) {
                restoreFocus.focus();
            }
        });
    };

    const tabButtons = [timelineTab, mervalTab];
    tabButtons.forEach(button => {
        button.addEventListener('click', () => selectView(button.dataset.marketView));
        button.addEventListener('keydown', event => {
            const currentIndex = tabButtons.indexOf(button);
            let targetIndex = null;
            if (event.key === 'ArrowRight') {
                targetIndex = (currentIndex + 1) % tabButtons.length;
            } else if (event.key === 'ArrowLeft') {
                targetIndex = (currentIndex - 1 + tabButtons.length) % tabButtons.length;
            } else if (event.key === 'Home') {
                targetIndex = 0;
            } else if (event.key === 'End') {
                targetIndex = tabButtons.length - 1;
            }
            if (targetIndex !== null) {
                event.preventDefault();
                tabButtons[targetIndex].focus();
                selectView(tabButtons[targetIndex].dataset.marketView);
            }
        });
    });

    expandButton.addEventListener('click', openDialog);
    dialogClose.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', restoreChart);
    dialog.addEventListener('click', event => {
        const bounds = dialog.getBoundingClientRect();
        const outside = event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom;
        if (outside) {
            dialog.close();
        }
    });
    window.addEventListener('resize', resizeActiveChart);

    selectView('timeline');
});
