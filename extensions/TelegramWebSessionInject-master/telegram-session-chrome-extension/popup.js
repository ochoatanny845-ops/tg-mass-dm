// Popup script for Telegram Session Injector
let selectedFile = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    checkTelegramTab();
    showStatus('Session parser ready', 'success');
});

// Setup event listeners
function setupEventListeners() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const importBtn = document.getElementById('importBtn');
    const openTelegramBtn = document.getElementById('openTelegramBtn');
    const githubLink = document.getElementById('githubLink');

    // GitHub link click
    githubLink.addEventListener('click', () => {
        chrome.tabs.create({
            url: 'https://github.com/keklick1337/TelegramWebSessionInject'
        });
    });

    // File upload area click
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    // File input change
    fileInput.addEventListener('change', handleFileSelect);

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    // Import button
    importBtn.addEventListener('click', importSession);

    // Open Telegram button
    openTelegramBtn.addEventListener('click', () => {
        chrome.tabs.create({
            url: 'https://web.telegram.org/a/'
        });
    });

    // Debug controls
    setupDebugControls();
}

// Handle file selection
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        handleFile(file);
    }
}

// Handle selected file
function handleFile(file) {
    if (!file.name.endsWith('.session')) {
        showStatus('Please select a .session file', 'error');
        return;
    }

    selectedFile = file;

    // Show file info
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileDetails = document.getElementById('fileDetails');

    fileName.textContent = file.name;
    fileDetails.textContent = `Size: ${formatFileSize(file.size)} | Modified: ${new Date(file.lastModified).toLocaleDateString()}`;
    fileInfo.style.display = 'block';

    // Enable import button
    document.getElementById('importBtn').disabled = false;

    showStatus('File selected. Click "Import Session" to continue.', 'info');
}

// Import session from file
async function importSession() {
    if (!selectedFile) {
        showStatus('No file selected', 'error');
        debugLog('Import failed: No file selected');
        return;
    }

    try {
        debugLog('Starting session import...');
        showProgress(true);
        setProgress(10);

        showStatus('Reading session file...', 'info');
        debugLog('Reading file as ArrayBuffer...');

        // Read file as ArrayBuffer
        const arrayBuffer = await readFileAsArrayBuffer(selectedFile);
        setProgress(30);
        debugLog(`File read successfully: ${arrayBuffer.byteLength} bytes`);

        showStatus('Parsing session data...', 'info');
        debugLog('Parsing session file with sql.js...');

        // Parse session file using the sql.js SQLite parser
        const sessionData = await window.parseSessionFile(arrayBuffer);
        setProgress(70);
        debugLog('Session data parsed successfully');
        debugObject('Parsed session data', sessionData);

        if (!sessionData || !sessionData.auth_key) {
            throw new Error('No valid session data found in file');
        }

        // Convert auth_key to lowercase hex format (as used by Telegram Web localStorage)
        let authKeyBytes;
        if (sessionData.auth_key instanceof Uint8Array) {
            authKeyBytes = sessionData.auth_key;
        } else if (typeof sessionData.auth_key === 'object') {
            // Convert object format {"0": 36, "1": 246, ...} to Uint8Array
            authKeyBytes = new Uint8Array(256);
            for (let i = 0; i < 256; i++) {
                authKeyBytes[i] = sessionData.auth_key[i.toString()] || 0;
            }
        } else {
            throw new Error('Invalid auth_key format');
        }

        // Convert to lowercase HEX (as in Telegram Web localStorage) and wrap in quotes
        const authKeyHex = Array.from(authKeyBytes)
            .map(b => b.toString(16).padStart(2, '0'))
            .join('').toLowerCase();

        debugLog(`Auth key converted to hex: ${authKeyHex.length} characters`);
        debugLog(`Auth key preview: ${authKeyHex.substring(0, 32)}...`);
        debugLog(`Auth key full (first 64 chars): ${authKeyHex.substring(0, 64)}`);
        debugLog(`Session data from parser:`, {
            dc_id: sessionData.dc_id,
            user_id: sessionData.user_id,
            server_address: sessionData.server_address,
            port: sessionData.port,
            auth_key_type: typeof sessionData.auth_key,
            auth_key_length: sessionData.auth_key ? sessionData.auth_key.length : 0
        });

        const processedSession = {
            dcId: sessionData.dc_id, // Используем реальный dc_id из файла
            authKey: authKeyHex, // lowercase HEX как в Telegram Web
            userId: sessionData.user_id || null,
            serverAddress: sessionData.server_address,
            port: sessionData.port,
            timestamp: Date.now()
        };

        debugObject('Processed session for injection', processedSession);

        showStatus('Injecting session into Telegram Web...', 'info');
        debugLog('Storing session data and preparing injection...');

        // Store session data
        await chrome.storage.local.set({
            sessionData: processedSession,
            timestamp: Date.now()
        });
        setProgress(90);

        // Inject into current Telegram tab or open new one
        await injectSessionIntoTab(processedSession);
        setProgress(100);

        showStatus('Session imported successfully! Telegram Web should now be authenticated.', 'success');
        debugLog('Session import completed successfully');

    } catch (error) {
        console.error('Import failed:', error);
        debugLog(`Import failed: ${error.message}`);
        debugLog(`Error stack: ${error.stack}`);
        showStatus(`Import failed: ${error.message}`, 'error');
    } finally {
        showProgress(false);
    }
}

