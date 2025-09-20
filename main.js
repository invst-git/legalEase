'use strict';

document.addEventListener('DOMContentLoaded', () => {
    // Dynamic API URL based on environment
    const BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
        ? 'http://127.0.0.1:8000' 
        : `${window.location.protocol}//${window.location.host}/api`;
    
    // Custom Notification System
    const showNotification = (message, type = 'info', duration = 5000) => {
        const container = document.getElementById('notification-container');
        if (!container) return;
        
        const notification = document.createElement('div');
        const notificationId = 'notification-' + Date.now();
        
        // Determine colors and icons based on type
        const typeConfig = {
            success: {
                bg: 'bg-green-50',
                border: 'border-green-200',
                text: 'text-green-800',
                icon: 'check_circle',
                iconColor: 'text-green-500'
            },
            error: {
                bg: 'bg-red-50',
                border: 'border-red-200',
                text: 'text-red-800',
                icon: 'error',
                iconColor: 'text-red-500'
            },
            warning: {
                bg: 'bg-yellow-50',
                border: 'border-yellow-200',
                text: 'text-yellow-800',
                icon: 'warning',
                iconColor: 'text-yellow-500'
            },
            info: {
                bg: 'bg-blue-50',
                border: 'border-blue-200',
                text: 'text-blue-800',
                icon: 'info',
                iconColor: 'text-blue-500'
            }
        };
        
        const config = typeConfig[type] || typeConfig.info;
        
        notification.id = notificationId;
        notification.className = `${config.bg} ${config.border} border rounded-lg shadow-lg p-4 max-w-sm transform transition-all duration-300 ease-in-out translate-x-full opacity-0`;
        
        notification.innerHTML = `
            <div class="flex items-start">
                <div class="flex-shrink-0">
                    <span class="material-symbols-outlined ${config.iconColor} text-xl">${config.icon}</span>
                </div>
                <div class="ml-3 flex-1">
                    <p class="${config.text} text-sm font-medium">${message}</p>
                </div>
                <div class="ml-4 flex-shrink-0">
                    <button onclick="removeNotification('${notificationId}')" class="inline-flex ${config.text} hover:opacity-75 focus:outline-none">
                        <span class="material-symbols-outlined text-lg">close</span>
                    </button>
                </div>
            </div>
        `;
        
        container.appendChild(notification);
        
        // Trigger animation
        setTimeout(() => {
            notification.classList.remove('translate-x-full', 'opacity-0');
        }, 10);
        
        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => {
                removeNotification(notificationId);
            }, duration);
        }
    };
    
    const removeNotification = (notificationId) => {
        const notification = document.getElementById(notificationId);
        if (notification) {
            notification.classList.add('translate-x-full', 'opacity-0');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    };
    
    // Custom Confirmation Modal
    const showConfirmation = (message, onConfirm, onCancel = null) => {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center p-4 z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-md w-full p-6 transform transition-all">
                <div class="flex items-center mb-4">
                    <span class="material-symbols-outlined text-yellow-500 text-2xl mr-3">warning</span>
                    <h3 class="text-lg font-semibold text-gray-900">Confirm Action</h3>
                </div>
                <p class="text-gray-600 mb-6">${message}</p>
                <div class="flex justify-end space-x-3">
                    <button id="confirm-cancel" class="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-300">
                        Cancel
                    </button>
                    <button id="confirm-ok" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-300">
                        Confirm
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const hideModal = () => {
            modal.classList.add('opacity-0');
            setTimeout(() => {
                if (modal.parentNode) {
                    modal.parentNode.removeChild(modal);
                }
            }, 300);
        };
        
        modal.querySelector('#confirm-ok').onclick = () => {
            hideModal();
            if (onConfirm) onConfirm();
        };
        
        modal.querySelector('#confirm-cancel').onclick = () => {
            hideModal();
            if (onCancel) onCancel();
        };
        
        // Close on backdrop click
        modal.onclick = (e) => {
            if (e.target === modal) {
                hideModal();
                if (onCancel) onCancel();
            }
        };
    };
    
    // Make functions globally available
    window.showNotification = showNotification;
    window.removeNotification = removeNotification;
    window.showConfirmation = showConfirmation;
    try { localStorage.removeItem('chimeraToken'); } catch (e) {}
    let appState = {
        token: null,
        selectedFile: null,
        currentAnalysis: {},
        conversationHistory: [],
        dashboardItems: [],
    };

    // --- DOM Element Cache ---
    const containers = {
        login: document.getElementById('login-container'),
        register: document.getElementById('register-container'),
        dashboard: document.getElementById('dashboard-container'),
        upload: document.getElementById('upload-container'),
        loading: document.getElementById('loading-container'),
        error: document.getElementById('error-container'),
        results: document.getElementById('results-container'),
        landing: document.getElementById('landing-container'),
    };
    const elements = {
        loginForm: document.getElementById('login-form'),
        registerForm: document.getElementById('register-form'),
        analysesList: document.getElementById('analyses-list'),
        dashboardSearch: document.getElementById('dashboard-search'),
        dashboardSort: document.getElementById('dashboard-sort'),
        fileInput: document.getElementById('file-upload-input'),
        selectedFileName: document.getElementById('selected-file-name'),
        fileSelectedContainer: document.getElementById('file-selected-container'),
        analyzeButton: document.getElementById('analyze-button'),
        errorMessage: document.getElementById('error-message'),
        simulationModal: document.getElementById('simulation-modal'),
        simulationModalContent: document.getElementById('simulation-modal-content'),
        queryForm: document.getElementById('query-form'),
        queryInput: document.getElementById('query-input'),
        conversationLog: document.getElementById('conversation-log'),
    };

    // --- API HELPER ---
    const apiCall = async (endpoint, options = {}) => {
        const headers = { ...options.headers };
        if (appState.token) {
            headers['Authorization'] = `Bearer ${appState.token}`;
        }
        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
            if (options.body) {
                options.body = JSON.stringify(options.body);
            }
        }
        options.headers = headers;
        const response = await fetch(`${BASE_URL}${endpoint}`, options);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'An unknown error occurred');
        }
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            return response.json();
        }
        return {};
    };

    // --- RENDER HELPERS ---
    const escapeHTML = (str = '') => str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');

    const renderInlineMarkdown = (str = '') => {
        return str.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    };

    const renderOracleAnswer = (answer = '', citation = '') => {
        const hasMultipart = /disclaimer:/i.test(answer) || /key clauses/i.test(answer) || /guidance/i.test(answer) || /final note/i.test(answer);
        if (!hasMultipart) {
            const safe = escapeHTML(answer);
            const formatted = renderInlineMarkdown(safe).replace(/\n/g, '<br>');
            return `
                <div class="text-left">
                    <div class="inline-block bg-gray-200 text-gray-800 rounded-lg px-3 py-2">${formatted}</div>
                    ${citation ? `<p class="text-xs text-gray-500 mt-1 border-l-2 pl-2 italic"><strong>Source:</strong> "${escapeHTML(citation)}"</p>` : ''}
                </div>`;
        }
        const lines = answer.split('\n').map(l => l.trim()).filter(Boolean);
        let html = '<div class="text-left"><div class="bg-gray-200 text-gray-800 rounded-lg px-4 py-3 inline-block text-sm">';
        let inList = false;
        const flushList = () => { if (inList) { html += '</ul>'; inList = false; } };
        const asHeading = (text, level = 4) => `<h${level} class="font-semibold ${level<=4 ? 'mb-2' : 'mt-2 mb-1'}">${escapeHTML(text)}</h${level}>`;
        lines.forEach(line => {
            if (/^disclaimer:/i.test(line)) {
                flushList();
                html += asHeading('Disclaimer', 4);
                html += `<p class="mb-2">${escapeHTML(line.replace(/^disclaimer:/i, '').trim())}</p>`;
                return;
            }
            if (/^key clauses that may be considered favorable to /i.test(line)) {
                flushList();
                html += asHeading(line, 5);
                return;
            }
            if (/^balanced factual analysis$/i.test(line)) {
                flushList();
                html += asHeading('Balanced factual analysis', 4);
                return;
            }
            if (/^guidance$/i.test(line)) {
                flushList();
                html += asHeading('Guidance', 4);
                return;
            }
            if (/^final note$/i.test(line)) {
                flushList();
                html += asHeading('Final note', 4);
                return;
            }
            if (/^(\*|-|•)\s+/.test(line)) {
                if (!inList) { html += '<ul class="list-disc list-inside space-y-1">'; inList = true; }
                html += `<li>${renderInlineMarkdown(escapeHTML(line.replace(/^(\*|-|•)\s+/, '')))}</li>`;
                return;
            }
            html += `<p class="mb-2">${renderInlineMarkdown(escapeHTML(line))}</p>`;
        });
        flushList();
        html += '</div></div>';
        return html;
    };

    // --- STATE MANAGEMENT & RENDERING ---
    const showState = (state) => {
        // Detach landing/login/register: route to dashboard instead
        if (state === 'landing' || state === 'login' || state === 'register') state = 'dashboard';
        Object.values(containers).forEach(c => c.classList.add('hidden'));
        if (containers[state]) containers[state].classList.remove('hidden');
        // Toggle Clause Oracle FAB visibility: show only on results page
        const coFab = document.getElementById('co-fab');
        if (coFab) {
            if (state === 'results') coFab.classList.remove('hidden');
            else coFab.classList.add('hidden');
        }
        // Toggle landing visibility: only show for explicit 'landing' state
        const landing = document.getElementById('landing-container');
        if (landing) {
            if (state === 'landing') {
                landing.classList.remove('hidden');
            } else {
                landing.classList.add('hidden');
            }
        }
        // Update global nav links per page
        const navToUpload = document.getElementById('nav-to-upload');
        const navToDashboard = document.getElementById('nav-to-dashboard');
        if (navToUpload && navToDashboard) {
            navToUpload.classList.remove('hidden');
            navToDashboard.classList.remove('hidden');
            if (state === 'upload') {
                navToUpload.classList.add('hidden'); // only show Dashboard on upload page
            } else if (state === 'dashboard') {
                navToDashboard.classList.add('hidden'); // only show Upload on dashboard page
            } // on results: show both
        }
        // Persist primary view so refresh keeps page
        try { localStorage.setItem('chimeraPage', state); } catch(e) {}
    };
    
    const updateDashboard = async () => {
        showState('dashboard');
        try {
            const items = await apiCall('/analyses/dashboard');
            appState.dashboardItems = Array.isArray(items) ? items : [];
            renderDashboardList();
            attachDashboardControls();
            const landing = document.getElementById('landing-container');
            if (landing) landing.classList.add('hidden');
        } catch (error) {
            console.error('Failed to fetch analyses:', error);
            // Stay on dashboard; authentication is disabled
        }
    };

    const getRiskTag = (risk) => {
        const level = (risk || '').toLowerCase();
        if (level === 'high') return '<span class="ml-2 text-red-700 text-xs font-semibold">🔴 High Risk</span>';
        if (level === 'medium') return '<span class="ml-2 text-yellow-700 text-xs font-semibold">🟡 Some Concerns</span>';
        return '<span class="ml-2 text-green-700 text-xs font-semibold">🟢 Standard</span>';
    };

    const formatDashboardDate = (iso) => {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            if (Number.isNaN(d.getTime())) {
                return String(iso).replace('T',' ').replace('Z','');
            }
            return d.toLocaleString(undefined, {
                year: 'numeric', month: 'short', day: '2-digit',
                hour: '2-digit', minute: '2-digit'
            });
        } catch (_) {
            return String(iso).replace('T',' ').replace('Z','');
        }
    };

    const renderDashboardList = () => {
        const query = (elements.dashboardSearch?.value || '').toLowerCase();
        const sort = elements.dashboardSort?.value || 'date_desc';
        let list = [...appState.dashboardItems];
        if (query) list = list.filter(i => (i.filename || '').toLowerCase().includes(query));
        list.sort((a, b) => {
            if (sort === 'date_asc') return (a.created_at || '').localeCompare(b.created_at || '');
            if (sort === 'alpha_asc') return (a.filename || '').localeCompare(b.filename || '');
            if (sort === 'alpha_desc') return (b.filename || '').localeCompare(a.filename || '');
            return (b.created_at || '').localeCompare(a.created_at || '');
        });
        if (!list.length) {
            elements.analysesList.innerHTML = '<p class="text-gray-500">No saved analyses yet.</p>';
            return;
        }
        elements.analysesList.innerHTML = list.map(i => `
            <div class="w-full p-3 border rounded hover:bg-gray-50">
                <div class="flex items-center w-full gap-3">
                    <button data-analysis-id="${i.id}" class="flex-1 min-w-0 text-left">
                        <span class="truncate font-medium">${i.filename || 'Untitled'}</span>
                    </button>
                    <span class="shrink-0 flex items-center gap-3 whitespace-nowrap">
                        <span class="text-xs text-gray-600 whitespace-nowrap tabular-nums">${i.created_at ? formatDashboardDate(i.created_at) : ''}</span>
                        ${getRiskTag(i.risk_level)}
                        <span role="button" class="risk-info-btn inline-flex items-center text-xs text-blue-600 hover:text-blue-800 cursor-pointer" title="Why this risk?" data-analysis-id="${i.id}">
                            <span class="material-symbols-outlined text-base">info</span>
                            <span class="ml-1 hidden sm:inline">Why?</span>
                        </span>
                        <button
                            class="export-pdf-btn inline-flex items-center text-xs text-green-600 hover:text-green-800 cursor-pointer px-2 py-1 rounded hover:bg-green-50"
                            title="Export PDF"
                            data-analysis-id="${i.id}">
                            <span class="material-symbols-outlined text-base">download</span>
                            <span class="ml-1 hidden sm:inline">Export</span>
                        </button>
                        <span
                            class="delete-analysis-btn material-symbols-outlined text-gray-400 hover:text-red-600 cursor-pointer"
                            title="Delete analysis"
                            data-analysis-id="${i.id}">delete</span>
                    </span>
                </div>
            </div>
        `).join('');
    };

    const attachDashboardControls = () => {
        if (elements.dashboardSearch && !elements.dashboardSearch._bound) {
            elements.dashboardSearch.addEventListener('input', renderDashboardList);
            elements.dashboardSearch._bound = true;
        }
        if (elements.dashboardSort && !elements.dashboardSort._bound) {
            elements.dashboardSort.addEventListener('change', renderDashboardList);
            elements.dashboardSort._bound = true;
        }
        if (elements.analysesList && !elements.analysesList._bound) {
            elements.analysesList.addEventListener('click', async (e) => {
                // Handle delete button clicks first to avoid loading the analysis
                const del = e.target.closest('.delete-analysis-btn');
                if (del) {
                    const id = parseInt(del.getAttribute('data-analysis-id'));
                    if (!id) return;
                    showConfirmation('Delete this analysis? This cannot be undone.', async () => {
                        try {
                            await apiCall(`/analyses/${id}`, { method: 'DELETE' });
                            appState.dashboardItems = appState.dashboardItems.filter(x => x.id !== id);
                            renderDashboardList();
                            showNotification('Analysis deleted successfully.', 'success');
                        } catch (err) {
                            showNotification('Failed to delete analysis.', 'error');
                        }
                    });
                    return;
                }
                // Handle export PDF button click
                const exportBtn = e.target.closest('.export-pdf-btn');
                if (exportBtn) {
                    const id = parseInt(exportBtn.getAttribute('data-analysis-id'));
                    if (id) {
                        e.preventDefault();
                        e.stopPropagation();
                        await exportAnalysisPDF(id);
                    }
                    return;
                }
                // Handle risk info click
                const info = e.target.closest('.risk-info-btn');
                if (info) {
                    const id = parseInt(info.getAttribute('data-analysis-id'));
                    if (id) {
                        e.preventDefault();
                        e.stopPropagation();
                        await openRiskInfo(id);
                    }
                    return;
                }
                const btn = e.target.closest('button[data-analysis-id]');
                if (!btn) return;
                const id = parseInt(btn.getAttribute('data-analysis-id'));
                if (id) loadAnalysis(id);
            });
            elements.analysesList._bound = true;
        }
    };

    const openRiskInfo = async (analysisId) => {
        try {
            const data = await apiCall(`/analyses/${analysisId}`);
            const levelRaw = (data.risk_level || '').toLowerCase();
            const levelMap = { high: 'High Risk', medium: 'Some Concerns', low: 'Standard' };
            const colorMap = {
                high: 'bg-red-100 text-red-700',
                medium: 'bg-yellow-100 text-yellow-800',
                low: 'bg-green-100 text-green-700'
            };
            const levelText = levelMap[levelRaw] || 'Standard';
            const levelClass = colorMap[levelRaw] || colorMap.low;
            const reason = (data.risk_reason || '').trim() || 'No justification available.';

            const modal = document.getElementById('risk-modal');
            const title = document.getElementById('risk-modal-title');
            const levelEl = document.getElementById('risk-modal-level');
            const reasonEl = document.getElementById('risk-modal-reason');
            const closeBtn = document.getElementById('risk-modal-close');
            const okBtn = document.getElementById('risk-modal-ok');

            title.textContent = 'Risk Justification';
            levelEl.className = `inline-flex items-center text-sm font-semibold px-2 py-1 rounded ${levelClass}`;
            levelEl.textContent = levelText;
            reasonEl.textContent = reason;

            modal.classList.remove('hidden');

            const hide = () => modal.classList.add('hidden');
            closeBtn.onclick = hide;
            okBtn.onclick = hide;
            // Close on backdrop click
            modal.addEventListener('click', (ev) => { if (ev.target === modal) hide(); }, { once: true });

        } catch (err) {
            showNotification('Failed to load risk justification.', 'error');
        }
    };

    const exportAnalysisPDF = async (analysisId) => {
        try {
            // Show loading state
            const exportBtn = document.querySelector(`.export-pdf-btn[data-analysis-id="${analysisId}"]`);
            if (exportBtn) {
                const originalContent = exportBtn.innerHTML;
                exportBtn.innerHTML = '<span class="material-symbols-outlined text-base animate-spin">refresh</span><span class="ml-1">Exporting...</span>';
                exportBtn.disabled = true;
                
                // Reset after 3 seconds regardless of outcome
                setTimeout(() => {
                    exportBtn.innerHTML = originalContent;
                    exportBtn.disabled = false;
                }, 3000);
            }

            // Call the export endpoint
            const response = await fetch(`${BASE_URL}/analyses/${analysisId}/export`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${appState.token}`,
                }
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Export failed');
            }

            // Get the filename from the Content-Disposition header
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `analysis_${analysisId}_export.pdf`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }

            // Create blob and download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            // Show success message
            if (exportBtn) {
                const originalContent = exportBtn.innerHTML;
                exportBtn.innerHTML = '<span class="material-symbols-outlined text-base text-green-600">check</span><span class="ml-1 text-green-600">Exported!</span>';
                setTimeout(() => {
                    exportBtn.innerHTML = originalContent;
                    exportBtn.disabled = false;
                }, 2000);
            }

        } catch (error) {
            console.error('Export failed:', error);
            showNotification(`Export failed: ${error.message}`, 'error');
            
            // Reset button state
            const exportBtn = document.querySelector(`.export-pdf-btn[data-analysis-id="${analysisId}"]`);
            if (exportBtn) {
                exportBtn.innerHTML = '<span class="material-symbols-outlined text-base">download</span><span class="ml-1 hidden sm:inline">Export</span>';
                exportBtn.disabled = false;
            }
        }
    };

    const loadAnalysis = async (analysisId) => {
        try {
            showState('loading');
            const data = await apiCall(`/analyses/${analysisId}`);
            // Convert FullAnalysisResponse to currentAnalysis shape
            const ia = {
                id: data.id,
                filename: data.filename,
                assessment: data.assessment,
                key_info: data.key_info,
                identified_actions: data.identified_actions,
                extracted_text: data.extracted_text,
                page_images: data.page_images,
                created_at: data.created_at,
                risk_level: data.risk_level,
                risk_highlights: data.risk_highlights || [],
            };
            renderResults(ia);
            // Prefetch timeline in background so it is ready when user views the tab
            try { fetchTimeline(); } catch (e) {}
            // Load conversation history into state and UI
            appState.conversationHistory = Array.isArray(data.conversation) ? data.conversation : [];
            renderConversationLog(appState.conversationHistory);
        } catch (error) {
            showError(error.message);
        }
    };

    const renderConversationLog = (messages = []) => {
        // In-panel chat was removed; this remains to support popup prefill.
    };

    const renderResults = (data) => {
    appState.currentAnalysis = data;
    appState.conversationHistory = [];
    try { if (data?.id) localStorage.setItem('chimeraAnalysisId', String(data.id)); } catch(e) {}
    document.getElementById('assessment-text').textContent = data.assessment;
    const keyInfoList = document.getElementById('key-info-list');
    keyInfoList.innerHTML = '';
    if (data.key_info) {
        data.key_info.forEach((item, idx) => {
            const showRewrite = item.is_negotiable;
            const showBenchmark = false; // Hidden
            keyInfoList.innerHTML += `<div class="click-highlight flex flex-col sm:flex-row py-2 border-b border-gray-100 justify-between group" data-highlight-text="${encodeURIComponent(item.value || '')}" data-item-type="key" data-item-index="${idx}"><div><dt class="font-medium text-gray-600">${escapeHTML(item.key)}:</dt><dd class="text-gray-800 cursor-pointer" title="Click to highlight in document">${escapeHTML(item.value)}</dd></div><div class="flex items-center mt-2 sm:mt-0 ml-auto space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">${showBenchmark ? `<button disabled aria-disabled="true" data-key="${escapeHTML(item.key)}" data-clause="${escapeHTML(item.value)}" class="benchmark-btn px-2 py-1 text-xs font-semibold text-blue-600 bg-blue-100 rounded-full opacity-50 cursor-not-allowed">Benchmark</button>` : ''}${showRewrite ? `<button data-key="${escapeHTML(item.key)}" data-clause="${escapeHTML(item.value)}" class="rewrite-clause-btn px-2 py-1 text-xs font-semibold text-primary-600 bg-primary-100 rounded-full">Rewrite</button>` : ''}</div></div>`;
        });
    }
    const actionsList = document.getElementById('actions-list');
    actionsList.innerHTML = '';
    if (data.identified_actions?.length > 0) {
        data.identified_actions.forEach((item, idx) => {
            // NOW an item is an object with a .text property
            const showRewrite = item.is_negotiable;
            const showBenchmark = false; // Hidden
            actionsList.innerHTML += `
                <li class="click-highlight list-none border border-gray-200 rounded-lg bg-white p-3" data-highlight-text="${encodeURIComponent(item.text || '')}" data-item-type="action" data-item-index="${idx}">
                    <div class="flex items-start justify-between">
                        <div class="flex items-start min-w-0">
                            <span class="material-symbols-outlined text-primary-500 mr-3 mt-1 flex-shrink-0">circle</span>
                            <div class="min-w-0">
                                <div class="action-text max-h-12 min-h-12 overflow-hidden transition-all">
                                    <span class="action-original cursor-pointer" title="Click to highlight in document">${escapeHTML(item.text)}</span>
                                    <span class="action-eli5 hidden text-gray-700"></span>
                                </div>
                            </div>
                        </div>
                        <button type="button" class="expand-btn ml-3 text-gray-500 hover:text-gray-700 flex items-center justify-center h-8 w-8 rounded" title="Expand">
                            <span class="material-symbols-outlined">expand_more</span>
                        </button>
                    </div>
                    <div class="mt-3 flex flex-wrap gap-2 justify-end">
                        ${showBenchmark ? `<button disabled aria-disabled="true" data-key="Action Item" data-clause="${item.text}" class="benchmark-btn px-2 py-1 text-xs font-semibold text-blue-600 bg-blue-100 rounded opacity-50 cursor-not-allowed">Benchmark</button>` : ''}
                        ${showRewrite ? `<button data-key="Action Item" data-clause="${item.text}" class="rewrite-clause-btn px-2 py-1 text-xs font-semibold text-primary-600 bg-primary-100 rounded">Rewrite</button>` : ''}
                        <button data-clause="${item.text}" class="simulate-risk-btn px-2 py-1 text-xs font-semibold text-primary-600 bg-primary-100 rounded">Simulate Risk</button>
                        <button data-clause="${item.text}" class="eli5-toggle-btn px-2 py-1 text-xs font-semibold text-purple-700 bg-purple-100 rounded">Simplify</button>
                    </div>
                </li>`;
        });
    }
    const displayName = data.filename || (appState.selectedFile && appState.selectedFile.name) || 'Document';
    document.querySelector('#doc-viewer-filename span.truncate').textContent = displayName;
    const docViewerContent = document.getElementById('doc-viewer-content');
    docViewerContent.innerHTML = '';
    const isPdf = (data.filename || '').toLowerCase().endsWith('.pdf');
    const hasPageImages = Array.isArray(data.page_images) && data.page_images.length > 0;
    // Prepare containers for both modes
    const extractedContainer = document.createElement('div');
    extractedContainer.id = 'extracted-container';
    const exactContainer = document.createElement('div');
    exactContainer.id = 'exact-pdf-container';
    exactContainer.className = 'w-full h-[70vh] bg-white border rounded hidden';

    const showExactToggle = isPdf && !hasPageImages; // No toggle for scanned PDFs (which have page images)
    if (showExactToggle) {
        // Toggle switch: show either Exact PDF or Extracted content
        const controls = document.createElement('div');
        controls.className = 'flex items-center justify-between mb-2';
        controls.innerHTML = `
            <label class="flex items-center gap-3 text-sm text-gray-700 select-none">
              <span>Exact View (PDF)</span>
              <button id="exact-toggle" type="button" aria-pressed="false" class="relative inline-flex h-6 w-11 items-center rounded-full bg-gray-300 transition">
                <span class="sr-only">Toggle exact view</span>
                <span class="inline-block h-5 w-5 translate-x-0 transform rounded-full bg-white shadow transition"></span>
              </button>
            </label>`;
        docViewerContent.appendChild(controls);
        docViewerContent.appendChild(exactContainer);
        docViewerContent.appendChild(extractedContainer);

        const toggle = controls.querySelector('#exact-toggle');
        const knob = toggle.querySelector('span.inline-block');
        let exactOn = false;
        const ensurePdfLoaded = () => {
            if (!exactContainer.dataset.loaded) {
                exactContainer.innerHTML = `<iframe src="${BASE_URL}/analyses/${data.id}/file#view=FitH" title="Document" class="w-full h-full" style="border:0"></iframe>`;
                exactContainer.dataset.loaded = '1';
            }
        };
        const updateView = () => {
            if (exactOn) {
                toggle.setAttribute('aria-pressed', 'true');
                toggle.classList.remove('bg-gray-300');
                toggle.classList.add('bg-primary-600');
                knob.style.transform = 'translateX(20px)';
                ensurePdfLoaded();
                exactContainer.classList.remove('hidden');
                extractedContainer.classList.add('hidden');
            } else {
                toggle.setAttribute('aria-pressed', 'false');
                toggle.classList.add('bg-gray-300');
                toggle.classList.remove('bg-primary-600');
                knob.style.transform = 'translateX(0)';
                exactContainer.classList.add('hidden');
                extractedContainer.classList.remove('hidden');
            }
        };
        toggle.addEventListener('click', () => { exactOn = !exactOn; updateView(); });
        updateView();
    } else {
        // Non-PDF: only show extracted
        docViewerContent.appendChild(extractedContainer);
    }

    // Render extracted content inside extractedContainer
    const pagesWrap = document.createElement('div');
    if (Array.isArray(data.page_images) && data.page_images.length > 0) {
        data.page_images.forEach((src, index) => {
            const item = document.createElement('div');
            item.className = 'bg-white shadow-sm rounded p-2 mb-4 relative';
            item.innerHTML = `<h4 class="font-medium text-gray-800 mb-2 border-b pb-1">Page ${index + 1}</h4>`;
            const wrap = document.createElement('div');
            wrap.className = 'relative';
            const img = document.createElement('img');
            img.src = src;
            img.alt = `Page ${index + 1}`;
            img.loading = 'lazy';
            img.className = 'w-full h-auto rounded border border-gray-200';
            const overlay = document.createElement('div');
            overlay.className = 'highlight-overlay absolute inset-0 pointer-events-none';
            wrap.appendChild(img);
            wrap.appendChild(overlay);
            item.appendChild(wrap);
            pagesWrap.appendChild(item);
        });
    } else if (data.extracted_text?.length > 0) {
        data.extracted_text.forEach((pageText, index) => {
            const item = document.createElement('div');
            item.className = 'bg-white shadow-sm rounded p-4 mb-4';
            item.innerHTML = `<h4 class="font-medium text-gray-800 mb-2 border-b pb-1">Page ${index + 1}</h4><p class="page-text text-sm text-gray-700 whitespace-pre-wrap"></p>`;
            item.querySelector('p').textContent = pageText || 'No text.';
            pagesWrap.appendChild(item);
        });
    }
    extractedContainer.appendChild(pagesWrap);
    // Apply precomputed risk highlights immediately (use the first to avoid overlaps)
    try {
        if (Array.isArray(data.risk_highlights) && data.risk_highlights.length > 0) {
            applyHighlights(data.risk_highlights);
        }
    } catch (_) {}
    showState('results');
    // Reset tabs to Analysis view
    const panelAnalysis = document.getElementById('panel-analysis');
    const panelTimeline = document.getElementById('panel-timeline');
    const tabAnalysis = document.getElementById('tab-analysis');
    const tabTimeline = document.getElementById('tab-timeline');
    if (panelAnalysis && panelTimeline && tabAnalysis && tabTimeline) {
        panelAnalysis.classList.remove('hidden');
        panelTimeline.classList.add('hidden');
        tabAnalysis.classList.add('border-b-2','border-primary-600','text-primary-700','font-semibold');
        tabTimeline.classList.remove('border-b-2','border-primary-600','text-primary-700','font-semibold');
    }
};
    const showError = (errorMessage) => { elements.errorMessage.textContent = errorMessage; showState('error'); };

    // --- AUTH, MODALS, and other CORE LOGIC ---
    const login = async (email, password) => {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);
        try {
            const data = await apiCall('/token', { method: 'POST', body: formData });
            appState.token = data.access_token;
            localStorage.setItem('chimeraToken', appState.token);
            updateDashboard();
        } catch (error) { showNotification(`Login failed: ${error.message}`, 'error'); }
    };

    // Click-to-highlight handlers (temporarily disabled)
    // document.addEventListener('click', async (e) => {
    //     const el = e.target.closest('.click-highlight');
    //     if (!el) return;
    //     const text = decodeURIComponent(el.getAttribute('data-highlight-text') || '');
    //     const analysisId = appState.currentAnalysis?.id;
    //     if (!text || !analysisId) return;
    //     try {
    //         const data = await apiCall(`/analyses/${analysisId}/locate`, { method: 'POST', body: { text } });
    //         applyHighlights(data.matches || []);
    //     } catch (err) {
    //         console.warn('Locate failed', err);
    //     }
    // });

    const clearHighlights = () => {
        // Remove any previous overlay boxes quickly
        document.querySelectorAll('.hl-box').forEach(n => n.remove());
        // Unwrap previous mark without rebuilding entire paragraph
        document.querySelectorAll('.page-text mark').forEach(m => {
            const txt = document.createTextNode(m.textContent || '');
            m.replaceWith(txt);
        });
    };

    const applyHighlights = (matches = []) => {
        // Ensure extracted view is visible for highlighting
        const exactToggle = document.getElementById('exact-toggle');
        if (exactToggle && exactToggle.getAttribute('aria-pressed') === 'true') exactToggle.click();
        clearHighlights();
        const pages = Array.from(document.querySelectorAll('#extracted-container > div > div.bg-white'));
        let scrolled = false;
        // Group matches by page for efficient rendering
        const byPage = new Map();
        (matches || []).forEach(m => {
            const idx = m.page_index || 0;
            if (!byPage.has(idx)) byPage.set(idx, []);
            byPage.get(idx).push(m);
        });
        byPage.forEach((list, pageIdx) => {
            const pageEl = pages[pageIdx];
            if (!pageEl) return;
            const img = pageEl.querySelector('img');
            const overlay = pageEl.querySelector('.highlight-overlay');
            // Image overlays (scanned)
            if (img && overlay) {
                list.forEach(m => {
                    if (!Array.isArray(m.boxes)) return;
                    m.boxes.forEach(b => {
                        const box = document.createElement('div');
                        box.className = 'hl-box risk-hl-box absolute bg-yellow-300 bg-opacity-40 border border-yellow-500 rounded-sm';
                        box.style.left = `${b.x * 100}%`;
                        box.style.top = `${b.y * 100}%`;
                        box.style.width = `${b.w * 100}%`;
                        box.style.height = `${b.h * 100}%`;
                        box.title = 'Risk Highlight';
                        overlay.appendChild(box);
                    });
                });
                if (!scrolled) { pageEl.scrollIntoView({ behavior: 'auto', block: 'center' }); scrolled = true; }
                return;
            }
            // Text highlights (digital)
            const p = pageEl.querySelector('p.page-text');
            if (!p) return;
            const text = p.textContent || '';
            // Collect and merge ranges
            let ranges = list
                .filter(m => typeof m.char_start === 'number' && typeof m.char_end === 'number')
                .map(m => ({ s: Math.max(0, m.char_start), e: Math.min(text.length, m.char_end) }))
                .filter(r => r.e > r.s)
                .sort((a,b) => a.s - b.s || a.e - b.e);
            if (!ranges.length) return;
            const merged = [];
            for (const r of ranges) {
                if (!merged.length || r.s > merged[merged.length-1].e) {
                    merged.push({ s: r.s, e: r.e });
                } else {
                    merged[merged.length-1].e = Math.max(merged[merged.length-1].e, r.e);
                }
            }
            let html = '';
            let pos = 0;
            for (const r of merged) {
                if (pos < r.s) html += escapeHTML(text.slice(pos, r.s));
                const mid = escapeHTML(text.slice(r.s, r.e));
                html += `<mark class="bg-yellow-200 risk-hl" title="Risk Highlight">${mid}</mark>`;
                pos = r.e;
            }
            if (pos < text.length) html += escapeHTML(text.slice(pos));
            p.innerHTML = html;
            if (!scrolled) { p.scrollIntoView({ behavior: 'auto', block: 'center' }); scrolled = true; }
        });
    };
    const register = async (email, password) => {
        try {
            await apiCall('/users/', { method: 'POST', body: { email, password } });
            showNotification('Registration successful!', 'success');
            showState('dashboard');
        } catch (error) { showNotification(`Registration failed: ${error.message}`, 'error'); }
    };
    const logout = () => {
        appState.token = null;
        localStorage.removeItem('chimeraToken');
        showState('dashboard');
    };
    const handleFileSelect = (file) => {
        if (!file) return;
        const allowed = ['pdf','doc','docx','txt','rtf'];
        const ext = (file.name.split('.').pop() || '').toLowerCase();
        if (!allowed.includes(ext)) {
            if (elements.errorMessage) {
                elements.errorMessage.textContent = 'Unsupported file type. Allowed: PDF, DOC, DOCX, TXT, RTF.';
            }
            appState.selectedFile = null;
            if(elements.fileInput) elements.fileInput.value = '';
            if(elements.fileSelectedContainer) elements.fileSelectedContainer.classList.add('hidden');
            if(elements.analyzeButton) elements.analyzeButton.disabled = true;
            return;
        }
        if (elements.errorMessage) elements.errorMessage.textContent = '';
        appState.selectedFile = file;
        elements.selectedFileName.textContent = file.name;
        elements.fileSelectedContainer.classList.remove('hidden');
        elements.analyzeButton.disabled = false;
    };
    const resetUpload = () => {
        appState.selectedFile = null;
        if(elements.fileInput) elements.fileInput.value = '';
        if(elements.fileSelectedContainer) elements.fileSelectedContainer.classList.add('hidden');
        if(elements.analyzeButton) elements.analyzeButton.disabled = true;
    };
    const showModal = (content) => { elements.simulationModalContent.innerHTML = content; elements.simulationModal.classList.remove('hidden'); };
    const hideModal = () => elements.simulationModal.classList.add('hidden');
    
    const handleApiAction = async (actionType, button) => {
        const { key, clause } = button.dataset;
        const loadingMessages = { simulate: 'Simulating...', rewrite: 'Generating...', benchmark: 'Benchmarking...'};
        showModal(`<div class="text-center p-8"><div class="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto"></div><p class="mt-4">${loadingMessages[actionType]}</p></div>`);
        try {
            let endpoint, body, renderFunc;
            switch(actionType) {
                case 'simulate':
                    endpoint = '/simulate'; body = { clause_text: clause, document_context: appState.currentAnalysis.assessment, key_info: appState.currentAnalysis.key_info };
                    renderFunc = (data) => `<h3 class="text-xl font-semibold mb-4 text-primary-800">Risk Simulation</h3><p class="text-gray-700">${data.simulation_text}</p>`;
                    break;
                case 'rewrite':
                    endpoint = '/rewrite'; body = { clause_key: key, clause_text: clause, document_context: appState.currentAnalysis.assessment };
                    renderFunc = (data) => `<h3 class="text-xl font-semibold mb-4 text-primary-800">Negotiation Helper</h3><ul class="space-y-2 text-sm">${data.rewritten_clauses.map(c => `<li class="border-t pt-2">${c}</li>`).join('')}</ul>`;
                    break;
                case 'benchmark':
                    endpoint = '/benchmark'; body = { clause_text: clause, clause_key: key };
                    renderFunc = (data) => `<h3 class="text-xl font-semibold mb-2 text-blue-800">Clause Benchmark</h3><p class="text-lg p-3 bg-blue-50 rounded-md">${data.benchmark_result}</p><h4 class="text-sm font-semibold mt-4 mb-2">Examples of similar clauses:</h4><ul class="space-y-1">${data.examples.map(ex => `<li class="border-t py-2 text-xs text-gray-500 italic">"${ex}"</li>`).join('')}</ul>`;
                    break;
            }
            const data = await apiCall(endpoint, { method: 'POST', body });
            const modalContent = `<button id="close-modal-btn" class="absolute top-4 right-4 text-gray-400 hover:text-gray-600">&times;</button>${renderFunc(data)}`;
            showModal(modalContent);
        } catch (error) {
            const errorContent = `<button id="close-modal-btn" class="absolute top-4 right-4 text-gray-400 hover:text-gray-600">&times;</button><h3 class="text-xl font-semibold mb-4 text-red-700">Error</h3><p class="text-gray-700">Could not complete request: ${error.message}</p>`;
            showModal(errorContent);
        }
    };

    const handleQuery = async (question) => {
        const popupLog = document.getElementById('co-popup-log');
        const log = popupLog || elements.conversationLog;
        let thinkingId;
        if (log) {
            // Only auto-add user bubble if not inside popup (popup already adds it)
            if (!popupLog) {
                log.innerHTML += `<div class="text-right"><p class="inline-block bg-primary-600 text-white rounded-lg px-3 py-2">${question}</p></div>`;
            }
            thinkingId = `thinking-${Date.now()}`;
            log.innerHTML += `<div id="${thinkingId}" class="text-left"><p class="inline-block bg-gray-200 text-gray-800 rounded-lg px-3 py-2">Thinking...</p></div>`;
            log.scrollTop = log.scrollHeight;
        }

        try {
            const fullText = appState.currentAnalysis.extracted_text.join('\n\n');
            const data = await apiCall('/query', { method: 'POST', body: { question, full_text: fullText, history: appState.conversationHistory, analysis_id: appState.currentAnalysis?.id } });
            const aiResponseHtml = renderOracleAnswer(data.answer, data.citation);
            if (thinkingId) {
                const thinkingEl = document.getElementById(thinkingId);
                if (thinkingEl) thinkingEl.innerHTML = aiResponseHtml;
            }
            // Avoid duplicating the user message in history when popup is open
            if (!popupLog) {
                appState.conversationHistory.push({ role: 'user', content: question });
            }
            appState.conversationHistory.push({ role: 'assistant', content: data.answer });
        } catch (error) {
            if (thinkingId) {
                const thinkingEl = document.getElementById(thinkingId);
                if (thinkingEl) thinkingEl.innerHTML = `<div class="text-left"><p class="inline-block bg-red-100 text-red-700 rounded-lg px-3 py-2">Error: ${error.message}</p></div>`;
            }
        }
        if (log) log.scrollTop = log.scrollHeight;
    };

    // Toggle ELI5 view for a single action item
    const handleEli5Toggle = async (button) => {
        const li = button.closest('li');
        if (!li) return;
        const originalEl = li.querySelector('.action-original');
        const eli5El = li.querySelector('.action-eli5');
        if (!originalEl || !eli5El) return;

        const showingEli5 = !eli5El.classList.contains('hidden');
        // If already loaded, just toggle
        if (eli5El.dataset.loaded === '1') {
            if (showingEli5) {
                eli5El.classList.add('hidden');
                originalEl.classList.remove('hidden');
                button.textContent = 'ELI5';
            } else {
                originalEl.classList.add('hidden');
                eli5El.classList.remove('hidden');
                button.textContent = 'Original';
            }
            return;
        }

        // Fetch ELI5 explanation via existing /query endpoint (no persistence)
        const clause = button.getAttribute('data-clause') || originalEl.textContent || '';
        const prevLabel = button.textContent;
        button.textContent = '...';
        button.disabled = true;
        try {
            const fullText = (appState.currentAnalysis?.extracted_text || []).join('\n\n');
            const question = `Explain in very simple terms (ELI5) what this means: "${clause}". Use 1-2 short sentences.`;
            const data = await apiCall('/query', { method: 'POST', body: { question, full_text: fullText, history: [] } });
            eli5El.textContent = data.answer || 'No explanation available.';
            eli5El.dataset.loaded = '1';
            // Show ELI5 view
            originalEl.classList.add('hidden');
            eli5El.classList.remove('hidden');
            button.textContent = 'Original';
        } catch (err) {
            showNotification('Failed to load ELI5 explanation.', 'error');
            button.textContent = prevLabel;
        } finally {
            button.disabled = false;
        }
    };
    
    // Toggle expand/collapse for an action card to reveal full text
    const handleExpandToggle = (button) => {
        const li = button.closest('li');
        if (!li) return;
        const textBox = li.querySelector('.action-text');
        const icon = button.querySelector('.material-symbols-outlined');
        if (!textBox || !icon) return;
        const collapsed = textBox.classList.contains('max-h-12');
        if (collapsed) {
            textBox.classList.remove('max-h-12');
            textBox.classList.remove('overflow-hidden');
            icon.textContent = 'expand_less';
            button.title = 'Collapse';
        } else {
            textBox.classList.add('max-h-12');
            textBox.classList.add('overflow-hidden');
            icon.textContent = 'expand_more';
            button.title = 'Expand';
        }
    };
    
    // --- EVENT LISTENERS & INITIALIZER ---
    const init = () => {
        elements.loginForm.addEventListener('submit', (e) => { e.preventDefault(); login(e.target.elements['login-email'].value, e.target.elements['login-password'].value); });
        elements.registerForm.addEventListener('submit', (e) => { e.preventDefault(); register(e.target.elements['register-email'].value, e.target.elements['register-password'].value); });

        document.body.addEventListener('click', (e) => {
            const target = e.target.closest('[id]');
            if (!target) return;
            switch(target.id) {
                case 'show-register': e.preventDefault(); showState('register'); break;
                case 'show-login': e.preventDefault(); showState('login'); break;
                case 'logout-button': logout(); break;
                case 'show-upload': resetUpload(); showState('upload'); break;
                case 'back-to-dashboard': updateDashboard(); break;
                case 'try-again-button': showState('upload'); break;
                case 'browse-button': elements.fileInput.click(); break;
                case 'remove-file-button': resetUpload(); break;
                case 'analyze-another-button': showState('upload'); break;
                case 'close-modal-btn': hideModal(); break;
                case 'co-fab': openChatPopup(); break;
            }
        });

        if (elements.fileInput) elements.fileInput.addEventListener('change', (e) => handleFileSelect(e.target.files[0]));
        if (elements.queryForm) {
            elements.queryForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const question = elements.queryInput.value.trim();
                if (question) {
                    handleQuery(question);
                    elements.queryInput.value = '';
                }
            });
        }
        if (elements.simulationModal) elements.simulationModal.addEventListener('click', (e) => { if (e.target === elements.simulationModal) hideModal(); });
        // Global Nav: route links
        const navToUpload = document.getElementById('nav-to-upload');
        const navToDashboard = document.getElementById('nav-to-dashboard');
        if (navToUpload && !navToUpload._bound) {
            navToUpload.addEventListener('click', (e) => { e.preventDefault(); resetUpload(); showState('upload'); });
            navToUpload._bound = true;
        }
        if (navToDashboard && !navToDashboard._bound) {
            navToDashboard.addEventListener('click', (e) => { e.preventDefault(); updateDashboard(); });
            navToDashboard._bound = true;
        }
        
        if (containers.results) {
            containers.results.addEventListener('click', (e) => {
                const button = e.target.closest('button');
                if (!button) return;
                if (button.classList.contains('simulate-risk-btn')) handleApiAction('simulate', button);
                if (button.classList.contains('rewrite-clause-btn')) handleApiAction('rewrite', button);
                // Benchmark disabled: no-op on benchmark button clicks
                // if (button.classList.contains('benchmark-btn')) handleApiAction('benchmark', button);
                if (button.classList.contains('eli5-toggle-btn')) handleEli5Toggle(button);
                if (button.classList.contains('expand-btn')) handleExpandToggle(button);
                if (button.id === 'tab-analysis') {
                    document.getElementById('panel-analysis')?.classList.remove('hidden');
                    document.getElementById('panel-timeline')?.classList.add('hidden');
                    button.classList.add('border-b-2','border-primary-600','text-primary-700','font-semibold');
                    document.getElementById('tab-timeline')?.classList.remove('border-b-2','border-primary-600','text-primary-700','font-semibold');
                }
                if (button.id === 'tab-timeline') {
                    document.getElementById('panel-analysis')?.classList.add('hidden');
                    document.getElementById('panel-timeline')?.classList.remove('hidden');
                    button.classList.add('border-b-2','border-primary-600','text-primary-700','font-semibold');
                    document.getElementById('tab-analysis')?.classList.remove('border-b-2','border-primary-600','text-primary-700','font-semibold');
                    // Fetch timeline
                    fetchTimeline();
                }
            });
        }
        
        if (elements.analyzeButton) {
            elements.analyzeButton.addEventListener('click', async () => {
                if (!appState.selectedFile) return;
                const landing = document.getElementById('landing-container');
                if (landing) landing.classList.add('hidden');
                showState('loading');
                const formData = new FormData();
                formData.append('document', appState.selectedFile);
                try {
                    const data = await apiCall('/analyze', { method: 'POST', body: formData });
                    renderResults(data);
                    // Prefetch timeline in background post-analysis
                    try { fetchTimeline(); } catch (e) {}
                } catch (error) { showError(error.message); }
            });
        }
        // Restore last viewed page on refresh
        try {
            const saved = localStorage.getItem('chimeraPage');
            if (saved === 'upload') {
                showState('upload');
            } else if (saved === 'results') {
                const lastId = parseInt(localStorage.getItem('chimeraAnalysisId') || '');
                if (lastId) {
                    loadAnalysis(lastId);
                } else {
                    updateDashboard();
                }
            } else {
                updateDashboard();
            }
        } catch (e) {
            updateDashboard();
        }
    };
    init();

    // Chat popup: reuse existing Clause Oracle UI inside a modal-like overlay
    const renderConversationHtml = (messages = []) => {
        return (messages || []).map((m) => {
            const role = (m.role || '').toLowerCase();
            const content = m.content || '';
            if (role === 'user') {
                return `<div class="text-right"><p class="inline-block bg-primary-600 text-white rounded-lg px-3 py-2">${escapeHTML(content)}</p></div>`;
            }
            return renderOracleAnswer(content, '');
        }).join('');
    };
    const openChatPopup = () => {
        const logHtml = renderConversationHtml(appState.conversationHistory);
        const popup = document.createElement('div');
        popup.id = 'co-popup-overlay';
        popup.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm';
        const card = document.createElement('div');
        card.className = 'bg-white rounded-xl shadow-2xl w-full max-w-2xl p-4 relative';
        card.innerHTML = `
            <button id="co-close" class="absolute top-3 right-3 text-gray-500 hover:text-gray-700">&times;</button>
            <h3 class="text-lg font-semibold mb-3">Clause Oracle</h3>
            <div id="co-popup-log" class="space-y-4 mb-4 max-h-80 overflow-y-auto pr-2">${logHtml}</div>
            <form id="co-popup-form" class="flex items-center gap-2">
                <input type="text" id="co-popup-input" placeholder="Ask your document..." class="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-300">
                <button type="submit" class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center"><span class="material-symbols-outlined">send</span></button>
            </form>`;
        popup.appendChild(card);
        document.body.appendChild(popup);
        // Ensure we start scrolled to the latest messages
        const initialLog = card.querySelector('#co-popup-log');
        if (initialLog) initialLog.scrollTop = initialLog.scrollHeight;
        const close = () => { document.body.removeChild(popup); };
        popup.addEventListener('click', (e) => { if (e.target === popup) close(); });
        card.querySelector('#co-close').addEventListener('click', close);
        card.querySelector('#co-popup-form').addEventListener('submit', (e) => {
            e.preventDefault();
            const input = card.querySelector('#co-popup-input');
            const q = (input.value || '').trim();
            if (!q) return;
            // mirror to the main handler so state and persistence stay intact
            // reflect question first so it appears above the answer
            const log = card.querySelector('#co-popup-log');
            log.innerHTML += `<div class="text-right"><p class="inline-block bg-primary-600 text-white rounded-lg px-3 py-2">${escapeHTML(q)}</p></div>`;
            // update in-memory history immediately (document-specific)
            appState.conversationHistory.push({ role: 'user', content: q });
            handleQuery(q);
            log.scrollTop = log.scrollHeight;
            input.value = '';
        });
    };

    const fetchTimeline = async () => {
        try {
            // If we already have events, list; else generate
            const data = await apiCall(`/timeline/${appState.currentAnalysis.id}`);
            // If empty, try generating
            if (!data.events || data.events.length === 0) {
                const gen = await apiCall('/timeline', { method: 'POST', body: { analysis_id: appState.currentAnalysis.id } });
                renderTimeline(gen);
            } else {
                renderTimeline(data);
            }
        } catch (err) {
            // Try generate if list failed (no events yet)
            try {
                const gen = await apiCall('/timeline', { method: 'POST', body: { analysis_id: appState.currentAnalysis.id } });
                renderTimeline(gen);
            } catch (e) {
                renderTimeline({ lifecycle_summary: 'Timeline unavailable.', events: [] });
            }
        }
    };

    const createGoogleCalendarEvent = (event) => {
        try {
            console.log('Creating calendar event for:', event);
            
            // Validate event data
            if (!event || !event.date || !event.label) {
                throw new Error('Invalid event data: missing required fields');
            }
            
            // Parse the event date - handle both YYYY-MM-DD and other formats
            let eventDate;
            console.log('Parsing date:', event.date);
            
            if (event.date.includes('-')) {
                // Handle YYYY-MM-DD format
                eventDate = new Date(event.date + 'T00:00:00Z');
            } else {
                // Try parsing as-is
                eventDate = new Date(event.date);
            }
            
            // Check if date is valid
            if (isNaN(eventDate.getTime())) {
                // Try alternative parsing
                console.log('First parsing failed, trying alternative...');
                eventDate = new Date(event.date + 'T00:00:00');
                if (isNaN(eventDate.getTime())) {
                    throw new Error('Invalid date format: ' + event.date);
                }
            }
            
            console.log('Parsed date:', eventDate.toISOString());
            
            // Get default times based on event kind
            const getDefaultTimes = (kind) => {
                const times = {
                    'payment_due': { start: '09:00', end: '09:30' },
                    'action_required': { start: '10:00', end: '11:00' },
                    'key_date': { start: '09:00', end: '17:00' }
                };
                return times[kind] || { start: '09:00', end: '10:00' };
            };
            
            const times = getDefaultTimes(event.kind || 'key_date');
            
            // Format times for Google Calendar (YYYYMMDDTHHMMSSZ)
            const formatTime = (date, time) => {
                const [hours, minutes] = time.split(':');
                const eventDateTime = new Date(date);
                eventDateTime.setUTCHours(parseInt(hours), parseInt(minutes), 0, 0);
                return eventDateTime.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
            };
            
            const startTime = formatTime(eventDate, times.start);
            const endTime = formatTime(eventDate, times.end);
            
            // Ensure we have valid times
            if (!startTime || !endTime) {
                throw new Error('Failed to format event times');
            }
            
            // Create Google Calendar URL
            const eventTitle = event.label || 'Legal Document Reminder';
            const eventDescription = event.description || 'Reminder from legal document analysis';
            
            const calendarUrl = `https://www.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(eventTitle)}&dates=${startTime}/${endTime}&details=${encodeURIComponent(eventDescription)}&location=Legal Document Reminder`;
            
            console.log('Opening calendar URL:', calendarUrl);
            
            // Open in new tab
            window.open(calendarUrl, '_blank');
        } catch (error) {
            console.error('Error creating calendar event:', error);
            console.error('Event data:', event);
            showNotification('Unable to create calendar reminder: ' + error.message, 'error');
        }
    };

    const renderTimeline = (data) => {
        const summaryEl = document.getElementById('lifecycle-summary');
        const trackEl = document.getElementById('timeline-track');
        const listEl = document.getElementById('timeline-events');
        if (!summaryEl || !trackEl || !listEl) return;
        // Only update lifecycle summary if new data has one, otherwise preserve existing
        if (data.lifecycle_summary) {
            summaryEl.textContent = data.lifecycle_summary;
        }
        listEl.innerHTML = '';
        // Vertical markers are implicit via CSS; we render event cards aligned to the line
        const events = Array.isArray(data.events) ? data.events.slice() : [];
        events.sort((a,b) => (a.date || '').localeCompare(b.date || ''));
        const iconFor = (kind) => {
            const name = kind==='payment_due' ? 'payments' : (kind==='action_required' ? 'notifications' : 'calendar_month');
            return `<span class="material-symbols-outlined text-black mr-2 align-middle">${name}</span>`;
        };
        events.forEach((ev) => {
            const li = document.createElement('li');
            li.className = 'timeline-item';
            // Card with hover-elevate; reminder button fades in on hover
            li.innerHTML = `
                <div class="group ml-6 p-4 bg-white border border-gray-200 rounded-lg transition-all duration-200 hover:shadow-md">
                    <div class="flex items-start justify-between gap-3">
                        <div class="flex items-start">
                            ${iconFor(ev.kind)}
                            <div>
                                <div class="timeline-date text-sm">${escapeHTML(formatDate(ev.date, ev.kind))}</div>
                                <div class="text-base font-semibold text-gray-900">${escapeHTML(ev.label || '')}</div>
                            </div>
                        </div>
                        <button
                          data-event-id="${ev.id}"
                          class="reminder-btn inline-flex items-center justify-center h-8 min-w-[120px] px-3 text-xs font-medium bg-primary-600 text-white rounded-md ring-1 ring-primary-600/20 hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-primary-600">
                          Add Reminder
                        </button>
                    </div>
                    ${ev.description ? `<p class="text-sm text-gray-600 mt-2">${escapeHTML(ev.description)}</p>` : ''}
                </div>`;
            
            // Add event listener for the reminder button
            const reminderBtn = li.querySelector('.reminder-btn');
            if (reminderBtn) {
                reminderBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    createGoogleCalendarEvent(ev);
                });
            }
            
            listEl.appendChild(li);
        });
    };

    const formatDate = (iso, kind) => {
        const fallback = kind === 'payment_due'
            ? 'Due date not specified'
            : (kind === 'action_required' ? 'Deadline not specified' : 'Date not specified');
        if (!iso) return fallback;
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return fallback;
        try {
            return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: '2-digit' });
        } catch (e) {
            return fallback;
        }
    };

    document.addEventListener('click', async (e) => {
        const btn = e.target.closest('.reminder-btn');
        if (!btn) return;
        const eventId = parseInt(btn.getAttribute('data-event-id'));
        const email = prompt('Where should we send the reminder?');
        if (!email) return;
        const daysStr = prompt('How many days before the date? (e.g., 30)');
        const days = parseInt(daysStr || '0') || 0;
        try {
            await apiCall('/reminders', { method: 'POST', body: { analysis_id: appState.currentAnalysis.id, event_id: eventId, email, days_before: days } });
            showNotification('Reminder scheduled.', 'success');
        } catch (err) {
            showNotification('Could not schedule reminder.', 'error');
        }
    });
});
