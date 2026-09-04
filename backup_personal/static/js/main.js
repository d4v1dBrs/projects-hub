document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. SKILLS MATRIX (RADAR CHART) ---
    const radarChart = echarts.init(document.getElementById('radarChart'));
    const radarOption = {
        backgroundColor: 'transparent',
        radar: {
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
        }]
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
        { id: 'BYMA', name: 'BYMA / BCRA / data912', symbolSize: 20, itemStyle: { color: '#222b3d' }, label: { position: 'bottom' } }
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
        animationDurationUpdate: 1500,
        animationEasingUpdate: 'quinticInOut',
        series: [
            {
                type: 'graph',
                layout: 'force',
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
                force: {
                    repulsion: 300,
                    edgeLength: [50, 100],
                    gravity: 0.1
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

    // --- 3. CAREER TIMELINE (Subway Map Style) ---
    const timelineChart = echarts.init(document.getElementById('timelineChart'));
    
    const timelineData = [
        // --- FINANCE ROLES (Cyan, Top) ---
        { id: 'start_fin', name: '2014', value: [15, 75], symbolSize: 1, label: { show: true, position: 'left', color: '#00f0ff', fontSize: 13, fontWeight: 'bold' }, itemStyle: { color: '#00f0ff' } },
        { id: 'bmb_1', name: 'Bull Market Brokers\n{sub|Trader}', value: [30, 75], symbolSize: 8, label: { show: true, position: 'bottom', color: '#fff', fontSize: 12, rich: { sub: { color: '#8b95a5', fontSize: 10, lineHeight: 18 } } }, itemStyle: { color: '#00f0ff' } },
        { id: 'bmb_2', name: 'Bull Market Brokers\n{sub|Head Trader}', value: [45, 75], symbolSize: 8, label: { show: true, position: 'bottom', color: '#fff', fontSize: 12, rich: { sub: { color: '#8b95a5', fontSize: 10, lineHeight: 18 } } }, itemStyle: { color: '#00f0ff' } },
        { id: 'criteria', name: 'Criteria ALyC\n{sub|Sales Trader IFAs}', value: [60, 75], symbolSize: 8, label: { show: true, position: 'bottom', color: '#fff', fontSize: 12, rich: { sub: { color: '#8b95a5', fontSize: 10, lineHeight: 18 } } }, itemStyle: { color: '#00f0ff' } },
        { id: 'branch_fin', name: '', value: [75, 75], symbolSize: 1, itemStyle: { color: '#00f0ff' } }, // Branch point
        { id: 'balanz_start', name: 'Balanz Capital\n{sub|Head S&T Strategy}', value: [85, 95], symbolSize: 8, label: { show: true, position: 'top', color: '#fff', fontSize: 12, fontWeight: 'bold', rich: { sub: { color: '#00f0ff', fontSize: 10, lineHeight: 18 } } }, itemStyle: { color: '#00f0ff' } },
        { id: 'end_fin', name: 'Present', value: [105, 95], symbolSize: 12, symbol: 'arrow', label: { show: false }, itemStyle: { color: '#00f0ff' } },
        
        // --- ACADEMIC ROLES (Orange, Bottom) ---
        { id: 'start_acad', name: '2011', value: [0, 40], symbolSize: 1, label: { show: true, position: 'left', color: '#ff9d00', fontSize: 13, fontWeight: 'bold' }, itemStyle: { color: '#ff9d00' } },
        { id: 'uba_ayu', name: 'UBA Ayudante\n{sub|Ayudante}', value: [15, 40], symbolSize: 8, label: { show: true, position: 'bottom', color: '#fff', fontSize: 12, rich: { sub: { color: '#8b95a5', fontSize: 10, lineHeight: 18 } } }, itemStyle: { color: '#ff9d00' } },
        { id: 'uba_prof', name: 'UBA 11+ yrs\n{sub|Professor}', value: [45, 40], symbolSize: 8, label: { show: true, position: 'bottom', color: '#fff', fontSize: 12, rich: { sub: { color: '#8b95a5', fontSize: 10, lineHeight: 18 } } }, itemStyle: { color: '#ff9d00' } },
        { id: 'branch_acad', name: '', value: [75, 40], symbolSize: 1, itemStyle: { color: '#ff9d00' } }, // Branch point
        { id: 'uca_prof', name: 'UCA 2+ yrs\n{sub|Professor}', value: [85, 25], symbolSize: 8, label: { show: true, position: 'bottom', color: '#fff', fontSize: 12, rich: { sub: { color: '#8b95a5', fontSize: 10, lineHeight: 18 } } }, itemStyle: { color: '#ff9d00' } },
        { id: 'end_uba', name: 'Present', value: [105, 40], symbolSize: 12, symbol: 'arrow', label: { show: false }, itemStyle: { color: '#ff9d00' } },
        { id: 'end_uca', name: 'Present', value: [105, 25], symbolSize: 12, symbol: 'arrow', label: { show: false }, itemStyle: { color: '#ff9d00' } },
        
        // --- HISTORICAL EVENTS (Floating Text) ---
        { id: 'event1', name: 'cepo, salida, PASO 2019, reperfilamiento,\npandemia, reestructuración, blanqueo', value: [65, 62], symbolSize: 1, label: { show: true, position: 'right', color: '#8b95a5', fontSize: 10, fontStyle: 'italic', lineHeight: 14 }, itemStyle: { color: 'transparent' } },
        { id: 'event2', name: 'cepo, salida, PASO 2019, reperfilamiento,\npandemia, reestructuración, blanqueo', value: [70, 84], symbolSize: 1, label: { show: true, position: 'right', color: '#8b95a5', fontSize: 10, fontStyle: 'italic', lineHeight: 14 }, itemStyle: { color: 'transparent' } }
    ];

    const timelineLinks = [
        // Finance Path
        { source: 'start_fin', target: 'bmb_1' },
        { source: 'bmb_1', target: 'bmb_2' },
        { source: 'bmb_2', target: 'criteria' },
        { source: 'criteria', target: 'branch_fin' },
        { source: 'branch_fin', target: 'balanz_start', lineStyle: { curveness: -0.4 } }, // Smooth S-curve upward
        { source: 'balanz_start', target: 'end_fin' },
        { source: 'branch_fin', target: 'event2', lineStyle: { width: 0 } }, // Invisible link to anchor text
        
        // Academic Path
        { source: 'start_acad', target: 'uba_ayu' },
        { source: 'uba_ayu', target: 'uba_prof' },
        { source: 'uba_prof', target: 'branch_acad' },
        { source: 'branch_acad', target: 'end_uba' },
        { source: 'branch_acad', target: 'uca_prof', lineStyle: { curveness: 0.4 } }, // Smooth S-curve downward
        { source: 'uca_prof', target: 'end_uca' }
    ];

    const timelineOption = {
        backgroundColor: 'transparent',
        grid: { top: 40, bottom: 40, left: 30, right: 30 },
        xAxis: { type: 'value', min: -5, max: 110, show: false },
        yAxis: { type: 'value', min: 0, max: 120, show: false },
        series: [
            {
                type: 'graph',
                layout: 'none',
                coordinateSystem: 'cartesian2d',
                symbolSize: 8,
                label: { show: true },
                edgeSymbol: ['none', 'none'],
                data: timelineData,
                links: timelineLinks,
                lineStyle: {
                    color: 'source', // CRITICAL: Makes lines inherit the node color (Cyan/Orange)
                    width: 6,
                    opacity: 1,
                    shadowBlur: 12
                },
                itemStyle: {
                    borderColor: '#171d29',
                    borderWidth: 2,
                    shadowBlur: 10
                }
            }
        ]
    };
    timelineChart.setOption(timelineOption);

    // Responsive handling
    window.addEventListener('resize', () => {
        radarChart.resize();
        nodeChart.resize();
        timelineChart.resize();
    });
});