// Read file as ArrayBuffer
function readFileAsArrayBuffer(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('Failed to read file'));
        reader.readAsArrayBuffer(file);
    });
}

// Inject session data into Telegram Web
async function injectSessionIntoTab(sessionData) {
    try {
        // Check if there's already a Telegram Web tab open
        const tabs = await chrome.tabs.query({
            url: 'https://web.telegram.org/*'
        });

        let targetTab;
        if (tabs.length > 0) {
            // Use existing tab
            targetTab = tabs[0];
            await chrome.tabs.reload(targetTab.id);
            // Wait a bit for the page to load
            await new Promise(resolve => setTimeout(resolve, 2000));
        } else {
            // Open new tab
            targetTab = await chrome.tabs.create({
                url: 'https://web.telegram.org/a/'
            });
            // Wait for page to load
            await new Promise(resolve => setTimeout(resolve, 3000));
        }

        // Inject the session data
        await chrome.scripting.executeScript({
            target: {
                tabId: targetTab.id
            },
            func: injectSession,
            args: [sessionData]
        });

        // Activate the tab
        await chrome.tabs.update(targetTab.id, {
            active: true
        });

    } catch (error) {
        console.error('Failed to inject session:', error);
        throw new Error(`Failed to inject session: ${error.message}`);
    }
}

function injectSession(sessionData) {
    try {
        console.log('Injecting session data...');
        const {
            dcId,
            authKey,
            userId
        } = sessionData;
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (k && (k.includes('auth_key') || k.includes('user_auth') || k === 'dc' || k.includes('server_salt'))) {
                keysToRemove.push(k);
            }
        }
        keysToRemove.forEach(k => localStorage.removeItem(k));
        const authKeyName = `dc${dcId}_auth_key`;
        localStorage.setItem(authKeyName, `"${authKey.toLowerCase()}"`);
        if (userId) {
            const userAuth = {
                date: Math.floor(Date.now() / 1000),
                id: userId,
                dcID: dcId
            };
            localStorage.setItem('user_auth', JSON.stringify(userAuth));
        }
        localStorage.setItem('dc', `"${dcId}"`);
        localStorage.setItem('server_time_offset', '0');
        const serverSalt = Array.from(crypto.getRandomValues(new Uint8Array(8))).map(b => b.toString(16).padStart(2, '0')).join('');
        localStorage.setItem(`dc${dcId}_server_salt`, `"${serverSalt}"`);
        const fingerprint = authKey.substring(0, 8).toLowerCase();
        localStorage.setItem('auth_key_fingerprint', `"${fingerprint}"`);
        console.log('=== VERIFICATION (ORIGINAL INLINE) ===');
        console.log('dc:', localStorage.getItem('dc'));
        const authKeyValue = localStorage.getItem(authKeyName);
        console.log(authKeyName + ':', authKeyValue ? authKeyValue.slice(0, 60) + '...' : 'null');
        console.log('user_auth:', localStorage.getItem('user_auth'));
        console.log('server_salt:', localStorage.getItem(`dc${dcId}_server_salt`));
        console.log('fingerprint:', localStorage.getItem('auth_key_fingerprint'));
        console.log('Keys now:', Object.keys(localStorage));
        console.log('=== /VERIFICATION ===');
        setTimeout(() => window.location.reload(), 800);
        return true;
    } catch (e) {
        console.error('PoC injection failed', e);
        return false;
    }
}

