document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. SKILLS MATRIX (RADAR CHART) ---
    const radarChart = echarts.init(document.getElementById('radarChart'));
    const radarOption = {
        backgroundColor: 'transparent',
        radar: {
            center: ['50%', '52%'],
            radius: '58%',
            indicator: [
                { name: 'Mercado de Capitales', max: 100 },
                { name: 'Sales & Trading', max: 100 },
                { name: 'Derivados y\nCobertura', max: 100 },
                { name: 'Análisis de datos\naplicado a mercado', max: 100 },
                { name: 'Gestión\nActiva de\nCarteras', max: 100 },
                { name: 'Liderazgo\nde mesa', max: 100 }
            ],
            splitNumber: 4,
            axisName: {
                color: '#8b95a5',
                fontSize: 10,
                lineHeight: 12
            },
            splitLine: {
                lineStyle: {
                    color: 'rgba(255, 255, 255, 0.1)'
                }
            },
            splitArea: {
                show: false
            },
            axisLine: {
                lineStyle: {
                    color: 'rgba(255, 255, 255, 0.1)'
                }
            }
        },
        series: [{
            type: 'radar',
            data: [
                {
                    value: [95, 98, 90, 85, 92, 95],
                    name: 'Skills',
                    itemStyle: {
                        color: '#00f0ff'
                    },
                    areaStyle: {
                        color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
                            { color: 'rgba(0, 240, 255, 0.1)', offset: 0 },
                            { color: 'rgba(0, 240, 255, 0.4)', offset: 1 }
                        ])
                    },
                    lineStyle: {
                        width: 2,
                        color: '#00f0ff',
                        shadowBlur: 10,
                        shadowColor: '#00f0ff'
                    },
                    symbol: 'circle',
                    symbolSize: 6
                }
            ]
        }],
        media: [
            {
                query: { maxWidth: 340 },
                option: {
                    radar: {
                        center: ['50%', '52%'],
                        radius: '43%',
                        axisName: { fontSize: 9, lineHeight: 11 }
                    }
                }
            }
        ]
    };
    radarChart.setOption(radarOption);

    // --- 2. TECH STACK (NODE GRAPH) ---
    const nodeChart = echarts.init(document.getElementById('nodeChart'));
    
    // Data definition for nodes
    const graphData = [
        // Center Nodes
        { id: 'Python', name: 'Python', symbolSize: 45, itemStyle: { color: 'transparent', borderColor: '#00f0ff', borderWidth: 2, shadowBlur: 10, shadowColor: '#00f0ff' } },
        { id: 'SQL', name: 'SQL', symbolSize: 35, itemStyle: { color: 'transparent', borderColor: '#00f0ff', borderWidth: 2, shadowBlur: 10, shadowColor: '#00f0ff' } },
        
        // Python ecosystem (Right)
        { id: 'pandas', name: 'pandas', symbolSize: 20, itemStyle: { color: '#222b3d' }, label: { position: 'right' } },
        { id: 'NumPy', name: 'NumPy', symbolSize: 20, itemStyle: { color: '#222b3d' }, label: { position: 'right' } },
        { id: 'cvxpy', name: 'cvxpy', symbolSize: 20, itemStyle: { color: '#222b3d' }, label: { position: 'right' } },
        { id: 'PyPortfolioOpt', name: 'PyPortfolio Opt', symbolSize: 20, itemStyle: { color: '#222b3d' }, label: { position: 'right' } },
        { id: 'BlackLitterman', name: 'Black-Litterman', symbolSize: 20, itemStyle: { color: '#222b3d' }, label: { position: 'right' } },
        { id: 'CVaR', name: 'CVaR', symbolSize: 20, itemStyle: { color: '#222b3d' }, label: { position: 'right' } },
        { id: 'R', name: 'R', symbolSize: 20, itemStyle: { color: '#222b3d' }, label: { position: 'right' } },
        
        // Finance Tools (Top Left)
        { id: 'EIKON', name: 'EIKON', symbolSize: 25, itemStyle: { color: '#222b3d' }, label: { position: 'left' } },
        { id: 'Bloomberg', name: 'Bloomberg', symbolSize: 25, itemStyle: { color: '#222b3d' }, label: { position: 'left' } },
        { id: 'Excel', name: 'Excel', symbolSize: 25, itemStyle: { color: '#222b3d' }, label: { position: 'left' } },
        { id: 'PowerBI', name: 'Power BI', symbolSize: 25, itemStyle: { color: '#222b3d' }, label: { position: 'left' } },
        
        // Quant Analysis (Bottom Left)
        { id: 'CFA', name: 'Cfa Research', symbolSize: 25, itemStyle: { color: '#222b3d' }, label: { position: 'left' } },
        
        // APIs (Bottom)
        { id: 'APIs', name: 'APIs', symbolSize: 25, itemStyle: { color: '#222b3d' }, label: { position: 'bottom' } },
        {
            id: 'BYMA',
            name: 'BYMA / BCRA / data912',
            symbolSize: 20,
            itemStyle: { color: '#222b3d' },
            label: {
                position: 'bottom',
                formatter: 'BYMA / BCRA /\ndata912',
                align: 'center',
                lineHeight: 14
            }
        }
    ];

    const graphLinks = [
        { source: 'Python', target: 'pandas' },
        { source: 'Python', target: 'NumPy' },
        { source: 'Python', target: 'cvxpy' },
        { source: 'Python', target: 'PyPortfolioOpt' },
        { source: 'Python', target: 'BlackLitterman' },
        { source: 'Python', target: 'CVaR' },
        { source: 'Python', target: 'R' },
        
        { source: 'Python', target: 'EIKON' },
        { source: 'Python', target: 'Bloomberg' },
        { source: 'Python', target: 'Excel' },
        { source: 'Python', target: 'PowerBI' },
        
        { source: 'Python', target: 'CFA' },
        { source: 'Python', target: 'SQL' },
        
        { source: 'SQL', target: 'APIs' },
        { source: 'APIs', target: 'BYMA' }
    ];

    const nodeOption = {
        backgroundColor: 'transparent',
        tooltip: {},
        animation: false,
        series: [
            {
                type: 'graph',
                layout: 'force',
                left: 65,
                right: 80,
                top: 45,
                bottom: 45,
                data: graphData.map(node => ({
                    ...node,
                    label: {
                        show: true,
                        color: '#ffffff',
                        fontSize: 10,
                        backgroundColor: '#171d29',
                        padding: [4, 8],
                        borderRadius: 10,
                        borderWidth: 1,
                        borderColor: node.itemStyle.borderColor || '#222b3d',
                        ...node.label
                    }
                })),
                links: graphLinks,
                roam: true,
                labelLayout: params => {
                    const padding = 6;
                    const label = params.labelRect;
                    let dx = 0;
                    let dy = 0;

                    if (label.x < padding) dx = padding - label.x;
                    if (label.x + label.width > nodeChart.getWidth() - padding) {
                        dx = nodeChart.getWidth() - padding - label.x - label.width;
                    }
                    if (label.y < padding) dy = padding - label.y;
                    if (label.y + label.height > nodeChart.getHeight() - padding) {
                        dy = nodeChart.getHeight() - padding - label.y - label.height;
                    }
                    return { dx, dy, hideOverlap: false };
                },
                force: {
                    repulsion: 300,
                    edgeLength: [50, 100],
                    gravity: 0.1,
                    layoutAnimation: false
                },
                lineStyle: {
                    color: '#00f0ff',
                    opacity: 0.4,
                    width: 1,
                    curveness: 0.2
                }
            }
        ]
    };
    nodeChart.setOption(nodeOption);

    // --- 3. CAREER + ARGENTINE MARKET TIMELINE ---
    const timelineChart = echarts.init(document.getElementById('timelineChart'));

    const financeCareer = [
        {
            value: [2014, 82],
            date: 'Ene-Dic 2014',
            labelDate: '2014',
            company: 'Bull Market Brokers',
            shortCompany: 'Bull Market',
            role: 'Treasurer',
            label: { position: 'bottom' },
            summary: 'Gestión integral de la tesorería operativa, los flujos de fondos y las obligaciones de liquidación del bróker.',
            responsibilities: [
                'Administración de transferencias y cupos operativos de clientes.',
                'Pago de obligaciones con BYMA, ROFEX, MAE y contrapartes.',
                'Diseño de un sistema online para controlar acreditaciones pendientes.',
                'Optimización de procedimientos ante auditores y organismos de control.'
            ],
            detail: 'Fue mi entrada al ecosistema operativo del mercado: entendí la cadena de liquidación, compliance y tesorería que sostiene cada operación.'
        },
        {
            value: [2015, 82],
            date: 'Ene 2015-Jun 2017',
            labelDate: '2015',
            company: 'Bull Market Brokers',
            shortCompany: 'Bull Market',
            role: 'Head Trader',
            label: { position: 'top' },
            summary: 'Conducción de la Mesa de Operaciones, gestionando carteras de clientes preferenciales y la cartera propia de la firma.',
            responsibilities: [
                'Monitoreo y rebalanceo de carteras administradas con foco riesgo-retorno.',
                'Estrategias direccionales y de arbitraje en MERVAL y ROFEX.',
                'Automatización del seguimiento de posiciones y del control de riesgo.',
                'Coordinación de ocho asesores y cobertura de clientes de alta complejidad.'
            ],
            detail: 'El P&L de la mesa, la experiencia del cliente y el desempeño del equipo dependían de decisiones tomadas en tiempo real. Allí consolidé criterio de trader y visión de líder comercial.'
        },
        {
            value: [2017.5, 82],
            date: 'Jul 2017-Mar 2019',
            labelDate: '2017',
            company: 'Criteria ALyC',
            shortCompany: 'Criteria',
            role: 'Head Trader',
            label: { position: 'top' },
            summary: 'Responsabilidad sobre la Mesa de Operaciones y sobre la experiencia de clientes individuales e institucionales.',
            responsibilities: [
                'Acompañamiento personalizado a clientes individuales.',
                'Cobertura directa a tesoreros, portfolio managers y áreas de inversión.',
                'Soporte técnico y estratégico al equipo comercial.',
                'Gestión proactiva de clientes durante escenarios de estrés de mercado.'
            ],
            detail: 'Este rol profundizó mi capacidad para traducir la complejidad del mercado en decisiones concretas, velocidad de respuesta y confianza real para el cliente.'
        },
        {
            value: [2019.2, 82],
            date: 'Mar 2019-Feb 2024',
            labelDate: '2019',
            company: 'Balanz Capital',
            shortCompany: 'Balanz',
            role: 'Sales Trader | Independent Financial Advisors',
            label: { position: 'bottom' },
            summary: 'Servicio financiero B2B para intermediarios, conectando productos de alto valor con sus canales de distribución.',
            responsibilities: [
                'Cobertura operativa y comercial a Agentes de Negociación.',
                'Soporte a Productores en estrategia de distribución y capacitación.',
                'Ejecución, análisis y desarrollo de negocio conjunto con ALYCs.',
                'Coordinación institucional de productos y servicios con Bancos.'
            ],
            detail: 'Desarrollé una visión 360° del mercado al trabajar simultáneamente con la lógica del producto, del canal financiero y del cliente final.'
        },
        {
            value: [2024.1, 82],
            date: 'Feb 2024-Actualidad',
            labelDate: '2024',
            company: 'Balanz Capital',
            shortCompany: 'Balanz',
            role: 'Head of Sales & Trading Strategy · Productores',
            label: { position: 'top' },
            summary: 'Liderazgo de la Mesa de Sales & Trading de Productores, combinando estrategia comercial, ejecución y relaciones institucionales.',
            responsibilities: [
                'Cobertura B2B a ALYCs, AN, Bancos y Agentes Productores.',
                'Ejecución en renta fija, renta variable, fondos, ETPs y estructurados.',
                'Diseño de estrategias institucionales según riesgo, retorno y horizonte.',
                'Capacitación de contrapartes y desarrollo de herramientas en Python.'
            ],
            detail: 'La propuesta de la mesa no se limita a ejecutar: aporta criterio operativo, productos exclusivos de balance y compromiso de largo plazo con cada contraparte.'
        },
        { value: [2026.75, 82], date: 'Actualidad', company: '', role: '', symbol: 'arrow', symbolSize: 12 }
    ];

    const ubaCareer = [
        {
            value: [2012.2, 59],
            date: 'Mar-Dic 2012',
            labelDate: '2012',
            company: 'Universidad de Buenos Aires',
            shortCompany: 'UBA',
            role: 'Ayudante Adscripto · Economía CBC',
            summary: 'Primera experiencia docente universitaria en Economía dentro del Ciclo Básico Común.',
            responsibilities: [
                'Acompañamiento académico en la materia Economía.',
                'Apoyo al desarrollo de clases y al seguimiento de estudiantes.'
            ],
            detail: 'Esta etapa abrió una trayectoria docente que más adelante se integraría de forma permanente con mi carrera en mercados.'
        },
        { value: [2012.95, 59], date: '', company: '', role: '', symbolSize: 0 },
        '-',
        {
            value: [2015.2, 59],
            date: 'Mar 2015-Actualidad',
            labelDate: '2015',
            company: 'Universidad de Buenos Aires',
            shortCompany: 'UBA',
            role: 'Profesor de Administración Financiera',
            summary: 'Docencia en la Cátedra Tapia de la FCE-UBA, conectando rigor académico con la realidad macrofinanciera argentina.',
            responsibilities: [
                'Análisis de estados contables, flujos de fondos y performance.',
                'Decisiones de inversión, financiamiento y estructura de capital.',
                'Identificación, medición y cobertura del riesgo financiero.',
                'Impacto de inflación y tipo de cambio sobre decisiones empresariales.'
            ],
            detail: 'Las clases masivas y la diversidad de perfiles exigen adaptación constante, rigor técnico y una forma clara de explicar cómo las finanzas funcionan en contextos de alta volatilidad.'
        },
        { value: [2026.75, 59], date: 'Actualidad', company: '', role: '', symbol: 'arrow', symbolSize: 12 }
    ];

    const ucaCareer = [
        {
            value: [2024.1, 59],
            date: '',
            company: '',
            role: '',
            symbol: 'none',
            symbolSize: 0
        },
        {
            value: [2024.65, 43],
            date: 'Ago 2024-Actualidad',
            labelDate: '2024',
            company: 'Pontificia Universidad Católica Argentina',
            shortCompany: 'UCA',
            role: 'Profesor de la Escuela de Negocios',
            summary: 'Docencia de grado, MBA y posgrado en Finanzas, integrando teoría con operatoria real de mercado.',
            responsibilities: [
                'Mercado de Capitales y regulación del ecosistema financiero.',
                'Finanzas Corporativas y Valoración de Empresas.',
                'Derivados y estrategias de cobertura aplicadas al mercado local.',
                'Gestión de Carteras, Black-Litterman, Markowitz y CVaR.'
            ],
            detail: 'Enseño finanzas desde la mesa, no desde el manual: cada clase incorpora precios, carteras y decisiones tomadas durante esa misma semana.'
        },
        { value: [2026.75, 43], date: 'Actualidad', company: '', role: '', symbol: 'arrow', symbolSize: 12 }
    ];

    const marketContextAt = year => {
        if (year < 2012.2) return 'UBA · Licenciatura en Administración';
        if (year < 2014) return 'UBA · Ayudante Adscripto de Economía CBC / Licenciatura';
        if (year < 2015) return 'Bull Market · Treasurer';
        if (year < 2017.5) return 'Bull Market · Head Trader | UBA · Profesor';
        if (year < 2019.2) return 'Criteria · Head Trader | UBA · Profesor';
        if (year < 2024.1) return 'Balanz · Sales Trader IFAs | UBA · Profesor';
        if (year < 2024.65) return 'Balanz · Head S&T Strategy · Productores | UBA · Profesor';
        return 'Balanz · Head S&T Strategy · Productores | UBA + UCA · Profesor';
    };

    const marketEvents = [
        {
            value: [2011.8, 18],
            date: 'Oct 2011',
            short: 'Primer cepo',
            title: 'Primer cepo cambiario',
            detail: 'Comienzan las restricciones de AFIP y toma relevancia el dólar implícito CCL/MEP.',
            context: ''
        },
        {
            value: [2012.4, 18],
            date: 'Abr / Jul 2012',
            short: 'YPF + cepo ahorro',
            title: 'Expropiación de YPF y cierre del dólar ahorro',
            detail: 'Se expropia el 51% de YPF y luego se prohíbe el acceso al mercado de cambios para atesoramiento.',
            context: ''
        },
        {
            value: [2014.5, 18],
            date: 'Ene / Jul 2014',
            short: 'Devaluación + default',
            title: 'Devaluación y default técnico',
            detail: 'El tipo de cambio oficial salta de $6,50 a $8 y Argentina entra en default técnico tras el fallo Griesa.',
            context: ''
        },
        {
            value: [2015.95, 18],
            date: 'Dic 2015',
            short: 'Salida del cepo',
            title: 'Levantamiento del cepo',
            detail: 'Se unifica el mercado de cambios y comienza un esquema de flotación administrada.',
            context: ''
        },
        {
            value: [2016.3, 18],
            date: 'Abr 2016',
            short: 'Pago a holdouts',
            title: 'Pago a holdouts y regreso a los mercados',
            detail: 'Argentina cierra el litigio y vuelve al mercado internacional con una mega emisión soberana.',
            context: ''
        },
        {
            value: [2017.98, 18],
            date: 'Dic 2017',
            short: '28D',
            title: 'Cambio de metas de inflación: 28D',
            detail: 'La conferencia que modifica las metas del BCRA marca un quiebre de confianza y el inicio de la caída de bonos.',
            context: ''
        },
        {
            value: [2018.55, 18],
            date: 'Abr–Sep 2018',
            short: 'Sudden stop + FMI',
            title: 'Crisis cambiaria y acuerdo con el FMI',
            detail: 'El sudden stop dispara la corrida contra las LEBAC y deriva en el acuerdo Stand-By, luego ampliado a US$57.000 millones.',
            context: ''
        },
        {
            value: [2019.7, 18],
            date: 'Ago–Oct 2019',
            short: 'PASO + reperfilamiento',
            title: 'Colapso post-PASO, reperfilamiento y nuevo cepo',
            detail: 'El Merval cae 48% en dólares, se reperfila deuda local de corto plazo y el cupo cambiario termina reducido a US$200.',
            context: ''
        },
        {
            value: [2020.7, 18],
            date: 'Ago–Sep 2020',
            short: 'Canje + supercepo',
            title: 'Reestructuración soberana y supercepo',
            detail: 'Cierran los canjes bajo ley extranjera y local, nacen Globales y Bonares Step-Up y se endurecen los controles.',
            context: ''
        },
        {
            value: [2021.45, 18],
            date: 'Jun 2021',
            short: 'MSCI Standalone',
            title: 'Argentina pasa a mercado Standalone',
            detail: 'MSCI reclasifica a Argentina desde Mercado Emergente a la categoría Standalone.',
            context: ''
        },
        {
            value: [2022.55, 18],
            date: 'Jun–Sep 2022',
            short: 'Corrida CER + dólar soja',
            title: 'Crisis de deuda CER y primer dólar soja',
            detail: 'La corrida contra la curva CER tensiona la liquidez y luego aparece el primer tipo de cambio diferencial para exportadores.',
            context: ''
        },
        {
            value: [2023.75, 18],
            date: 'Ago / Dic 2023',
            short: 'Devaluación + BOPREAL',
            title: 'Saltos cambiarios y lanzamiento de BOPREAL',
            detail: 'Tras las PASO llega una devaluación del 22%; en diciembre se produce otro salto y comienzan las licitaciones de BOPREAL.',
            context: ''
        },
        {
            value: [2024.3, 18],
            date: '1S 2024',
            short: 'Licuación + ancla fiscal',
            title: 'Licuación de pasivos y ancla fiscal',
            detail: 'Bajan las tasas, se licúan pases del BCRA y el ajuste fiscal se convierte en el principal ancla macroeconómica.',
            context: ''
        },
        {
            value: [2025.3, 18],
            date: 'Abr 2025',
            short: 'Fin del cepo',
            title: 'Fin de las restricciones cambiarias',
            detail: 'Se normalizan los flujos de capital y convergen operativamente los dólares financieros.',
            context: ''
        },
        {
            value: [2026.25, 18],
            date: '1S 2026',
            short: 'Crédito corporativo',
            title: 'Nuevo régimen y reactivación de ONs',
            detail: 'El mercado se adapta al régimen estabilizado y recupera profundidad el crédito corporativo.',
            context: ''
        }
    ].map((event, index) => ({
        ...event,
        context: marketContextAt(event.value[0]),
        label: { position: index % 2 === 0 ? 'top' : 'bottom' }
    }));

    const createTimelineTextElement = (tagName, className, text) => {
        const element = document.createElement(tagName);
        if (className) element.className = className;
        if (text) element.textContent = text;
        return element;
    };

    const buildTimelineTextContent = () => {
        const container = document.getElementById('timelineTextContent');
        if (!container) return;

        const roleGroups = [
            { title: 'Carrera en mercados', items: financeCareer },
            { title: 'Docencia universitaria', items: [...ubaCareer, ...ucaCareer] }
        ];

        roleGroups.forEach(group => {
            const section = createTimelineTextElement('section', 'timeline-text-section');
            section.appendChild(createTimelineTextElement('h4', '', group.title));
            group.items
                .filter(item => item && typeof item === 'object' && item.company)
                .forEach(item => {
                    const card = createTimelineTextElement('article', 'timeline-text-card');
                    card.appendChild(createTimelineTextElement('div', 'timeline-text-card__period', item.date));
                    card.appendChild(createTimelineTextElement('h5', '', `${item.company} · ${item.role}`));
                    card.appendChild(createTimelineTextElement('p', '', item.summary));
                    card.appendChild(createTimelineTextElement('div', 'timeline-text-card__heading', 'Responsabilidades'));
                    const responsibilities = createTimelineTextElement('ul');
                    item.responsibilities.forEach(responsibility => {
                        responsibilities.appendChild(createTimelineTextElement('li', '', responsibility));
                    });
                    card.appendChild(responsibilities);
                    card.appendChild(createTimelineTextElement('div', 'timeline-text-card__heading', 'Detalle'));
                    card.appendChild(createTimelineTextElement('p', '', item.detail));
                    section.appendChild(card);
                });
            container.appendChild(section);
        });

        const marketSection = createTimelineTextElement('section', 'timeline-text-section');
        marketSection.appendChild(createTimelineTextElement('h4', '', 'Mercado argentino'));
        marketEvents.forEach(item => {
            const card = createTimelineTextElement('article', 'timeline-text-card');
            card.appendChild(createTimelineTextElement('div', 'timeline-text-card__period', item.date));
            card.appendChild(createTimelineTextElement('h5', '', item.title));
            card.appendChild(createTimelineTextElement('p', '', item.detail));
            card.appendChild(createTimelineTextElement('p', 'timeline-text-card__context', `Tu etapa: ${item.context}`));
            marketSection.appendChild(card);
        });
        container.appendChild(marketSection);
    };

    buildTimelineTextContent();

    const careerLabel = {
        show: true,
        position: 'top',
        distance: 8,
        formatter: params => params.data.company
            ? `{year|${params.data.labelDate}}  {company|${params.data.shortCompany}}\n{role|${params.data.role
                .replace(' | Independent Financial Advisors', ' · IFAs')
                .replace('Head of Sales & Trading Strategy · Productores', 'Head S&T · Productores')
                .replace('Ayudante Adscripto · Economía CBC', 'Ayudante · Economía CBC')
                .replace('Profesor de Administración Financiera', 'Profesor · Adm. Financiera')
                .replace('Profesor de la Escuela de Negocios', 'Profesor · Escuela de Negocios')}}`
            : '',
        rich: {
            year: { color: '#00f0ff', fontSize: 9, fontWeight: 600 },
            company: { color: '#ffffff', fontSize: 10, fontWeight: 600 },
            role: { color: '#8b95a5', fontSize: 9, lineHeight: 15 }
        }
    };

    const academicLabel = {
        ...careerLabel,
        position: 'bottom',
        rich: {
            year: { color: '#ff9d00', fontSize: 9, fontWeight: 600 },
            company: { color: '#ffffff', fontSize: 10, fontWeight: 600 },
            role: { color: '#8b95a5', fontSize: 9, lineHeight: 15 }
        }
    };

    const ucaLabel = {
        ...academicLabel,
        position: 'right',
        distance: 10,
        backgroundColor: 'rgba(23, 29, 41, 0.92)',
        padding: [3, 5],
        borderRadius: 4
    };

    const careerSeries = (name, data, color, label) => ({
        name,
        type: 'line',
        data,
        symbol: 'circle',
        symbolSize: 8,
        showSymbol: true,
        lineStyle: { color, width: 5, shadowBlur: 10, shadowColor: color },
        itemStyle: { color, borderColor: '#171d29', borderWidth: 2 },
        label,
        emphasis: { focus: 'series' },
        z: 4
    });

    const roleTooltip = item => {
        const responsibilities = item.responsibilities
            .map(responsibility => `<li>${responsibility}</li>`)
            .join('');
        return `<article class="timeline-tooltip timeline-tooltip--role">`
            + `<div class="timeline-tooltip__period">${item.date}</div>`
            + `<div class="timeline-tooltip__title">${item.company} · ${item.role}</div>`
            + `<p class="timeline-tooltip__summary">${item.summary}</p>`
            + `<div class="timeline-tooltip__heading">Responsabilidades</div>`
            + `<ul class="timeline-tooltip__list">${responsibilities}</ul>`
            + `<div class="timeline-tooltip__heading">Detalle</div>`
            + `<p class="timeline-tooltip__detail">${item.detail}</p>`
            + `</article>`;
    };

    const marketTooltip = item => `<article class="timeline-tooltip timeline-tooltip--market">`
        + `<div class="timeline-tooltip__period">${item.date}</div>`
        + `<div class="timeline-tooltip__title">${item.title}</div>`
        + `<p class="timeline-tooltip__detail">${item.detail}</p>`
        + `<div class="timeline-tooltip__context"><span>Tu etapa:</span> ${item.context}</div>`
        + `</article>`;

    const timelineOption = {
        backgroundColor: 'transparent',
        animationDuration: 900,
        grid: { top: 55, bottom: 82, left: 42, right: 38 },
        legend: { show: false },
        tooltip: {
            trigger: 'item',
            triggerOn: 'mousemove|click',
            appendTo: '#timelineTooltipPortal',
            className: 'timeline-tooltip-shell',
            confine: false,
            enterable: true,
            hideDelay: 250,
            backgroundColor: 'rgba(15, 20, 30, 0.97)',
            borderColor: '#334155',
            borderWidth: 1,
            padding: 12,
            textStyle: { color: '#dbe4f0', fontSize: 11 },
            position: (point, params, element, rect, size) => {
                const margin = 12;
                const gap = 16;
                const chartElement = timelineChart.getDom();
                const chartStyles = window.getComputedStyle(chartElement);
                const scrollContainer = chartElement.closest('.timeline-scroll');
                const portal = document.getElementById('timelineTooltipPortal');
                const portalRect = portal.getBoundingClientRect();
                const scrollLeft = scrollContainer.scrollLeft;
                const scrollTop = scrollContainer.scrollTop;
                const anchorLeft = point[0] + Number.parseFloat(chartStyles.paddingLeft);
                const anchorTop = point[1] + Number.parseFloat(chartStyles.paddingTop);
                const contentWidth = element.offsetWidth || size.contentSize[0];
                const contentHeight = element.offsetHeight || size.contentSize[1];
                const minLeft = scrollLeft + margin;
                const minTop = scrollTop + margin;
                const maxLeft = Math.max(minLeft, scrollLeft + portalRect.width - contentWidth - margin);
                const maxTop = Math.max(minTop, scrollTop + portalRect.height - contentHeight - margin);
                let left = anchorLeft + gap;
                let top = anchorTop - (contentHeight / 2);

                if (left + contentWidth + margin > scrollLeft + portalRect.width) {
                    left = anchorLeft - contentWidth - gap;
                }

                left = Math.max(minLeft, Math.min(left, maxLeft));
                top = Math.max(minTop, Math.min(top, maxTop));
                return [left, top];
            },
            formatter: params => {
                const tooltipParams = Array.isArray(params)
                    ? params.find(entry => entry.data?.company || entry.data?.title)
                    : params;
                if (!tooltipParams) return '';
                const item = tooltipParams.data;
                if (tooltipParams.seriesName === 'Mercado argentino') return marketTooltip(item);
                if (!item.company) return '';
                return roleTooltip(item);
            }
        },
        xAxis: {
            type: 'value',
            min: 2011,
            max: 2027,
            interval: 1,
            axisLine: { lineStyle: { color: '#334155' } },
            axisTick: { show: false },
            axisLabel: {
                color: '#64748b',
                fontSize: 9,
                formatter: value => value <= 2026 ? value : ''
            },
            splitLine: { show: false },
            axisPointer: {
                show: true,
                snap: true,
                lineStyle: { color: 'rgba(255,255,255,0.25)', type: 'dashed' },
                label: { show: false }
            }
        },
        yAxis: {
            type: 'value',
            min: 0,
            max: 100,
            show: false
        },
        series: [
            careerSeries('Carrera en mercados', financeCareer, '#00f0ff', careerLabel),
            careerSeries('Docencia UBA', ubaCareer, '#ff9d00', academicLabel),
            careerSeries('Docencia UCA', ucaCareer, '#ffb84d', ucaLabel),
            {
                name: 'Mercado argentino',
                type: 'line',
                data: [[2011, 18], [2026.45, 18]],
                symbol: 'none',
                silent: true,
                lineStyle: { color: '#64748b', width: 2 },
                markLine: {
                    silent: true,
                    symbol: 'none',
                    label: { show: false },
                    lineStyle: { color: 'rgba(148, 163, 184, 0.12)', type: 'dashed', width: 1 },
                    data: marketEvents.map(event => ({ xAxis: event.value[0] }))
                },
                z: 1
            },
            {
                name: 'Mercado argentino',
                type: 'scatter',
                data: marketEvents,
                symbol: 'diamond',
                symbolSize: 9,
                itemStyle: {
                    color: '#94a3b8',
                    borderColor: '#171d29',
                    borderWidth: 2,
                    shadowBlur: 8,
                    shadowColor: 'rgba(148, 163, 184, 0.6)'
                },
                label: {
                    show: true,
                    distance: 7,
                    formatter: params => `{date|${params.data.date}}\n{event|${params.data.short}}`,
                    rich: {
                        date: { color: '#cbd5e1', fontSize: 8, fontWeight: 600, lineHeight: 11 },
                        event: { color: '#7f8b9d', fontSize: 8, lineHeight: 10, width: 78, overflow: 'break' }
                    }
                },
                emphasis: {
                    scale: 1.5,
                    itemStyle: { color: '#ffffff', borderColor: '#00f0ff' }
                },
                z: 5
            }
        ]
    };
    timelineChart.setOption(timelineOption);

    // Responsive handling
    window.addEventListener('resize', () => {
        radarChart.resize();
        nodeChart.resize();
        const timelineElement = document.getElementById('timelineChart');
        if (timelineElement?.clientWidth && timelineElement.clientHeight) {
            timelineChart.resize();
        }
    });
});
