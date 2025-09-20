'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const BASE_URL = 'http://127.0.0.1:8000';
    let appState = {
        token: localStorage.getItem('chimeraToken'),
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
    };
    
    const updateDashboard = async () => {
        if (!appState.token) {
            showState('landing');
            return;
        }
        showState('dashboard');
        try {
            const items = await apiCall('/analyses/dashboard');
            appState.dashboardItems = Array.isArray(items) ? items : [];
            renderDashboardList();
            attachDashboardControls();
            // Hide landing when logged in
            const landing = document.getElementById('landing-container');
            if (landing) landing.classList.add('hidden');
        } catch (error) {
            console.error('Failed to fetch analyses:', error);
            logout();
        }
    };

    const getRiskTag = (risk) => {
        const level = (risk || '').toLowerCase();
        if (level === 'high') return '<span class="ml-2 text-red-700 text-xs font-semibold">🔴 High Risk</span>';
        if (level === 'medium') return '<span class="ml-2 text-yellow-700 text-xs font-semibold">🟡 Some Concerns</span>';
        return '<span class="ml-2 text-green-700 text-xs font-semibold">🟢 Standard</span>';
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
            <button data-analysis-id="${i.id}" class="w-full text-left p-3 border rounded hover:bg-gray-50 flex items-center justify-between">
                <span class="truncate font-medium">${i.filename || 'Untitled'}</span>
                <span class="text-xs text-gray-500 ml-3">${i.created_at ? i.created_at.replace('T',' ').replace('Z','') : ''}</span>
                ${getRiskTag(i.risk_level)}
            </button>
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
            elements.analysesList.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-analysis-id]');
                if (!btn) return;
                const id = parseInt(btn.getAttribute('data-analysis-id'));
                if (id) loadAnalysis(id);
            });
            elements.analysesList._bound = true;
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
            };
            renderResults(ia);
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
    document.getElementById('assessment-text').textContent = data.assessment;
    const keyInfoList = document.getElementById('key-info-list');
    keyInfoList.innerHTML = '';
    if (data.key_info) {
        data.key_info.forEach(item => {
            const showRewrite = item.is_negotiable;
            const showBenchmark = item.is_benchmarkable;
            keyInfoList.innerHTML += `<div class="flex flex-col sm:flex-row py-2 border-b border-gray-100 justify-between group"><div><dt class="font-medium text-gray-600">${item.key}:</dt><dd class="text-gray-800">${item.value}</dd></div><div class="flex items-center mt-2 sm:mt-0 ml-auto space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">${showBenchmark ? `<button data-key="${item.key}" data-clause="${item.value}" class="benchmark-btn px-2 py-1 text-xs font-semibold text-blue-600 bg-blue-100 rounded-full">Benchmark</button>` : ''}${showRewrite ? `<button data-key="${item.key}" data-clause="${item.value}" class="rewrite-clause-btn px-2 py-1 text-xs font-semibold text-primary-600 bg-primary-100 rounded-full">Rewrite</button>` : ''}</div></div>`;
        });
    }
    const actionsList = document.getElementById('actions-list');
    actionsList.innerHTML = '';
    if (data.identified_actions?.length > 0) {
        data.identified_actions.forEach(item => {
            // NOW an item is an object with a .text property
            const showRewrite = item.is_negotiable;
            const showBenchmark = item.is_benchmarkable;
            actionsList.innerHTML += `
                <li class="flex items-start py-2 justify-between group">
                    <div class="flex items-start"><span class="material-symbols-outlined text-primary-500 mr-3 mt-1">circle</span><span>${item.text}</span></div>
                    <div class="flex items-center ml-auto space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        ${showBenchmark ? `<button data-key="Action Item" data-clause="${item.text}" class="benchmark-btn px-2 py-1 text-xs font-semibold text-blue-600 bg-blue-100 rounded-full">Benchmark</button>` : ''}
                        ${showRewrite ? `<button data-key="Action Item" data-clause="${item.text}" class="rewrite-clause-btn px-2 py-1 text-xs font-semibold text-primary-600 bg-primary-100 rounded-full">Rewrite</button>` : ''}
                        <button data-clause="${item.text}" class="simulate-risk-btn ml-2 px-2 py-1 text-xs font-semibold text-primary-600 bg-primary-100 rounded-full">Simulate Risk</button>
                    </div>
                </li>`;
        });
    }
    const displayName = data.filename || (appState.selectedFile && appState.selectedFile.name) || 'Document';
    document.querySelector('#doc-viewer-filename span.truncate').textContent = displayName;
    const docViewerContent = document.getElementById('doc-viewer-content');
    docViewerContent.innerHTML = '';
    if (Array.isArray(data.page_images) && data.page_images.length > 0) {
        data.page_images.forEach((src, index) => {
            docViewerContent.innerHTML += `<div class="bg-white shadow-sm rounded p-2 mb-4"><h4 class="font-medium text-gray-800 mb-2 border-b pb-1">Page ${index + 1}</h4><img src="${src}" alt="Page ${index + 1}" class="w-full h-auto rounded border border-gray-200" loading="lazy"></div>`;
        });
    } else if (data.extracted_text?.length > 0) {
        data.extracted_text.forEach((pageText, index) => {
            docViewerContent.innerHTML += `<div class="bg-white shadow-sm rounded p-4 mb-4"><h4 class="font-medium text-gray-800 mb-2 border-b pb-1">Page ${index + 1}</h4><p class="text-sm text-gray-700 whitespace-pre-wrap">${pageText || "No text."}</p></div>`;
        });
    }
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
        } catch (error) { alert(`Login failed: ${error.message}`); }
    };
    const register = async (email, password) => {
        try {
            await apiCall('/users/', { method: 'POST', body: { email, password } });
            alert('Registration successful! Please log in.');
            showState('login');
        } catch (error) { alert(`Registration failed: ${error.message}`); }
    };
    const logout = () => {
        appState.token = null;
        localStorage.removeItem('chimeraToken');
        showState('login');
    };
    const handleFileSelect = (file) => {
        if (!file) return;
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
            appState.conversationHistory.push({ role: 'user', content: question });
            appState.conversationHistory.push({ role: 'assistant', content: data.answer });
        } catch (error) {
            if (thinkingId) {
                const thinkingEl = document.getElementById(thinkingId);
                if (thinkingEl) thinkingEl.innerHTML = `<div class="text-left"><p class="inline-block bg-red-100 text-red-700 rounded-lg px-3 py-2">Error: ${error.message}</p></div>`;
            }
        }
        if (log) log.scrollTop = log.scrollHeight;
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
        
        if (containers.results) {
            containers.results.addEventListener('click', (e) => {
                const button = e.target.closest('button');
                if (!button) return;
                if (button.classList.contains('simulate-risk-btn')) handleApiAction('simulate', button);
                if (button.classList.contains('rewrite-clause-btn')) handleApiAction('rewrite', button);
                if (button.classList.contains('benchmark-btn')) handleApiAction('benchmark', button);
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
                } catch (error) { showError(error.message); }
            });
        }
        updateDashboard();
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
            log.innerHTML += `<div class="text-right"><p class="inline-block bg-primary-600 text-white rounded-lg px-3 py-2">${q}</p></div>`;
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

    const renderTimeline = (data) => {
        const summaryEl = document.getElementById('lifecycle-summary');
        const trackEl = document.getElementById('timeline-track');
        const listEl = document.getElementById('timeline-events');
        if (!summaryEl || !trackEl || !listEl) return;
        summaryEl.textContent = data.lifecycle_summary || '';
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
            alert('Reminder scheduled.');
        } catch (err) {
            alert('Could not schedule reminder.');
        }
    });
});