// Check if Telegram Web tab is open
async function checkTelegramTab() {
    try {
        const tabs = await chrome.tabs.query({
            url: 'https://web.telegram.org/*'
        });
        const openTelegramBtn = document.getElementById('openTelegramBtn');

        if (tabs.length > 0) {
            openTelegramBtn.textContent = 'Switch to Telegram Web';
            openTelegramBtn.onclick = () => {
                chrome.tabs.update(tabs[0].id, {
                    active: true
                });
                window.close();
            };
        }
    } catch (error) {
        console.log('Could not check for Telegram tabs:', error);
    }
}

// Utility functions
function showStatus(message, type) {
    const status = document.getElementById('status');
    status.textContent = message;
    status.className = `status ${type}`;
    status.style.display = 'block';

    // Auto-hide success messages
    if (type === 'success') {
        setTimeout(() => {
            status.style.display = 'none';
        }, 5000);
    }
}

function showProgress(show) {
    const progress = document.getElementById('progress');
    progress.style.display = show ? 'block' : 'none';
    if (!show) {
        setProgress(0);
    }
}

function setProgress(percent) {
    const progressBar = document.getElementById('progressBar');
    progressBar.style.width = percent + '%';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Debug functionality
function setupDebugControls() {
    const debugToggle = document.getElementById('debugToggle');
    const debugWindow = document.getElementById('debugWindow');
    const debugControls = document.getElementById('debugControls');
    const clearDebugBtn = document.getElementById('clearDebugBtn');
    const copyDebugBtn = document.getElementById('copyDebugBtn');
    const analyzeFileBtn = document.getElementById('analyzeFileBtn');

    // Toggle debug window
    debugToggle.addEventListener('click', () => {
        const isShow = debugWindow.classList.toggle('show');
        debugControls.classList.toggle('show', isShow);
        debugToggle.textContent = isShow ? '🔍 Hide Debug Info' : '🔍 Show Debug Info';

        if (isShow) {
            debugLog('Debug window opened');
        }
    });

    // Clear debug log
    clearDebugBtn.addEventListener('click', () => {
        debugWindow.textContent = 'Debug log cleared...\n';
    });

    // Copy debug log
    copyDebugBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(debugWindow.textContent).then(() => {
            debugLog('Debug log copied to clipboard');
        });
    });

    // Analyze current file
    analyzeFileBtn.addEventListener('click', () => {
        if (selectedFile) {
            analyzeSelectedFile();
        } else {
            debugLog('No file selected for analysis');
        }
    });
}

function debugLog(message) {
    const debugWindow = document.getElementById('debugWindow');
    const timestamp = new Date().toLocaleTimeString();
    debugWindow.textContent += `[${timestamp}] ${message}\n`;
    debugWindow.scrollTop = debugWindow.scrollHeight;
}

function debugObject(label, obj) {
    const debugWindow = document.getElementById('debugWindow');
    const timestamp = new Date().toLocaleTimeString();
    debugWindow.textContent += `[${timestamp}] ${label}:\n${JSON.stringify(obj, null, 2)}\n\n`;
    debugWindow.scrollTop = debugWindow.scrollHeight;
}

async function analyzeSelectedFile() {
    if (!selectedFile) {
        debugLog('No file selected');
        return;
    }

    try {
        debugLog(`=== ANALYZING FILE: ${selectedFile.name} ===`);
        debugLog(`File size: ${selectedFile.size} bytes`);
        debugLog(`File type: ${selectedFile.type}`);
        debugLog(`Last modified: ${new Date(selectedFile.lastModified)}`);

        const arrayBuffer = await readFileAsArrayBuffer(selectedFile);
        debugLog(`Buffer loaded: ${arrayBuffer.byteLength} bytes`);

        // Basic SQLite validation
        const uint8Array = new Uint8Array(arrayBuffer);
        const header = String.fromCharCode(...uint8Array.slice(0, 16));
        debugLog(`SQLite header: "${header}"`);

        if (!header.startsWith('SQLite format 3')) {
            debugLog('ERROR: Not a valid SQLite file!');
            return;
        }

        debugLog('Valid SQLite file detected');

        // Check if sql.js is available
        debugLog('Checking sql.js availability...');
        debugLog(`window.initSqlJs exists: ${typeof window.initSqlJs !== 'undefined'}`);
        debugLog(`getDetailedAnalysis function exists: ${typeof window.getDetailedAnalysis !== 'undefined'}`);

        if (typeof window.initSqlJs === 'undefined') {
            debugLog('ERROR: sql.js not loaded! Check if sql-wasm.js is included correctly.');
            return;
        }

        if (typeof window.getDetailedAnalysis === 'undefined') {
            debugLog('ERROR: getDetailedAnalysis function not available! Check sqlite-parser.js');
            return;
        }

        debugLog('Attempting to initialize sql.js...');

        // Test initialization first
        try {
            await window.initializeSqlJs();
            debugLog('sql.js initialization successful');
        } catch (initError) {
            debugLog(`sql.js initialization failed: ${initError.message}`);
            debugLog(`Init error stack: ${initError.stack}`);
            return;
        }

        debugLog('Starting detailed database analysis...');

        // Use the new SQLite parser for detailed analysis
        const analysisResult = await window.getDetailedAnalysis(arrayBuffer);

        if (analysisResult.success) {
            debugLog('=== DATABASE ANALYSIS SUCCESSFUL ===');
            debugObject('Database Info', analysisResult.analysis);

            debugLog('=== TABLE DETAILS ===');
            for (const [tableName, tableInfo] of Object.entries(analysisResult.analysis.tables)) {
                debugLog(`\nTable: ${tableName}`);
                debugLog(`  Rows: ${tableInfo.rowCount}`);
                debugLog(`  Columns: ${tableInfo.columns.join(', ')}`);

                if (tableInfo.error) {
                    debugLog(`  Error: ${tableInfo.error}`);
                } else if (tableInfo.sampleData.length > 0) {
                    debugLog(`  Sample data (first ${tableInfo.sampleData.length} rows):`);
                    tableInfo.sampleData.forEach((row, i) => {
                        debugLog(`    Row ${i + 1}: [${row.map(v => typeof v === 'string' ? `"${v}"` : v).join(', ')}]`);
                    });
                }
            }

            // Try to extract session data
            debugLog('\n=== ATTEMPTING SESSION DATA EXTRACTION ===');
            try {
                const sessionData = await window.parseSessionFile(arrayBuffer);
                debugLog('Session extraction successful!');
                debugObject('Extracted Session Data', {
                    dc_id: sessionData.dc_id,
                    auth_key_length: sessionData.auth_key ? sessionData.auth_key.length : 0,
                    auth_key_preview: sessionData.auth_key ?
                        Array.from(sessionData.auth_key.slice(0, 16)).map(b => b.toString(16).padStart(2, '0')).join('') + '...' : 'none',
                    user_id: sessionData.user_id,
                    server_address: sessionData.server_address,
                    port: sessionData.port
                });
            } catch (sessionError) {
                debugLog(`Session extraction failed: ${sessionError.message}`);
            }

        } else {
            debugLog('=== DATABASE ANALYSIS FAILED ===');
            debugLog(`Error: ${analysisResult.error}`);
            if (analysisResult.stack) {
                debugLog(`Stack trace: ${analysisResult.stack}`);
            }
        }

    } catch (error) {
        debugLog(`=== ANALYSIS ERROR ===`);
        debugLog(`Error: ${error.message}`);
        debugLog(`Stack: ${error.stack}`);
    }
}

